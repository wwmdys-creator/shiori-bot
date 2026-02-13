"""nudge.py — 栞（Shiori）低活動メンバーナッジモジュール

30日以上非活動のメンバーに対し、話題に関連する過去発言を根拠に
さりげない言及を生成する。T8テンプレートでLLMを使用。

COMMON_MISTAKES §15: build_nudge_hint() は必ず実装すること。
  引数は4つ（current_topic, target_display_name, past_relevant_message, last_active_date）。
COMMON_MISTAKES §10: NudgeManager(llm, member_profile) — 2引数必須。

依存: llm.py, member_profile.py
参照: interface_contract.md §2.7, prompt_templates.md T8
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("shiori.nudge")

JST = timezone(timedelta(hours=9))

# T8 システムプロンプト
T8_SYSTEM_PROMPT = (
    "あなたは栞（Shiori）の思考補助です。\n"
    "会話中にさりげなく低活動メンバーに言及する文を生成します。\n"
    "「呼び戻し」ではなく「思い出した」というニュアンスで、自然に織り込んでください。\n"
    "JSONのみを出力してください。"
)

# T8 ユーザープロンプトテンプレート
T8_USER_TEMPLATE = """以下の情報をもとに、会話の中でさりげなく低活動メンバーに言及する一文を生成してください。

現在の話題: {current_topic}
言及したいメンバー: {target_display_name}
そのメンバーの過去の関連発言: {past_relevant_message}
最終活動日: {last_active_date}

ルール:
1. 栞のキャラクターで書く（19歳の大学生、記録係）
2. 「思い出した」「フィールドノートに書いてあった」等の自然な導入
3. 直接の@メンションは使わない（テキスト表記のみ）
4. 最近見かけないことへの軽い言及を含める
5. 50字以内の1文

以下のJSON形式で回答してください:
{{"nudge_text": "言及文", "connection_type": "topic_match|expertise_match|prediction_related"}}"""

# ナッジ対象の非活動日数閾値
NUDGE_INACTIVITY_DAYS = 30


class NudgeManager:
    """低活動メンバーナッジ管理クラス。

    COMMON_MISTAKES §10: コンストラクタは llm, member_profile の2引数必須。

    Attributes:
        llm: LLMClient インスタンス
        member_profile: MemberProfileManager インスタンス
    """

    def __init__(self, llm, member_profile):
        self.llm = llm
        self.member_profile = member_profile
        logger.info("NudgeManager initialized")

    async def select_nudge_target(
        self,
        current_topic: str,
    ) -> dict | None:
        """ナッジ対象を選定する。

        条件: 30日以上非活動 + 現在の話題に関連する過去発言あり

        Args:
            current_topic: 現在の話題テキスト

        Returns:
            dict | None: {"member": dict, "past_message": str} | None
        """
        inactive_members = self._get_inactive_members()
        if not inactive_members:
            return None

        # 話題との関連度で優先順位をつける
        for member in inactive_members:
            relevant = self.find_relevant_past_message(member, current_topic)
            if relevant:
                return {"member": member, "past_message": relevant}

        return None

    async def build_nudge_hint(
        self,
        current_topic: str,
        target_display_name: str,
        past_relevant_message: str,
        last_active_date: str,
    ) -> dict | None:
        """T8テンプレートでナッジ文案を生成する。

        COMMON_MISTAKES §15: 引数は4つ。

        Args:
            current_topic: 現在の話題テキスト
            target_display_name: ナッジ対象メンバーの表示名
            past_relevant_message: そのメンバーの過去の関連発言
            last_active_date: 最終活動日（YYYY-MM-DD形式）

        Returns:
            dict | None: {"nudge_text": str, "connection_type": str} | None
        """
        user_prompt = T8_USER_TEMPLATE.format(
            current_topic=current_topic,
            target_display_name=target_display_name,
            past_relevant_message=past_relevant_message,
            last_active_date=last_active_date,
        )

        result = await self.llm.call_template(
            template_name="T8",
            system=T8_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=150,
            temperature=0.7,
        )

        if result is None:
            logger.warning("T8 nudge hint generation failed")
            return None

        nudge_text = result.get("nudge_text", "")
        if not nudge_text:
            return None

        return {
            "nudge_text": nudge_text,
            "connection_type": result.get("connection_type", "topic_match"),
        }

    def find_relevant_past_message(
        self,
        member: dict,
        current_topic: str,
    ) -> str | None:
        """メンバーの過去発言から現在の話題に関連するものを検索する。

        Args:
            member: メンバープロファイル辞書
            current_topic: 現在の話題テキスト

        Returns:
            str | None: 関連する過去発言。なければNone。
        """
        # キーワードベースの簡易マッチング
        topic_lower = current_topic.lower()

        # メンバーの専門領域をキーワードとして使用
        expertise = member.get("expertise", "")
        if not expertise:
            return None

        expertise_keywords = [
            kw.strip().lower()
            for kw in expertise.replace("、", ",").split(",")
            if kw.strip()
        ]

        # 話題に専門領域のキーワードが含まれているか
        for kw in expertise_keywords:
            if kw in topic_lower:
                notes = member.get("notes", "")
                prediction_topics = member.get("prediction_topics", "")
                past_info = notes or prediction_topics or expertise
                return f"「{past_info}」に関する発言（{member.get('display_name', '')}の専門分野）"

        return None

    def _get_inactive_members(self) -> list[dict]:
        """30日以上非活動のメンバーリストを返す。"""
        now = datetime.now(JST)
        inactive = []

        for username, profile in self.member_profile.profiles.items():
            last_active = profile.get("last_active", "")
            if not last_active:
                continue

            try:
                last_date = datetime.strptime(last_active, "%Y-%m-%d").replace(tzinfo=JST)
                days_inactive = (now - last_date).days
            except ValueError:
                continue

            if days_inactive >= NUDGE_INACTIVITY_DAYS:
                profile_copy = dict(profile)
                profile_copy["days_inactive"] = days_inactive
                inactive.append(profile_copy)

        # 非活動日数が長い順にソート
        inactive.sort(key=lambda m: m.get("days_inactive", 0), reverse=True)
        return inactive
