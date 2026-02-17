"""
response_generator.py - 応答生成モジュール（v5.3拡張版）

Shiori v5.3 - §9 昇格演出 / §3 記録・自由モード / §12.6.3 インターフェース契約
Interface Contract: §12.6.3 (ResponseGenerator.generate)
Error Pattern: F-07 (文字数チェック), F-08 (質問50%), F-09 (オープンエンド禁止), F-10 (箇条書き禁止)

v5.2 → v5.3 差分:
    - generate() に level_up_hint (str|None) と response_mode ("record"|"free") を追加
    - response_mode="record" 時のフォーマット型システムプロンプト挿入
    - level_up_hint 非None 時のシステムプロンプト末尾追加
    - _remove_bullet_points() 追加 (F-10対策)
    - _truncate_response() 追加 (F-07対策)
    - _get_heart_emoji() 追加 (§4 ハートカラー連動)
"""

import logging
import os
import random
import re

logger = logging.getLogger(__name__)

# ===== 定数 =====

# カジュアル応答の文字数制限（v5.2 既存）
CASUAL_RESPONSE_MULTIPLIER = 2.5
CASUAL_RESPONSE_MAX_CHARS = 300
CASUAL_RESPONSE_MIN_CHARS = 30

# ハートカラー（§4 / §12.3 — config.py と同期すること）
HEART_EMOJI_MAP = {
    1: "🧡",  # Lv1: 0-19
    2: "💛",  # Lv2: 20-49
    3: "💗",  # Lv3: 50-79
    4: "❤️",  # Lv4: 80-100
}

# 記録モード用システムプロンプト追加指示（§3.3.1）
RECORD_MODE_INSTRUCTION = """

【応答モード: 記録モード（Record Mode）】
あなたは今、予測記録モードで応答してください。
以下のフォーマットで記録確認を出力してください:

📎 予測記録
━━━━━━━━━━
【カテゴリ】{推定カテゴリ}
【時間軸】{推定時期}
【内容】{予測内容の要約}
━━━━━━━━━━
{差分があれば差分指摘}
{ひとこと感想（1文以内、栞のキャラクターで）}

注意事項:
- 自由会話は行わないでください
- フォーマットに従った構造化出力のみ
- 昇格演出や質問は挿入しないでください
"""

# 自由モード用システムプロンプト追加指示（§3.3.2）
FREE_MODE_INSTRUCTION = """

【応答モード: 自由モード（Free Mode）】
自然な会話形式で応答してください。
構造化フォーマット（📎記録形式や【カテゴリ】等）は使わないでください。
栞のキャラクターが前面に出る、自然で温かい応答をしてください。
"""


class ResponseConfig:
    """応答設定（v5.2 既存、変更なし）

    Attributes:
        response_type: "casual" | "prediction" | "member_query" | "summary" | "other"
        max_chars: 応答最大文字数（Noneで無制限）
        use_sonnet: Sonnetモデルを使うか
        trust_level: 信頼度レベル（1-4）
    """

    def __init__(
        self,
        response_type: str = "casual",
        max_chars: int | None = None,
        use_sonnet: bool = True,
        trust_level: int = 1,
    ):
        self.response_type = response_type
        self.max_chars = max_chars
        self.use_sonnet = use_sonnet
        self.trust_level = trust_level


class ResponseGenerator:
    """応答生成

    Public API (Interface Contract §12.6.3):
        - generate(message, config, context, level_up_hint, response_mode) -> str
        - calculate_max_chars(input_message, response_type) -> int | None
        - should_ask_question() -> bool
        - format_question(options) -> str

    v5.3追加:
        - level_up_hint: 昇格演出プロンプト（§9.5）
        - response_mode: "record" | "free"（§3.3）
    """

    def __init__(self, llm):
        """
        Args:
            llm: LLMClient インスタンス（AsyncAnthropic使用）
        """
        self.llm = llm

    async def generate(
        self,
        message,
        config: ResponseConfig,
        context: str | None = None,
        level_up_hint: str | None = None,
        response_mode: str = "free",
        *,
        system_prompt: str | None = None,
        api_messages: list[dict] | None = None,
    ) -> str:
        """応答を生成する

        v5.3追加パラメータ:
            level_up_hint: 昇格直後の場合、演出プロンプトが渡される（§9.5参照）
                Noneでなければシステムプロンプト末尾に追加する
            response_mode: "record"ならフォーマット型応答、"free"なら自由会話（§3.3参照）
                デフォルトは"free"
            system_prompt: 呼び出し元で構築済みのシステムプロンプト（省略時は内部で構築）
                bot.pyメインパスではbuild_system_prompt()で構築した完全なプロンプトを渡す
            api_messages: 呼び出し元で構築済みのAPIメッセージリスト（省略時はmessage.contentから生成）
                bot.pyメインパスではconvert_context_to_api_format()の戻り値を渡す

        ⚠️ level_up_hint は level_up_pending から pop() で取得した値（§9.4参照）
           get() で取得するとフラグが消費されず無限演出になる（COMMON_MISTAKES N-03）
        ⚠️ 記録モードでは level_up_hint は無視される（§9.5.2）

        Args:
            message: discord.Message オブジェクト
            config: ResponseConfig 応答設定
            context: 追加コンテキスト文字列
            level_up_hint: 昇格演出プロンプト（自由モード時のみ有効）
            response_mode: "record" | "free"
            system_prompt: 構築済みシステムプロンプト（keyword-only）
            api_messages: 構築済みAPIメッセージリスト（keyword-only）

        Returns:
            str: 生成された応答テキスト
        """
        try:
            # ----- システムプロンプト構築 -----
            if system_prompt is not None:
                # C-01修正: bot.pyメインパスから構築済みプロンプトが渡された場合はそのまま使用
                final_prompt = system_prompt
                logger.debug(
                    "[ResponseGenerator] Using pre-built system_prompt (%d chars)",
                    len(final_prompt),
                )
            else:
                # CFR等の軽量パスではResponseGenerator内部で構築
                final_prompt = self.llm.build_system_prompt(
                    trust_level=config.trust_level,
                    member_profile=None,
                    channel_overrides=None,
                    community_knowledge_text=None,
                )

            # モード別指示の追加（§3.3）
            if response_mode == "record":
                final_prompt += RECORD_MODE_INSTRUCTION
                logger.debug("[ResponseGenerator] Response mode: RECORD")
            else:
                final_prompt += FREE_MODE_INSTRUCTION
                logger.debug("[ResponseGenerator] Response mode: FREE")

            # 追加コンテキスト（v5.2 既存 — CFRパス等で使用）
            if context:
                final_prompt += f"\n\n{context}"

            # 昇格演出プロンプト挿入（§9.5 — 自由モード時のみ）
            if level_up_hint and response_mode == "free":
                final_prompt += f"\n\n{level_up_hint}"
                logger.info(
                    "[ResponseGenerator] Level-up hint inserted into system prompt"
                )
            elif level_up_hint and response_mode == "record":
                logger.info(
                    "[ResponseGenerator] Level-up hint skipped (record mode)"
                )

            # ハートカラー指示（§4 — ハートを含める場合のカラー指定）
            heart_emoji = self._get_heart_emoji(config.trust_level)
            final_prompt += (
                f"\n\nこのメンバーへのハート絵文字は{heart_emoji}を使用してください。"
            )

            # ----- メッセージ構築 -----
            if api_messages is not None:
                # C-01修正: bot.pyメインパスから構築済みメッセージが渡された場合
                messages_for_api = api_messages
            else:
                user_content = message.content if hasattr(message, "content") else str(message)
                messages_for_api = [{"role": "user", "content": user_content}]

            # ----- API呼び出し -----
            max_tokens = 500
            if config.max_chars:
                # 概算: 日本語1文字≒2トークン、余裕を持たせる
                max_tokens = min(max_tokens, config.max_chars * 2)

            response_text = await self.llm.generate_response(
                system_prompt=final_prompt,
                messages=messages_for_api,
                max_tokens=max_tokens,
                temperature=0.7,
            )

            # ----- 後処理 -----
            # F-10: 箇条書き除去（自由モード時のみ）
            if response_mode == "free":
                response_text = self._remove_bullet_points(response_text)

            # F-07: 文字数チェック＆切り詰め
            if config.max_chars:
                response_text = self._truncate_response(
                    response_text, config.max_chars
                )

            return response_text

        except Exception as e:
            logger.error(f"[ResponseGenerator] generate failed: {e}")
            return self._fallback_response(response_mode)

    def calculate_max_chars(
        self,
        input_message: str,
        response_type: str,
    ) -> int | None:
        """最大応答文字数を計算する（v5.2 既存、変更なし）

        Args:
            input_message: 入力メッセージ
            response_type: 応答タイプ

        Returns:
            int: 最大文字数
            None: 制限なし
        """
        if response_type == "casual":
            raw = int(len(input_message) * CASUAL_RESPONSE_MULTIPLIER)
            return max(
                CASUAL_RESPONSE_MIN_CHARS,
                min(raw, CASUAL_RESPONSE_MAX_CHARS),
            )
        return None

    def should_ask_question(self) -> bool:
        """質問を付けるべきか判定する（v5.2 既存、変更なし）

        F-08対策: 50%の確率で質問を付与

        Returns:
            bool: 質問を付けるか
        """
        return random.random() < 0.5

    def format_question(self, options: list[str]) -> str:
        """多肢選択式の質問を生成する（v5.2 既存、変更なし）

        Args:
            options: 選択肢リスト（2-4個）

        Returns:
            str: 質問文

        Raises:
            ValueError: 選択肢が2未満または5以上
        """
        if len(options) < 2 or len(options) > 4:
            raise ValueError(
                f"options must be 2-4, got {len(options)}"
            )
        if len(options) == 2:
            return f"{options[0]}ですか、それとも{options[1]}ですか？"
        parts = "、".join(options[:-1])
        return f"{parts}、それとも{options[-1]}ですか？"

    # ===== 内部メソッド =====

    def _get_heart_emoji(self, trust_level: int) -> str:
        """信頼度レベルに対応するハート絵文字を返す（§4）

        Args:
            trust_level: 信頼度レベル（1-4）

        Returns:
            str: ハート絵文字
        """
        level = min(max(trust_level, 1), 4)
        return HEART_EMOJI_MAP.get(level, "🧡")

    def _remove_bullet_points(self, text: str) -> str:
        """箇条書きパターンを検出し文章形式に変換する（F-10対策）

        Args:
            text: 応答テキスト

        Returns:
            str: 箇条書きを除去したテキスト
        """
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if re.match(r"^[・\-\*]\s", stripped):
                cleaned.append(re.sub(r"^[・\-\*]\s*", "", stripped))
            elif re.match(r"^\d+[.．]\s", stripped):
                cleaned.append(re.sub(r"^\d+[.．]\s*", "", stripped))
            else:
                cleaned.append(stripped)
        return "\n".join(cleaned)

    def _truncate_response(self, text: str, max_chars: int) -> str:
        """応答を文末で切り詰める（F-07対策）

        文境界（句点・疑問符・感嘆符）で切ることで自然な終端を保つ。

        Args:
            text: 応答テキスト
            max_chars: 最大文字数

        Returns:
            str: 切り詰めたテキスト
        """
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        for sep in ["。", "？", "！", "\n"]:
            last_pos = truncated.rfind(sep)
            if last_pos > max_chars * 0.6:
                return truncated[: last_pos + 1]
        return truncated[:max_chars]

    def _fallback_response(self, response_mode: str) -> str:
        """API失敗時のフォールバック応答

        Args:
            response_mode: "record" | "free"

        Returns:
            str: フォールバックテキスト
        """
        if response_mode == "record":
            return "📎 記録処理中にエラーが発生しました。もう一度お試しください。"
        return (
            "すみません、少し考えがまとまりませんでした。"
            "もう一度話しかけていただけますか？"
        )
