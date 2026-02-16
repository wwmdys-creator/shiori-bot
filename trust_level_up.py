"""
trust_level_up.py - 信頼度レベル昇格検出・演出（Trust Level Promotion Detection）

Shiori v5.3 - §9 信頼度レベル昇格演出
Interface Contract: §12.7.5
Error Pattern: N-03（pop/get混同）, N-04（記録モードでの演出挿入）

レベル境界を跨いだ瞬間に一度だけ変化を匂わせる特別な反応を行い、
メンバー間の口コミ的な話題を自然発生させる。
"""

import logging

logger = logging.getLogger(__name__)


# =====================================================================
# 定数
# =====================================================================

# レベル閾値（§4.2 ハートカラーシステムと同一）
# ⚠️ config.py の HEART_THRESHOLDS と完全一致させること
LEVEL_THRESHOLDS: dict[int, tuple[int, int]] = {
    1: (0, 19),     # newbie → 🧡
    2: (20, 49),    # low    → 💛
    3: (50, 79),    # high   → 💚
    4: (80, 100),   # max    → 💗
}


# 昇格演出プロンプト辞書（§9.6）
# 各レベルへの昇格時にシステムプロンプトへ追加するテキスト。
# LLM（Sonnet）がこの指示に基づいて演出的な1文を生成する。
LEVEL_UP_HINT_PROMPTS: dict[int, str] = {
    2: (
        "【特別指示】このメンバーとの会話に少し慣れてきた感覚を"
        "自然に1文だけ表現してください。"
        "具体的な数値や仕組みには言及しないこと。"
    ),
    3: (
        "【特別指示】このメンバーに対して少し特別な親しみを"
        "感じている様子を自然に1文だけ表現してください。"
        "具体的な数値や仕組みには言及しないこと。"
    ),
    4: (
        "【特別指示】このメンバーとの関係が特別であることを"
        "控えめに1文だけ表現してください。"
        "具体的な数値や仕組みには言及しないこと。"
    ),
}


# =====================================================================
# TrustLevelUpDetector クラス
# =====================================================================

class TrustLevelUpDetector:
    """信頼度レベル昇格検出（Trust Level Promotion Detector）

    スコア変更時に呼び出され、レベル境界を跨いだ場合のみ
    昇格情報を返す。跨いでいなければ None を返す。

    Public API (Interface Contract §12.7.5):
        - check_level_up(user_id, old_score, new_score) -> dict | None
        - _score_to_level(score) -> int
    """

    def check_level_up(
        self,
        user_id: str,
        old_score: int,
        new_score: int,
    ) -> dict | None:
        """レベルアップが発生したか判定する

        Args:
            user_id:   [必須] メンバーID（ログ出力用）
            old_score: [必須] 変更前のスコア（0-100）
            new_score: [必須] 変更後のスコア（0-100）

        Returns:
            None: レベル変化なし、または降格（降格は演出しない）
            dict: {
                "old_level": int,
                "new_level": int,
                "new_heart": str,   # 新レベルのハート絵文字
                "pending": True,    # フラグ消費制御用
            }

        Note:
            降格（new_level < old_level）は演出しない（§9.3.3）。
            ネガティブな体験を避けるための設計判断。
        """
        old_level = self._score_to_level(old_score)
        new_level = self._score_to_level(new_score)

        if new_level > old_level:
            # 昇格時のハート絵文字を取得
            new_heart = self._level_to_heart(new_level)
            logger.info(
                f"[LevelUp] Detected for {user_id}: "
                f"Lv{old_level} → Lv{new_level} ({new_heart})"
            )
            return {
                "old_level": old_level,
                "new_level": new_level,
                "new_heart": new_heart,
                "pending": True,
            }
        return None

    def _score_to_level(self, score: int) -> int:
        """スコアからレベルを算出する

        Args:
            score: 好感度スコア（0-100）

        Returns:
            int: 1〜4

        ⚠️ 範囲外の値は安全側にLv1を返す
        """
        for level, (low, high) in LEVEL_THRESHOLDS.items():
            if low <= score <= high:
                return level
        # 範囲外（負の値や100超）はLv1に安全にフォールバック
        return 1

    @staticmethod
    def _level_to_heart(level: int) -> str:
        """レベルに対応するハート絵文字を返す

        Args:
            level: 信頼度レベル（1-4）

        Returns:
            str: ハート絵文字
        """
        hearts = {
            1: "🧡",
            2: "💛",
            3: "💚",
            4: "💗",
        }
        return hearts.get(level, "🧡")


# =====================================================================
# bot.py 統合用ヘルパー関数
# =====================================================================

async def on_trust_score_change(
    bot,
    user_id: str,
    old_score: int,
    new_score: int,
) -> None:
    """スコア変更時に昇格チェックを行い、フラグを設定する

    好感度スコアが変更されるすべての箇所から呼び出す。
    昇格検出の失敗は応答生成をブロックしない（エラー隔離原則）。

    Args:
        bot:       [必須] ShioriBot インスタンス（level_up_pending を保持）
        user_id:   [必須] メンバーID
        old_score: [必須] 変更前スコア
        new_score: [必須] 変更後スコア

    ⚠️ bot.level_up_pending: dict[str, dict] がインスタンス変数として
       事前に初期化されている必要がある
    ⚠️ bot.level_up_detector: TrustLevelUpDetector がインスタンス変数として
       事前に初期化されている必要がある
    """
    try:
        result = bot.level_up_detector.check_level_up(
            user_id, old_score, new_score
        )
        if result:
            bot.level_up_pending[user_id] = {
                "pending": True,
                "new_level": result["new_level"],
            }
            logger.info(
                f"[LevelUp] Pending for {user_id}: "
                f"Lv{result['old_level']} → Lv{result['new_level']}"
            )
    except Exception as e:
        # 昇格検出の失敗は応答生成をブロックしない
        # （COMMON_MISTAKES Part B: エラー隔離原則）
        logger.error(f"[LevelUp] Detection failed for {user_id}: {e}")


def consume_level_up_flag(
    level_up_pending: dict,
    user_id: str,
    response_mode: str,
) -> str:
    """昇格フラグを消費し、演出プロンプトを返す

    応答生成の冒頭で呼び出す。

    Args:
        level_up_pending: [必須] bot.level_up_pending 辞書
        user_id:          [必須] メンバーID
        response_mode:    [必須] "record" | "free"

    Returns:
        str: 昇格演出プロンプト（演出なしの場合は空文字列）

    ⚠️ COMMON_MISTAKES N-03: pop() 必須。get() は絶対に使わない。
       get() だとフラグが残り、毎回昇格演出が無限に繰り返される。
    ⚠️ COMMON_MISTAKES N-04: 記録モードでは演出を挿入しない。
       記録モード時は pop() した値を再登録し、次の自由モード応答まで保持する。
    """
    # ★★★ 最重要: pop() を使うこと。get() は絶対に使わない ★★★
    level_up_info = level_up_pending.pop(user_id, None)

    if level_up_info is None:
        return ""

    if not level_up_info.get("pending"):
        return ""

    # N-04: 記録モードでは演出しない → フラグを再登録して保持
    if response_mode == "record":
        level_up_pending[user_id] = level_up_info
        logger.info(
            f"[LevelUp] Skipped in record mode for {user_id}, "
            f"flag re-registered for next free mode response"
        )
        return ""

    # 自由モード → 演出プロンプトを返す
    new_level = level_up_info["new_level"]
    extra_context = LEVEL_UP_HINT_PROMPTS.get(new_level, "")
    if extra_context:
        logger.info(
            f"[LevelUp] Inserting hint for {user_id} (Lv{new_level})"
        )
    return extra_context
