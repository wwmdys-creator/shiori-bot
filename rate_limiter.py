"""
rate_limiter.py - レート制限モジュール

Q17: B案 - チャンネルごとに5秒のクールダウン
連続メンションへの対応を制御
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import os


class RateLimiter:
    """
    チャンネルごとのレート制限
    
    同一チャンネルで連続してメンションされた場合、
    クールダウン期間中は応答を控える
    """
    
    def __init__(self, cooldown_seconds: int = 5):
        """
        Args:
            cooldown_seconds: クールダウン秒数（デフォルト30秒）
        """
        self.cooldown_seconds = cooldown_seconds
        self._last_response: dict[int, datetime] = {}  # channel_id -> last response time
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, channel_id: int) -> tuple[bool, Optional[int]]:
        """
        レート制限をチェック
        
        Args:
            channel_id: チャンネルID
        
        Returns:
            tuple[bool, Optional[int]]: 
                (応答可能か, 残り待機秒数)
                応答可能ならTrue, None
                制限中ならFalse, 残り秒数
        """
        async with self._lock:
            now = datetime.now()
            
            if channel_id not in self._last_response:
                return True, None
            
            last_time = self._last_response[channel_id]
            elapsed = (now - last_time).total_seconds()
            
            if elapsed >= self.cooldown_seconds:
                return True, None
            
            remaining = int(self.cooldown_seconds - elapsed)
            return False, remaining
    
    async def record_response(self, channel_id: int) -> None:
        """
        応答を記録
        
        Args:
            channel_id: チャンネルID
        """
        async with self._lock:
            self._last_response[channel_id] = datetime.now()
    
    async def acquire(self, channel_id: int) -> tuple[bool, Optional[int]]:
        """
        レート制限を取得（チェック＆記録を一度に行う）
        
        応答可能な場合は自動的に記録も行う
        
        Args:
            channel_id: チャンネルID
        
        Returns:
            tuple[bool, Optional[int]]: 
                (取得成功か, 残り待機秒数)
        """
        can_respond, remaining = await self.check_rate_limit(channel_id)
        
        if can_respond:
            await self.record_response(channel_id)
        
        return can_respond, remaining
    
    def get_cooldown_message(self, remaining_seconds: int) -> str:
        """
        クールダウン中のキャラクター口調メッセージを取得
        
        Args:
            remaining_seconds: 残り秒数
        
        Returns:
            メッセージ
        """
        if remaining_seconds <= 5:
            return f"あっ、少しお待ちください……📎 あと{remaining_seconds}秒で応答できます"
        elif remaining_seconds <= 15:
            return f"すみません、まだノートを整理中です……📎 あと{remaining_seconds}秒お待ちください"
        else:
            return f"ごめんなさい、前の処理がまだ終わっていなくて……📎💦 あと{remaining_seconds}秒お待ちください"
    
    async def clear_channel(self, channel_id: int) -> None:
        """
        特定チャンネルのレート制限をクリア（管理用）
        
        Args:
            channel_id: チャンネルID
        """
        async with self._lock:
            if channel_id in self._last_response:
                del self._last_response[channel_id]
    
    async def clear_all(self) -> None:
        """全チャンネルのレート制限をクリア（管理用）"""
        async with self._lock:
            self._last_response.clear()
    
    def get_stats(self) -> dict:
        """レート制限の統計情報を取得"""
        now = datetime.now()
        active_channels = 0
        
        for channel_id, last_time in self._last_response.items():
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.cooldown_seconds:
                active_channels += 1
        
        return {
            "tracked_channels": len(self._last_response),
            "active_cooldowns": active_channels,
            "cooldown_seconds": self.cooldown_seconds
        }


# シングルトンインスタンス
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(cooldown_seconds: Optional[int] = None) -> RateLimiter:
    """
    RateLimiterのシングルトンインスタンスを取得
    
    Args:
        cooldown_seconds: クールダウン秒数（初回のみ有効）
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        # 環境変数から読み込み、なければデフォルト30秒
        seconds = cooldown_seconds or int(os.getenv("RATE_LIMIT_SECONDS", "30"))
        _rate_limiter = RateLimiter(seconds)
    
    return _rate_limiter


class UserRateLimiter:
    """
    ユーザーごとのレート制限（オプション）
    
    同一ユーザーからの連続メンションを制御
    チャンネルレート制限とは別に使用可能
    """
    
    def __init__(self, cooldown_seconds: int = 10):
        self.cooldown_seconds = cooldown_seconds
        self._last_request: dict[int, datetime] = {}  # user_id -> last request time
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, user_id: int) -> tuple[bool, Optional[int]]:
        """ユーザーのレート制限をチェック"""
        async with self._lock:
            now = datetime.now()
            
            if user_id not in self._last_request:
                return True, None
            
            last_time = self._last_request[user_id]
            elapsed = (now - last_time).total_seconds()
            
            if elapsed >= self.cooldown_seconds:
                return True, None
            
            remaining = int(self.cooldown_seconds - elapsed)
            return False, remaining
    
    async def record_request(self, user_id: int) -> None:
        """ユーザーのリクエストを記録"""
        async with self._lock:
            self._last_request[user_id] = datetime.now()
