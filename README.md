# Info Agent

Arch Linux で動く、追加課金なしのRSS中心情報収集エージェントです。OpenAI APIキー、有料検索API、外部SaaSは使いません。

## 機能

- `config/sources.yaml` のRSS/Atomフィードを取得
- 午前5時10分に気象庁から東京（地域コード `44132`）の5時発表予報を取得・保存
- 各RSS/Atomフィードから最大5件の記事を取得
- トピックごとのキーワードで取得記事を絞り込み。一致記事がない場合は最新5件を取得
- URL正規化とタイトルハッシュで重複除外
- `outputs/daily/YYYY-MM-DD.md` にMarkdown日報を出力
- 日報の記事を `## カテゴリ` → `### ソース` の順で分類
- 取得済み記事は `outputs/state/seen.json` に保存
- Gmail SMTPでMarkdown日報をメール送信
- `systemd --user` timerで毎日自動実行

天気予報は気象庁の東京地方の府県予報データを使用します。毎朝5時10分に前日以前のキャッシュを削除してから、5時発表分だけを `outputs/state/weather.json` へ保存し、午前7時の日報処理で読み込みます。11時・17時発表分や前日のキャッシュは日報へ混在させません。天気予報は日報の先頭に表示し、取得に失敗してもニュース日報の生成とメール送信は継続します。

## セットアップ

```bash
sudo pacman -Syu
sudo pacman -S --needed python
./scripts/setup_venv.sh
```

Arch Linux の `python` パッケージには `venv` が含まれるため、Ubuntu/Debian系の `python3-venv` に相当する個別パッケージは不要です。外部Pythonパッケージも使っていないため、PyPIへの接続は不要です。

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

Arch Linux の `systemd --user` timerで、毎朝5時10分に5時発表の天気予報だけを保存します。その後、毎朝7時に保存済みの天気予報を読み込み、ニュース収集、日報生成、メール送信を実行します。Arch Linux は systemd を標準で使用するため、別途インストールは不要です。時刻はシステムのローカルタイムで解釈されます。

ユニットは、このリポジトリが `~/Projects/M-Digest` に配置されている前提です。別の場所に配置した場合は、`systemd/user/info-agent-daily.service` の `WorkingDirectory` と `ExecStart` を実際の絶対パスに変更してください。

ユニットをユーザーsystemd設定へコピーします。

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/info-agent-daily.service ~/.config/systemd/user/
cp systemd/user/info-agent-daily.timer ~/.config/systemd/user/
cp systemd/user/info-agent-weather.service ~/.config/systemd/user/
cp systemd/user/info-agent-weather.timer ~/.config/systemd/user/
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
systemctl --user enable --now info-agent-weather.timer info-agent-daily.timer
```

天気取得が毎朝5時10分、日報処理が毎朝7時に予約されていることを確認します。

```bash
systemctl --user status info-agent-daily.timer
systemctl --user status info-agent-weather.timer
systemctl --user list-timers info-agent-weather.timer info-agent-daily.timer
systemctl --user cat info-agent-daily.timer
systemctl --user cat info-agent-weather.timer
```

ログと直近の実行結果を確認します。

```bash
journalctl --user -u info-agent-daily.service
journalctl --user -u info-agent-weather.service
```

手動でsystemd経由実行:

```bash
systemctl --user start info-agent-daily.service
```

天気予報だけを手動取得する場合:

```bash
systemctl --user start info-agent-weather.service
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
scripts/run_weather.sh           天気予報取得
systemd/user/*.service|*.timer   天気取得・日報生成用user timer
src/info_agent/                  Python実装
```
