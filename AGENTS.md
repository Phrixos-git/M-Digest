# AGENTS.md

## 開発ルール
- 変更前に簡潔に目的を提示する
‐ 既存の構成を大きく変更する際は確認する
‐ 変更後は可能な範囲でテストまたはビルドを行う

## GITHUBルール
- `git push`は、ユーザの明示的な指示があった場合のみ行うこと
- 作業開始前に必ずfutureブランチにいるか確認する。いなければdevブランチを元に作成する。形式：future_YYYYMMDD
- 同日のfutureブランチがある際はそれを利用する
- push前に `git status` と `git diff --stat` を確認する。
- commit message は日本語で簡潔に書く。
- secret、token、`.env`、秘密鍵をcommitしない。
- main/masterへ直接pushしない
