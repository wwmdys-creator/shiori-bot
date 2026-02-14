"""
📎 栞（Shiori）v5.2 — 設定定数
Shiori_v5_2_Interface_Contract.md §2 に準拠
"""

import os

# ── LLMモデル ──
MAIN_MODEL = os.getenv("MAIN_MODEL", "claude-sonnet-4-20250514")
TIER1_MODEL = os.getenv("TIER1_MODEL", "claude-haiku-4-5-20250901")

# ── Haiku制限 ──
HAIKU_MAX_MESSAGE_CHARS = int(os.getenv("HAIKU_MAX_INPUT_CHARS", "500"))
HAIKU_MAX_CONTEXT_CHARS = int(os.getenv("HAIKU_MAX_CONTEXT_CHARS", "300"))
HAIKU_MAX_SYSTEM_CHARS = 200
HAIKU_MAX_SUMMARY_CHARS = 100

# ── CFR設定 ──
CFR_ENABLED = os.getenv("CFR_ENABLED", "true").lower() == "true"
CFR_MAX_FOLLOWUP_COUNT = int(os.getenv("CFR_MAX_FOLLOWUP_COUNT", "2"))
CFR_CONTEXT_EXPIRY_SECONDS = int(os.getenv("CFR_CONTEXT_EXPIRY_SECONDS", "300"))
CFR_CHANNEL_COOLDOWN_SECONDS = int(os.getenv("CFR_CHANNEL_COOLDOWN_SECONDS", "180"))
CFR_MIN_CONFIDENCE = float(os.getenv("CFR_MIN_CONFIDENCE", "0.6"))
CFR_CLEANUP_INTERVAL_MINUTES = 1
COOLDOWN_CLEANUP_INTERVAL_MINUTES = 5

# ── 応答フォーマット ──
CASUAL_RESPONSE_MULTIPLIER = 1.5
CASUAL_RESPONSE_MAX_CHARS = 300
CASUAL_RESPONSE_MIN_CHARS = 30
QUESTION_FREQUENCY_THRESHOLD = 0.5

# ── 保存間隔 ──
AUTO_SAVE_INTERVAL_MINUTES = int(os.getenv("AUTO_SAVE_INTERVAL_MINUTES", "30"))

# ── データパス ──
DATA_DIR = os.getenv("DATA_DIR", "data")
MEMBERS_FILE = os.path.join(DATA_DIR, "members.md")
MEMBERS_EXTENDED_FILE = os.path.join(DATA_DIR, "members_extended.md")
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.md")
COMMUNITY_LEXICON_FILE = os.path.join(DATA_DIR, "community_lexicon.md")

# ── Discord ──
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Bot自身のID（起動時に設定） ──
BOT_USER_ID: int | None = None
