"""
📎 栞（Shiori）v5.2 — リアクションハンドラー
Shiori_v5_2_Interface_Contract.md §7 に準拠

F-12: リアクションと応答は独立。両方同時に実行可能。
"""

import logging
import re

import discord

logger = logging.getLogger("shiori.reaction")


class ReactionHandler:
    """リアクション処理"""

    # 好意的パターン（正規表現）
    POSITIVE_PATTERNS: list[re.Pattern] = [
        # 褒め言葉（栞 + 褒め）
        re.compile(
            r"(栞|しおり|shiori|📎).*(すごい|さすが|優秀|賢い|えらい|天才)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(すごい|さすが|優秀|賢い|えらい|天才).*(栞|しおり|shiori|📎)",
            re.IGNORECASE,
        ),
        # 感謝
        re.compile(r"(ありがと|サンキュー|thx|thanks)", re.IGNORECASE),
        re.compile(r"(助かっ|助けてくれ|おかげ)"),
        # 好意表明（栞 + 好き）
        re.compile(
            r"(栞|しおり|shiori|📎).*(好き|かわいい|可愛い|推し|すこ)",
            re.IGNORECASE,
        ),
        # 愛称
        re.compile(r"(しおりん|栞ちゃん|📎ちゃん|栞たん)"),
    ]

    # 短い肯定的反応（栞への返信時）
    SHORT_POSITIVES: list[str] = [
        "ありがとう",
        "さんきゅ",
        "助かる",
        "なるほど",
        "いいね",
        "👍",
        "🙏",
    ]

    def should_heart_react(
        self,
        message_content: str,
        is_reply_to_shiori: bool,
    ) -> bool:
        """
        ❤️リアクションを付けるべきか判定。
        """
        content = message_content.strip()
        if not content:
            return False

        # パターンマッチ
        for pattern in self.POSITIVE_PATTERNS:
            if pattern.search(content):
                return True

        # 栞への返信時の短い肯定的反応
        if is_reply_to_shiori:
            for positive in self.SHORT_POSITIVES:
                if positive in content:
                    return True

        return False

    async def add_heart_reaction(self, message: discord.Message) -> bool:
        """❤️リアクションを付ける"""
        try:
            await message.add_reaction("❤️")
            logger.info(
                "Heart reaction added: msg=%d, author=%s",
                message.id,
                message.author.display_name,
            )
            return True
        except discord.errors.Forbidden:
            logger.warning("No permission to add reaction: msg=%d", message.id)
            return False
        except Exception:
            logger.exception("Failed to add reaction: msg=%d", message.id)
            return False
