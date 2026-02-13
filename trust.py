"""trust.py — 栞（Shiori）信頼度管理モジュール

メンバーの信頼度スコア（0-100）とレベル（1-5）を管理する。

参照: interface_contract.md §2.3, §6
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("shiori.trust")

# スコア変動表（§6.2）
SCORE_DELTAS = {
    "mention": 3,
    "prediction": 2,
    "answer": 5,
    "self_review": 7,
    "correction": 5,
    "summary_request": 2,
    "explanation": 4,
}

# 30日非活動時の減衰（§6.3）
DECAY_AMOUNT = 5
DECAY_DAYS = 30


class TrustManager:
    """信頼度管理クラス。

    Attributes:
        members: user_id → メンバー情報の辞書
        filepath: データファイルパス
    """

    def __init__(self):
        self.members: dict[int, dict] = {}
        self.filepath = "data/members.md"

    async def load(self, filepath: str = "data/members.md") -> None:
        """起動時にメンバー台帳を読み込む。

        Args:
            filepath: メンバー台帳ファイルパス
        """
        self.filepath = filepath
        path = Path(filepath)

        if not path.exists():
            logger.info(f"Members file not found: {filepath}, starting fresh")
            self.members = {}
            return

        try:
            content = path.read_text(encoding="utf-8")
            self.members = self._parse_members_md(content)
            logger.info(f"Loaded {len(self.members)} members from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load members: {e}")
            self.members = {}

    def _parse_members_md(self, content: str) -> dict[int, dict]:
        """members.mdをパースしてメンバー辞書を返す。"""
        members = {}

        # 各メンバーブロックをパース
        # フォーマット例:
        # ## user_id: 123456789
        # - display_name: Rom🧄
        # - score: 75
        # - last_active: 2025-01-15
        # - join_date: 2024-06-01

        pattern = r"## user_id: (\d+)\n((?:- .+\n?)+)"
        matches = re.findall(pattern, content)

        for user_id_str, block in matches:
            user_id = int(user_id_str)
            member = {"user_id": user_id}

            for line in block.strip().split("\n"):
                if line.startswith("- "):
                    key_val = line[2:].split(": ", 1)
                    if len(key_val) == 2:
                        key, val = key_val
                        if key == "score":
                            member[key] = int(val)
                        else:
                            member[key] = val

            members[user_id] = member

        return members

    async def record_interaction(
        self,
        user_id: int,
        action: str,
    ) -> dict:
        """インタラクションを記録し、信頼度を更新する。

        Args:
            user_id: Discord user ID
            action: アクション名（"mention", "prediction"等）

        Returns:
            dict: {"old_score": int, "new_score": int,
                   "old_level": int, "new_level": int, "delta": int}
        """
        # 新規メンバーの場合は初期化
        if user_id not in self.members:
            self.members[user_id] = {
                "user_id": user_id,
                "display_name": f"Member#{user_id % 10000}",
                "score": 0,
                "last_active": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "join_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }

        member = self.members[user_id]
        old_score = member.get("score", 0)
        old_level = self._calculate_level(old_score)

        # スコア変動
        delta = SCORE_DELTAS.get(action, 0)
        new_score = min(100, old_score + delta)  # 上限100
        new_level = self._calculate_level(new_score)

        # 更新
        member["score"] = new_score
        member["last_active"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logger.debug(
            f"[record_interaction] user={user_id}, action={action}, "
            f"score: {old_score} -> {new_score}, level: {old_level} -> {new_level}"
        )

        return {
            "old_score": old_score,
            "new_score": new_score,
            "old_level": old_level,
            "new_level": new_level,
            "delta": delta,
        }

    async def apply_decay(self, user_id: int) -> None:
        """30日非活動時の-5減衰を適用する（§6.3）。

        Args:
            user_id: Discord user ID
        """
        if user_id not in self.members:
            return

        member = self.members[user_id]
        last_active_str = member.get("last_active")

        if not last_active_str:
            return

        try:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d")
            last_active = last_active.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)

            if now - last_active > timedelta(days=DECAY_DAYS):
                old_score = member.get("score", 0)
                new_score = max(0, old_score - DECAY_AMOUNT)  # 下限0
                member["score"] = new_score
                logger.info(
                    f"[apply_decay] user={user_id}, "
                    f"score: {old_score} -> {new_score}"
                )
        except ValueError as e:
            logger.warning(f"[apply_decay] Invalid date format: {e}")

    def get_trust_level(self, user_id: int) -> int:
        """現在の信頼度レベル（1-5）を返す。

        未知ユーザーは1を返す。同期メソッド。

        Args:
            user_id: Discord user ID

        Returns:
            int: 信頼度レベル（1-5）
        """
        if user_id not in self.members:
            return 1

        score = self.members[user_id].get("score", 0)
        return self._calculate_level(score)

    def get_trust_score(self, user_id: int) -> int:
        """現在の信頼度スコア（0-100）を返す。

        未知ユーザーは0を返す。同期メソッド。

        Args:
            user_id: Discord user ID

        Returns:
            int: 信頼度スコア（0-100）
        """
        if user_id not in self.members:
            return 0

        return self.members[user_id].get("score", 0)

    def _calculate_level(self, score: int) -> int:
        """スコアからレベルを算出する（§6.1）。

        Args:
            score: 信頼度スコア（0-100）

        Returns:
            int: 信頼度レベル（1-5）
        """
        if score >= 100:
            return 5
        if score >= 80:
            return 4
        if score >= 50:
            return 3
        if score >= 20:
            return 2
        return 1

    async def anonymize_member(self, user_id: int) -> str:
        """離脱メンバーの匿名化（Q26: B案）。

        Args:
            user_id: Discord user ID

        Returns:
            str: 匿名化後の名前（'元メンバー#NNN'）
        """
        anon_name = f"元メンバー#{user_id % 1000:03d}"

        if user_id in self.members:
            self.members[user_id]["display_name"] = anon_name
            self.members[user_id]["anonymized"] = "true"
            logger.info(f"[anonymize_member] user={user_id} -> {anon_name}")

        return anon_name

    async def save(self) -> None:
        """members.md にメンバー台帳を書き出す。"""
        path = Path(self.filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# メンバー台帳\n"]

        for user_id, member in sorted(self.members.items()):
            lines.append(f"## user_id: {user_id}")
            for key, val in member.items():
                if key != "user_id":
                    lines.append(f"- {key}: {val}")
            lines.append("")

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        logger.info(f"Saved {len(self.members)} members to {self.filepath}")

    def update_display_name(self, user_id: int, display_name: str) -> None:
        """メンバーの表示名を更新する。

        Args:
            user_id: Discord user ID
            display_name: 新しい表示名
        """
        if user_id in self.members:
            self.members[user_id]["display_name"] = display_name
        else:
            self.members[user_id] = {
                "user_id": user_id,
                "display_name": display_name,
                "score": 0,
                "last_active": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "join_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }

    def get_inactive_members(self, days: int = 30) -> list[dict]:
        """指定日数以上非活動のメンバーリストを返す。

        Args:
            days: 非活動日数の閾値

        Returns:
            list[dict]: 非活動メンバーのリスト
        """
        inactive = []
        now = datetime.now(timezone.utc)
        threshold = timedelta(days=days)

        for user_id, member in self.members.items():
            last_active_str = member.get("last_active")
            if not last_active_str:
                continue

            try:
                last_active = datetime.strptime(last_active_str, "%Y-%m-%d")
                last_active = last_active.replace(tzinfo=timezone.utc)

                if now - last_active > threshold:
                    inactive.append(member)
            except ValueError:
                continue

        return inactive
