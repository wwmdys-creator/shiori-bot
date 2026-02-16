"""
trust_level_up.py - 信頼度レベル昇格検出・演出

Shiori v5.3 - §9 信頼度レベル昇格演出
Interface Contract: §12.7.5
Error Pattern: N-03 (pop/get混同防止), N-04 (記録モード演出制御)

COMMON_MISTAKES §10: bot.py から呼ばれるクラス名・メソッド名を厳密に一致させる。
COMMON_MISTAKES §13: check_level_up() は sync 関数。LLM呼び出しなし。
COMMON_MISTAKES §15: 全公開メソッドが実装済みであること。
"""

import logging

from config import HEART_THRESHOLDS

logger = logging.getLogger(__name__)


# ===== §9.6 昇格演出プロンプト辞書 =====
# 各レベルへの昇格時にシステムプロンプトへ追加するテキスト。
# キー: 昇格先レベル (2, 3, 4)
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


def get_heart_emoji(score: int) -> str:
    """スコアからハートカラー絵文字を返す（§4.2 ハートカラーシステム）

    Args:
        score: 好感度スコア (0-100)

    Returns:
        str: ハート絵文字
    """
    heart_map = {
        1: "🧡",  # newbie
        2: "💛",  # low
        3: "💗",  # high (§12.7.5 準拠)
        4: "❤️",  # max
    }
    for level, (low, high) in HEART_THRESHOLDS.items():
        if low <= score <= high:
            return heart_map.get(level, "🧡")
    return "🧡"  # 範囲外は安全側


class TrustLevelUpDetector:
    """信頼度レベル昇格検出（Trust Level Promotion Detector）

    スコア変更時に呼び出され、レベル境界を跨いだ場合のみ
    昇格情報を返す。跨いでいなければ None を返す。

    Public API (Interface Contract §12.7.5):
        - check_level_up(user_id, old_score, new_score) -> dict | None

    ⚠️ LEVEL_THRESHOLDS は config.py の HEART_THRESHOLDS を共有参照する。
       閾値変更時は config.py 側で一元管理すること。
    """

    def check_level_up(
        self,
        user_id: str,
        old_score: int,
        new_score: int,
    ) -> dict | None:
        """レベルアップが発生したか判定する

        Args:
            user_id: メンバーID（ログ出力用）
            old_score: 変更前のスコア（0-100）
            new_score: 変更後のスコア（0-100）

        Returns:
            None: レベル変化なし、または降格（演出しない）
            dict: {"old_level": int, "new_level": int, "new_heart": str}
                  §12.4.1 形式の昇格情報

        ⚠️ 降格（new_level < old_level）は演出しない設計（§9.3.3）
        """
        old_level = self._score_to_level(old_score)
        new_level = self._score_to_level(new_score)

        if new_level > old_level:
            result = {
                "old_level": old_level,
                "new_level": new_level,
                "new_heart": get_heart_emoji(new_score),
            }
            logger.info(
                f"[LevelUp] Detected for {user_id}: "
                f"Lv{old_level} → Lv{new_level} "
                f"(score {old_score} → {new_score})"
            )
            return result
        return None

    def _score_to_level(self, score: int) -> int:
        """スコアからレベルを算出する

        Args:
            score: 好感度スコア (0-100)

        Returns:
            int: 1〜4

        ⚠️ 範囲外の値は安全側にLv1を返す
        """
        for level, (low, high) in HEART_THRESHOLDS.items():
            if low <= score <= high:
                return level
        return 1  # 範囲外は安全側にLv1
