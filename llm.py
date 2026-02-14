"""
📎 栞（Shiori）v5.2 — LLMクライアント（統合版）
AsyncAnthropic wrapper。

v4.1 互換メソッド:
  - call_template()        : T1-T8 テンプレート呼び出し（Haiku）
  - build_system_prompt()  : system_prompt.txt + コンテキスト注入
  - convert_context_to_api_format() : 内部形式 → API形式変換
  - generate_response()    : メイン応答生成（Sonnet）
  - format_discussion_summary() : T7出力のフォーマット

v5.2 メソッド:
  - call_haiku()  : HaikuPromptRegistry経由の呼び出し
  - call_sonnet() : Sonnet直接呼び出し

COMMON_MISTAKES §10: bot.py が呼ぶ全メソッドを実装済み。
COMMON_MISTAKES §13: AsyncAnthropic（非同期）を使用。
COMMON_MISTAKES §14: convert_context_to_api_format() でフォーマット変換。
"""

import json
import logging
import re
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, MAIN_MODEL, TIER1_MODEL
from haiku_prompts import HaikuPrompt, HaikuPromptRegistry

logger = logging.getLogger("shiori.llm")

# ── system_prompt.txt のパス（COMMON_MISTAKES §18: Volume と Git の両方を探す）
_SYSTEM_PROMPT_PATHS = [
    Path("system_prompt.txt"),
    Path("/app/system_prompt.txt"),
]


# ── JSON安全パーサ（Shiori_v5_2_Haiku_Prompts.md §9 準拠）──

def safe_parse_json(text: str) -> dict | None:
    """Haiku/テンプレート出力をJSONとしてパース。

    - ```json ... ``` コードブロックを除去
    - 前後の余分なテキストを除去
    - パース失敗時は None を返す
    """
    # コードブロック除去
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)

    # JSON部分を抽出（ネストしていない単純なオブジェクト）
    match = re.search(r"\{[^{}]*\}", text)
    if not match:
        # ネストされたJSONも試行
        match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _load_system_prompt_file() -> str:
    """system_prompt.txt をロードする。見つからなければ空文字列。"""
    for path in _SYSTEM_PROMPT_PATHS:
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                logger.debug("Loaded system_prompt.txt from %s (%d chars)", path, len(content))
                return content
    logger.warning("system_prompt.txt not found in any expected path")
    return ""


class LLMClient:
    """Anthropic APIクライアント（v4.1 + v5.2 統合）"""

    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self._system_prompt_base: str = _load_system_prompt_file()

    # ═══════════════════════════════════════════════════
    #  v4.1 互換メソッド（bot.py から呼ばれる）
    # ═══════════════════════════════════════════════════

    async def call_template(
        self,
        template_name: str,
        system: str,
        user: str,
        max_tokens: int = 200,
        temperature: float = 0.3,
    ) -> dict | None:
        """T1-T8 テンプレート呼び出し（Haiku）。

        prompt_templates.md のインターフェース契約に準拠。
        戻り値: パース済みdict。パース/API失敗時は None。

        Args:
            template_name: テンプレート識別子（"T1"〜"T8"）
            system: システムプロンプト文字列
            user: ユーザープロンプト文字列
            max_tokens: 最大出力トークン
            temperature: 温度パラメータ
        """
        try:
            logger.debug(
                "[%s] call_template: system=%d chars, user=%d chars",
                template_name, len(system), len(user),
            )
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
            logger.error(
                "[%s] API error: Error code: %s - %s",
                template_name, getattr(e, "status_code", "?"), e,
            )
            return None
        except Exception as e:
            logger.error("[%s] Unexpected error: %s", template_name, e)
            return None

    def build_system_prompt(
        self,
        trust_level: int,
        member_profile: dict | None = None,
        channel_overrides: dict | None = None,
        community_knowledge_text: str = "",
    ) -> str:
        """メイン応答用のシステムプロンプトを構築する。

        system_prompt.txt（キャラクター定義）をベースに、
        信頼度レベル、対話相手のプロファイル、チャンネル設定、
        コミュニティ知識を動的に注入する。

        Args:
            trust_level: 対話相手の信頼度レベル（1-5）
            member_profile: 対話相手のプロファイル辞書（get_profileの戻り値）
            channel_overrides: チャンネル別設定辞書
            community_knowledge_text: コミュニティ知識テキスト

        Returns:
            構築済みシステムプロンプト文字列
        """
        parts: list[str] = []

        # 1. キャラクター定義（system_prompt.txt）
        if self._system_prompt_base:
            parts.append(self._system_prompt_base)
        else:
            # フォールバック: 最低限のキャラクター指示
            parts.append(
                "あなたは栞（Shiori）です。19歳の大学生で、"
                "シンギュラリティ・サーバーのフィールドワーク記録係です。"
                "一人称は「わたし」、他者は「〇〇さん」と呼びます。"
            )

        # 2. 信頼度レベルによるトーン指示（§12.1 準拠）
        tone_map = {
            1: "完全な丁寧語で応答してください。初対面の相手です。",
            2: "丁寧語ベースで、やや柔らかい口調で応答してください。",
            3: "丁寧語ベースで、親しみのある表現を混ぜて応答してください。",
            4: "敬語を残しつつ、砕けた表現を使って応答してください。",
            5: "親しい後輩のような口調で応答してください。",
        }
        tone_instruction = tone_map.get(trust_level, tone_map[1])
        parts.append(f"\n[信頼度レベル: {trust_level}]\n{tone_instruction}")

        # 3. 対話相手のプロファイル
        if member_profile:
            display_name = member_profile.get("display_name", "")
            expertise = member_profile.get("expertise", "")
            position = member_profile.get("position", "")
            style = member_profile.get("style", "")
            role_protection = member_profile.get("role_protection", "")

            profile_lines = [f"\n[対話相手: {display_name}さん]"]
            if position:
                profile_lines.append(f"ポジション: {position}")
            if expertise:
                profile_lines.append(f"関心領域: {expertise}")
            if style:
                profile_lines.append(f"発言スタイル: {style}")
            if role_protection:
                profile_lines.append(f"役割保護ルール: {role_protection}")
            parts.append("\n".join(profile_lines))

        # 4. チャンネルオーバーライド
        if channel_overrides:
            constraints = channel_overrides.get("constraints", [])
            tone = channel_overrides.get("tone", "")
            if constraints or tone:
                override_lines = ["\n[チャンネル設定]"]
                if tone:
                    override_lines.append(f"トーン: {tone}")
                for c in constraints:
                    override_lines.append(f"制約: {c}")
                parts.append("\n".join(override_lines))

        # 5. コミュニティ知識
        if community_knowledge_text:
            parts.append(
                f"\n[コミュニティ知識]\n"
                f"以下はサーバーメンバーの情報です。"
                f"メンバーについて聞かれた場合はこの情報を使って回答してください。\n"
                f"{community_knowledge_text}"
            )

        return "\n\n".join(parts)

    def convert_context_to_api_format(
        self,
        context_messages: list[dict],
        bot_user_id: int,
    ) -> list[dict]:
        """内部コンテキスト形式をAnthropic Messages API形式に変換する。

        COMMON_MISTAKES §14: 内部形式とAPI形式の変換を明示的に実装。
        - Bot自身のメッセージ → role: "assistant"
        - その他のメッセージ → role: "user"
        - 連続する同一roleのメッセージは結合する（API要件）

        Args:
            context_messages: _collect_context() の戻り値
            bot_user_id: Bot自身のuser ID

        Returns:
            Anthropic API の messages パラメータ用リスト
        """
        if not context_messages:
            return []

        api_messages: list[dict] = []

        for msg in context_messages:
            content = msg.get("content", "").strip()
            if not content:
                continue

            author_name = msg.get("author_display_name", "unknown")
            is_bot = msg.get("is_bot", False) and msg.get("author_id") == bot_user_id

            if is_bot:
                role = "assistant"
                text = content
            else:
                role = "user"
                text = f"{author_name}: {content}"

            # 連続する同一roleのメッセージを結合（Anthropic API要件）
            if api_messages and api_messages[-1]["role"] == role:
                api_messages[-1]["content"] += f"\n{text}"
            else:
                api_messages.append({"role": role, "content": text})

        # API要件: 最初のメッセージは "user" である必要がある
        if api_messages and api_messages[0]["role"] == "assistant":
            api_messages.insert(0, {"role": "user", "content": "(会話開始)"})

        # API要件: 最後のメッセージは "user" である必要がある
        if api_messages and api_messages[-1]["role"] == "assistant":
            api_messages.append({"role": "user", "content": "(続き)"})

        return api_messages

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """メイン応答を生成する（Sonnet）。

        Args:
            system_prompt: build_system_prompt() の戻り値
            messages: convert_context_to_api_format() の戻り値
            max_tokens: 最大出力トークン
            temperature: 温度パラメータ

        Returns:
            生成された応答テキスト。エラー時はエラーメッセージ。
        """
        if not messages:
            messages = [{"role": "user", "content": "こんにちは"}]

        try:
            logger.debug(
                "generate_response: system=%d chars, messages=%d turns, model=%s",
                len(system_prompt), len(messages), MAIN_MODEL,
            )
            response = await self._client.messages.create(
                model=MAIN_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text

        except anthropic.APIError as e:
            logger.error("generate_response API error: %s", e)
            return "すみません、ちょっと通信エラーが……もう一度話しかけてもらえますか？📎"
        except Exception as e:
            logger.error("generate_response unexpected error: %s", e)
            return "あっ、えっと……ごめんなさい、ちょっと調子が悪いみたいです📎"

    @staticmethod
    def format_discussion_summary(t7_result: dict) -> str:
        """T7（議論要約）の出力を栞のDiscord応答形式にフォーマットする。

        prompt_templates.md §T7 のフォーマット変換仕様に準拠。

        Args:
            t7_result: call_template("T7", ...) の戻り値

        Returns:
            Discord送信用のフォーマット済み文字列
        """
        topic = t7_result.get("topic", "（論題不明）")
        positions = t7_result.get("positions", [])
        unresolved = t7_result.get("unresolved", [])

        lines = [f"📓 議論まとめ", f"論題: {topic}", ""]
        for p in positions:
            member = p.get("member", "?")
            position = p.get("position", "")
            lines.append(f"{member}説: {position}")
        if unresolved:
            lines.append("")
            lines.append("未決着: " + "、".join(unresolved))
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════
    #  v5.2 メソッド（CFR, 動的学習, 応答分類等で使用）
    # ═══════════════════════════════════════════════════

    async def call_haiku(
        self,
        prompt_id: str,
        *,
        template_vars: dict[str, str],
    ) -> str:
        """Haikuプロンプトを実行（HaikuPromptRegistry経由）。

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
        """Sonnetを直接呼び出し。

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
