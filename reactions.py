"""reactions.py — 栞（Shiori）絵文字リアクション管理モジュール

メッセージへの絵文字リアクション追加を管理する。

参照: interface_contract.md §2.14

v4.1変更: ✅（CHECKMARK）定数は存在しない。Q27凍結に伴い削除済み。
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

logger = logging.getLogger("shiori.reactions")


class ReactionManager:
    """絵文字リアクション管理クラス。

    使用する絵文字（Q25: C案改）:
    - CLIP (📎): 予測記録時
    - NOTEBOOK (📓): 議論まとめ・週報時
    - QUESTION (❓): プレモーテム質問時
    - BOOK (📖): 高信頼度メンバー（Lv4以上）への特別反応

    Note:
        ✅（CHECKMARK）は廃止済み（Q27凍結）。
    """

    # 絵文字定数
    CLIP = "📎"
    NOTEBOOK = "📓"
    QUESTION = "❓"
    BOOK = "📖"

    # リアクションタイプとの対応
    REACTION_MAP = {
        "prediction": CLIP,
        "discussion": NOTEBOOK,
        "premortem": QUESTION,
        "high_trust": BOOK,
        "summary": NOTEBOOK,
        "weekly_report": NOTEBOOK,
    }

    async def add_reaction(
        self,
        message: "discord.Message",
        reaction_type: str,
    ) -> None:
        """メッセージに適切な絵文字リアクションを追加する。

        Args:
            message: discord.py の Message オブジェクト
            reaction_type: リアクション種別
                - "prediction": 予測記録時
                - "discussion": 議論まとめ時
                - "premortem": プレモーテム質問時
                - "high_trust": 高信頼度メンバーへの反応
                - "summary": 要約時
                - "weekly_report": 週報時
        """
        emoji = self.REACTION_MAP.get(reaction_type)

        if not emoji:
            logger.warning(f"[add_reaction] Unknown reaction_type: {reaction_type}")
            return

        try:
            await message.add_reaction(emoji)
            logger.debug(
                f"[add_reaction] Added {emoji} to message {message.id} "
                f"(type={reaction_type})"
            )
        except Exception as e:
            logger.error(f"[add_reaction] Failed to add reaction: {e}")

    async def add_clip_reaction(self, message: "discord.Message") -> None:
        """予測記録リアクション（📎）を追加する。

        Args:
            message: discord.py の Message オブジェクト
        """
        await self.add_reaction(message, "prediction")

    async def add_notebook_reaction(self, message: "discord.Message") -> None:
        """議論まとめリアクション（📓）を追加する。

        Args:
            message: discord.py の Message オブジェクト
        """
        await self.add_reaction(message, "discussion")

    async def add_question_reaction(self, message: "discord.Message") -> None:
        """プレモーテム質問リアクション（❓）を追加する。

        Args:
            message: discord.py の Message オブジェクト
        """
        await self.add_reaction(message, "premortem")

    async def add_book_reaction(self, message: "discord.Message") -> None:
        """高信頼度リアクション（📖）を追加する。

        Args:
            message: discord.py の Message オブジェクト
        """
        await self.add_reaction(message, "high_trust")

    async def remove_reaction(
        self,
        message: "discord.Message",
        reaction_type: str,
    ) -> None:
        """メッセージから絵文字リアクションを削除する。

        Args:
            message: discord.py の Message オブジェクト
            reaction_type: リアクション種別
        """
        emoji = self.REACTION_MAP.get(reaction_type)

        if not emoji:
            logger.warning(f"[remove_reaction] Unknown reaction_type: {reaction_type}")
            return

        try:
            # Bot自身のリアクションを削除
            await message.remove_reaction(emoji, message.guild.me)
            logger.debug(
                f"[remove_reaction] Removed {emoji} from message {message.id}"
            )
        except Exception as e:
            logger.error(f"[remove_reaction] Failed to remove reaction: {e}")

    def get_emoji_for_type(self, reaction_type: str) -> str | None:
        """リアクション種別に対応する絵文字を返す。

        Args:
            reaction_type: リアクション種別

        Returns:
            str | None: 絵文字。該当なしならNone。
        """
        return self.REACTION_MAP.get(reaction_type)

    @staticmethod
    def is_bookmark_emoji(emoji: str) -> bool:
        """ブックマーク（しおり）として扱う絵文字か判定する。

        メンバーが📎や🔖をつけた場合は記録要求と解釈する。

        Args:
            emoji: 絵文字文字列

        Returns:
            bool: ブックマーク絵文字ならTrue
        """
        bookmark_emojis = {"📎", "🔖", "📌", "🏷️"}
        return emoji in bookmark_emojis
