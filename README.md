# Info Agent

Ubuntu 26.04 LTS aarch64 で動く、追加課金なしのRSS中心情報収集エージェントです。OpenAI APIキー、有料検索API、外部SaaSは使いません。

## 機能

- `config/sources.yaml` のRSS/Atomフィードを取得
- 各RSS/Atomフィードから最大5件の記事を取得
- トピックごとのキーワードで取得記事を絞り込み。一致記事がない場合は最新5件を取得
- URL正規化とタイトルハッシュで重複除外
- `outputs/daily/YYYY-MM-DD.md` にMarkdown日報を出力
- 取得済み記事は `outputs/state/seen.json` に保存
- Gmail SMTPでMarkdown日報をメール送信
- `systemd --user` timerで毎日自動実行

## セットアップ

```bash
sudo apt update
sudo apt install -y python3 python3-venv
./scripts/setup_venv.sh
```

外部Pythonパッケージは使っていないため、PyPIへの接続は不要です。

## 手動実行

```bash
./scripts/run_daily.sh
```

出力例:

```text
outputs/daily/2026-06-11.md
```

過去に取得済みの記事も含めたい場合:

```bash
./scripts/run_daily.sh --include-seen
```

`--include-seen` は `outputs/state/seen.json` に保存済みの記事情報も日報に含めます。古い状態ファイルにハッシュだけが保存されている記事は本文情報を復元できませんが、既存の `outputs/daily/*.md` に残っている記事は読み戻して対象にします。

## メール送信

日報生成後、実行時に必ずメール送信します。SMTPサーバーはGmailの `smtp.gmail.com:587` を既定で使います。

送信先、送信元、GmailのアプリパスワードなどはGitHubへ上げないよう、Git管理外の `.env` に保存します。このリポジトリの `.gitignore` は `.env` と `.env.*` を除外済みです。

メール本文には `今日のニュースです` だけを入れ、生成したMarkdown日報は添付ファイルとして送信します。

`.env` の作成手順:

```bash
cp .env.example .env
$EDITOR .env
```

`.env` には最低限、次の値を設定してください。

```bash
INFO_AGENT_SMTP_USERNAME=your-gmail-address@gmail.com
INFO_AGENT_SMTP_PASSWORD=your-gmail-app-password
INFO_AGENT_EMAIL_TO=kurahasb@gmail.com
```

Gmailで通常のログインパスワードは使わず、Googleアカウントで2段階認証を有効にしてからアプリパスワードを作成し、`INFO_AGENT_SMTP_PASSWORD` に設定してください。

設定後に実行します。

```bash
./scripts/run_daily.sh
```

設定値:

- `INFO_AGENT_SMTP_USERNAME`: Gmailアドレス
- `INFO_AGENT_SMTP_PASSWORD`: Gmailのアプリパスワード
- `INFO_AGENT_EMAIL_FROM`: 送信元。未指定時は `INFO_AGENT_SMTP_USERNAME` を使用
- `INFO_AGENT_EMAIL_TO`: 送信先。複数指定する場合はカンマ区切り
- `INFO_AGENT_SMTP_HOST`: SMTPサーバー。未指定時は `smtp.gmail.com`
- `INFO_AGENT_SMTP_PORT`: SMTPポート。未指定時はSTARTTLSなら587、SSLなら465
- `INFO_AGENT_SMTP_STARTTLS`: STARTTLSを使うか。未指定時は `true`
- `INFO_AGENT_SMTP_SSL`: SMTP SSLを使うか。未指定時は `false`
- `INFO_AGENT_EMAIL_SUBJECT`: 件名。未指定時は `YYYY-MM-DD 今日のニュース`

systemd timerは `~/.config/info-agent/email.env` も読み込みます。`.env` を使わない場合は、同じ環境変数を `KEY=value` 形式で `~/.config/info-agent/email.env` に保存してください。

## RSSソースの追加

`config/sources.yaml` に追加します。

```yaml
topics:
  - name: example
    label: example
    feeds:
      - name: Example Feed
        url: https://example.com/feed.xml
    keywords:
      - Python
      - Linux
```

このプロジェクトのYAML読み込みは外部依存を避けるため、小さな設定形式だけをサポートしています。トップレベルは `topics:`、各トピックは `name`、`label`、`feeds`、`keywords` を持てます。記事の `title` または `summary` にトピック内のキーワードが含まれる場合は一致した記事を日報に出力します。一致する記事が1件もない場合は、そのフィードの最新5件を出力します。キーワードが空の場合は、そのトピックのフィードは絞り込みなしで扱います。

## systemd user timer

Ubuntu 26.04 LTS の `systemd --user` timerで、毎朝7時に日報生成とメール送信を実行します。時刻はシステムのローカルタイムで解釈されます。

ユニットをユーザーsystemd設定へコピーします。

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/info-agent-daily.service ~/.config/systemd/user/
cp systemd/user/info-agent-daily.timer ~/.config/systemd/user/
```

`.env` を使わずuser timer専用にメール設定を置く場合は、次のように作成します。

```bash
mkdir -p ~/.config/info-agent
cp .env.example ~/.config/info-agent/email.env
$EDITOR ~/.config/info-agent/email.env
chmod 600 ~/.config/info-agent/email.env
```

timerを有効化します。

```bash
systemctl --user daemon-reload
systemctl --user enable --now info-agent-daily.timer
```

毎朝7時に予約されていることを確認します。

```bash
systemctl --user status info-agent-daily.timer
systemctl --user list-timers info-agent-daily.timer
systemctl --user cat info-agent-daily.timer
```

ログと直近の実行結果を確認します。

```bash
journalctl --user -u info-agent-daily.service
```

手動でsystemd経由実行:

```bash
systemctl --user start info-agent-daily.service
```

ログアウト中もuser timerを動かしたい場合は、lingerを有効化します。

```bash
loginctl enable-linger "$USER"
```

タイマー時刻を変える場合は `systemd/user/info-agent-daily.timer` の `OnCalendar` を編集して、再コピー後に `systemctl --user daemon-reload` と `systemctl --user restart info-agent-daily.timer` を実行してください。

## ディレクトリ

```text
config/sources.yaml              RSS/Atom取得元
outputs/daily/YYYY-MM-DD.md      日報
outputs/state/seen.json          重複除外用の状態
scripts/setup_venv.sh            venv作成
scripts/run_daily.sh             日次実行
systemd/user/*.service|*.timer   user timer
src/info_agent/                  Python実装
```
