"""llm.py — 栞（Shiori）LLMクライアントモジュール

Anthropic Claude API インターフェース。
COMMON_MISTAKES §13: 必ず AsyncAnthropic（非同期クライアント）を使用する。

依存: member_profile.py, errors.py
参照: interface_contract.md §2.2, prompt_templates.md 全体
"""

import json
import logging
from pathlib import Path

import anthropic

logger = logging.getLogger("shiori.llm")

# 使用モデル（Q10: B案）
MODEL_NAME = "claude-haiku-4-5-20251001"


class LLMClient:
    """Anthropic Claude API クライアント。

    COMMON_MISTAKES §13: AsyncAnthropic を使用。Anthropic（同期）は禁止。

    Attributes:
        client: AsyncAnthropic インスタンス
        system_prompt_template: system_prompt.txt の内容
    """

    def __init__(self):
        # COMMON_MISTAKES §13: 必ず AsyncAnthropic を使用
        self.client = anthropic.AsyncAnthropic()
        self.system_prompt_template = self._load_system_prompt_template()
        logger.info("LLMClient initialized with AsyncAnthropic")

    def _load_system_prompt_template(self) -> str:
        """system_prompt.txt を読み込む。"""
        filepath = Path("system_prompt.txt")
        if not filepath.exists():
            logger.warning("system_prompt.txt not found, using empty template")
            return ""
        return filepath.read_text(encoding="utf-8")

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """メイン応答生成。

        Args:
            system_prompt: システムプロンプト（動的コンテキスト注入済み）
            messages: Anthropic API形式 [{"role": "user"|"assistant", "content": str}]
            max_tokens: 最大トークン数
            temperature: 生成温度

        Returns:
            str: 生成されたテキスト
        """
        try:
            response = await self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text

        except anthropic.APIError as e:
            logger.error(f"[generate_response] API error: {e}")
            return "あっ、すみません……ちょっと処理がうまくいかなかったみたいです。もう一度呼んでもらえますか？"
        except Exception as e:
            logger.error(f"[generate_response] Unexpected error: {e}")
            return "えっと……すみません、ちょっと何かうまくいかなかったみたいです。"

    async def call_template(
        self,
        template_name: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> dict | None:
        """バックグラウンドテンプレート呼び出し（T1-T8）。

        JSON形式のdictを返す。パース失敗時はNoneを返す。

        Args:
            template_name: "T1"〜"T8"
            system: テンプレート固有のシステムプロンプト
            user: テンプレート固有のユーザープロンプト
            max_tokens: 最大トークン数
            temperature: 生成温度

        Returns:
            dict | None: パース済みJSON。失敗時None。
        """
        try:
            response = await self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text

            # JSON抽出（コードブロックを考慮）
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            logger.warning(
                f"[{template_name}] JSON parse failed: {e}. "
                f"Raw text: {text[:100] if 'text' in dir() else 'N/A'}..."
            )
            return None
        except anthropic.APIError as e:
            logger.error(f"[{template_name}] API error: {e}")
            return None
        except Exception as e:
            logger.error(f"[{template_name}] Unexpected error: {e}")
            return None

    def build_system_prompt(
        self,
        trust_level: int,
        member_profile: dict | None,
        channel_overrides: dict | None,
        community_knowledge: str | None = None,
    ) -> str:
        """system_prompt.txt + 動的コンテキストを結合してシステムプロンプトを構築する。

        同期メソッド（I/O不要のため）。

        Args:
            trust_level: 信頼度レベル（1-5）
            member_profile: member_profile.py の get_profile() 戻り値
            channel_overrides: channel_config.py の get_overrides() 戻り値
            community_knowledge: member_profile.py の get_community_knowledge_text() 戻り値

        Returns:
            str: 完成したシステムプロンプト
        """
        prompt = self.system_prompt_template

        # 信頼度レベルブロック
        trust_block = self._build_trust_level_block(trust_level)
        prompt = prompt.replace("{trust_level_block}", trust_block)

        # メンバー役割保護ブロック
        member_protection_block = self._build_member_protection_block()
        prompt = prompt.replace("{member_protection_block}", member_protection_block)

        # チャンネルオーバーライドブロック
        channel_block = self._build_channel_overrides_block(channel_overrides)
        prompt = prompt.replace("{channel_overrides_block}", channel_block)

        # コミュニティ知識ブロック（対話相手プロファイル + 全体知識）
        community_block = self._build_community_knowledge_block(
            member_profile, community_knowledge
        )
        prompt = prompt.replace("{community_knowledge_block}", community_block)

        # コンテキストブロック（会話コンテキストは別途注入されるため空）
        prompt = prompt.replace("{context_block}", "")

        return prompt

    def _build_trust_level_block(self, trust_level: int) -> str:
        """信頼度レベルブロックを構築する。"""
        return f"現在の対話相手の信頼度レベル: Lv{trust_level}"

    def _build_member_protection_block(self) -> str:
        """メンバー役割保護ブロックを構築する。"""
        return """- Rom🧄さん: ニュースキュレーション担当。栞はリンク要約を索引レベルに留める
- hnさん: 現役研究者。専門知識で張り合わない
- ろーるさん: 唯一の体系的懐疑論者。慎重派ポジションを守る
- 船長さん: 技術予測のベテラン。敬意を持って接する"""

    def _build_channel_overrides_block(
        self, channel_overrides: dict | None
    ) -> str:
        """チャンネルオーバーライドブロックを構築する。"""
        if not channel_overrides:
            return "（チャンネル固有の設定なし）"

        lines = []
        if channel_overrides.get("tone"):
            lines.append(f"トーン: {channel_overrides['tone']}")
        if channel_overrides.get("premortem") is False:
            lines.append("プレモーテム質問: OFF")
        if channel_overrides.get("nudge") is False:
            lines.append("ナッジ言及: OFF")
        if channel_overrides.get("recording") is False:
            lines.append("予測記録: OFF")

        return "\n".join(lines) if lines else "（チャンネル固有の設定なし）"

    def _build_community_knowledge_block(
        self,
        member_profile: dict | None,
        community_knowledge: str | None = None,
    ) -> str:
        """コミュニティ知識ブロックを構築する。

        Args:
            member_profile: 対話相手の個別プロファイル
            community_knowledge: Tier A-Bメンバー + コンセンサス情報

        Returns:
            str: コミュニティ知識ブロック
        """
        lines = []

        # 1. 全体コミュニティ知識（Tier A-B + コンセンサス）
        if community_knowledge and community_knowledge != "（コミュニティ知識なし）":
            lines.append("## サーバーのコミュニティ知識")
            lines.append(community_knowledge)
            lines.append("")

        # 2. 対話相手の個別プロファイル
        if member_profile:
            lines.append("## 現在の対話相手")
            if member_profile.get("display_name"):
                lines.append(f"名前: {member_profile['display_name']}さん")
            if member_profile.get("tier"):
                lines.append(f"Tier: {member_profile['tier']}")
            if member_profile.get("expertise"):
                lines.append(f"専門領域: {member_profile['expertise']}")
            if member_profile.get("prediction_topics"):
                lines.append(f"主な予測トピック: {member_profile['prediction_topics']}")
            if member_profile.get("notes"):
                lines.append(f"観察所見: {member_profile['notes']}")
        else:
            if not lines:
                lines.append("（対話相手のプロファイル情報なし）")

        return "\n".join(lines) if lines else "（コミュニティ知識なし）"

    def convert_context_to_api_format(
        self,
        context_messages: list[dict],
        bot_user_id: int,
    ) -> list[dict]:
        """内部メッセージ形式 → Anthropic API messages形式に変換する。

        COMMON_MISTAKES §14: データフォーマット変換層の明示的実装。

        同期メソッド。

        変換ルール:
        - is_bot=True → role: "assistant"
        - is_bot=False → role: "user"
        - 連続する同一roleのメッセージは結合する
        - content には発言者名を "{display_name}: {本文}" 形式でプレフィックス

        Args:
            context_messages: 内部形式メッセージリスト
            bot_user_id: Bot自身のDiscord user ID

        Returns:
            list[dict]: Anthropic API形式のメッセージリスト
        """
        if not context_messages:
            return []

        api_messages: list[dict] = []

        for msg in context_messages:
            # roleの決定
            is_bot = msg.get("is_bot", False)
            if msg.get("author_id") == bot_user_id:
                is_bot = True

            role = "assistant" if is_bot else "user"

            # contentの構築
            display_name = msg.get("author_display_name", "不明")
            content_text = msg.get("content", "")
            formatted_content = f"{display_name}: {content_text}"

            # 連続する同一roleのメッセージは結合
            if api_messages and api_messages[-1]["role"] == role:
                api_messages[-1]["content"] += f"\n{formatted_content}"
            else:
                api_messages.append({
                    "role": role,
                    "content": formatted_content,
                })

        # Anthropic APIは最初のメッセージがuserであることを要求
        if api_messages and api_messages[0]["role"] == "assistant":
            api_messages.insert(0, {
                "role": "user",
                "content": "(会話の続き)",
            })

        return api_messages

    def format_discussion_summary(self, t7_result: dict) -> str:
        """T7結果を議論まとめ形式にフォーマットする。

        Args:
            t7_result: T7テンプレートの出力

        Returns:
            str: フォーマット済みの議論まとめテキスト
        """
        topic = t7_result.get("topic", "（論題不明）")
        positions = t7_result.get("positions", [])
        unresolved = t7_result.get("unresolved", [])

        lines = [
            "📓 議論まとめ",
            f"論題: {topic}",
            "",
        ]

        for pos in positions:
            member = pos.get("member", "不明")
            position = pos.get("position", "")
            lines.append(f"{member}さん説: {position}")

        if unresolved:
            lines.append("")
            lines.append(f"未決着: {', '.join(unresolved)}")

        return "\n".join(lines)
