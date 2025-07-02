#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最新ページキャッチツール

指定されたWebサイトのXPATH部分について差分テキスト（加わった部分）を検出し、
メールで通知するプログラム。英語文書の場合はOpenAIによる和訳要約も付与。
"""

import os
import sys
import re
import time
import yaml
import logging
import argparse
import smtplib
import requests
import json
import chardet
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from email.header import Header
from lxml import html
from openai import OpenAI
import difflib


class LatestPageCatch:
    """
    最新ページキャッチクラス
    
    指定されたWebサイトのXPATH部分について差分テキスト（加わった部分）を検出し、
    メールで通知するクラス。英語文書の場合はOpenAIによる和訳要約も付与。
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初期化
        
        Args:
            config_path: 設定ファイルのパス
        """
        # 設定ファイルの読み込み
        self.config = self._load_config(config_path)
        
        # ロガーの設定
        self._setup_logger()
        
        # データディレクトリとログディレクトリの作成
        self._create_directories()
        
        # OpenAIクライアントの初期化
        self.openai_client = self._init_openai_client()
        
        self.logger.info("最新ページキャッチツールを初期化しました。")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        設定ファイルを読み込む
        
        Args:
            config_path: 設定ファイルのパス
            
        Returns:
            Dict[str, Any]: 設定情報
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            sys.exit(1)
    
    def _setup_logger(self):
        """ロガーを設定する"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.config.get('debug', False) else logging.INFO)
        
        # コンソールハンドラ
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if self.config.get('debug', False) else logging.INFO)
        console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # ファイルハンドラ
        log_dir = self.config.get('log_dir', 'log')
        log_file = os.path.join(log_dir, 'latest_page_catch.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG if self.config.get('debug', False) else logging.INFO)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
    
    def _create_directories(self):
        """データディレクトリとログディレクトリを作成する"""
        data_dir = self.config.get('data_dir', 'data')
        log_dir = self.config.get('log_dir', 'log')
        
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger.debug(f"データディレクトリを作成しました: {data_dir}")
        self.logger.debug(f"ログディレクトリを作成しました: {log_dir}")
    
    def _init_openai_client(self) -> Optional[OpenAI]:
        """
        OpenAIクライアントを初期化する
        
        Returns:
            Optional[OpenAI]: OpenAIクライアント
        """
        openai_config = self.config.get('openai', {})
        api_key = openai_config.get('api_key')
        
        if not api_key:
            self.logger.warning("OpenAI APIキーが設定されていません。英語文書の和訳要約機能は無効になります。")
            return None
        
        try:
            client = OpenAI(api_key=api_key)
            self.logger.debug("OpenAIクライアントを初期化しました。")
            return client
        except Exception as e:
            self.logger.error(f"OpenAIクライアントの初期化に失敗しました: {e}")
            return None
    
    def _sanitize_filename(self, url: str) -> str:
        """
        URLをファイル名に使える文字列に変換する
        
        Args:
            url: URL
            
        Returns:
            str: サニタイズされたファイル名
        """
        return re.sub(r'[^\w.-]', '_', url)
    
    def _get_formatted_date(self) -> str:
        """
        日付をyyyymmdd-hhmmss形式で取得する
        
        Returns:
            str: フォーマットされた日付
        """
        now = datetime.now()
        return now.strftime('%Y%m%d-%H%M%S')
    
    def _get_formatted_date_for_subject(self) -> str:
        """
        日付をyyyy/MM/dd形式で取得する
        
        Returns:
            str: フォーマットされた日付
        """
        now = datetime.now()
        return now.strftime('%Y/%m/%d')
    
    def _fetch_html(self, url: str, xpath: str, user_agent: str = "") -> Tuple[str, str]:
        """
        HTMLを取得する
        
        Args:
            url: URL
            xpath: XPath
            user_agent: ユーザーエージェント
            
        Returns:
            Tuple[str, str]: (HTML, 使用したユーザーエージェント)
        """
        self.logger.info(f"HTMLを取得します: {url}")
        
        # ユーザーエージェントの準備
        user_agents = self.config.get('user_agents', [])
        if user_agent:
            # 指定されたユーザーエージェントを最初に試す
            if user_agent in user_agents:
                user_agents.remove(user_agent)
            user_agents.insert(0, user_agent)
        
        last_error = None
        
        for agent in user_agents:
            try:
                self.logger.debug(f"ユーザーエージェントを試行: {agent}")
                
                headers = {
                    'User-Agent': agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
                
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=10
                )
                
                response.raise_for_status()
                
                # レスポンスのエンコーディングを取得
                content_type = response.headers.get('Content-Type', '')
                encoding = None
                
                # Content-Typeヘッダーからエンコーディングを取得
                if 'charset=' in content_type:
                    encoding = content_type.split('charset=')[-1].strip()
                
                # エンコーディングが指定されていない場合は自動検出
                if not encoding:
                    # レスポンスの内容からエンコーディングを検出
                    result = chardet.detect(response.content)
                    encoding = result['encoding']
                    self.logger.debug(f"エンコーディングを検出: {encoding}, 信頼度: {result['confidence']}")
                
                # エンコーディングが検出できない場合はUTF-8を使用
                if not encoding:
                    encoding = 'utf-8'
                
                # 適切なエンコーディングでレスポンスの内容をデコード
                try:
                    html_content = response.content.decode(encoding, errors='replace')
                except (LookupError, UnicodeDecodeError):
                    # エンコーディングが無効な場合はUTF-8を使用
                    html_content = response.content.decode('utf-8', errors='replace')
                
                # XPathが指定されている場合は該当部分を抽出
                if xpath and xpath.strip():
                    try:
                        # HTMLをバイト形式に変換してからパース
                        html_bytes = html_content.encode('utf-8')
                        tree = html.fromstring(html_bytes)
                        elements = tree.xpath(xpath)
                        if elements:
                            html_content = html.tostring(elements[0], encoding='unicode')
                            self.logger.debug(f"XPath処理成功: {xpath}")
                        else:
                            self.logger.warning(f"XPathで指定された要素が見つかりませんでした: {xpath}")
                    except Exception as e:
                        self.logger.error(f"XPath処理中にエラーが発生しました: {e}")
                
                self.logger.info(f"HTMLの取得に成功しました: {url} (ユーザーエージェント: {agent})")
                return html_content, agent
                
            except Exception as e:
                self.logger.warning(f"HTMLの取得に失敗しました: {url}, エラー: {str(e)} (ユーザーエージェント: {agent})")
                last_error = e
        
        # すべてのユーザーエージェントで失敗した場合
        error_message = str(last_error) if last_error else "不明なエラー"
        self.logger.error(f"すべてのユーザーエージェントでHTMLの取得に失敗しました: {url}, エラー: {error_message}")
        raise Exception(f"HTMLの取得に失敗しました: {url}, エラー: {error_message}")
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """
        HTMLからテキストを抽出する
        
        Args:
            html_content: HTML
            
        Returns:
            str: 抽出されたテキスト
        """
        try:
            # スクリプトタグとその内容を除去
            html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.IGNORECASE)
            
            # HTMLのエンコーディングを検出
            if isinstance(html_content, str):
                # 文字列の場合はバイト形式に変換
                html_bytes = html_content.encode('utf-8', errors='replace')
            else:
                # すでにバイト形式の場合はそのまま使用
                html_bytes = html_content
            
            # エンコーディングを検出
            encoding = 'utf-8'
            try:
                # HTMLのメタタグからエンコーディングを取得
                if b'charset=' in html_bytes:
                    charset_match = re.search(b'charset=([^"\'\\s]+)', html_bytes)
                    if charset_match:
                        encoding = charset_match.group(1).decode('ascii', errors='replace')
            except Exception:
                pass
            
            # パーサーを作成してHTMLをパース
            parser = html.HTMLParser(encoding=encoding)
            try:
                tree = html.fromstring(html_bytes, parser=parser)
            except Exception as e:
                self.logger.warning(f"HTMLのパースに失敗しました: {e}")
                # 失敗した場合は別のエンコーディングを試す
                try:
                    # chardetを使用してエンコーディングを検出
                    result = chardet.detect(html_bytes)
                    detected_encoding = result['encoding']
                    if detected_encoding and detected_encoding != encoding:
                        self.logger.debug(f"別のエンコーディングを試行: {detected_encoding}")
                        parser = html.HTMLParser(encoding=detected_encoding)
                        tree = html.fromstring(html_bytes, parser=parser)
                    else:
                        # 最後の手段としてUTF-8を使用
                        parser = html.HTMLParser(encoding='utf-8')
                        tree = html.fromstring(html_bytes, parser=parser)
                except Exception as e2:
                    self.logger.error(f"HTMLのパースに再度失敗しました: {e2}")
                    # テキストとして扱う
                    return html_content if isinstance(html_content, str) else html_content.decode('utf-8', errors='replace')
            
            # スタイル、noscript、iframeを削除
            for element in tree.xpath('//style | //noscript | //iframe'):
                element.getparent().remove(element)
            
            # テキストを抽出し、適切にデコード
            texts = []
            for text_element in tree.xpath('//text()'):
                if text_element.strip():
                    texts.append(text_element.strip())
            
            # テキストを結合
            text = ' '.join(texts)
            
            # 余分な空白を削除
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            self.logger.error(f"テキスト抽出中にエラーが発生しました: {e}")
            return ""
    
    def _save_html(self, html_content: str, file_path: str):
        """
        HTMLをファイルに保存する
        
        Args:
            html_content: HTML
            file_path: 保存先ファイルパス
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.debug(f"HTMLをファイルに保存しました: {file_path}")
        except Exception as e:
            self.logger.error(f"HTMLの保存に失敗しました: {file_path}, エラー: {e}")
    
    def _find_latest_files(self, url: str, xpath: str) -> List[str]:
        """
        指定されたURLに対応する最新のファイルとその1つ前のファイルを探す
        
        Args:
            url: URL
            xpath: XPath
            
        Returns:
            List[str]: [最新のファイル, 1つ前のファイル]
        """
        data_dir = self.config.get('data_dir', 'data')
        sanitized_name = self._sanitize_filename(url + xpath)
        
        files = [f for f in os.listdir(data_dir) if sanitized_name in f]
        if len(files) < 2:
            return []
        
        # 日付でソート
        files.sort(key=lambda x: x.split('_')[0], reverse=True)
        
        return [os.path.join(data_dir, files[0]), os.path.join(data_dir, files[1])]
    
    def _compare_and_get_diff(self, file1: str, file2: str) -> str:
        """
        ファイルの差分を比較して追加された部分を取得する
        
        Args:
            file1: 新しいファイル
            file2: 古いファイル
            
        Returns:
            str: 追加された差分テキスト
        """
        if not os.path.exists(file1) or not os.path.exists(file2):
            self.logger.warning(f"比較対象のファイルが存在しません: file1={os.path.exists(file1)}, file2={os.path.exists(file2)}")
            return ""
        
        try:
            # ファイルからテキストを抽出
            with open(file1, 'r', encoding='utf-8') as f:
                text1 = self._extract_text_from_html(f.read())
            
            with open(file2, 'r', encoding='utf-8') as f:
                text2 = self._extract_text_from_html(f.read())
            
            # テキストが同じ場合は差分なし
            if text1 == text2:
                self.logger.debug("差分なし（完全一致）")
                return ""
            
            # 差分を取得
            diff = difflib.unified_diff(
                text2.splitlines(),
                text1.splitlines(),
                lineterm=''
            )
            
            # 追加された行のみを抽出
            added_lines = []
            for line in diff:
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:])
            
            # 追加された行がない場合は空文字を返す
            if not added_lines:
                self.logger.debug("差分なし（追加行なし）")
                return ""
            
            return '\n'.join(added_lines)
            
        except Exception as e:
            self.logger.error(f"差分比較中にエラーが発生しました: {e}")
            return ""
    
    def _is_english_text(self, text: str) -> bool:
        """
        テキストが英語かどうかを判定する
        URL形式のテキストを除いた残りテキストについて、半分以上がアルファベット文字であれば英語文書と判定
        
        Args:
            text: 判定するテキスト
            
        Returns:
            bool: 英語文書かどうか
        """
        # URLを除去
        text_without_urls = re.sub(r'https?://\S+', '', text)
        text_without_urls = re.sub(r'www\.\S+', '', text_without_urls)
        
        # 空白と記号を除去
        text_without_urls = re.sub(r'[^\w\s]', '', text_without_urls)
        
        if not text_without_urls:
            return False
        
        # アルファベット文字の数をカウント
        alpha_count = sum(1 for c in text_without_urls if c.isalpha() and ord(c) < 128)
        total_count = len(text_without_urls)
        
        # アルファベット文字が半分以上であれば英語文書と判定
        return alpha_count / total_count > 0.5
    
    def _translate_and_summarize(self, text: str) -> str:
        """
        英語テキストを和訳して要約する
        
        Args:
            text: 英語テキスト
            
        Returns:
            str: 和訳要約テキスト
        """
        if not self.openai_client:
            self.logger.warning("OpenAIクライアントが初期化されていないため、和訳要約を行いません。")
            return ""
        
        try:
            openai_config = self.config.get('openai', {})
            model = openai_config.get('model', 'gpt-4o-mini')
            max_tokens = openai_config.get('max_tokens', 1000)
            temperature = openai_config.get('temperature', 0.7)
            prompt_template = openai_config.get('translation_summary_prompt', '以下の英文を日本語で要約してください。\n\n英文:\n{text}')
            
            prompt = prompt_template.format(text=text)
            
            self.logger.debug(f"OpenAIに問い合わせを行います。モデル: {model}")
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            summary = response.choices[0].message.content
            self.logger.debug("和訳要約が完了しました。")
            
            return summary
        except Exception as e:
            self.logger.error(f"和訳要約中にエラーが発生しました: {e}")
            return ""
    
    def _send_email(self, subject: str, body: str) -> bool:
        """
        メールを送信する
        
        Args:
            subject: 件名
            body: 本文
            
        Returns:
            bool: 送信成功したかどうか
        """
        mail_config = self.config.get('mail', {})
        
        if not mail_config.get('send', True):
            self.logger.info("メール送信フラグがオフのため、メールを送信しません。")
            self._save_mail_log(subject, body)
            return True
        
        smtp_server = mail_config.get('smtp_server', 'smtp.gmail.com')
        smtp_port = mail_config.get('smtp_port', 587)
        user = mail_config.get('user')
        password = mail_config.get('password')
        from_email = mail_config.get('from', user)
        to_emails = mail_config.get('to', [])
        
        if not user or not password or not to_emails:
            self.logger.error("メール設定が不完全です。")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            
            # 件名のエンコーディングを設定
            from email.header import Header
            msg['Subject'] = Header(subject, 'utf-8')
            
            msg['Date'] = formatdate(localtime=True)
            
            # 文字エンコーディングを明示的にUTF-8に指定
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
                server.send_message(msg)
            
            self.logger.info(f"メールを送信しました: {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            self.logger.error(f"メール送信中にエラーが発生しました: {e}")
            self._save_mail_log(subject, body)
            return False
    
    def _save_mail_log(self, subject: str, body: str):
        """
        メール内容をログに保存する
        
        Args:
            subject: 件名
            body: 本文
        """
        log_dir = self.config.get('log_dir', 'log')
        mail_log_file = os.path.join(log_dir, 'mail.log')
        
        try:
            with open(mail_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Subject: {subject}\n\n")
                f.write(f"{body}\n")
            self.logger.info(f"メール内容をログに保存しました: {mail_log_file}")
        except Exception as e:
            self.logger.error(f"メールログの保存に失敗しました: {e}")
    
    def _update_config_with_user_agent(self, site_name: str, url: str, xpath: str, user_agent: str):
        """
        成功したユーザーエージェントで設定ファイルを更新する
        
        Args:
            site_name: サイト名
            url: URL
            xpath: XPath
            user_agent: 成功したユーザーエージェント
        """
        try:
            # 設定ファイルを読み込む
            with open('config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # サイト設定を更新
            for site in config.get('sites', []):
                if site.get('name') == site_name and site.get('url') == url and site.get('xpath') == xpath:
                    site['user_agent'] = user_agent
                    break
            
            # 設定ファイルを保存
            with open('config.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            self.logger.info(f"設定ファイルを更新しました: {site_name}, ユーザーエージェント: {user_agent}")
        except Exception as e:
            self.logger.error(f"設定ファイルの更新に失敗しました: {e}")
    
    def run(self, send_mail: bool = True):
        """
        メイン処理を実行する
        
        Args:
            send_mail: メールを送信するかどうか
        """
        self.logger.info("最新ページキャッチツールを実行します。")
        
        # メール送信フラグを設定
        if not send_mail:
            self.config['mail']['send'] = False
            self.logger.info("メール送信フラグがオフに設定されました。")
        
        data_dir = self.config.get('data_dir', 'data')
        sites = self.config.get('sites', [])
        
        update_text = '# 更新あり\n'
        no_update_text = '# 更新なし\n'
        has_updates = False
        errors = []
        
        for site in sites:
            site_name = site.get('name', '')
            url = site.get('url', '')
            xpath = site.get('xpath', '')
            user_agent = site.get('user_agent', '')
            
            if not url:
                self.logger.warning(f"URLが設定されていないサイトをスキップします: {site_name}")
                continue
            
            self.logger.info(f"サイトの処理を開始します: {site_name}, URL: {url}")
            
            try:
                # HTMLを取得
                html_content, used_agent = self._fetch_html(url, xpath, user_agent)
                
                # 成功したユーザーエージェントが設定と異なる場合は設定を更新
                if user_agent != used_agent:
                    self._update_config_with_user_agent(site_name, url, xpath, used_agent)
                
                # HTMLを保存
                formatted_date = self._get_formatted_date()
                sanitized_name = self._sanitize_filename(url + xpath)
                file_path = os.path.join(data_dir, f"{formatted_date}_{sanitized_name}.txt")
                self._save_html(html_content, file_path)
                
                # 最新のファイルとその1つ前のファイルを探して比較
                files = self._find_latest_files(url, xpath)
                if len(files) == 2:
                    diff_text = self._compare_and_get_diff(files[0], files[1])
                    
                    if diff_text:
                        has_updates = True
                        
                        # 英語文書かどうかを判定
                        is_english = self._is_english_text(diff_text)
                        
                        # 英語文書の場合は和訳要約を生成
                        translation_summary = ""
                        if is_english:
                            self.logger.info(f"英語文書を検出しました: {site_name}")
                            translation_summary = self._translate_and_summarize(diff_text)
                        
                        # 更新テキストを作成
                        update_text += f"\n## {site_name}\n{url}\n\n{diff_text}\n"
                        
                        # 和訳要約がある場合は追加
                        if translation_summary:
                            update_text += f"\n### 和訳要約\n{translation_summary}\n"
                        
                        self.logger.info(f"更新を検出しました: {site_name}")
                    else:
                        no_update_text += f"{site_name}\n"
                        self.logger.info(f"更新はありませんでした: {site_name}")
                else:
                    no_update_text += f"{site_name}\n"
                    self.logger.info(f"比較対象のファイルが不足しています: {site_name}")
            
            except Exception as e:
                self.logger.error(f"サイトの処理中にエラーが発生しました: {site_name}, エラー: {e}")
                errors.append(f"Error processing {site_name} ({url}): {str(e)}")
        
        # メール送信
        formatted_date_for_subject = self._get_formatted_date_for_subject()
        subject_prefix = "更新あり：" if has_updates else "更新なし："
        subject = f"{subject_prefix}差分報告（{formatted_date_for_subject}）"
        body = update_text + '\n' + no_update_text
        
        if errors:
            body += '\n# エラー:\n' + '\n'.join(errors)
        
        self._send_email(subject, body)
        
        self.logger.info("最新ページキャッチツールの実行が完了しました。")


def parse_arguments():
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(description='最新ページキャッチツール')
    parser.add_argument('-c', '--config', default='config.yaml', help='設定ファイルのパス')
    parser.add_argument('-n', '--no-mail', action='store_true', help='メールを送信しない')
    return parser.parse_args()


def main():
    """メイン関数"""
    args = parse_arguments()
    
    try:
        # 最新ページキャッチツールの初期化
        latest_page_catch = LatestPageCatch(args.config)
        
        # 実行
        latest_page_catch.run(not args.no_mail)
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()