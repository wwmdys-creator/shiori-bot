"""
📎 栞（Shiori）v5.2 — CFR（Contextual Follow-up Response）
Shiori_v5_2_Interface_Contract.md §3.1, §3.2, §4 に準拠
Shiori_v5_2_CFR_State_Machine.md に準拠

v5.3-P0P1-v3: DIRECT_MENTION_PATTERNS を config.py に移動（SSoT化）
              _check_direct_mention() → config.contains_shiori_keyword() 参照

F-01: is_active() で期限・回数・発動済みを一括チェック
F-02: 応答送信と mark_cfr_triggered() は必ずセット
F-03: CFR応答は新しいCFRコンテキストを生成しない（bot.py側で制御）
F-13: remaining_checks はHaiku分析の「前に」同期的にデクリメント
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from config import (
    CFR_CHANNEL_COOLDOWN_SECONDS,
    CFR_CONTEXT_EXPIRY_SECONDS,
    CFR_MAX_FOLLOWUP_COUNT,
    CFR_MIN_CONFIDENCE,
    HAIKU_MAX_MESSAGE_CHARS,
    HAIKU_MAX_SUMMARY_CHARS,
    contains_shiori_keyword,
)
from haiku_context import HaikuContextManager
from haiku_prompts import parse_with_default
from llm import LLMClient

logger = logging.getLogger("shiori.cfr")


# ── データクラス ──


@dataclass
class CFRResult:
    """CFR関連性判定の結果"""

    should_respond: bool
    confidence: float
    relevance_type: Literal[
        "direct_mention", "implicit_reference", "question", "reaction", "none"
    ]
    suggested_tone: Literal["clarify", "agree", "elaborate", "acknowledge", "none"]
    reasoning: str = ""


@dataclass
class CFRContext:
    """CFR追跡用のコンテキスト"""

    shiori_message_id: int
    channel_id: int
    created_at: datetime
    shiori_response_summary: str
    remaining_checks: int = CFR_MAX_FOLLOWUP_COUNT
    cfr_triggered: bool = False

    def is_expired(self) -> bool:
        """期限切れ判定"""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.created_at).total_seconds()
        return elapsed > CFR_CONTEXT_EXPIRY_SECONDS

    def is_exhausted(self) -> bool:
        """チェック回数消費判定"""
        return self.remaining_checks <= 0

    def is_active(self) -> bool:
        """アクティブ判定（F-01: 期限・回数・発動済みを一括チェック）"""
        return (
            not self.is_expired()
            and not self.is_exhausted()
            and not self.cfr_triggered
        )


# ── CFRTracker ──


class CFRTracker:
    """CFRコンテキストの追跡管理"""

    def __init__(self) -> None:
        self._active_contexts: dict[int, CFRContext] = {}
        self._last_cfr_time: dict[int, datetime] = {}

    def register_response(
        self,
        shiori_message_id: int,
        channel_id: int,
        shiori_response: str,
    ) -> CFRContext:
        """
        栞の返信をCFRコンテキストとして登録。
        同一チャンネルの既存コンテキストは上書き。
        """
        summary = HaikuContextManager.summarize_shiori_response(shiori_response)
        context = CFRContext(
            shiori_message_id=shiori_message_id,
            channel_id=channel_id,
            created_at=datetime.now(timezone.utc),
            shiori_response_summary=summary,
        )
        self._active_contexts[channel_id] = context
        logger.info(
            "CFR registered: channel=%d, msg=%d, summary='%s'",
            channel_id,
            shiori_message_id,
            summary[:50],
        )
        return context

    def get_active_context(self, channel_id: int) -> CFRContext | None:
        """
        アクティブなCFRコンテキストを取得。
        F-01: 非アクティブならNoneを返す。
        """
        context = self._active_contexts.get(channel_id)
        if context is None:
            return None
        if not context.is_active():
            return None
        return context

    def check_followup(self, channel_id: int) -> CFRContext | None:
        """
        後続メッセージがCFR対象か確認し、コンテキストを返す。
        F-13: remaining_checks を同期的にデクリメントしてからコンテキストを返す。
        """
        context = self.get_active_context(channel_id)
        if context is None:
            return None
        # F-13: デクリメントはHaiku分析の「前に」同期的に行う
        context.remaining_checks -= 1
        logger.debug(
            "CFR check_followup: channel=%d, remaining=%d",
            channel_id,
            context.remaining_checks,
        )
        return context

    def mark_cfr_triggered(self, channel_id: int) -> None:
        """
        CFR発動をマーク。
        F-02: cfr_triggered=True + _last_cfr_time更新をセットで実行。
        """
        context = self._active_contexts.get(channel_id)
        if context:
            context.cfr_triggered = True
            self._last_cfr_time[channel_id] = datetime.now(timezone.utc)
            logger.info("CFR triggered: channel=%d", channel_id)

    def is_channel_on_cooldown(self, channel_id: int) -> bool:
        """
        チャンネルがクールダウン中か判定。
        F-14: クールダウンはCFRのみに適用、メンション/返信には影響しない。
        """
        last_time = self._last_cfr_time.get(channel_id)
        if last_time is None:
            return False
        now = datetime.now(timezone.utc)
        elapsed = (now - last_time).total_seconds()
        return elapsed < CFR_CHANNEL_COOLDOWN_SECONDS

    def cleanup_expired(self) -> int:
        """期限切れコンテキストを削除"""
        expired_channels = [
            ch
            for ch, ctx in self._active_contexts.items()
            if ctx.is_expired() or ctx.cfr_triggered
        ]
        for ch in expired_channels:
            del self._active_contexts[ch]
        if expired_channels:
            logger.debug("CFR cleanup: removed %d contexts", len(expired_channels))
        return len(expired_channels)


# ── CFRAnalyzer ──

# Haiku出力 type → (relevance_type, suggested_tone) マッピング
_TYPE_MAPPING: dict[str, tuple[str, str]] = {
    "question": ("question", "clarify"),
    "agree": ("reaction", "acknowledge"),
    "disagree": ("reaction", "clarify"),
    "elaborate": ("implicit_reference", "elaborate"),
    "none": ("none", "none"),
}


class CFRAnalyzer:
    """CFR関連性判定"""

    # v5.3-P0P1-v3: DIRECT_MENTION_PATTERNS を config.py に移動（SSoT化）
    # contains_shiori_keyword() を使用する。

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._ctx_mgr = HaikuContextManager()

    async def analyze(
        self,
        shiori_summary: str,
        target_message: str,
    ) -> CFRResult:
        """
        メッセージの関連性を判定。
        1. 直接言及チェック（正規表現、高速パス）
        2. 暗黙的関連性判定（Haiku呼び出し）
        """
        # F-04: 切り詰め済みデータを使用
        shiori_summary = HaikuContextManager.truncate(
            shiori_summary, HAIKU_MAX_SUMMARY_CHARS
        )
        target_message = HaikuContextManager.truncate(
            target_message, HAIKU_MAX_MESSAGE_CHARS
        )

        # Step 1: 直接言及（高速パス）
        if self._check_direct_mention(target_message):
            return CFRResult(
                should_respond=True,
                confidence=0.95,
                relevance_type="direct_mention",
                suggested_tone="acknowledge",
                reasoning="直接言及あり",
            )

        # Step 2: 暗黙的関連性（Haiku）
        return await self._analyze_implicit(shiori_summary, target_message)

    def _check_direct_mention(self, message: str) -> bool:
        """直接言及の有無をチェック（config.py SSoT参照）"""
        return contains_shiori_keyword(message)

    async def _analyze_implicit(
        self,
        shiori_summary: str,
        target_message: str,
    ) -> CFRResult:
        """暗黙的関連性をHaikuで判定"""
        try:
            raw = await self._llm.call_haiku(
                "cfr_relevance_check",
                template_vars={
                    "shiori_summary": shiori_summary,
                    "target_message": target_message,
                },
            )
        except Exception:
            logger.exception("CFR Haiku call failed")
            return CFRResult(
                should_respond=False,
                confidence=0.0,
                relevance_type="none",
                suggested_tone="none",
                reasoning="Haiku呼び出し失敗",
            )

        # F-06: safe_parse_json + デフォルト値
        result = parse_with_default(
            raw, {"related": False, "confidence": 0.0, "type": "none"}
        )

        related = bool(result.get("related", False))
        confidence = float(result.get("confidence", 0.0))
        rtype = str(result.get("type", "none"))

        # confidence閾値チェック
        should_respond = related and confidence >= CFR_MIN_CONFIDENCE

        relevance_type, suggested_tone = _TYPE_MAPPING.get(
            rtype, ("none", "none")
        )

        return CFRResult(
            should_respond=should_respond,
            confidence=confidence,
            relevance_type=relevance_type,
            suggested_tone=suggested_tone,
            reasoning=f"Haiku判定: related={related}, type={rtype}",
        )
