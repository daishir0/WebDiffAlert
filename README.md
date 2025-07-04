# WebDiffAlert

## Overview
WebDiffAlert is a Python tool that monitors specified websites for changes in content at specific XPath locations. When changes are detected, it sends email notifications with the differences. For English content, it can also generate Japanese summaries using OpenAI.

## Installation

### Prerequisites
- Python 3.8 or higher
- Anaconda or Miniconda (recommended)

### Steps
1. Clone the repository:
```bash
git clone https://github.com/daishir0/WebDiffAlert.git
cd WebDiffAlert
```

2. Create and activate a conda environment:
```bash
conda create -n webdiffalert python=3.8
conda activate webdiffalert
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Configure the settings:
```bash
cp config.yaml.sample config.yaml
```

5. Edit the `config.yaml` file with your settings:
   - Add your OpenAI API key
   - Configure your email settings
   - Add or modify the websites you want to monitor

## Usage

### Manual Execution
Run the program manually:
```bash
python main.py
```

To run without sending emails (for testing):
```bash
python main.py --no-mail
```

### Automated Execution with Systemd
1. Copy the service and timer files to the systemd directory:
```bash
sudo cp webdiffalert.service /etc/systemd/system/
sudo cp webdiffalert.timer /etc/systemd/system/
```

2. Reload systemd:
```bash
sudo systemctl daemon-reload
```

3. Enable and start the timer:
```bash
sudo systemctl enable webdiffalert.timer
sudo systemctl start webdiffalert.timer
```

4. Check the status:
```bash
sudo systemctl status webdiffalert.timer
```

## Notes
- The first run will only save the current state of websites. Differences will be detected from the second run onwards.
- For English content, the program uses OpenAI to generate Japanese summaries. Make sure your OpenAI API key is valid.
- The program uses multiple user agents to try accessing websites that might block certain user agents.
- **Selenium Integration**: The tool now supports websites with dynamic content loaded by JavaScript. By setting `use_selenium: true` in the site configuration, WebDiffAlert will use a headless browser to render the page with JavaScript before capturing the content.
- All data is stored in the `data` directory, and logs are stored in the `log` directory.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# WebDiffAlert

## 概要
WebDiffAlertは、指定されたWebサイトの特定のXPath位置のコンテンツ変更を監視するPythonツールです。変更が検出されると、差分をメールで通知します。英語コンテンツの場合、OpenAIを使用して日本語の要約も生成できます。

## インストール方法

### 前提条件
- Python 3.8以上
- Anaconda または Miniconda（推奨）

### 手順
1. リポジトリをクローンします：
```bash
git clone https://github.com/daishir0/WebDiffAlert.git
cd WebDiffAlert
```

2. conda環境を作成して有効化します：
```bash
conda create -n webdiffalert python=3.8
conda activate webdiffalert
```

3. 必要なパッケージをインストールします：
```bash
pip install -r requirements.txt
```

4. 設定をコピーします：
```bash
cp config.yaml.sample config.yaml
```

5. `config.yaml`ファイルを編集して設定を行います：
   - OpenAI APIキーを追加
   - メール設定を構成
   - 監視したいWebサイトを追加または変更

## 使い方

### 手動実行
プログラムを手動で実行します：
```bash
python main.py
```

メール送信なしで実行する場合（テスト用）：
```bash
python main.py --no-mail
```

### Systemdによる自動実行
1. サービスファイルとタイマーファイルをsystemdディレクトリにコピーします：
```bash
sudo cp webdiffalert.service /etc/systemd/system/
sudo cp webdiffalert.timer /etc/systemd/system/
```

2. systemdをリロードします：
```bash
sudo systemctl daemon-reload
```

3. タイマーを有効化して起動します：
```bash
sudo systemctl enable webdiffalert.timer
sudo systemctl start webdiffalert.timer
```

4. ステータスを確認します：
```bash
sudo systemctl status webdiffalert.timer
```

## 注意点
- 初回実行時は、Webサイトの現在の状態が保存されるだけです。差分は2回目以降の実行で検出されます。
- 英語コンテンツの場合、プログラムはOpenAIを使用して日本語の要約を生成します。OpenAI APIキーが有効であることを確認してください。
- プログラムは複数のユーザーエージェントを使用して、特定のユーザーエージェントをブロックする可能性のあるWebサイトへのアクセスを試みます。
- **Seleniumの統合**: このツールは、JavaScriptによって読み込まれる動的コンテンツを持つWebサイトをサポートするようになりました。サイト設定で`use_selenium: true`を設定することで、WebDiffAlertはコンテンツをキャプチャする前にヘッドレスブラウザでJavaScriptを実行してページをレンダリングします。
- すべてのデータは`data`ディレクトリに保存され、ログは`log`ディレクトリに保存されます。

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。