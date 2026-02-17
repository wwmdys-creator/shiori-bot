"""trust.py — 栞（Shiori）信頼度管理モジュール

メンバーの信頼度スコア（0-100）とレベル（1-4）を管理する。

v5.2: 基本的なスコア管理・レベル算出・減衰・匿名化
v5.3: 好感度上昇量2倍化（§2）、ハートカラー連動（§4）、
      calculate_score_change() 追加（§12.5.1）、4段階レベル統合（§9.3.2）
v5.3-Phase6: V-01修正 — HEART_THRESHOLDS/TRUST_GAIN_MULTIPLIER を
             config.py からインポートに統一（COMMON_MISTAKES N-04/CS-07）
v5.3-P0: HEART_EMOJIS/get_heart_emoji も config.py に集約。
         ローカル重複定義を削除（N-04: 三重重複解消）。

参照: interface_contract.md §2.3, §6
      Shiori_v5_3_Detailed_Spec §2, §4, §9, §12.5.1
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# P1-1: JST定義 — タイムスタンプ形式統一用
JST = timezone(timedelta(hours=9))

# ⚠️ V-01修正 + P0修正: config.py を単一参照元とする（COMMON_MISTAKES N-04）
# HEART_EMOJIS, get_heart_emoji も config.py に集約済み
from config import (
    HEART_THRESHOLDS,
    TRUST_GAIN_MULTIPLIER,
    get_heart_emoji,
)

logger = logging.getLogger("shiori.trust")

# ============================================================
# 定数
# ============================================================

# スコア変動表（v5.2 §6.2 — 基本値。v5.3では上昇要因に倍率適用）
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

# ===== v5.3 定数（V-01修正後） =====
# ⚠️ TRUST_GAIN_MULTIPLIER — config.py からインポート済み
# ⚠️ HEART_THRESHOLDS      — config.py からインポート済み
# ⚠️ HEART_EMOJIS          — config.py に集約済み（P0修正: ローカル定義削除）
# ⚠️ get_heart_emoji()      — config.py に集約済み（P0修正: ローカル定義削除）


# ============================================================
# モジュールレベル関数（他モジュールからimport可能）
# ============================================================

# P0修正: get_heart_emoji() は config.py からインポート済み。
# 後方互換性のため `from trust import get_heart_emoji` は引き続き動作する
# （config.py からの re-export として機能）。


def calculate_score_change(action: str) -> int:
    """好感度スコアの変動値を計算する（§12.5.1）。

    モジュールレベル関数。TrustManager外からも呼び出し可能。

    Args:
        action: SCORE_DELTAS のキー
            有効値: "mention", "prediction", "answer",
                    "self_review", "correction",
                    "summary_request", "explanation" 等

    Returns:
        int: 変動値
            上昇要因（正の値）: 基本値 × TRUST_GAIN_MULTIPLIER（§2）
            減衰要因（負の値）: 基本値そのまま（倍率適用なし）

    ⚠️ 戻り値をスコアに加算後、0〜100にクランプすること
    ⚠️ action が SCORE_DELTAS に存在しない場合は 0 を返す
    """
    base_delta = SCORE_DELTAS.get(action, 0)

    if base_delta > 0:
        # 上昇要因にのみ倍率適用（§2）
        return base_delta * TRUST_GAIN_MULTIPLIER
    else:
        # 減衰要因はそのまま（倍率適用なし）
        return base_delta


# ============================================================
# TrustManager クラス
# ============================================================

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

        v5.3: calculate_score_change() 経由で倍率適用済みの
        変動値を使用する（§2, §12.5.1）。

        Args:
            user_id: Discord user ID
            action: アクション名（"mention", "prediction"等）

        Returns:
            dict: {"old_score": int, "new_score": int,
                   "old_level": int, "new_level": int, "delta": int}
        """
        if user_id not in self.members:
            self.members[user_id] = {
                "user_id": user_id,
                "display_name": f"Member#{user_id % 10000}",
                "score": 0,
                "last_active": datetime.now(JST).strftime("%Y-%m-%d"),
                "join_date": datetime.now(JST).strftime("%Y-%m-%d"),
            }

        member = self.members[user_id]
        old_score = member.get("score", 0)
        old_level = self._calculate_level(old_score)

        delta = calculate_score_change(action)
        new_score = max(0, min(100, old_score + delta))
        new_level = self._calculate_level(new_score)

        member["score"] = new_score
        member["last_active"] = datetime.now(JST).strftime("%Y-%m-%d")

        logger.debug(
            f"[record_interaction] user={user_id}, action={action}, "
            f"delta={delta} (base={SCORE_DELTAS.get(action, 0)}×"
            f"{TRUST_GAIN_MULTIPLIER if delta > 0 else 1}), "
            f"score: {old_score} -> {new_score}, "
            f"level: {old_level} -> {new_level}"
        )

        return {
            "old_score": old_score,
            "new_score": new_score,
            "old_level": old_level,
            "new_level": new_level,
            "delta": delta,
        }

    async def apply_decay(self, user_id: int) -> dict | None:
        """30日非活動時の-5減衰を適用する（§6.3）。

        v5.3: TRUST_GAIN_MULTIPLIER は減衰には適用しない（§2規定）。

        Args:
            user_id: Discord user ID

        Returns:
            dict | None: 減衰適用時は {"old_score", "new_score"} を返す。
        """
        if user_id not in self.members:
            return None

        member = self.members[user_id]
        last_active_str = member.get("last_active")

        if not last_active_str:
            return None

        try:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d")
            last_active = last_active.replace(tzinfo=JST)
            now = datetime.now(JST)

            if now - last_active > timedelta(days=DECAY_DAYS):
                old_score = member.get("score", 0)
                new_score = max(0, old_score - DECAY_AMOUNT)
                member["score"] = new_score
                logger.info(
                    f"[apply_decay] user={user_id}, "
                    f"score: {old_score} -> {new_score} "
                    f"(decay={DECAY_AMOUNT}, multiplier NOT applied)"
                )
                return {"old_score": old_score, "new_score": new_score}
        except ValueError as e:
            logger.warning(f"[apply_decay] Invalid date format: {e}")

        return None

    def get_trust_level(self, user_id: int) -> int:
        """現在の信頼度レベル（1-4）を返す。"""
        if user_id not in self.members:
            return 1
        score = self.members[user_id].get("score", 0)
        return self._calculate_level(score)

    def get_trust_score(self, user_id: int) -> int:
        """現在の信頼度スコア（0-100）を返す。"""
        if user_id not in self.members:
            return 0
        return self.members[user_id].get("score", 0)

    def get_heart_emoji_for_user(self, user_id: int) -> str:
        """ユーザーIDに対応するハート絵文字を返す（§4.2）。"""
        score = self.get_trust_score(user_id)
        return get_heart_emoji(score)

    def _calculate_level(self, score: int) -> int:
        """スコアからレベルを算出する（v5.3 §4.2, §9.3.2）。

        | Lv | スコア範囲 | ハート |
        |----|-----------|--------|
        |  1 | 0〜19     | 🧡     |
        |  2 | 20〜49    | 💛     |
        |  3 | 50〜79    | 💗     |
        |  4 | 80〜100   | ❤️     |
        """
        for level, (low, high) in HEART_THRESHOLDS.items():
            if low <= score <= high:
                return level
        return 1

    async def anonymize_member(self, user_id: int) -> str:
        """離脱メンバーの匿名化（Q26: B案）。"""
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
        """メンバーの表示名を更新する。"""
        if user_id in self.members:
            self.members[user_id]["display_name"] = display_name
        else:
            self.members[user_id] = {
                "user_id": user_id,
                "display_name": display_name,
                "score": 0,
                "last_active": datetime.now(JST).strftime("%Y-%m-%d"),
                "join_date": datetime.now(JST).strftime("%Y-%m-%d"),
            }

    def get_inactive_members(self, days: int = 30) -> list[dict]:
        """指定日数以上非活動のメンバーリストを返す。"""
        inactive = []
        now = datetime.now(JST)
        threshold = timedelta(days=days)

        for user_id, member in self.members.items():
            last_active_str = member.get("last_active")
            if not last_active_str:
                continue
            try:
                last_active = datetime.strptime(last_active_str, "%Y-%m-%d")
                last_active = last_active.replace(tzinfo=JST)
                if now - last_active > threshold:
                    inactive.append(member)
            except ValueError:
                continue

        return inactive
