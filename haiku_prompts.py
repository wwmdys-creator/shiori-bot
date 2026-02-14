"""
📎 栞（Shiori）v5.2 — Haikuプロンプト管理
Shiori_v5_2_Haiku_Prompts.md §8, §9 に準拠

F-06: safe_parse_json() で全Haiku JSON出力を安全にパース。
"""

import json
import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class HaikuPrompt:
    """Haikuプロンプト定義"""

    id: str
    system: str
    user_template: str
    max_tokens: int
    output_type: Literal["json", "text"]


class HaikuPromptRegistry:
    """プロンプト管理"""

    _prompts: dict[str, HaikuPrompt] = {}

    @classmethod
    def register(cls, prompt: HaikuPrompt) -> None:
        cls._prompts[prompt.id] = prompt

    @classmethod
    def get(cls, prompt_id: str) -> HaikuPrompt:
        if prompt_id not in cls._prompts:
            raise KeyError(f"Unknown prompt: {prompt_id}")
        return cls._prompts[prompt_id]


# ── JSON安全パース ──


def safe_parse_json(text: str) -> dict | None:
    """
    Haikuの出力をJSONとしてパース。
    - コードブロック (```json ... ```) を除去
    - 前後の余分なテキストを除去
    - パース失敗時は None
    """
    if not text:
        return None
    # コードブロック除去
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    # JSONっぽい部分を抽出
    match = re.search(r"\{[^{}]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def parse_with_default(text: str, default: dict) -> dict:
    """パース失敗時はデフォルト値を返す"""
    result = safe_parse_json(text)
    return result if result is not None else default


# ── プロンプト登録 ──

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="cfr_relevance_check",
        system="発言が直前の栞の発言への反応か判定。JSON出力のみ。",
        user_template="栞: {shiori_summary}\n対象: {target_message}",
        max_tokens=100,
        output_type="json",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="learning_category",
        system="発言を分類。JSON出力のみ。",
        user_template=(
            "{author}: {message}\n\n"
            "分類: interest(関心変化)/personal(個人情報)"
            "/stance(立場変化)/speech(口癖)/none"
        ),
        max_tokens=50,
        output_type="json",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="learning_extraction",
        system="記録すべき情報を1文で抽出。JSON出力のみ。",
        user_template="発言: {message}\nカテゴリ: {category}",
        max_tokens=80,
        output_type="json",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="casual_response",
        system="あなたは栞、2045年から来た19歳の記録係。短く自然に返答。敬語ベース。",
        user_template="{author}: {message}\n\n(最大{max_chars}文字で返答)",
        max_tokens=150,
        output_type="text",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="cfr_response",
        system="あなたは栞。直前の自分の発言に関連するコメントへ自然に返答。短く。敬語。",
        user_template=(
            "[栞の直前発言]: {shiori_summary}\n"
            "[相手の反応]: {target_message}\n"
            "[反応タイプ]: {reaction_type}\n\n"
            "(自然に返答、最大100文字)"
        ),
        max_tokens=100,
        output_type="text",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="response_type_classification",
        system="メッセージの種類を分類。JSON出力のみ。",
        user_template=(
            "{message}\n\n"
            "分類: casual(雑談)/question(質問)/prediction(予測)"
            "/member_query(メンバー質問)/summary(要約依頼)/other"
        ),
        max_tokens=50,
        output_type="json",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="question_options",
        system="話題に関する選択肢を2-3個生成。JSON出力のみ。",
        user_template=(
            '話題: {topic}\n\n'
            '例: ["2030年より前", "2030年以降"] や ["技術的要因", "社会的要因", "両方"]'
        ),
        max_tokens=80,
        output_type="json",
    )
)

HaikuPromptRegistry.register(
    HaikuPrompt(
        id="brief_proposal",
        system="栞として、専門外でも基本的な提案を1-2文で。「わたしの時代では」調。",
        user_template=(
            "質問: {question}\n分野: {field}\n\n"
            "(詳しい人への振りは不要、自分の提案のみ)"
        ),
        max_tokens=100,
        output_type="text",
    )
)
