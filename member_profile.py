"""
📎 栞（Shiori）— メンバープロファイル管理（v4.1 + v5.2 統合版）

v4.1 互換メソッド:
  - profiles (property)
  - get_profile(user_id)
  - get_community_knowledge_text(compact)
  - get_member_summary_for_highlight(queried_name)

v5.2 追加メソッド:
  - find_member_by_name(name)
  - get_member_summary(user_id, max_chars)
  - add_dynamic_memo(user_id, memo)
  - remove_dynamic_memo(user_id, keyword)

COMMON_MISTAKES §19: パーサーは実際の members_seed.md 形式に準拠:
  ## メンバー: DisplayName
  - **field:** value
"""

import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger("shiori.member_profile")

# ── 定数 ──
# COMMON_MISTAKES §18: Volume マウントパスとリポジトリパスのフォールバック
_VOLUME_PATH = os.environ.get("MEMBERS_FILE", "data/members_seed.md")
_REPO_FALLBACK = "members_seed.md"

# パース正規表現（members_seed.md に明記されたもの）
MEMBER_HEADER = re.compile(r"^## メンバー:\s*(.+)$")
FIELD_PATTERN = re.compile(r"^- \*\*(.+?):\*\*\s*(.+)$")


class MemberProfileManager:
    """メンバープロファイル管理（v4.1 + v5.2 統合）"""

    def __init__(self) -> None:
        self._members: dict[str, dict] = {}
        # key: user_id (Discord Snowflake ID string), value: profile dict
        self._raw_content: str = ""
        self._file_path: str = ""

    # ================================================================
    # 読み込み / 書き出し
    # ================================================================

    async def load(self) -> None:
        """members_seed.md を読み込み"""
        # COMMON_MISTAKES §18: フォールバックチェーン
        for path in [_VOLUME_PATH, _REPO_FALLBACK]:
            if os.path.exists(path):
                self._file_path = path
                break
        else:
            logger.warning("Members file not found: %s / %s", _VOLUME_PATH, _REPO_FALLBACK)
            return

        with open(self._file_path, "r", encoding="utf-8") as f:
            self._raw_content = f.read()
        self._parse_members()
        logger.info("Loaded %d member profiles from %s", len(self._members), self._file_path)

    async def save(self) -> None:
        """members_seed.md に書き出し"""
        if not self._file_path:
            self._file_path = _VOLUME_PATH
        os.makedirs(os.path.dirname(self._file_path) or ".", exist_ok=True)
        content = self._serialize_members()
        with open(self._file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved %d member profiles to %s", len(self._members), self._file_path)

    # ================================================================
    # v4.1 互換メソッド（bot.py から呼ばれる）
    # ================================================================

    @property
    def profiles(self) -> dict[str, dict]:
        """全プロファイル辞書を返す（v4.1互換）"""
        return self._members

    def get_profile(self, user_id: str = "", **kwargs) -> dict | None:
        """
        user_id でプロファイルを取得（v4.1互換）
        bot.py: profile = self.member_profile.get_profile(user_id=user_id)
        """
        # kwargs から user_id を取得（キーワード引数対応）
        uid = user_id or kwargs.get("user_id", "")
        uid = str(uid)
        if uid in self._members:
            return self._members[uid]
        # user_id が "pending" のメンバーは username で逆引き
        for profile in self._members.values():
            if profile.get("username") == uid:
                return profile
        return None

    def get_community_knowledge_text(self, compact: bool = True) -> str:
        """
        全メンバー情報をテキストとして返す（v4.1互換）
        compact=True: 名前 + tier + expertise のみ
        compact=False: 全フィールド
        """
        if not self._members:
            return ""
        parts = []
        for uid, profile in self._members.items():
            name = profile.get("display_name", uid)
            expertise = profile.get("expertise", "")
            if compact:
                # V-02修正: Tier情報をLLMに送信しない（非公開情報漏洩防止）
                parts.append(f"- {name}: {expertise}")
            else:
                lines = [f"## {name}"]
                lines.append(f"- user_id: {uid}")
                # V-02修正: tier行を除去（非公開情報漏洩防止）
                lines.append(f"- expertise: {expertise}")
                position = profile.get("position", "")
                if position:
                    lines.append(f"- ポジション: {position}")
                notes = profile.get("notes", "")
                if notes:
                    lines.append(f"- notes: {notes}")
                protection = profile.get("protection_rule", "")
                if protection and protection != "null":
                    lines.append(f"- protection_rule: {protection}")
                stances = profile.get("stances", [])
                if stances:
                    lines.append("- 代表的主張:")
                    for s in stances:
                        lines.append(f"  - {s}")
                dynamic_memos = profile.get("dynamic_memos", [])
                if dynamic_memos:
                    lines.append("- 動的メモ:")
                    for m in dynamic_memos:
                        lines.append(f"  - {m}")
                parts.append("\n".join(lines))
        separator = "\n" if compact else "\n\n"
        return separator.join(parts)

    def get_member_summary_for_highlight(self, queried_name: str) -> str | None:
        """
        名前で検索し、ハイライト用の詳細サマリーを返す（v4.1互換）
        bot.py: member_summary = self.member_profile.get_member_summary_for_highlight(queried_name)
        """
        profile = self.find_member_by_name(queried_name)
        if not profile:
            return None

        name = profile.get("display_name", "")
        lines = [f"【メンバー情報: {name}】"]
        # V-03修正: Tier行を除去（非公開情報漏洩防止）
        lines.append(f"- 関心領域: {profile.get('expertise', '不明')}")
        notes = profile.get("notes", "")
        if notes:
            lines.append(f"- 特記事項: {notes}")
        protection = profile.get("protection_rule", "")
        if protection and protection != "null":
            lines.append(f"- 保護ルール: {protection}")
        stances = profile.get("stances", [])
        if stances:
            lines.append("- 代表的主張:")
            for s in stances[:3]:
                lines.append(f"  - {s}")
        dynamic_memos = profile.get("dynamic_memos", [])
        if dynamic_memos:
            lines.append("- 動的メモ:")
            for m in dynamic_memos[-5:]:  # 直近5件
                lines.append(f"  - {m}")
        return "\n".join(lines)

    # ================================================================
    # v5.2 メソッド
    # ================================================================

    def find_member_by_name(self, name: str) -> dict | None:
        """
        メンバーを名前で検索（部分一致）。
        display_name, username, header_name のいずれかに部分一致すれば返す。
        COMMON_MISTAKES §20: エイリアス対応（notes 内の旧名も検索）
        """
        name_lower = name.lower()
        for uid, profile in self._members.items():
            display = profile.get("display_name", "").lower()
            username = profile.get("username", "").lower()
            header_name = profile.get("header_name", "").lower()
            notes = profile.get("notes", "").lower()
            if (
                name_lower in display
                or name_lower in username
                or name_lower in header_name
                or name_lower in notes
            ):
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
        profile = self._members.get(str(user_id))
        if not profile:
            return ""
        parts = []
        name = profile.get("display_name", user_id)
        parts.append(name)
        # V-02b修正: Tier情報をLLMに送信しない（非公開情報漏洩防止）
        expertise = profile.get("expertise", "")
        if expertise:
            parts.append(f"関心: {expertise}")
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
        uid = str(user_id)
        profile = self._members.get(uid)
        if not profile:
            return False
        memo = memo[:100]
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dated_memo = f"[{date_str}] {memo}"
        if "dynamic_memos" not in profile:
            profile["dynamic_memos"] = []
        profile["dynamic_memos"].append(dated_memo)
        logger.info("Dynamic memo added: user=%s, memo='%s'", uid, dated_memo[:50])
        return True

    async def remove_dynamic_memo(
        self,
        user_id: str,
        keyword: str,
    ) -> bool:
        """キーワードを含む動的メモを削除"""
        uid = str(user_id)
        profile = self._members.get(uid)
        if not profile:
            return False
        memos = profile.get("dynamic_memos", [])
        original_count = len(memos)
        profile["dynamic_memos"] = [m for m in memos if keyword not in m]
        removed = original_count - len(profile["dynamic_memos"])
        if removed > 0:
            logger.info(
                "Dynamic memo removed: user=%s, keyword='%s', count=%d",
                uid, keyword, removed,
            )
            return True
        return False

    # ================================================================
    # 内部パース（COMMON_MISTAKES §19: 実ファイル形式に準拠）
    # ================================================================

    def _parse_members(self) -> None:
        """
        members_seed.md をパースしてプロファイル辞書に変換。

        実際の形式:
          ## メンバー: DisplayName
          - **user_id:** 1081782858332524645
          - **username:** katsucurry_apple
          ...
          ### 動的メモ
          - [2026-02-14] memo text
        """
        self._members = {}
        # "## メンバー:" で始まるセクションを分割
        sections = re.split(r"\n(?=## メンバー:)", self._raw_content)
        for section in sections:
            section = section.strip()
            if not MEMBER_HEADER.match(section.split("\n")[0] if section else ""):
                continue
            profile = self._parse_member_section(section)
            if profile:
                uid = profile.get("user_id", "")
                if uid and uid != "pending":
                    self._members[uid] = profile
                elif profile.get("username"):
                    # pending の場合は username をキーに
                    self._members[profile["username"]] = profile

    def _parse_member_section(self, section: str) -> dict | None:
        """個別メンバーセクションをパース"""
        lines = section.split("\n")
        if not lines:
            return None

        # ヘッダ行から名前抽出: "## メンバー: DisplayName"
        header_match = MEMBER_HEADER.match(lines[0].strip())
        if not header_match:
            return None
        header_name = header_match.group(1).strip()

        profile: dict = {
            "header_name": header_name,
            "display_name": header_name,
            "username": "",
            "user_id": "",
            "tier": "",
            "expertise": "",
            "trust_score": "0",
            "trust_level": "1",
            "last_active": "",
            "joined_at": "",
            "total_predictions": "0",
            "protection_rule": "",
            "notes": "",
            "stances": [],
            "dynamic_memos": [],
        }

        current_subsection = ""
        for line in lines[1:]:
            stripped = line.strip()

            # サブセクション検出
            if stripped.startswith("### "):
                current_subsection = stripped.replace("### ", "").strip()
                continue

            # 信頼度変動履歴テーブルはスキップ
            if current_subsection == "信頼度変動履歴":
                continue

            # 動的メモセクション
            if current_subsection in ("動的メモ", "dynamic_memos"):
                if stripped.startswith("- ") or stripped.startswith("* "):
                    memo = stripped[2:].strip()
                    if memo:
                        profile["dynamic_memos"].append(memo)
                continue

            # フィールド行: - **field:** value
            field_match = FIELD_PATTERN.match(stripped)
            if field_match:
                key = field_match.group(1).strip()
                value = field_match.group(2).strip()
                if key in profile:
                    profile[key] = value
                continue

        # display_name フィールドが明示されていればそちらを優先
        if profile.get("display_name") == header_name:
            # フィールドから display_name が設定されていればそれを使う
            pass  # すでに FIELD_PATTERN で上書き済み

        return profile

    def _serialize_members(self) -> str:
        """プロファイル辞書をmarkdown形式にシリアライズ"""
        parts = [
            "# 📎 栞（Shiori）メンバー初期シード（members_seed.md）\n",
            "---\n",
        ]
        for uid, profile in self._members.items():
            header_name = profile.get("header_name", profile.get("display_name", uid))
            parts.append(f"## メンバー: {header_name}\n")

            # 固定フィールド順序（元ファイルと一致させる）
            field_order = [
                "user_id", "username", "display_name", "tier",
                "expertise", "trust_score", "trust_level",
                "last_active", "joined_at", "total_predictions",
                "protection_rule", "notes",
            ]
            for field in field_order:
                value = profile.get(field, "")
                if field == "user_id":
                    # 内部キーが username の場合は pending を書く
                    value = value if value else uid
                parts.append(f"- **{field}:** {value}")

            # 信頼度変動履歴（空テーブル維持）
            parts.append("\n### 信頼度変動履歴\n")
            parts.append("| 日時 | 変動 | 理由 | 累計 |")
            parts.append("|------|------|------|------|\n")

            # 動的メモ
            parts.append("### 動的メモ\n")
            memos = profile.get("dynamic_memos", [])
            for m in memos:
                parts.append(f"- {m}")

            parts.append("\n---\n")

        return "\n".join(parts)
