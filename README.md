# Info Agent

Info Agentは、Arch Linuxで動くRSS中心の情報収集エージェントです。ニュースと天気予報をMarkdownの日報にまとめ、メールで送信します。追加課金は不要で、OpenAI APIキー、有料検索API、外部SaaSは使いません。

## 日報を作成する流れ

ニュースの取得元は、`config/sources.yaml`に登録したRSS/Atomフィードです。各フィードから最大5件の記事を取得し、トピックごとのキーワードで絞り込みます。一致する記事がない場合は、そのフィードの最新5件を使います。

記事の重複は、URLの正規化とタイトルのハッシュで判定します。取得済みの記事は`outputs/state/seen.json`に保存し、日報は`outputs/daily/YYYY-MM-DD.md`へ出力します。日報の記事は、`## カテゴリ`、`### ソース`の順に分類します。

天気予報には、気象庁の東京地方の府県予報データを使います。地域コードは`44132`です。毎朝5時10分に前日以前のキャッシュを削除し、5時発表分だけを`outputs/state/weather.json`へ保存します。午前7時の日報処理では、このキャッシュを読み込みます。

天気予報は日報の先頭に表示します。11時・17時発表分や前日のキャッシュは含めません。天気予報の取得に失敗しても、ニュース日報の生成とメール送信は継続します。

生成した日報はGmailのSMTPサーバー経由で送信します。毎日の自動実行には、`systemd --user`のタイマーを使います。

## セットアップ

```bash
sudo pacman -Syu
sudo pacman -S --needed python
./scripts/setup_venv.sh
```

Arch Linuxの`python`パッケージには`venv`が含まれるため、Ubuntu/Debian系の`python3-venv`に相当する個別パッケージは不要です。外部のPythonパッケージも使っていないため、PyPIへ接続する必要はありません。

## 手動実行

```bash
./scripts/run_daily.sh
```

生成した日報のパスが表示されます。

```text
outputs/daily/2026-06-11.md
```

過去に取得した記事も含めたい場合は、`--include-seen`を指定します。

```bash
./scripts/run_daily.sh --include-seen
```

`--include-seen`を指定すると、`outputs/state/seen.json`に保存済みの記事情報も日報に含めます。古い状態ファイルにハッシュだけが保存されている場合は、そのファイルから記事の本文情報を復元できません。ただし、既存の`outputs/daily/*.md`に記事が残っていれば、日報から読み戻して対象にします。

## メール送信

日報を生成した後は、毎回メールを送信します。既定のSMTPサーバーは、Gmailの`smtp.gmail.com:587`です。

送信先、送信元、Gmailのアプリパスワードなどは、GitHubへ公開しないよう、Git管理外の`.env`に保存します。このリポジトリの`.gitignore`では、`.env`と`.env.*`を除外しています。

メール本文は`今日のニュースです`の一文とし、生成したMarkdown日報を添付します。

まず、設定例をコピーして`.env`を作成し、編集します。

```bash
cp .env.example .env
$EDITOR .env
```

`.env`には、最低限次の値を設定してください。

```bash
INFO_AGENT_SMTP_USERNAME=your-gmail-address@gmail.com
INFO_AGENT_SMTP_PASSWORD=your-gmail-app-password
INFO_AGENT_EMAIL_TO=kurahasb@gmail.com
```

Gmailの認証には、通常のログインパスワードは使いません。Googleアカウントで2段階認証を有効にし、アプリパスワードを作成して`INFO_AGENT_SMTP_PASSWORD`に設定してください。

設定後に実行します。

```bash
./scripts/run_daily.sh
```

メール送信に使う環境変数は次のとおりです。

| 環境変数 | 用途 | 未指定時の値・指定方法 |
| --- | --- | --- |
| `INFO_AGENT_SMTP_USERNAME` | Gmailアドレス | Gmail利用時は必須 |
| `INFO_AGENT_SMTP_PASSWORD` | Gmailのアプリパスワード | Gmail利用時は必須 |
| `INFO_AGENT_EMAIL_FROM` | 送信元 | `INFO_AGENT_SMTP_USERNAME`を使用 |
| `INFO_AGENT_EMAIL_TO` | 送信先 | 必須。複数指定する場合はカンマ区切り |
| `INFO_AGENT_SMTP_HOST` | SMTPサーバー | `smtp.gmail.com` |
| `INFO_AGENT_SMTP_PORT` | SMTPポート | STARTTLSなら587、SSLなら465 |
| `INFO_AGENT_SMTP_STARTTLS` | STARTTLSを使うか | `true` |
| `INFO_AGENT_SMTP_SSL` | SMTP SSLを使うか | `false` |
| `INFO_AGENT_EMAIL_SUBJECT` | 件名 | `YYYY-MM-DD 今日のニュース` |

systemdから日報処理を実行する場合は、`~/.config/info-agent/email.env`も読み込みます。`.env`を使わない場合は、同じ環境変数を`KEY=value`形式でこのファイルに保存してください。

## RSSソースの追加

RSSソースを追加するには、`config/sources.yaml`にフィードの名前とURL、絞り込み用のキーワードを記述します。

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

YAMLの読み込みでは外部依存を避けるため、限られた設定形式だけをサポートしています。トップレベルは`topics:`で、各トピックには`name`、`label`、`feeds`、`keywords`を指定できます。

記事の`title`または`summary`にトピック内のキーワードが含まれていれば、その記事を日報に出力します。一致する記事が1件もない場合は、そのフィードの最新5件を出力します。キーワードが空の場合は、そのトピックのフィードを絞り込まずに扱います。

## systemdによる自動実行

`systemd --user`のタイマーで、天気取得と日報処理を毎日実行します。Arch Linuxはsystemdを標準で使用するため、別途インストールする必要はありません。実行時刻はシステムのローカルタイムで解釈されます。

| 実行時刻 | 処理 |
| --- | --- |
| 毎朝5時10分 | 5時発表の天気予報だけを取得・保存 |
| 毎朝7時 | 保存済みの天気予報を読み込み、ニュース収集、日報生成、メール送信を実行 |

ユニットファイルは、このリポジトリを`~/Projects/M-Digest`に配置する前提で記述しています。別の場所に配置した場合は、`systemd/user/info-agent-daily.service`と`systemd/user/info-agent-weather.service`の`WorkingDirectory`と`ExecStart`を、実際の絶対パスに変更してください。

ユニットファイルをsystemdのユーザー設定ディレクトリへコピーします。

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/info-agent-daily.service ~/.config/systemd/user/
cp systemd/user/info-agent-daily.timer ~/.config/systemd/user/
cp systemd/user/info-agent-weather.service ~/.config/systemd/user/
cp systemd/user/info-agent-weather.timer ~/.config/systemd/user/
```

`.env`を使わず、自動実行用のメール設定を別ファイルに置く場合は、次のように作成します。

```bash
mkdir -p ~/.config/info-agent
cp .env.example ~/.config/info-agent/email.env
$EDITOR ~/.config/info-agent/email.env
chmod 600 ~/.config/info-agent/email.env
```

タイマーを有効化します。

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

ログと直近の実行結果は、次のコマンドで確認します。

```bash
journalctl --user -u info-agent-daily.service
journalctl --user -u info-agent-weather.service
```

日報処理をsystemd経由で手動実行するには、次のコマンドを使います。

```bash
systemctl --user start info-agent-daily.service
```

天気予報だけを手動取得する場合は、天気取得用のサービスを起動します。

```bash
systemctl --user start info-agent-weather.service
```

ログアウト中もタイマーを動かしたい場合は、lingerを有効化します。

```bash
loginctl enable-linger "$USER"
```

日報処理の実行時刻を変える場合は、`systemd/user/info-agent-daily.timer`の`OnCalendar`を編集します。編集したファイルをユーザー設定ディレクトリへ再コピーし、`systemctl --user daemon-reload`と`systemctl --user restart info-agent-daily.timer`を実行してください。

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
