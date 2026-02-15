"""
信頼度レベル昇格検出モジュール — trust_level_up.py
v5.3 新規（§9 昇格演出）

依存: config.py (HEART_THRESHOLDS)
"""

import logging

from config import HEART_THRESHOLDS

logger = logging.getLogger(__name__)

# =====================================================================
#  ハート絵文字マッピング
# =====================================================================

# HEART_THRESHOLDS のレベルに対応する絵文字
# ⚠️ COMMON_MISTAKES N-04: HEART_THRESHOLDS を単一参照元とする
LEVEL_HEART_EMOJI: dict[int, str] = {
    1: "🧡",   # newbie (0-19)
    2: "💛",   # low    (20-49)
    3: "💗",   # high   (50-79)
    4: "❤️",   # max    (80-100)
}

# 昇格時のヒントプロンプト（システムプロンプト末尾に追加）
LEVEL_UP_HINT_PROMPTS: dict[int, str] = {
    2: "（さりげなく、以前より少し距離が縮まった気がする、と感じる一言を添えて）",
    3: "（この人のことをよく知るようになった喜びを、ほんの少し言葉の端に滲ませて）",
    4: "（特別な存在になった嬉しさを、タイムトラベラーの秘密を打ち明けるようにさりげなく）",
}

# 昇格フラグ管理（メモリ上の辞書）
# ⚠️ COMMON_MISTAKES N-03: フラグ取得時は必ず pop() を使用
#    info = level_up_pending.pop(user_id, None)
#    get() は禁止 — フラグが消費されず無限昇格演出になる
# ⚠️ N-04: 記録モード時は pop() せず、次の自由モード応答まで保持する
level_up_pending: dict[str, dict] = {}


class TrustLevelUpDetector:
    """信頼度レベル昇格検出（§9 詳細参照）

    HEART_THRESHOLDS を参照してレベル境界を判定する。
    独自の閾値定義を持たない（COMMON_MISTAKES N-04: 単一参照元原則）。
    """

    def check_level_up(
        self,
        user_id: str,
        old_score: int,
        new_score: int,
    ) -> dict | None:
        """レベル境界を跨いだか判定する

        Args:
            user_id:   メンバーID（ログ出力用）
            old_score: 変更前スコア（0-100）
            new_score: 変更後スコア（0-100）

        Returns:
            None: レベル変化なし、または降格（昇格のみ検出）
            dict: §12.4.1 形式の昇格情報
                  {"old_level": int, "new_level": int, "new_heart": str}
        """
        old_level = self._score_to_level(old_score)
        new_level = self._score_to_level(new_score)

        # 昇格のみ検出（降格は演出なし）
        if new_level <= old_level:
            return None

        new_heart = LEVEL_HEART_EMOJI.get(new_level, "🧡")

        logger.info(
            "昇格検出: user=%s, score %d→%d, level %d→%d, heart=%s",
            user_id, old_score, new_score, old_level, new_level, new_heart,
        )

        return {
            "old_level": old_level,
            "new_level": new_level,
            "new_heart": new_heart,
        }

    def _score_to_level(self, score: int) -> int:
        """スコアからレベルを算出する

        Returns:
            int: 1〜4

        ⚠️ 範囲外の値は安全側に Lv1 を返す
        """
        # HEART_THRESHOLDS を参照（N-04: 単一参照元）
        for level, (low, high) in HEART_THRESHOLDS.items():
            if low <= score <= high:
                return level

        # 範囲外 → 安全側
        return 1


def get_level_up_hint(user_id: str) -> str | None:
    """昇格フラグを消費してヒントプロンプトを取得する

    ⚠️ COMMON_MISTAKES N-03: pop() で取得（get() 禁止）
    ⚠️ この関数は自由モード応答時のみ呼び出すこと
       記録モード時は昇格フラグを消費しない（N-04）

    Args:
        user_id: メンバーID

    Returns:
        str:  昇格ヒントプロンプト（システムプロンプト末尾に追加用）
        None: 昇格なし
    """
    info = level_up_pending.pop(user_id, None)  # ⚠️ pop() 必須
    if info is None:
        return None

    new_level = info["new_level"]
    hint = LEVEL_UP_HINT_PROMPTS.get(new_level)
    if hint:
        logger.info(
            "昇格演出発動: user=%s, new_level=%d", user_id, new_level,
        )
    return hint


def register_level_up(user_id: str, level_up_info: dict) -> None:
    """昇格フラグを登録する

    Args:
        user_id:       メンバーID
        level_up_info: check_level_up() の戻り値
    """
    level_up_pending[user_id] = level_up_info
    logger.info(
        "昇格フラグ登録: user=%s, info=%s", user_id, level_up_info,
    )
