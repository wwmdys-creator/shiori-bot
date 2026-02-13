"""passive_monitor.py — 栞（Shiori）受動監視モジュール

メンション/返信なしのメッセージに対し、T1で予測を含むか判定する。
MAIN CHANNELカテゴリ外のメッセージは即座にNoneを返す。

依存: llm.py, predictions.py（PredictionLedger）, channel_config.py（ChannelConfig）
参照: interface_contract.md §2.9, prompt_templates.md T1, event_flow.md §5
"""

import logging

logger = logging.getLogger("shiori.passive_monitor")

# T1 システムプロンプト
T1_SYSTEM_PROMPT = (
    "あなたは未来予測の分類アシスタントです。\n"
    "Discordの「シンギュラリティ・サーバー」に投稿されたメッセージを分析し、\n"
    "未来予測を含むかどうかを判定します。\n"
    "JSONのみを出力してください。説明文は不要です。"
)

# T1 ユーザープロンプトテンプレート
T1_USER_TEMPLATE = """以下のDiscordメッセージが「未来予測」を含むか判定してください。

メッセージ:
投稿者: {author_display_name}
日時: {timestamp}
内容: {message_content}

判定基準:
- 年号（2025以降）＋予測的表現（「〜になる」「〜が実現」「〜までに」「〜だろう」等）
- 技術・社会の将来に関する具体的な見通し
- 単なる願望や冗談ではなく、投稿者が一定の根拠を持って述べている予測

以下のJSON形式で回答してください:
{{"is_prediction": true/false, "confidence": 0.0-1.0, "prediction_text": "予測内容の要約（50字以内）"}}"""

# 予測として記録する最低信頼度
PREDICTION_CONFIDENCE_THRESHOLD = 0.6


class PassiveMonitor:
    """受動監視クラス。

    Attributes:
        llm: LLMClient インスタンス
        predictions: PredictionLedger インスタンス
        channel_config: ChannelConfig インスタンス
    """

    def __init__(self, llm, predictions, channel_config):
        self.llm = llm
        self.predictions = predictions
        self.channel_config = channel_config

    async def check_message(self, message: dict) -> dict | None:
        """メッセージが予測を含むかT1で判定する。

        MAIN CHANNELカテゴリ外のメッセージは即座にNoneを返す。

        Args:
            message: {"user_id": int, "display_name": str,
                      "content": str, "timestamp": str, "channel": str,
                      "channel_category_id": int | None}

        Returns:
            dict | None: {"is_prediction": bool, "confidence": float,
                          "prediction_text": str} | None
        """
        # MAIN CHANNELカテゴリ外のメッセージはスキップ
        category_id = message.get("channel_category_id")
        if not self.channel_config.is_main_channel_category(category_id):
            return None

        content = message.get("content", "")
        if not content or len(content) < 10:
            # 短すぎるメッセージは予測としてあり得ない
            return None

        user_prompt = T1_USER_TEMPLATE.format(
            author_display_name=message.get("display_name", "不明"),
            timestamp=message.get("timestamp", ""),
            message_content=content,
        )

        result = await self.llm.call_template(
            template_name="T1",
            system=T1_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=200,
            temperature=0.3,
        )

        if result is None:
            logger.warning("T1 prediction detection failed")
            return None

        return {
            "is_prediction": result.get("is_prediction", False),
            "confidence": result.get("confidence", 0.0),
            "prediction_text": result.get("prediction_text", ""),
        }

    async def process_prediction(
        self,
        message: dict,
        t1_result: dict,
    ) -> dict | None:
        """検出された予測を記録する。

        predictions.record_prediction() に委譲する。
        detection_method は "passive" を設定する。

        Args:
            message: check_message() と同じ形式のメッセージ辞書
            t1_result: check_message() の戻り値

        Returns:
            dict | None: 記録された予測レコード | None（記録条件未達時）
        """
        if not t1_result.get("is_prediction", False):
            return None

        confidence = t1_result.get("confidence", 0.0)
        if confidence < PREDICTION_CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Prediction below threshold: "
                f"confidence={confidence:.2f} < {PREDICTION_CONFIDENCE_THRESHOLD}"
            )
            return None

        prediction_text = t1_result.get("prediction_text", "")
        if not prediction_text:
            logger.warning("T1 returned is_prediction=True but empty prediction_text")
            return None

        record = await self.predictions.record_prediction(
            message=message,
            prediction_text=prediction_text,
            detection_method="passive",
        )

        logger.info(
            f"Passive prediction recorded: "
            f"user={message.get('display_name', '?')}, "
            f"text={prediction_text[:30]}..."
        )

        return record
