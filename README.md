# Info Agent

Ubuntu 26.04 LTS aarch64 で動く、追加課金なしのRSS中心情報収集エージェントです。OpenAI APIキー、有料検索API、外部SaaSは使いません。

## 機能

- `config/sources.yaml` のRSS/Atomフィードを取得
- 各RSS/Atomフィードから最大5件の記事を取得
- トピックごとのキーワードで取得記事を絞り込み。一致記事がない場合は最新5件を取得
- URL正規化とタイトルハッシュで重複除外
- `outputs/daily/YYYY-MM-DD.md` にMarkdown日報を出力
- 取得済み記事は `outputs/state/seen.json` に保存
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

ユニットをユーザーsystemd設定へコピーします。

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/info-agent-daily.service ~/.config/systemd/user/
cp systemd/user/info-agent-daily.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now info-agent-daily.timer
```

状態確認:

```bash
systemctl --user status info-agent-daily.timer
systemctl --user list-timers info-agent-daily.timer
journalctl --user -u info-agent-daily.service
```

手動でsystemd経由実行:

```bash
systemctl --user start info-agent-daily.service
```

タイマー時刻を変える場合は `systemd/user/info-agent-daily.timer` の `OnCalendar` を編集して、再コピー後に `systemctl --user daemon-reload` を実行してください。

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
