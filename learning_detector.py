"""
📎 栞（Shiori）v5.2 — 動的学習検出
Shiori_v5_2_Interface_Contract.md §5.1 に準拠

F-05: 正規表現→Haikuカテゴリ分類→Haiku情報抽出のステップ分割。
F-15: 正規表現プレチェック（has_trigger）で不要なHaiku呼び出しを削減。
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from config import HAIKU_MAX_MESSAGE_CHARS
from haiku_context import HaikuContextManager
from haiku_prompts import parse_with_default
from llm import LLMClient

logger = logging.getLogger("shiori.learning")


@dataclass
class LearningResult:
    """動的メンバー学習の結果"""

    has_learnable_info: bool
    category: (
        Literal["interest", "personal", "stance", "speech_pattern", "relationship", "none"]
        | None
    )
    extracted_info: str | None
    confidence: float


# カテゴリ名の正規化マッピング（Haiku出力の揺れ吸収）
_CATEGORY_NORMALIZE: dict[str, str] = {
    "interest": "interest",
    "personal": "personal",
    "stance": "stance",
    "speech": "speech_pattern",
    "speech_pattern": "speech_pattern",
    "relationship": "relationship",
    "none": "none",
}

_NO_LEARNING = LearningResult(
    has_learnable_info=False,
    category=None,
    extracted_info=None,
    confidence=0.0,
)


class LearningDetector:
    """学習対象検出"""

    # 基本トリガー（個人情報・生活変化）
    TRIGGER_PATTERNS: list[re.Pattern] = [
        re.compile(r"最近"),
        re.compile(r"転職"),
        re.compile(r"興味"),
        re.compile(r"ハマっ"),
        re.compile(r"変わっ"),
        re.compile(r"〜派"),
        re.compile(r"引っ越"),
        re.compile(r"始めた"),
        re.compile(r"やめた"),
        re.compile(r"推し"),
        # v5.3.1: シンギュラリティサーバー向け拡張
        # 意見・見解の表明
        re.compile(r"と思[うっ]"),
        re.compile(r"だと[思考]"),
        re.compile(r"と考え"),
        re.compile(r"気がする"),
        re.compile(r"予[測想]"),
        re.compile(r"[楽悲]観"),
        re.compile(r"信じ"),
        re.compile(r"期待"),
        re.compile(r"懸念"),
        re.compile(r"仮説"),
        # 技術的スタンス
        re.compile(r"使ってみ"),
        re.compile(r"試し[てた]"),
        re.compile(r"触っ[てた]"),
        re.compile(r"作っ[てた]"),
        re.compile(r"実装"),
        re.compile(r"個人的に"),
        re.compile(r"自分[はの]"),
        # 生活・状況の共有
        re.compile(r"仕事"),
        re.compile(r"勉強"),
        re.compile(r"読[んめ]"),
        re.compile(r"買っ"),
    ]

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def has_trigger(self, message: str) -> bool:
        """トリガーキーワードの有無をチェック（正規表現）"""
        return any(p.search(message) for p in self.TRIGGER_PATTERNS)

    async def detect(
        self,
        message: str,
        author_name: str,
        skip_trigger: bool = False,
    ) -> LearningResult:
        """
        学習対象を検出。
        Step 1: has_trigger() でキーワードチェック
        Step 2: Haikuでカテゴリ分類
        Step 3: none以外ならHaikuで情報抽出

        Args:
            message: メッセージ本文
            author_name: 投稿者表示名
            skip_trigger: True の場合 Step 1 をスキップ（手動スキャン用）
        """
        # Step 1: 正規表現プレチェック（F-15）
        if not skip_trigger and not self.has_trigger(message):
            return _NO_LEARNING

        # F-04: 切り詰め
        truncated = HaikuContextManager.truncate(message, HAIKU_MAX_MESSAGE_CHARS)

        # Step 2: カテゴリ分類（Haiku）
        try:
            raw_category = await self._llm.call_haiku(
                "learning_category",
                template_vars={
                    "author": author_name[:30],
                    "message": truncated[:300],
                },
            )
        except Exception:
            logger.exception("Learning category Haiku failed")
            return _NO_LEARNING

        cat_result = parse_with_default(
            raw_category, {"category": "none", "confidence": 0.0}
        )
        raw_cat = str(cat_result.get("category", "none"))
        category = _CATEGORY_NORMALIZE.get(raw_cat, "none")
        cat_confidence = float(cat_result.get("confidence", 0.0))

        if category == "none":
            return LearningResult(
                has_learnable_info=False,
                category="none",
                extracted_info=None,
                confidence=cat_confidence,
            )

        # Step 3: 情報抽出（Haiku）
        try:
            raw_extract = await self._llm.call_haiku(
                "learning_extraction",
                template_vars={
                    "message": truncated[:350],
                    "category": category,
                },
            )
        except Exception:
            logger.exception("Learning extraction Haiku failed")
            return LearningResult(
                has_learnable_info=True,
                category=category,
                extracted_info=None,
                confidence=cat_confidence,
            )

        ext_result = parse_with_default(raw_extract, {"extracted": ""})
        extracted = str(ext_result.get("extracted", ""))[:100]

        if not extracted:
            return LearningResult(
                has_learnable_info=True,
                category=category,
                extracted_info=None,
                confidence=cat_confidence,
            )

        logger.info(
            "Learning detected: author=%s, category=%s, info='%s'",
            author_name,
            category,
            extracted[:50],
        )
        return LearningResult(
            has_learnable_info=True,
            category=category,
            extracted_info=extracted,
            confidence=cat_confidence,
        )
