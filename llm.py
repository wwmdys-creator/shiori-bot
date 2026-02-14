"""
📎 栞（Shiori）v5.2 — LLMクライアント
AsyncAnthropic wrapper。call_haiku() / call_sonnet() を提供。

F-04: call_haiku() は入力文字数を検証してから呼び出す。
F-06: JSONモードの出力は safe_parse_json() でパースする（呼び出し側で処理）。
"""

import logging

from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, MAIN_MODEL, TIER1_MODEL
from haiku_prompts import HaikuPrompt, HaikuPromptRegistry

logger = logging.getLogger("shiori.llm")


class LLMClient:
    """Anthropic APIクライアント"""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def call_haiku(
        self,
        prompt_id: str,
        *,
        template_vars: dict[str, str],
    ) -> str:
        """
        Haikuプロンプトを実行。

        Args:
            prompt_id: HaikuPromptRegistryに登録済みのID
            template_vars: user_templateに渡す変数辞書

        Returns:
            Haikuの出力テキスト
        """
        prompt: HaikuPrompt = HaikuPromptRegistry.get(prompt_id)
        user_content = prompt.user_template.format(**template_vars)

        logger.debug(
            "Haiku call [%s]: system=%d chars, user=%d chars",
            prompt_id,
            len(prompt.system),
            len(user_content),
        )

        response = await self._client.messages.create(
            model=TIER1_MODEL,
            max_tokens=prompt.max_tokens,
            system=prompt.system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text

    async def call_sonnet(
        self,
        *,
        system: str,
        user_content: str,
        max_tokens: int = 1024,
    ) -> str:
        """
        Sonnetを直接呼び出し。

        Args:
            system: システムプロンプト
            user_content: ユーザーメッセージ
            max_tokens: 最大出力トークン数

        Returns:
            Sonnetの出力テキスト
        """
        logger.debug(
            "Sonnet call: system=%d chars, user=%d chars",
            len(system),
            len(user_content),
        )

        response = await self._client.messages.create(
            model=MAIN_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
