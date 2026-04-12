# TODO

## 次回やること

1. **記事の表示順を変更** — Claude/Anthropic → 国内 → 海外 の順にする
   - `templates/index.html` の `render_section` 呼び出し順を変更
   - `send_line_notification()` の順も合わせて変更

2. **記事数を絞る** — 海外・国内それぞれ最大10件に制限
   - `render_html()` で international / domestic をそれぞれ上位10件にスライス

3. **LINE連携** — LINE Messaging APIのセットアップ・動作確認
   - LINE Developersでチャネル作成 → Channel Access Token と User ID を取得
   - ローカルで `export` して `python main.py` でテスト

4. **GitHub Actions連携** — リポジトリ作成・Pages有効化
   - `gh repo create` でリポジトリ作成
   - Secrets に `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID` を登録
   - GitHub Pages を `docs/` フォルダから配信設定
   - 手動実行（workflow_dispatch）で動作確認
