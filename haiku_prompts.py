"""
haiku_prompts.py - Haikuプロンプト管理モジュール（v5.3拡張版）

Shiori v5.3 - §6.3 プロファイル照合プロンプト新設
Interface Contract: §12.6.5 (HaikuPromptRegistry)
Error Pattern: F-04 (切り詰め), F-05 (1ステップ1責務), F-06 (safe_parse_json)

v5.2 → v5.3 差分:
    - mention_profile_update プロンプト新設（§6.3）
    - HaikuPromptRegistry に profile_update を追加登録
    - safe_parse_json() / parse_with_default() をモジュール内に配置

既存プロンプト（v5.2継続）:
    - cfr_relevance_check: CFR関連性判定
    - learning_category: 学習カテゴリ分類
    - learning_extraction: 学習情報抽出
    - response_type_classification: 応答タイプ分類
    - question_options: 質問選択肢生成
    - casual_response: 雑談応答
    - cfr_response: CFR応答
    - brief_proposal: 簡易提案生成
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


# ===== JSON安全パース（F-06対策） =====

def safe_parse_json(text: str) -> dict | None:
    """
    Haikuの出力をJSONとしてパースする。

    - コードブロック (```json ... ```) を除去
    - 前後の余分なテキストを除去
    - パース失敗時は None を返す

    Args:
        text: Haiku出力テキスト

    Returns:
        dict: パース結果
        None: パース失敗
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


def parse_with_default(text: str, default: dict) -> dict:
    """パース失敗時はデフォルト値を返す（F-06対策）。

    Args:
        text: Haiku出力テキスト
        default: パース失敗時のデフォルト値

    Returns:
        dict: パース結果またはデフォルト値
    """
    result = safe_parse_json(text)
    return result if result is not None else default


# ===== プロンプト定義 =====

@dataclass
class HaikuPrompt:
    """Haikuプロンプト定義

    Attributes:
        id: プロンプトID（一意キー）
        system: システムプロンプト
        user_template: ユーザープロンプトテンプレート（{変数}形式）
        max_tokens: 最大出力トークン数
        output_type: 出力形式（"json" or "text"）
    """
    id: str
    system: str
    user_template: str
    max_tokens: int
    output_type: Literal["json", "text"]


class HaikuPromptRegistry:
    """プロンプトレジストリ

    Public API:
        - register(prompt) -> None
        - get(prompt_id) -> HaikuPrompt
        - list_ids() -> list[str]
    """

    _prompts: dict[str, HaikuPrompt] = {}

    @classmethod
    def register(cls, prompt: HaikuPrompt) -> None:
        """プロンプトを登録する。

        Args:
            prompt: HaikuPrompt インスタンス
        """
        cls._prompts[prompt.id] = prompt

    @classmethod
    def get(cls, prompt_id: str) -> HaikuPrompt:
        """IDでプロンプトを取得する。

        Args:
            prompt_id: プロンプトID

        Returns:
            HaikuPrompt: プロンプト定義

        Raises:
            KeyError: 未登録のIDの場合
        """
        if prompt_id not in cls._prompts:
            raise KeyError(f"Unknown prompt: {prompt_id}")
        return cls._prompts[prompt_id]

    @classmethod
    def list_ids(cls) -> list[str]:
        """登録済みプロンプトIDの一覧を返す。"""
        return list(cls._prompts.keys())


# ===== v5.2 既存プロンプト登録 =====

HaikuPromptRegistry.register(HaikuPrompt(
    id="cfr_relevance_check",
    system="発言が直前の栞の発言への反応か判定。JSON出力のみ。",
    user_template="栞: {shiori_summary}\n対象: {target_message}",
    max_tokens=100,
    output_type="json",
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="learning_category",
    system=(
        "あなたはDiscordコミュニティのメンバー分析AIです。"
        "発言から、そのメンバーについて記録・記憶すべき情報があるか分類してください。"
        "技術や未来予測についての意見・スタンスも重要な記録対象です。"
        "JSON出力のみ。"
    ),
    user_template=(
        "{author}の発言: {message}\n\n"
        "以下から1つ選んでください:\n"
        "- opinion: 意見・見解・予測スタンスの表明（「〜と思う」「〜は楽観的」「AGIは2030年」等）\n"
        "- interest: 関心・興味の表明（「最近〜にハマっている」「〜を試している」等）\n"
        "- personal: 個人情報の開示（仕事・生活・経歴・スキル等）\n"
        "- expertise: 専門知識・技術的知見の共有（詳しい解説、独自分析等）\n"
        "- stance: 立場の変化（「前は〜だったが今は〜」等）\n"
        "- none: 上記に該当しない（リンク共有のみ、相槌、短い反応等）\n\n"
        '出力例: {{"category": "opinion", "confidence": 0.8}}'
    ),
    max_tokens=50,
    output_type="json",
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="learning_extraction",
    system=(
        "メンバーの発言から、そのメンバーについて覚えておくべき情報を"
        "1文（50文字以内）で簡潔に抽出してください。"
        "主語は省略し「〜と考えている」「〜に詳しい」「〜を使っている」等の形式で。"
        "JSON出力のみ。"
    ),
    user_template=(
        "発言: {message}\n"
        "カテゴリ: {category}\n\n"
        '出力例: {{"extracted": "AGIの実現時期は2030年頃と予測している"}}'
    ),
    max_tokens=100,
    output_type="json",
))

# 手動スキャン用: 分類+抽出を1回のコールに統合
HaikuPromptRegistry.register(HaikuPrompt(
    id="learning_direct_extract",
    system=(
        "あなたはDiscordコミュニティのメンバー記録係です。\n"
        "発言から、このメンバーについて覚えておくと有用な情報を抽出してください。\n"
        "【記録すべきもの】意見、予測、関心事、使っているツール、専門知識、"
        "経験談、仕事の話、趣味、スタンス表明、独自の分析や考察など。\n"
        "【記録しないもの】URLのみの共有、他人の発言の引用のみ、"
        "「草」「わかる」等の短い相槌、ニュースの転載（自分の意見なし）。\n"
        "迷ったら記録する方向で判断してください。\n"
        "JSON出力のみ。"
    ),
    user_template=(
        "{author}の発言:\n{message}\n\n"
        "worthがtrueなら、50文字以内で1文にまとめてください。\n"
        "主語不要。「〜と考えている」「〜に関心がある」「〜を使っている」等の形式。\n\n"
        '記録すべき場合: {{"worth": true, "extracted": "AIアライメント問題に楽観的な立場"}}\n'
        '記録不要の場合: {{"worth": false, "extracted": ""}}'
    ),
    max_tokens=100,
    output_type="json",
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="response_type_classification",
    system="メッセージの種類を分類。JSON出力のみ。",
    user_template=(
        "{message}\n\n"
        "分類: casual(雑談)/question(質問)/prediction(予測)"
        "/member_query(メンバー質問)/summary(要約依頼)/other"
    ),
    max_tokens=50,
    output_type="json",
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="question_options",
    system="話題に関する選択肢を2-3個生成。JSON出力のみ。",
    user_template=(
        "話題: {topic}\n\n"
        '例: ["2030年より前", "2030年以降"] '
        'や ["技術的要因", "社会的要因", "両方"]'
    ),
    max_tokens=80,
    output_type="json",
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="casual_response",
    system="あなたは栞、2045年から来た19歳の記録係。短く自然に返答。敬語ベース。",
    user_template="{author}: {message}\n\n(最大{max_chars}文字で返答)",
    max_tokens=150,
    output_type="text",
))

HaikuPromptRegistry.register(HaikuPrompt(
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
))

HaikuPromptRegistry.register(HaikuPrompt(
    id="brief_proposal",
    system="栞として、専門外でも基本的な提案を1-2文で。「わたしの時代では」調。",
    user_template=(
        "質問: {question}\n"
        "分野: {field}\n\n"
        "(詳しい人への振りは不要、自分の提案のみ)"
    ),
    max_tokens=100,
    output_type="text",
))


# ===== v5.3 新規プロンプト =====

# §6.3 メンション時プロファイル照合（★v5.3新設）
HaikuPromptRegistry.register(HaikuPrompt(
    id="mention_profile_update",
    system=(
        "メンバーの発言と既存プロファイルを比較し、"
        "更新すべき情報を検出。JSON出力のみ。"
    ),
    user_template="既存: {profile_summary}\n発言: {message_content}",
    max_tokens=150,
    output_type="json",
))

# P0P1-v2: ハートリアクション好意判定（★新設）
# Haiku で「栞に好意的か」を判定する。キーワードマッチ廃止。
HaikuPromptRegistry.register(HaikuPrompt(
    id="heart_favorability_check",
    system=(
        "あなたはDiscordボット「栞」への発言を分析します。\n"
        "発言が栞に対して好意的・友好的・感謝・応援・共感を"
        "示しているか判定してください。\n"
        "中立的な質問や事務的な依頼は好意的とはみなしません。\n"
        "JSON出力のみ: {\"is_favorable\": true/false}"
    ),
    user_template="発言: {message_content}",
    max_tokens=30,
    output_type="json",
))


# ===== プロファイル照合ヘルパー関数（§6.3） =====

# デフォルト応答（F-06対策: Haiku失敗時は「何もしない」）
PROFILE_UPDATE_DEFAULT = {
    "has_update": False,
    "updates": [],
}


async def check_profile_update(
    haiku_client,
    profile_summary: str,
    message_content: str,
) -> dict:
    """メンション時にプロファイル変更を検出する（§6.3）。

    F-04対策: 入力を切り詰めてからHaikuに渡す
    F-05対策: プロファイル照合は1ステップ1責務
    F-06対策: パース失敗時はデフォルト値を返す

    Args:
        haiku_client: Haiku APIクライアント（AsyncAnthropic）
        profile_summary: 既存プロファイル要約（200文字以下に切り詰め済みを期待）
        message_content: 今回の発言内容（300文字以下に切り詰め済みを期待）

    Returns:
        dict: {
            "has_update": bool,
            "updates": [
                {
                    "field": "interest" | "personal" | "stance" | "speech_pattern",
                    "old_value": str | null,
                    "new_value": str,
                    "confidence": float  # 0.0-1.0
                }
            ]
        }

    Expected output example:
        {"has_update": true, "updates": [
            {"field": "stance", "old_value": "AGI楽観派",
             "new_value": "AGI慎重派に変化", "confidence": 0.85}
        ]}
    """
    prompt = HaikuPromptRegistry.get("mention_profile_update")

    # F-04: 切り詰め（HaikuContextManager相当）
    trimmed_profile = profile_summary[:200]
    trimmed_message = message_content[:300]

    try:
        response = await haiku_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=prompt.max_tokens,
            system=prompt.system,
            messages=[{
                "role": "user",
                "content": prompt.user_template.format(
                    profile_summary=trimmed_profile,
                    message_content=trimmed_message,
                ),
            }],
        )
        raw_text = response.content[0].text
        result = parse_with_default(raw_text, PROFILE_UPDATE_DEFAULT)

        # 信頼度フィルタ: confidence 0.7未満の更新を除外
        if result.get("updates"):
            result["updates"] = [
                u for u in result["updates"]
                if isinstance(u, dict) and u.get("confidence", 0) >= 0.7
            ]
            result["has_update"] = len(result["updates"]) > 0

        return result

    except Exception as e:
        logger.error(f"[ProfileUpdate] Haiku call failed: {e}")
        return PROFILE_UPDATE_DEFAULT
