# AI News Radar - Configuration

# RSS Feeds: (display_name, feed_url, is_ai_specific, lang)
# is_ai_specific=True: skip keyword filtering (all articles are AI-related)
# is_ai_specific=False: apply keyword filter on title + summary
# lang: "en" or "ja"
FEEDS = [
    # International
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", True, "en"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", True, "en"),
    ("MIT Tech Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", True, "en"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml", True, "en"),
    ("Google AI Blog", "https://blog.google/technology/ai/rss/", True, "en"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", True, "en"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", False, "en"),
    # Japanese
    ("ITmedia AI+", "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml", True, "ja"),
    ("AI-SCHOLAR", "https://ai-scholar.tech/feed", True, "ja"),
    ("GIGAZINE", "https://gigazine.net/news/rss_2.0/", False, "ja"),
    ("PC Watch", "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf", False, "ja"),
]

AI_KEYWORDS_EN = [
    "artificial intelligence", "machine learning", "deep learning", "neural network",
    "generative ai", "gen ai", "llm", "large language model",
    "gpt", "chatgpt", "openai", "anthropic", "claude ai", "gemini ai", "copilot",
    "midjourney", "stable diffusion", "diffusion model",
    "ai model", "ai agent", "ai startup", "ai chip", "ai safety",
    "text-to-image", "text-to-video", "foundation model",
    "nvidia ai", "meta ai", "microsoft ai", "google ai", "apple ai",
    "hugging face", "ai training", "ai inference",
]

# Patterns that match as whole words to avoid false positives (e.g. "AI" in "MAIL")
AI_KEYWORDS_EN_WORD = [
    r"\bai\b", r"\bllms?\b", r"\bgpt[-\s]?\d", r"\bchatbot\b",
]

AI_KEYWORDS_JA = [
    "AI", "人工知能", "機械学習", "深層学習", "生成AI", "大規模言語モデル",
    "ディープラーニング", "ニューラルネットワーク", "チャットボット",
    "画像生成", "自然言語処理", "LLM", "対話型AI", "AIモデル", "AIエージェント",
]

# Claude / Anthropic specific sources (scraped, no RSS available)
CLAUDE_SOURCES = [
    ("Claude Code Changelog", "https://code.claude.com/docs/en/changelog"),
    ("Anthropic News", "https://www.anthropic.com/news"),
    ("Anthropic Engineering", "https://www.anthropic.com/engineering"),
    ("Anthropic Research", "https://www.anthropic.com/research"),
]

SEEN_FILE = "data/seen.json"
OUTPUT_HTML = "docs/index.html"
TEMPLATE_FILE = "templates/index.html"
MAX_SEEN_URLS = 5000
LINE_MAX_ARTICLES = 10
