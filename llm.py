"""
📎 栞（Shiori）v5.2 — LLMクライアント
AsyncAnthropic wrapper。call_haiku() / call_sonnet() / call_template() を提供。

F-04: call_haiku() は入力文字数を検証してから呼び出す。
F-06: JSONモードの出力は safe_parse_json() でパースする（呼び出し側で処理）。
"""

import json
import logging
import re

import anthropic
from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, MAIN_MODEL, TIER1_MODEL
from haiku_prompts import HaikuPrompt, HaikuPromptRegistry

logger = logging.getLogger("shiori.llm")


def safe_parse_json(text: str) -> dict | None:
    """
    Haikuの出力をJSONとしてパース。

    - コードブロック (```json ... ```) を除去
    - 前後の余分なテキストを除去
    - パース失敗時は None
    """
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    match = re.search(r"\{[^{}]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


class LLMClient:
    """Anthropic APIクライアント"""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    # ------------------------------------------------------------------
    # call_template: prompt_templates.md インターフェース契約準拠
    #   passive_monitor.py, categories.py, timeline.py, predictions.py,
    #   summarizer.py, nudge.py 等から呼ばれる共通ラッパー
    # ------------------------------------------------------------------
    async def call_template(
        self,
        template_name: str,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
    ) -> dict | None:
        """
        Haikuテンプレート呼び出し（JSON出力前提）。

        Args:
            template_name: テンプレート識別子（T1, T2, ... T8 等）
            system: システムプロンプト
            user: ユーザーメッセージ（テンプレート変数展開済み）
            max_tokens: 最大出力トークン数
            temperature: 温度パラメータ

        Returns:
            パース済みdict、またはパース/API失敗時 None
        """
        logger.debug(
            "call_template [%s]: system=%d chars, user=%d chars",
            template_name,
            len(system),
            len(user),
        )

        try:
            response = await self._client.messages.create(
                model=TIER1_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text
            result = safe_parse_json(text)
            if result is None:
                logger.warning(
                    "[%s] JSON parse failed: %s", template_name, text[:100]
                )
            return result
        except anthropic.APIError as e:
            logger.error("[%s] API error: %s", template_name, e)
            return None
        except Exception as e:
            logger.error("[%s] Unexpected error: %s", template_name, e)
            return None

    # ------------------------------------------------------------------
    # call_haiku: HaikuPromptRegistry ベースの呼び出し
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # call_sonnet: メイン応答生成用
    # ------------------------------------------------------------------
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
