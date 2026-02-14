"""
📎 栞（Shiori）v5.2 — メンバープロファイル管理
Shiori_v5_2_Interface_Contract.md §5.2 に準拠

members_extended.md を読み書きし、動的メモを追加/削除する。
"""

import logging
import os
import re
from datetime import datetime, timezone

from config import MEMBERS_EXTENDED_FILE, HAIKU_MAX_CONTEXT_CHARS

logger = logging.getLogger("shiori.member_profile")


class MemberProfileManager:
    """メンバープロファイル管理"""

    def __init__(self) -> None:
        self._members: dict[str, dict] = {}
        # key: user_id, value: profile dict
        self._raw_content: str = ""

    async def load(self) -> None:
        """members_extended.md を読み込み"""
        if not os.path.exists(MEMBERS_EXTENDED_FILE):
            logger.warning("Members file not found: %s", MEMBERS_EXTENDED_FILE)
            return
        with open(MEMBERS_EXTENDED_FILE, "r", encoding="utf-8") as f:
            self._raw_content = f.read()
        self._parse_members()
        logger.info("Loaded %d member profiles", len(self._members))

    async def save(self) -> None:
        """members_extended.md に書き出し"""
        content = self._serialize_members()
        os.makedirs(os.path.dirname(MEMBERS_EXTENDED_FILE), exist_ok=True)
        with open(MEMBERS_EXTENDED_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved %d member profiles", len(self._members))

    def find_member_by_name(self, name: str) -> dict | None:
        """
        メンバーを名前で検索（部分一致）。
        display_name, username のいずれかに部分一致すれば返す。
        """
        name_lower = name.lower()
        for uid, profile in self._members.items():
            display = profile.get("display_name", "").lower()
            username = profile.get("username", "").lower()
            if name_lower in display or name_lower in username:
                return profile
        return None

    def get_member_summary(
        self,
        user_id: str,
        max_chars: int = 300,
    ) -> str:
        """
        メンバー情報の要約を取得（Haiku用）。
        ポジション + 関心領域のみ（代表的主張は省略）。
        """
        profile = self._members.get(user_id)
        if not profile:
            return ""
        parts = []
        name = profile.get("display_name", user_id)
        parts.append(name)
        position = profile.get("position", "")
        if position:
            parts.append(f"({position})")
        interests = profile.get("interests", [])
        if interests:
            parts.append(f"関心: {', '.join(interests[:3])}")
        summary = " ".join(parts)
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3] + "..."
        return summary

    async def add_dynamic_memo(
        self,
        user_id: str,
        memo: str,
    ) -> bool:
        """
        動的メモを追加。日付プレフィックス [YYYY-MM-DD] を自動付与。
        """
        profile = self._members.get(user_id)
        if not profile:
            return False
        memo = memo[:100]
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dated_memo = f"[{date_str}] {memo}"
        if "dynamic_memos" not in profile:
            profile["dynamic_memos"] = []
        profile["dynamic_memos"].append(dated_memo)
        logger.info("Dynamic memo added: user=%s, memo='%s'", user_id, dated_memo[:50])
        return True

    async def remove_dynamic_memo(
        self,
        user_id: str,
        keyword: str,
    ) -> bool:
        """キーワードを含む動的メモを削除"""
        profile = self._members.get(user_id)
        if not profile:
            return False
        memos = profile.get("dynamic_memos", [])
        original_count = len(memos)
        profile["dynamic_memos"] = [m for m in memos if keyword not in m]
        removed = original_count - len(profile["dynamic_memos"])
        if removed > 0:
            logger.info(
                "Dynamic memo removed: user=%s, keyword='%s', count=%d",
                user_id,
                keyword,
                removed,
            )
            return True
        return False

    # ── 内部パース ──

    def _parse_members(self) -> None:
        """members_extended.md をパースしてプロファイル辞書に変換"""
        self._members = {}
        # ## で始まるセクションをメンバーとして分割
        sections = re.split(r"\n(?=## )", self._raw_content)
        for section in sections:
            section = section.strip()
            if not section.startswith("## "):
                continue
            profile = self._parse_member_section(section)
            if profile and "user_id" in profile:
                self._members[profile["user_id"]] = profile

    def _parse_member_section(self, section: str) -> dict | None:
        """個別メンバーセクションをパース"""
        lines = section.split("\n")
        if not lines:
            return None
        # ヘッダ行から名前抽出
        header = lines[0].replace("## ", "").strip()

        profile: dict = {
            "display_name": header,
            "username": "",
            "user_id": "",
            "position": "",
            "interests": [],
            "stances": [],
            "dynamic_memos": [],
        }

        current_section = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("### "):
                current_section = stripped.replace("### ", "").strip().lower()
                continue

            if not stripped or stripped.startswith("#"):
                continue

            # キー: 値 形式
            kv_match = re.match(r"[-*]\s*\*?\*?(.+?)\*?\*?\s*[:：]\s*(.+)", stripped)
            if kv_match:
                key = kv_match.group(1).strip().lower()
                value = kv_match.group(2).strip()
                if key in ("username", "ユーザー名"):
                    profile["username"] = value
                elif key in ("user_id", "id"):
                    profile["user_id"] = value
                elif key in ("position", "ポジション"):
                    profile["position"] = value
                elif key in ("関心領域", "interests"):
                    profile["interests"] = [
                        i.strip() for i in value.split(",") if i.strip()
                    ]
                continue

            # 動的メモセクション
            if current_section in ("動的メモ", "dynamic_memos", "dynamic memo"):
                if stripped.startswith("- ") or stripped.startswith("* "):
                    memo = stripped[2:].strip()
                    if memo:
                        profile["dynamic_memos"].append(memo)
                continue

            # スタンスセクション
            if current_section in ("代表的主張", "stances"):
                if stripped.startswith("- ") or stripped.startswith("* "):
                    profile["stances"].append(stripped[2:].strip())

        return profile

    def _serialize_members(self) -> str:
        """プロファイル辞書をmarkdown形式にシリアライズ"""
        parts = ["# メンバープロファイル（拡張）\n"]
        for uid, profile in self._members.items():
            parts.append(f"## {profile.get('display_name', uid)}\n")
            parts.append(f"- **username**: {profile.get('username', '')}")
            parts.append(f"- **user_id**: {uid}")
            parts.append(f"- **position**: {profile.get('position', '')}")
            interests = profile.get("interests", [])
            if interests:
                parts.append(f"- **関心領域**: {', '.join(interests)}")
            stances = profile.get("stances", [])
            if stances:
                parts.append("\n### 代表的主張")
                for s in stances:
                    parts.append(f"- {s}")
            memos = profile.get("dynamic_memos", [])
            if memos:
                parts.append("\n### 動的メモ")
                for m in memos:
                    parts.append(f"- {m}")
            parts.append("")  # 空行
        return "\n".join(parts)
