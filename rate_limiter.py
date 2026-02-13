"""rate_limiter.py — 栞（Shiori）レート制限モジュール

チャンネルごとのクールダウンを管理し、過剰応答を防ぐ。

参照: interface_contract.md §2.11
"""

import logging
import time

logger = logging.getLogger("shiori.rate_limiter")

# デフォルトのクールダウン秒数
DEFAULT_COOLDOWN_SECONDS = 30


class RateLimiter:
    """レート制限管理クラス。

    Attributes:
        cooldown_seconds: クールダウン秒数
        _last_response: チャンネルID → 最終応答タイムスタンプ
    """

    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS):
        """初期化。

        Args:
            cooldown_seconds: クールダウン秒数（デフォルト30秒）
        """
        self.cooldown_seconds = cooldown_seconds
        self._last_response: dict[int, float] = {}
        logger.info(
            f"RateLimiter initialized with cooldown={cooldown_seconds}s"
        )

    def can_respond(self, channel_id: int) -> bool:
        """クールダウン期間が過ぎていればTrueを返す。

        同期メソッド。

        Args:
            channel_id: Discord channel ID

        Returns:
            bool: 応答可能ならTrue
        """
        if channel_id not in self._last_response:
            return True

        elapsed = time.time() - self._last_response[channel_id]
        can = elapsed >= self.cooldown_seconds

        if not can:
            remaining = self.cooldown_seconds - elapsed
            logger.debug(
                f"[can_respond] channel={channel_id} "
                f"cooldown remaining: {remaining:.1f}s"
            )

        return can

    def record_response(self, channel_id: int) -> None:
        """応答したことを記録する。

        同期メソッド。

        Args:
            channel_id: Discord channel ID
        """
        self._last_response[channel_id] = time.time()
        logger.debug(f"[record_response] channel={channel_id}")

    def get_remaining_cooldown(self, channel_id: int) -> float:
        """残りクールダウン時間を秒で返す。

        Args:
            channel_id: Discord channel ID

        Returns:
            float: 残り秒数（0以上）
        """
        if channel_id not in self._last_response:
            return 0.0

        elapsed = time.time() - self._last_response[channel_id]
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, remaining)

    def reset(self, channel_id: int) -> None:
        """特定チャンネルのクールダウンをリセットする。

        Args:
            channel_id: Discord channel ID
        """
        if channel_id in self._last_response:
            del self._last_response[channel_id]
            logger.debug(f"[reset] channel={channel_id}")

    def reset_all(self) -> None:
        """全チャンネルのクールダウンをリセットする。"""
        self._last_response.clear()
        logger.info("[reset_all] All cooldowns cleared")

    def set_cooldown(self, seconds: int) -> None:
        """クールダウン秒数を変更する。

        Args:
            seconds: 新しいクールダウン秒数
        """
        old = self.cooldown_seconds
        self.cooldown_seconds = max(0, seconds)
        logger.info(f"[set_cooldown] {old}s -> {self.cooldown_seconds}s")

    def bypass_once(self, channel_id: int) -> None:
        """次回の応答時にクールダウンをバイパスする。

        メンション応答など、クールダウンに関係なく応答すべき場合に使用。

        Args:
            channel_id: Discord channel ID
        """
        # クールダウンを過去に設定することでバイパス
        self._last_response[channel_id] = (
            time.time() - self.cooldown_seconds - 1
        )
        logger.debug(f"[bypass_once] channel={channel_id}")
