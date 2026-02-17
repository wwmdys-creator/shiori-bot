"""
リアクションハンドラモジュール — reaction_handler.py
v5.2 → v5.3 更新

変更点:
  §1:  should_heart_react() 2引数 → 3引数（is_mention_to_shiori 追加）
  §4:  get_heart_emoji() 追加 — 好感度レベル別ハートカラー
  §10: delayed_add_reaction() 追加 — 20秒遅延リアクション
  §10.10.2: schedule_delayed_reaction() 追加 — 安全ラッパー

依存: config.py (HEART_THRESHOLDS, REACTION_DELAY_SECONDS)
"""

import asyncio
import logging
import random
import re

import discord

from config import HEART_THRESHOLDS, REACTION_DELAY_SECONDS

logger = logging.getLogger(__name__)

# =====================================================================
#  ハートカラーマッピング（§4 — HEART_THRESHOLDS 参照）
# =====================================================================

# ⚠️ COMMON_MISTAKES N-04: HEART_THRESHOLDS を単一参照元とする
#    この辞書は HEART_THRESHOLDS のレベルキーに対応
_HEART_EMOJIS: dict[int, str] = {
    1: "🧡",   # newbie (0-19)
    2: "💛",   # low    (20-49)
    3: "💗",   # high   (50-79)
    4: "❤️",   # max    (80-100)
}


# =====================================================================
#  ハートリアクション判定キーワード
# =====================================================================

# ポジティブな話題・共感キーワード
_POSITIVE_PATTERNS = [
    r"すごい", r"面白い", r"なるほど", r"いいね",
    r"わかる", r"同意", r"賛成", r"確かに",
    r"ありがと", r"助かる", r"感謝",
    r"楽しみ", r"期待", r"ワクワク",
    r"予測", r"予想", r"未来",
]
_POSITIVE_REGEX = re.compile("|".join(_POSITIVE_PATTERNS))

# リアクション確率（キーワードマッチ時）
_REACTION_PROBABILITY: float = 0.3


class ReactionHandler:
    """ハートリアクション管理

    v5.3 変更点:
      - should_heart_react(): 3引数に拡張（§1）
      - get_heart_emoji(): 好感度スコア別ハートカラー（§4）
      - delayed_add_reaction(): 20秒遅延リアクション（§10）
      - schedule_delayed_reaction(): 安全ラッパー（§10.10.2）
      - handle_reaction(): 統合フロー更新
    """

    def should_heart_react(
        self,
        message_content: str,
        is_reply_to_shiori: bool,
        is_mention_to_shiori: bool,
    ) -> bool:
        """ハートリアクションを付与すべきか判定する（§1, §12.6.1）

        v5.3変更: is_mention_to_shiori 引数追加
          - 栞宛ての返信 or メンションの場合、判定対象
          - どちらでもない場合は付与しない（§1 リアクション制限強化）

        Args:
            message_content:       メッセージ内容
            is_reply_to_shiori:    栞への返信か
            is_mention_to_shiori:  栞へのメンションか

        Returns:
            True: リアクション付与対象
            False: 付与しない
        """
        # §1: 栞宛てでなければリアクションしない
        if not is_reply_to_shiori and not is_mention_to_shiori:
            return False

        content = message_content.strip()
        if not content:
            return False

        # キーワードマッチ → 確率判定
        if _POSITIVE_REGEX.search(content):
            return random.random() < _REACTION_PROBABILITY

        return False

    def get_heart_emoji(self, trust_score: int) -> str:
        """好感度スコアに応じたハート絵文字を返す（§4）

        HEART_THRESHOLDS を参照してレベルを決定し、
        対応する絵文字を返す。

        Args:
            trust_score: 好感度スコア（0-100）

        Returns:
            str: ハート絵文字（🧡 / 💛 / 💗 / ❤️）
        """
        # HEART_THRESHOLDS から該当レベルを検索
        for level, (low, high) in HEART_THRESHOLDS.items():
            if low <= trust_score <= high:
                return _HEART_EMOJIS.get(level, "🧡")

        # 範囲外 → デフォルト
        return "🧡"

    async def handle_reaction(
        self,
        message: discord.Message,
        trust_score: int,
        is_reply_to_shiori: bool,
        is_mention_to_shiori: bool,
    ) -> None:
        """リアクション統合フロー（§4.5, §12.6.2）

        v5.3変更:
          - is_mention_to_shiori 引数追加
          - schedule_delayed_reaction() 安全ラッパー経由に変更
          - 固定ハート → 好感度レベル別ハートカラー

        ⚠️ COMMON_MISTAKES N-01:
           delayed_add_reaction() は create_task() 経由でのみ呼び出す。
           await で直接呼び出すと応答が20秒ブロックされる。

        Args:
            message:               対象メッセージ
            trust_score:           メッセージ投稿者の好感度スコア
            is_reply_to_shiori:    栞への返信か
            is_mention_to_shiori:  栞へのメンションか
        """
        if not self.should_heart_react(
            message.content, is_reply_to_shiori, is_mention_to_shiori
        ):
            return

        emoji = self.get_heart_emoji(trust_score)

        # ⚠️ N-01: schedule_delayed_reaction() 安全ラッパー経由（§10.10.2）
        schedule_delayed_reaction(message, emoji)
        logger.info(
            "リアクション予約: msg=%s, emoji=%s, delay=%ds",
            message.id, emoji, REACTION_DELAY_SECONDS,
        )


# =====================================================================
#  遅延リアクション（§10, §12.5.2）
# =====================================================================

async def delayed_add_reaction(
    message: discord.Message,
    emoji: str,
    delay: int = REACTION_DELAY_SECONDS,
) -> bool:
    """遅延付きリアクション付与

    ⚠️ 本関数は asyncio.create_task() で呼び出すこと
       await 直接呼出しは応答を delay 秒ブロックする（COMMON_MISTAKES N-01）

    ⚠️ COMMON_MISTAKES N-02:
       4種のエラーを個別にキャッチする

    Args:
        message: リアクション対象メッセージ
        emoji:   リアクション絵文字
        delay:   遅延秒数（デフォルト: REACTION_DELAY_SECONDS）

    Returns:
        True:  リアクション成功
        False: 失敗
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        # Bot停止時 → 静かに終了
        return False

    try:
        await message.add_reaction(emoji)
        logger.info(
            "リアクション付与完了: msg=%s, emoji=%s", message.id, emoji,
        )
        return True

    except discord.NotFound:
        # メッセージ削除済み
        logger.warning(
            "リアクション失敗(NotFound): msg=%s — メッセージ削除済み",
            message.id,
        )
        return False

    except discord.Forbidden:
        # 権限不足
        logger.warning(
            "リアクション失敗(Forbidden): msg=%s — 権限不足",
            message.id,
        )
        return False

    except asyncio.CancelledError:
        # Bot停止時
        return False

    except Exception as exc:
        # その他の予期せぬエラー
        logger.error(
            "リアクション失敗(予期せぬエラー): msg=%s, error=%s",
            message.id, exc,
        )
        return False


# =====================================================================
#  安全ラッパー（§10.10.2）
# =====================================================================

def schedule_delayed_reaction(
    message: discord.Message,
    emoji: str,
) -> None:
    """遅延リアクションのスケジュール（Schedule Delayed Reaction）

    create_task() の呼び出しを try/except で囲み、
    スケジューリング自体の失敗が他の処理に影響しないことを保証する。

    §10.10.2 で規定された安全ラッパー。
    全リアクション付与箇所はこの関数経由で呼び出すこと。

    Args:
        message: リアクション対象メッセージ
        emoji:   リアクション絵文字
    """
    try:
        asyncio.create_task(delayed_add_reaction(message, emoji))
    except Exception as e:
        logger.error(
            "[Reaction] Failed to schedule delayed reaction "
            "for message %s: %s",
            message.id, e,
        )
