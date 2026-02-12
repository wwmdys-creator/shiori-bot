"""
nudge.py — 低活動メンバーnudge

応答内でさりげなく低活動メンバーを言及し、コミュニティへの参加を促す。
自発的には投稿しない。メンション応答に織り込む形で発動。
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

from member_profile import MEMBER_PROFILES, MemberProfile

logger = logging.getLogger("shiori.nudge")

# 最後に発言を確認してからこの秒数以上経過したメンバーをnudge候補にする
# デフォルト14日
NUDGE_THRESHOLD_SECONDS = 14 * 24 * 60 * 60

# 同一メンバーへのnudge間隔（最低7日空ける）
NUDGE_COOLDOWN_SECONDS = 7 * 24 * 60 * 60

# nudgeが発動する確率（毎回の応答で）
NUDGE_PROBABILITY = 0.25  # 25%


class NudgeManager:
    """低活動メンバーのnudge管理"""

    def __init__(self) -> None:
        # user_id -> last_seen Unix timestamp
        self._last_seen: dict[str, float] = {}
        # user_id -> last_nudged Unix timestamp
        self._last_nudged: dict[str, float] = {}

    def update_activity(self, user_id: str) -> None:
        """メンバーの最終活動を記録"""
        self._last_seen[user_id] = time.time()

    def get_nudge_candidate(self, exclude_user_id: str = "") -> Optional[str]:
        """
        nudge候補のメンバーを1名返す。該当なしならNone。
        exclude_user_id: 現在の会話相手（nudge対象外）
        """
        if random.random() > NUDGE_PROBABILITY:
            return None

        now = time.time()
        candidates: list[tuple[str, MemberProfile]] = []

        for username, profile in MEMBER_PROFILES.items():
            # 現在の会話相手は除外
            if username == exclude_user_id:
                continue
            # プロファイルが薄いメンバーは除外（nudgeしても効果薄い）
            if not profile.position or profile.position == "メンバー":
                continue

            last_seen = self._last_seen.get(username, 0)
            last_nudged = self._last_nudged.get(username, 0)

            # 閾値チェック: 十分に長く見かけていない
            if last_seen > 0 and (now - last_seen) < NUDGE_THRESHOLD_SECONDS:
                continue

            # クールダウンチェック
            if last_nudged > 0 and (now - last_nudged) < NUDGE_COOLDOWN_SECONDS:
                continue

            candidates.append((username, profile))

        if not candidates:
            return None

        chosen_username, _ = random.choice(candidates)
        self._last_nudged[chosen_username] = now
        logger.info(f"Nudge candidate selected: {chosen_username}")
        return chosen_username

    def generate_nudge_text(self, username: str) -> str:
        """
        nudgeテキストを生成
        
        LLMのコンテキストに追加する指示文を返す。
        LLMがこれを見て自然に会話に織り込む。
        """
        profile = MEMBER_PROFILES.get(username)
        if not profile:
            return ""

        # プロファイル情報から自然な言及パターンを構築
        templates = [
            f"（{username}さん、最近お見かけしませんが、この話題についてご意見があればぜひ……📓）",
            f"この議論、以前{username}さんが{profile.position}としてコメントされていたことを思い出しました",
            f"{username}さんの専門である{profile.expertise}の視点からも聞いてみたいですね",
        ]

        return random.choice(templates)
