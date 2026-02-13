"""timeline.py — 栞（Shiori）時間軸解析モジュール

予測の時間範囲を抽出する。T3テンプレートでLLMを使用。

依存: llm.py, errors.py
参照: interface_contract.md §2.6, prompt_templates.md T3
"""

import logging

logger = logging.getLogger("shiori.timeline")

# T3 システムプロンプト
T3_SYSTEM_PROMPT = (
    "あなたは時間軸抽出アシスタントです。\n"
    "未来予測から時間範囲（開始年〜終了年）を抽出します。\n"
    "JSONのみを出力してください。説明文は不要です。"
)

# T3 ユーザープロンプトテンプレート
T3_USER_TEMPLATE = """以下の予測から時間軸（年の範囲）を抽出してください。

予測内容: {prediction_text}
元メッセージ: {original_message_content}

ルール:
1. 開始年と終了年を YYYY 形式で抽出
2. 特定の年が明示されていない場合は "?" を使用
3. 「2030年までに」→ start="?", end="2030"
4. 「2028年頃」→ start="2028", end="2028"
5. 「10年以内」→ 現在年から計算
6. 表示用文字列は "YYYY-YYYY年" 形式

以下のJSON形式で回答してください:
{{"timeline_start": "YYYY or ?", "timeline_end": "YYYY or ?", "timeline_display": "YYYY-YYYY年", "confidence": 0.0-1.0}}"""


class TimelineAnalyzer:
    """時間軸解析クラス。

    Attributes:
        llm: LLMClient インスタンス
    """

    def __init__(self, llm):
        self.llm = llm

    async def extract(
        self,
        prediction_text: str,
        original_message_content: str,
    ) -> dict:
        """T3テンプレートで時間軸を抽出する。

        Args:
            prediction_text: T1出力の予測テキスト
            original_message_content: 元メッセージ本文

        Returns:
            dict: {"timeline_start": str, "timeline_end": str,
                    "timeline_display": str, "confidence": float}
        """
        user_prompt = T3_USER_TEMPLATE.format(
            prediction_text=prediction_text,
            original_message_content=original_message_content,
        )

        result = await self.llm.call_template(
            template_name="T3",
            system=T3_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=100,
            temperature=0.3,
        )

        if result is None:
            logger.warning("T3 extraction failed, using default timeline")
            return {
                "timeline_start": "?",
                "timeline_end": "?",
                "timeline_display": "?-?年",
                "confidence": 0.0,
            }

        return {
            "timeline_start": result.get("timeline_start", "?"),
            "timeline_end": result.get("timeline_end", "?"),
            "timeline_display": result.get("timeline_display", "?-?年"),
            "confidence": result.get("confidence", 0.5),
        }

    @staticmethod
    def timelines_overlap(
        old_start: str,
        old_end: str,
        new_start: str,
        new_end: str,
    ) -> bool:
        """2つの時間軸が重複するか判定する。

        '?' を含む場合は True（重複扱い＝差分指摘しない）を返す。

        Args:
            old_start: 旧予測の開始年
            old_end: 旧予測の終了年
            new_start: 新予測の開始年
            new_end: 新予測の終了年

        Returns:
            bool: 重複する場合True
        """
        if "?" in (old_start, old_end, new_start, new_end):
            return True  # オープンレンジは重複ありと見なす（指摘しない）

        try:
            return int(old_start) <= int(new_end) and int(new_start) <= int(old_end)
        except (ValueError, TypeError):
            logger.warning(
                f"Timeline comparison failed: "
                f"old={old_start}-{old_end}, new={new_start}-{new_end}"
            )
            return True  # パース失敗時も指摘しない
