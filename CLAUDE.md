# CLAUDE.md

このファイルは、このリポジトリでコードを操作する際に Claude Code（claude.ai/code）に対する指示を提供します。

## コマンド

```bash
# セットアップ
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 実行（--dry-run は LINE 通知と seen.json の更新をスキップ）
python main.py --dry-run
python main.py
```

## アーキテクチャ

単一スクリプトパイプライン（`main.py`）が上から下へ実行されます：

1. **RSS フィード** → `fetch_all_feeds()` — `feedparser` を使用、ソースは `config.py:FEEDS` で定義
2. **Claude/Anthropic ソース** → `fetch_claude_sources()` — GitHub Releases API + Claude Code バージョンの CHANGELOG.md、anthropic.com/news、/engineering、/research の BeautifulSoup スクレイピング
3. **フィルタ** → `filter_articles()` — `AI_KEYWORDS_EN` / `AI_KEYWORDS_EN_WORD` / `AI_KEYWORDS_JA` に対するキーワードマッチング、AI 特化フィードはフィルタリングをスキップ
4. **重複排除** → `deduplicate()` — `data/seen.json` と比較
5. **翻訳** → `translate_articles()` — `lang="en"` の記事に対して Google Translate を `deep-translator` 経由で実行
6. **レンダリング** → `render_html()` — Jinja2 テンプレート → `docs/index.html`（GitHub Pages）
7. **通知** → `send_line_notification()` — LINE Messaging API、`LINE_CHANNEL_ACCESS_TOKEN` + `LINE_USER_ID` が必須

## 主要な設計判断

- 各記事辞書は以下を持ちます： `title`、`url`、`published`（UTC タイムゾーン付きの datetime）、`summary`、`source`、`lang`（`"en"`/`"ja"`）、`category`（`"claude"` / `"international"` / `"domestic"`）、`title_ja`、`summary_ja`
- `category` フィールドが 3 つの HTML セクションを制御： Claude/Anthropic（オレンジ）、海外（青）、国内（赤）
- `data/seen.json` は GitHub Actions によってリポジトリにコミットされるため、重複排除は実行間で永続化されます。`MAX_SEEN_URLS=5000`（FIFO）でキャップ
- Anthropic ページは JS レンダリングの SPA です — スクレイピングは静的 HTML では機能しますが一部コンテンツを見落とします。Claude Code の変更ログは GitHub API を代わりに使用
- `--dry-run` フラグは LINE 通知と `seen.json` の変更を防止し、ローカルテストに安全です

## 設定（`config.py`）

- `FEEDS` — `(name, url, is_ai_specific, lang)` のタプル。`is_ai_specific=True` の場合、キーワードフィルタリングをスキップ
- `CLAUDE_SOURCES` — Anthropic スクレイピング対象の `(name, url)` リスト
- `AI_KEYWORDS_EN_WORD` — 誤検知を減らすための単語境界付きの正規表現パターン（例：`\bai\b`）

## GitHub Actions（`.github/workflows/update.yml`）

毎日 JST 07:00（`cron: '0 22 * * *'`）で実行されます。実行後、`docs/index.html` と `data/seen.json` をリポジトリにコミットバックします。GitHub Pages は `main` ブランチの `docs/` から提供されます。必須シークレット： `LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`。
