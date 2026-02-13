"""channel_config.py — 栞（Shiori）チャンネル別設定モジュール

チャンネルごとの振る舞いを設定する。

参照: interface_contract.md §2.10, channel_behavior.md §6.2
"""

import logging
import os

logger = logging.getLogger("shiori.channel_config")

# チャンネルオーバーライド設定（channel_behavior.md §6.2 参照）
CHANNEL_OVERRIDES = {
    "未来予測を投稿するch": {
        "tone": "formal",
        "recording": True,
        "premortem": True,
        "nudge": True,
        "priority": "high",
        "description": "予測記録・差分指摘を積極的に実施",
    },
    "雑談ch": {
        "tone": "casual",
        "recording": False,
        "premortem": False,
        "nudge": False,
        "priority": "low",
        "description": "カジュアルなトーン。予測記録は控えめ",
    },
    "vc連携": {
        "tone": "neutral",
        "recording": False,
        "premortem": False,
        "nudge": False,
        "priority": "medium",
        "description": "要約依頼に集中",
    },
    "技術系": {
        "tone": "technical",
        "recording": True,
        "premortem": True,
        "nudge": True,
        "priority": "medium",
        "description": "専門用語を適度に使用",
    },
    "ai関連": {
        "tone": "technical",
        "recording": True,
        "premortem": True,
        "nudge": True,
        "priority": "high",
        "description": "AI関連の予測を重点的に記録",
    },
    "週報": {
        "tone": "formal",
        "recording": False,
        "premortem": False,
        "nudge": False,
        "priority": "low",
        "description": "週報確認。記録は別途",
    },
}


class ChannelConfig:
    """チャンネル設定管理クラス。

    Attributes:
        main_channel_category_id: MAIN CHANNELカテゴリのID
        overrides: チャンネル別オーバーライド設定
    """

    def __init__(self):
        self.main_channel_category_id: int = int(
            os.getenv("MAIN_CHANNEL_CATEGORY_ID", "0")
        )
        self.overrides: dict = CHANNEL_OVERRIDES
        logger.info(
            f"ChannelConfig initialized. "
            f"MAIN_CHANNEL_CATEGORY_ID={self.main_channel_category_id}"
        )

    def is_main_channel_category(self, category_id: int | None) -> bool:
        """チャンネルがMAIN CHANNELカテゴリに属するか判定する。

        同期メソッド。

        Args:
            category_id: チャンネルのカテゴリID

        Returns:
            bool: MAIN CHANNELカテゴリならTrue
        """
        if self.main_channel_category_id == 0:
            # 環境変数未設定の場合は全てのチャンネルを対象とする
            return True

        if category_id is None:
            return False

        return category_id == self.main_channel_category_id

    def get_overrides(self, channel_name: str) -> dict | None:
        """チャンネル名からオーバーライド設定を返す。

        同期メソッド。

        Args:
            channel_name: チャンネル名

        Returns:
            dict | None: オーバーライド設定。該当なしならNone。
        """
        if not channel_name:
            return None

        # 完全一致
        channel_lower = channel_name.lower()
        for key, config in self.overrides.items():
            if key.lower() == channel_lower:
                return config

        # 部分一致（チャンネル名に含まれる場合）
        for key, config in self.overrides.items():
            if key.lower() in channel_lower:
                return config

        return None

    def is_dm(self, message) -> bool:
        """メッセージがDMかどうか判定する。

        同期メソッド。

        Args:
            message: discord.py の Message オブジェクト

        Returns:
            bool: DMならTrue
        """
        # discord.py の DMChannel または GroupChannel を検出
        if hasattr(message, "guild"):
            return message.guild is None
        return False

    def should_record_predictions(self, channel_name: str) -> bool:
        """チャンネルで予測記録を行うべきか判定する。

        Args:
            channel_name: チャンネル名

        Returns:
            bool: 記録すべきならTrue
        """
        overrides = self.get_overrides(channel_name)
        if overrides:
            return overrides.get("recording", True)

        # デフォルトは記録する
        return True

    def should_do_premortem(self, channel_name: str) -> bool:
        """チャンネルでプレモーテム質問を行うべきか判定する。

        Args:
            channel_name: チャンネル名

        Returns:
            bool: 行うべきならTrue
        """
        overrides = self.get_overrides(channel_name)
        if overrides:
            return overrides.get("premortem", True)

        # デフォルトは行う
        return True

    def should_do_nudge(self, channel_name: str) -> bool:
        """チャンネルでナッジ言及を行うべきか判定する。

        Args:
            channel_name: チャンネル名

        Returns:
            bool: 行うべきならTrue
        """
        overrides = self.get_overrides(channel_name)
        if overrides:
            return overrides.get("nudge", True)

        # デフォルトは行う
        return True

    def get_tone(self, channel_name: str) -> str:
        """チャンネルのトーン設定を返す。

        Args:
            channel_name: チャンネル名

        Returns:
            str: トーン設定（"formal", "casual", "technical", "neutral"）
        """
        overrides = self.get_overrides(channel_name)
        if overrides:
            return overrides.get("tone", "neutral")

        return "neutral"

    def get_priority(self, channel_name: str) -> str:
        """チャンネルの優先度を返す。

        Args:
            channel_name: チャンネル名

        Returns:
            str: 優先度（"high", "medium", "low"）
        """
        overrides = self.get_overrides(channel_name)
        if overrides:
            return overrides.get("priority", "medium")

        return "medium"
