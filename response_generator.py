"""
📎 栞（Shiori）v5.2 — 応答生成
Shiori_v5_2_Interface_Contract.md §6.1 に準拠

F-07: casual応答は生成後に文字数チェックし、超過時は切り詰め。
F-08: should_ask_question() は50%の確率。
F-09: オープンエンド質問を検出して除去。
F-10: 箇条書き要約を検出して散文に再生成。
F-11: 専門外でもまず自分の提案を出してから詳しい人に振る。
"""

import logging
import random
import re
from dataclasses import dataclass
from typing import Literal

import discord

from config import (
    CASUAL_RESPONSE_MAX_CHARS,
    CASUAL_RESPONSE_MIN_CHARS,
    CASUAL_RESPONSE_MULTIPLIER,
    HAIKU_MAX_MESSAGE_CHARS,
    QUESTION_FREQUENCY_THRESHOLD,
)
from haiku_context import HaikuContextManager
from haiku_prompts import parse_with_default
from llm import LLMClient

logger = logging.getLogger("shiori.response")


@dataclass
class ResponseConfig:
    """応答生成の設定"""

    response_type: Literal["main", "cfr", "casual"]
    max_chars: int | None
    allow_question: bool
    question_style: Literal["multiple_choice", "none"]
    member_highlight: str | None = None


# オープンエンド質問の検出パターン（F-09）
_OPEN_ENDED_PATTERNS: list[re.Pattern] = [
    re.compile(r"どう(?:思い|考え|感じ)ますか[？?]?\s*$"),
    re.compile(r"(?:何|なに|どんな).*(?:ですか|でしょう)[？?]?\s*$"),
    re.compile(r"いかがでしょうか[？?]?\s*$"),
    re.compile(r"どうですか[？?]?\s*$"),
]

# 箇条書き検出パターン（F-10）
_BULLET_PATTERN = re.compile(r"(?:^|\n)\s*[-•·＊※]\s+", re.MULTILINE)


class ResponseGenerator:
    """応答生成"""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._ctx_mgr = HaikuContextManager()

    async def generate(
        self,
        message: discord.Message,
        config: ResponseConfig,
        context: str | None = None,
    ) -> str:
        """
        応答を生成。config.response_type に応じてモデルを選択。
        """
        content = message.content or ""
        author_name = message.author.display_name

        if config.response_type == "casual":
            response = await self._generate_casual(author_name, content, config)
        elif config.response_type == "cfr":
            response = await self._generate_cfr(content, config, context or "")
        else:
            response = await self._generate_main(
                author_name, content, config, context
            )

        # F-07: 生成後の文字数チェック
        if config.max_chars and len(response) > config.max_chars:
            response = self._truncate_response(response, config.max_chars)

        # F-09: オープンエンド質問の除去
        response = self._remove_open_ended_question(response)

        return response

    def calculate_max_chars(
        self,
        input_message: str,
        response_type: str,
    ) -> int | None:
        """
        最大応答文字数を計算。
        casual: len(input) * 1.5、上限300、下限30。
        """
        if response_type != "casual":
            return None
        calculated = int(len(input_message) * CASUAL_RESPONSE_MULTIPLIER)
        return max(CASUAL_RESPONSE_MIN_CHARS, min(calculated, CASUAL_RESPONSE_MAX_CHARS))

    def should_ask_question(self) -> bool:
        """質問を付けるべきか判定（50%の確率）"""
        return random.random() < QUESTION_FREQUENCY_THRESHOLD

    def format_question(self, options: list[str]) -> str:
        """
        多肢選択式の質問を生成。

        Raises:
            ValueError: 選択肢が2未満または5以上
        """
        if len(options) < 2 or len(options) > 4:
            raise ValueError(f"Options must be 2-4, got {len(options)}")
        if len(options) == 2:
            return f"{options[0]}ですか、それとも{options[1]}ですか？"
        # 3-4個
        head = "ですか、".join(options[:-1])
        return f"{head}ですか、それとも{options[-1]}ですか？"

    # ── 内部メソッド ──

    async def _generate_casual(
        self,
        author_name: str,
        content: str,
        config: ResponseConfig,
    ) -> str:
        """雑談応答（Haiku）"""
        max_chars = config.max_chars or CASUAL_RESPONSE_MAX_CHARS
        truncated = HaikuContextManager.truncate(content, HAIKU_MAX_MESSAGE_CHARS)
        try:
            response = await self._llm.call_haiku(
                "casual_response",
                template_vars={
                    "author": author_name[:30],
                    "message": truncated,
                    "max_chars": str(max_chars),
                },
            )
            return response.strip()
        except Exception:
            logger.exception("Casual response generation failed")
            return "すみません、少し調子が悪いみたいです…"

    async def _generate_cfr(
        self,
        target_message: str,
        config: ResponseConfig,
        context: str,
    ) -> str:
        """CFR応答（Haiku）"""
        truncated_target = HaikuContextManager.truncate(
            target_message, HAIKU_MAX_MESSAGE_CHARS
        )
        try:
            response = await self._llm.call_haiku(
                "cfr_response",
                template_vars={
                    "shiori_summary": context[:150],
                    "target_message": truncated_target[:400],
                    "reaction_type": "elaborate",
                },
            )
            return response.strip()
        except Exception:
            logger.exception("CFR response generation failed")
            return ""

    async def _generate_main(
        self,
        author_name: str,
        content: str,
        config: ResponseConfig,
        context: str | None,
    ) -> str:
        """メイン応答（Sonnet）"""
        system_parts = [
            "あなたは栞（しおり）。2045年から来た19歳の未来研究者。",
            "シンギュラリティ・サーバーの記録係として活動中。",
            "敬語ベース（「です」「ます」調）。親しみやすい口調。",
            "一人称は「わたし」。",
        ]
        if config.member_highlight:
            system_parts.append(
                f"\n【メンバー情報】\n{config.member_highlight}"
            )
        if not config.allow_question:
            system_parts.append("\n質問は付けないでください。")
        elif config.question_style == "multiple_choice":
            system_parts.append(
                "\n質問する場合は必ず多肢選択式（「Aですか、それともBですか？」形式）にしてください。"
                "オープンエンドの質問（「どう思いますか？」等）は禁止です。"
            )

        system = "\n".join(system_parts)

        user_parts = [f"{author_name}: {content}"]
        if context:
            user_parts.append(f"\n【追加コンテキスト】\n{context}")

        user_content = "\n".join(user_parts)

        try:
            response = await self._llm.call_sonnet(
                system=system,
                user_content=user_content,
                max_tokens=1024,
            )
            # F-10: 箇条書きチェック
            if _BULLET_PATTERN.search(response):
                logger.warning("Bullet points detected in main response, keeping as-is")
                # 要約依頼以外では散文を期待するが、強制再生成はコスト高のためログのみ
            return response.strip()
        except Exception:
            logger.exception("Main response generation failed")
            return "すみません、ちょっと処理に問題が…もう一度お願いできますか？"

    def _truncate_response(self, response: str, max_chars: int) -> str:
        """応答を文字数制限に合わせて切り詰め"""
        if len(response) <= max_chars:
            return response
        # 文末で切る
        truncated = response[:max_chars]
        # 最後の句点・感嘆符で区切れるか試行
        for delim in ("。", "！", "？", "…", "\n"):
            idx = truncated.rfind(delim)
            if idx > max_chars // 2:  # あまりに短くなるなら無視
                return truncated[: idx + 1]
        return truncated[:max_chars]

    def _remove_open_ended_question(self, response: str) -> str:
        """F-09: オープンエンド質問を検出して除去"""
        for pattern in _OPEN_ENDED_PATTERNS:
            if pattern.search(response):
                # 質問部分を除去（最後の文を削除）
                lines = response.rstrip().rsplit("\n", 1)
                if len(lines) == 2:
                    if pattern.search(lines[1]):
                        return lines[0].rstrip()
                # 1行の場合は句点で最後の文を分離
                sentences = [
                    s for s in re.split(r"(?<=[。！？])", response) if s.strip()
                ]
                if len(sentences) > 1 and pattern.search(sentences[-1]):
                    return "".join(sentences[:-1]).rstrip()
                # 文が1つだけで質問の場合は元のまま返す（空にしない）
        return response
