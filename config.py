"""
Shiori Bot 設定モジュール — config.py
v5.2 既存定数 + v5.3 追加定数

変更履歴:
  v5.2: 初版（48行）
  v5.3: BOT_VERSION, TRUST_GAIN_MULTIPLIER, HEART_THRESHOLDS,
        REACTION_DELAY_SECONDS, DAILY/WEEKLY 定数,
        SEED_DIR/DATA_DIR 分離, resolve_data_path() 追加
  v5.3-P0: HEART_EMOJIS, get_heart_emoji() を集約
           （N-04: 三重重複の解消 — Single Source of Truth）
"""

import os
from pathlib import Path

# =====================================================================
#  v5.2 既存定数（変更なし）
# =====================================================================

# --- LLM モデル ---
MAIN_MODEL: str = os.getenv("MAIN_MODEL", "claude-sonnet-4-20250514")
TIER1_MODEL: str = os.getenv("TIER1_MODEL", "claude-haiku-4-5-20251001")

# --- Haiku 文字数制限 ---
HAIKU_MAX_MESSAGE_CHARS: int = 500
HAIKU_MAX_CONTEXT_CHARS: int = 300
HAIKU_MAX_SYSTEM_CHARS: int = 200
HAIKU_MAX_SUMMARY_CHARS: int = 100

# --- CFR (Contextual Follow-up Response) ---
CFR_ENABLED: bool = os.getenv("CFR_ENABLED", "true").lower() == "true"
CFR_MAX_FOLLOWUP_COUNT: int = 2
CFR_CONTEXT_EXPIRY_SECONDS: int = 300
CFR_CHANNEL_COOLDOWN_SECONDS: int = 180
CFR_MIN_CONFIDENCE: float = 0.6
CFR_CLEANUP_INTERVAL_MINUTES: int = 1

# --- レート制限 ---
COOLDOWN_CLEANUP_INTERVAL_MINUTES: int = 5

# --- カジュアル応答 ---
CASUAL_RESPONSE_MULTIPLIER: float = 1.5
CASUAL_RESPONSE_MAX_CHARS: int = 300
CASUAL_RESPONSE_MIN_CHARS: int = 30

# --- その他 ---
QUESTION_FREQUENCY_THRESHOLD: float = 0.5
AUTO_SAVE_INTERVAL_MINUTES: int = int(
    os.getenv("AUTO_SAVE_INTERVAL_MINUTES", "30")
)

# --- 認証 ---
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# --- チャンネル ---
MAIN_CHANNEL_CATEGORY_ID: int = int(
    os.getenv("MAIN_CHANNEL_CATEGORY_ID", "0")
)

# --- Bot ユーザーID（on_ready で設定） ---
BOT_USER_ID: int | None = None


# =====================================================================
#  v5.3 追加定数
# =====================================================================

# --- バージョン管理 ---
BOT_VERSION: str = "5.3"
DEPLOY_DATE: str = "2026-02-16"  # デプロイ時に手動更新

# --- 好感度2倍化（§2） ---
TRUST_GAIN_MULTIPLIER: int = 2
# ⚠️ 上昇要因にのみ適用。減衰（daily_decay等の負値）には適用しない

# --- ハートカラー閾値（§4, §9 で共有 — COMMON_MISTAKES N-04: 単一参照元） ---
HEART_THRESHOLDS: dict[int, tuple[int, int]] = {
    1: (0, 19),    # newbie → 🧡
    2: (20, 49),   # low    → 💛
    3: (50, 79),   # high   → 💗
    4: (80, 100),  # max    → ❤️
}

# --- ハートカラー絵文字マッピング（§4.2 — N-04: 単一参照元） ---
# ⚠️ P0修正: trust.py, trust_level_up.py, reaction_handler.py の
#    三重重複を解消。全モジュールはここを参照すること。
HEART_EMOJIS: dict[int, str] = {
    1: "🧡",  # newbie (Lv1: 0-19)
    2: "💛",  # low    (Lv2: 20-49)
    3: "💗",  # high   (Lv3: 50-79)
    4: "❤️",  # max    (Lv4: 80-100)
}

# --- リアクション遅延（§10） ---
REACTION_DELAY_SECONDS: int = 20

# --- 日次メンテナンス（§5） ---
DAILY_MAINTENANCE_HOUR: int = 18   # JST
DAILY_MAINTENANCE_MINUTE: int = 0

# --- 週次独り言（§8） ---
MONOLOGUE_DAY: int = 6       # calendar.SUNDAY（月曜=0, 日曜=6）
MONOLOGUE_HOUR: int = 21     # JST
MONOLOGUE_MINUTE: int = 0
MONOLOGUE_MIN_CHARS: int = 80
MONOLOGUE_MAX_CHARS: int = 150

# --- 予測ハイライト（§5.7） ---
APPROACHING_MONTHS: int = 6   # 接近判定の月数
INACTIVE_DAYS: int = 30       # 非活動判定の日数
MAX_HIGHLIGHTS: int = 2       # ハイライト最大件数

# --- 議論まとめ（§7） ---
MEMBER_SUMMARY_FETCH_LIMIT: int = 100  # Q9決定: 直近100件取得


# =====================================================================
#  ハートカラー共通関数（N-04: 単一参照元）
# =====================================================================

def get_heart_emoji(score: int) -> str:
    """スコアに対応するハート絵文字を返す（§4.2）

    全モジュール共通の唯一の実装。trust.py, trust_level_up.py,
    reaction_handler.py はこの関数を参照する。

    Args:
        score: 信頼度スコア（0-100）

    Returns:
        str: ハート絵文字（🧡💛💗❤️のいずれか）
    """
    for level, (low, high) in HEART_THRESHOLDS.items():
        if low <= score <= high:
            return HEART_EMOJIS.get(level, "🧡")
    return "🧡"  # 範囲外は安全側


# =====================================================================
#  v5.3 seed/data 分離（COMMON_MISTAKES §18 対策）
# =====================================================================

# seed/ — Git管理の初期データ（読み取り専用）
SEED_DIR: str = os.getenv("SEED_DIR", "seed")

# data/ — Railway Volume上のランタイムデータ（読み書き）
DATA_DIR: str = os.getenv("DATA_DIR", "data")

# --- seed ファイルパス定数 ---
SEED_MEMBERS_SEED: str = os.path.join(SEED_DIR, "members_seed.md")
SEED_MEMBERS_EXTENDED: str = os.path.join(SEED_DIR, "members_extended.md")
SEED_COMMUNITY_LEXICON: str = os.path.join(SEED_DIR, "community_lexicon.md")
SEED_CONSENSUS_TRACKER: str = os.path.join(SEED_DIR, "consensus_tracker.md")
SEED_CATEGORIES: str = os.path.join(SEED_DIR, "categories.md")
SEED_CHANNEL_BEHAVIOR: str = os.path.join(SEED_DIR, "channel_behavior.md")

# --- data ファイルパス定数（ランタイム生成） ---
DATA_MEMBERS_EXTENDED: str = os.path.join(DATA_DIR, "members_extended.md")
DATA_PREDICTIONS: str = os.path.join(DATA_DIR, "predictions.md")
DATA_MEMBERS: str = os.path.join(DATA_DIR, "members.md")

# --- v5.2 互換パス定数（既存コードが参照） ---
MEMBERS_FILE: str = DATA_MEMBERS
MEMBERS_EXTENDED_FILE: str = DATA_MEMBERS_EXTENDED
PREDICTIONS_FILE: str = DATA_PREDICTIONS
COMMUNITY_LEXICON_FILE: str = os.path.join(SEED_DIR, "community_lexicon.md")


def resolve_data_path(filename: str, *, writable: bool = False) -> Path:
    """data/ → seed/ フォールバック付きファイルパス解決

    COMMON_MISTAKES §18 対策:
      Railway Volumeが data/ にマウントされると、Git管理ファイルが
      上書きされる。この関数は data/ を優先し、なければ seed/ に
      フォールバックする。

    Args:
        filename: ファイル名（ディレクトリなし、例: "members_extended.md"）
        writable: True の場合、data/ パスを返す（書き込み先として）
                  ファイルが存在しなくても data/ パスを返す

    Returns:
        Path — 解決されたファイルパス

    Examples:
        >>> resolve_data_path("members_extended.md")
        # data/members_extended.md が存在 → Path("data/members_extended.md")
        # data/ になく seed/ にある   → Path("seed/members_extended.md")

        >>> resolve_data_path("members_extended.md", writable=True)
        # 常に → Path("data/members_extended.md")
    """
    if writable:
        data_path = Path(DATA_DIR) / filename
        # data/ ディレクトリがなければ作成
        data_path.parent.mkdir(parents=True, exist_ok=True)
        return data_path

    # 読み取り: data/ → seed/ フォールバック
    data_path = Path(DATA_DIR) / filename
    if data_path.exists():
        return data_path

    seed_path = Path(SEED_DIR) / filename
    if seed_path.exists():
        return seed_path

    # どちらにもない場合は data/ パスを返す（呼び出し側で FileNotFoundError）
    return data_path
