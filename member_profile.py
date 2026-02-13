"""member_profile.py — 栞（Shiori）メンバープロファイル管理モジュール

メンバープロファイル、コミュニティ用語、コンセンサス情報を管理する。

COMMON_MISTAKES §10: 旧名 profiles.py → 現名 member_profile.py
`from profiles import` とするとImportError。

参照: interface_contract.md §2.12
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("shiori.member_profile")


class MemberProfileManager:
    """メンバープロファイル管理クラス。

    3つのデータファイルを統合管理:
    - data/members_extended.md: メンバープロファイル
    - data/community_lexicon.md: コミュニティ用語辞典
    - data/consensus_tracker.md: コンセンサストラッカー

    Attributes:
        profiles: username → プロファイル辞書
        user_id_map: user_id → username のマッピング
        lexicon: 用語名 → 定義辞書
        consensus: トピック → コンセンサス情報辞書
    """

    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.user_id_map: dict[str, str] = {}  # user_id (str) → display_name
        self.lexicon: dict[str, dict] = {}
        self.consensus: dict[str, dict] = {}

    async def load(self) -> None:
        """起動時に3ファイルをフルロード。"""
        await self._load_profiles()
        await self._load_lexicon()
        await self._load_consensus()

    async def _load_profiles(self) -> None:
        """members_extended.md を読み込む。"""
        import os
        # デバッグ: 現在のディレクトリとファイル一覧を出力
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Files in current directory: {os.listdir('.')}")
        if os.path.exists('data'):
            logger.info(f"Files in data/: {os.listdir('data')}")
        else:
            logger.warning("data/ directory does not exist!")
        
        filepath = Path("data/members_extended.md")

        if not filepath.exists():
            logger.warning("members_extended.md not found, using empty profiles")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.profiles = self._parse_profiles(content)
            self._build_user_id_map()

            if not self.profiles:
                logger.warning("No profiles loaded (parse returned empty)")
            else:
                logger.info(f"Loaded {len(self.profiles)} profiles")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")

    def _parse_profiles(self, content: str) -> dict[str, dict]:
        """members_extended.md をパースする。
        
        実際のフォーマット:
        ### Rom🧄（katsucurry_apple）
        - **user_id**: katsucurry_apple
        - **表示名**: Rom🧄
        - **ポジション**: ...
        - **関心領域**: ...
        """
        profiles = {}

        # Tierセクションの検出パターン
        tier_pattern = r"## Tier-([ABC])"

        # メンバーブロックのパターン（### から次の ### または ## まで）
        # ### Name（username）形式
        member_pattern = r"### ([^（\n]+)(?:（([^）]+)）)?\n([\s\S]*?)(?=\n### |\n## |$)"

        # 各メンバーブロックを抽出
        for match in re.finditer(member_pattern, content):
            display_name = match.group(1).strip()
            username = match.group(2).strip() if match.group(2) else display_name
            block = match.group(3)

            # 「動的メモ」や「ファイル仕様」等はスキップ
            if display_name in ("動的メモ", "ファイル仕様", "使用ガイド", "合意度スケール",
                                "サーバー全体の傾向", "ポジションマップ", "構造的対立軸",
                                "シフト履歴", "未決着論点"):
                continue
            # 不完全なパース結果をスキップ
            if "セクション" in display_name or "`" in display_name:
                continue

            profile = {
                "display_name": display_name,
                "username": username,
            }

            # Tierの判定（ブロック位置からセクションを特定）
            block_start = match.start()
            tier_matches = list(re.finditer(tier_pattern, content[:block_start]))
            if tier_matches:
                profile["tier"] = tier_matches[-1].group(1)

            # フィールドのパース（- **key**: value 形式）
            field_pattern = r"- \*\*([^*]+)\*\*:\s*(.+)"
            for field_match in re.finditer(field_pattern, block):
                key = field_match.group(1).strip()
                value = field_match.group(2).strip()

                # キー名の正規化
                key_map = {
                    "user_id": "user_id",
                    "表示名": "display_name",
                    "投稿数": "post_count",
                    "ポジション": "position",
                    "思想的特徴": "ideology",
                    "関心領域": "expertise",
                    "発言スタイル": "style",
                    "栞の役割保護": "shiori_protection",
                    "チャンネル横断": "channels",
                }
                normalized_key = key_map.get(key, key)
                profile[normalized_key] = value

            # prediction_topics は expertise から推測
            if "expertise" in profile:
                profile["prediction_topics"] = profile["expertise"]

            # 有効なプロファイルのみ追加（最低限 user_id がある）
            if profile.get("user_id") or username:
                profiles[username] = profile

        return profiles

    def _build_user_id_map(self) -> None:
        """user_id → display_name のマッピングを構築。"""
        self.user_id_map = {}
        for username, profile in self.profiles.items():
            user_id = profile.get("user_id", username)
            self.user_id_map[user_id] = profile.get("display_name", username)

    async def _load_lexicon(self) -> None:
        """community_lexicon.md を読み込む。"""
        filepath = Path("data/community_lexicon.md")

        if not filepath.exists():
            logger.info("community_lexicon.md not found, using empty lexicon")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.lexicon = self._parse_lexicon(content)
            logger.info(f"Loaded {len(self.lexicon)} terms")
        except Exception as e:
            logger.error(f"Failed to load lexicon: {e}")

    def _parse_lexicon(self, content: str) -> dict[str, dict]:
        """community_lexicon.md をパースする。
        
        実際のフォーマット（テーブル形式）:
        | 用語 | 英語 / 原語 | 意味 | 主な使用者 |
        |------|-------------|------|-----------|
        | AGI | Artificial General Intelligence | 汎用人工知能 | 全員 |
        """
        lexicon = {}

        # テーブル行をパース
        # | 用語 | 英語 | 意味 | 使用者 | のパターン
        table_row_pattern = r"\| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|"

        for match in re.finditer(table_row_pattern, content):
            term = match.group(1).strip()
            english = match.group(2).strip()
            definition = match.group(3).strip()
            users = match.group(4).strip()

            # ヘッダー行や区切り行をスキップ
            if term in ("用語", "表現", "---", "------") or term.startswith("-"):
                continue
            if english.startswith("-"):
                continue

            lexicon[term] = {
                "term": term,
                "english": english,
                "definition": definition,
                "users": users,
            }

        return lexicon

    async def _load_consensus(self) -> None:
        """consensus_tracker.md を読み込む。"""
        filepath = Path("data/consensus_tracker.md")

        if not filepath.exists():
            logger.info("consensus_tracker.md not found, using empty consensus")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.consensus = self._parse_consensus(content)
            logger.info(f"Loaded {len(self.consensus)} consensus topics")
        except Exception as e:
            logger.error(f"Failed to load consensus: {e}")

    def _parse_consensus(self, content: str) -> dict[str, dict]:
        """consensus_tracker.md をパースする。
        
        実際のフォーマット:
        ## Theme 1: AGIタイムライン（AGI Timeline）
        **合意度**: ★★★☆☆（方向性は一致、時期は分岐）
        ### サーバー全体の傾向
        - **合意点**: ...
        - **論争点**: ...
        """
        consensus = {}

        # Theme セクションを抽出
        theme_pattern = r"## Theme \d+: ([^（\n]+)(?:（([^）]+)）)?\n([\s\S]*?)(?=\n## Theme |\n## [^T]|$)"

        for match in re.finditer(theme_pattern, content):
            topic_ja = match.group(1).strip()
            topic_en = match.group(2).strip() if match.group(2) else ""
            block = match.group(3)

            entry = {
                "topic": topic_ja,
                "topic_en": topic_en,
            }

            # 合意度を抽出
            agreement_match = re.search(r"\*\*合意度\*\*:\s*([★☆]+)", block)
            if agreement_match:
                entry["agreement_level"] = agreement_match.group(1)

            # 合意点を抽出
            consensus_match = re.search(r"- \*\*合意点\*\*:\s*(.+)", block)
            if consensus_match:
                entry["majority"] = consensus_match.group(1).strip()

            # 論争点を抽出
            dispute_match = re.search(r"- \*\*論争点\*\*:\s*(.+)", block)
            if dispute_match:
                entry["disputes"] = dispute_match.group(1).strip()

            # ポジションマップからメンバーごとの意見を抽出
            positions = []
            position_pattern = r"\| ([^|]+) \| ([^|]+) \| ([^|]+) \|"
            for pos_match in re.finditer(position_pattern, block):
                member = pos_match.group(1).strip()
                prediction = pos_match.group(2).strip()
                reason = pos_match.group(3).strip()

                if member not in ("メンバー", "---", "------") and not member.startswith("-"):
                    positions.append({
                        "member": member,
                        "prediction": prediction,
                        "reason": reason,
                    })

            if positions:
                entry["positions"] = positions

            # 未決着論点を抽出
            unresolved = []
            unresolved_section = re.search(r"### 未決着論点\n([\s\S]*?)(?=\n### |\n## |$)", block)
            if unresolved_section:
                for line in unresolved_section.group(1).split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        unresolved.append(line[2:])
            if unresolved:
                entry["unresolved"] = unresolved

            consensus[topic_ja] = entry

        return consensus

    def get_profile(
        self,
        user_id: int | str = None,
        username: str = None,
    ) -> dict | None:
        """メンバープロファイルを返す。

        user_idまたはusernameで検索。同期メソッド。

        Args:
            user_id: Discord user ID または username文字列
            username: Discord username

        Returns:
            dict | None: プロファイル情報。該当なしならNone。
        """
        # user_id が文字列の場合（実際のフォーマットでは username が user_id として記録）
        if user_id:
            user_id_str = str(user_id)
            if user_id_str in self.user_id_map:
                display_name = self.user_id_map[user_id_str]
                # display_nameからプロファイルを検索
                for uname, profile in self.profiles.items():
                    if profile.get("display_name") == display_name:
                        return profile

            # usernameとして検索
            if user_id_str in self.profiles:
                return self.profiles[user_id_str]

        if username:
            if username in self.profiles:
                return self.profiles[username]
            # display_nameで検索
            for uname, profile in self.profiles.items():
                if profile.get("display_name") == username:
                    return profile

        return None

    def get_profile_summary(self, user_id: int | str) -> str:
        """コンテキスト注入用の要約プロファイルを返す（200字以内）。

        COMMON_MISTAKES §10: 引数は user_id の1つのみ。

        同期メソッド。

        Args:
            user_id: Discord user ID

        Returns:
            str: 要約プロファイル
        """
        profile = self.get_profile(user_id=user_id)

        if not profile:
            return "（プロファイル情報なし）"

        parts = []

        name = profile.get("display_name", "不明")
        parts.append(f"{name}さん")

        tier = profile.get("tier")
        if tier:
            parts.append(f"(Tier {tier})")

        expertise = profile.get("expertise")
        if expertise:
            # 長すぎる場合は省略
            if len(expertise) > 50:
                expertise = expertise[:47] + "..."
            parts.append(f"専門: {expertise}")

        position = profile.get("position")
        if position:
            if len(position) > 50:
                position = position[:47] + "..."
            parts.append(f"役割: {position}")

        summary = " / ".join(parts)

        # 200字制限
        if len(summary) > 200:
            summary = summary[:197] + "..."

        return summary

    def get_tier_ab_summaries(self) -> str:
        """Tier A-Bメンバーの要約プロファイル一覧を返す（常時ロード用）。

        同期メソッド。

        Returns:
            str: Tier A-Bメンバーの要約一覧
        """
        tier_ab = []

        for username, profile in self.profiles.items():
            tier = profile.get("tier", "")
            if tier in ("A", "B"):
                summary = self.get_profile_summary(profile.get("user_id", username))
                tier_ab.append(summary)

        if not tier_ab:
            return "（Tier A-Bメンバーなし）"

        return "\n".join(tier_ab)

    def get_community_knowledge_text(self, compact: bool = False) -> str:
        """コミュニティ知識をテキスト形式で返す。

        Args:
            compact: コンパクト形式にするか

        Returns:
            str: コミュニティ知識テキスト
        """
        lines = []

        # Tier A-Bメンバー
        tier_ab = self.get_tier_ab_summaries()
        if tier_ab and tier_ab != "（Tier A-Bメンバーなし）":
            lines.append("【主要メンバー】")
            lines.append(tier_ab)
            lines.append("")

        # コンセンサス情報（compact時は省略）
        if not compact and self.consensus:
            lines.append("【サーバーのコンセンサス】")
            for topic, info in list(self.consensus.items())[:3]:
                majority = info.get("majority", "不明")
                lines.append(f"- {topic}: {majority}")
            lines.append("")

        return "\n".join(lines) if lines else "（コミュニティ知識なし）"

    def lookup_term(self, term: str) -> dict | None:
        """community_lexicon.md から用語を検索する。

        同期メソッド。

        Args:
            term: 検索する用語

        Returns:
            dict | None: {"term": str, "definition": str, ...}
        """
        # 完全一致
        if term in self.lexicon:
            return self.lexicon[term]

        # 部分一致
        term_lower = term.lower()
        for key, val in self.lexicon.items():
            if term_lower in key.lower():
                return val

        return None

    def lookup_consensus(self, topic: str) -> dict | None:
        """consensus_tracker.md からトピックのコンセンサスを検索する。

        同期メソッド。

        Args:
            topic: 検索するトピック

        Returns:
            dict | None: {"topic": str, "majority": str, "positions": list, ...}
        """
        # 完全一致
        if topic in self.consensus:
            return self.consensus[topic]

        # 部分一致
        topic_lower = topic.lower()
        for key, val in self.consensus.items():
            if topic_lower in key.lower():
                return val

        return None

    def get_display_name(self, user_id: int | str) -> str:
        """user_idから表示名を返す。

        不明な場合は'不明なメンバー'を返す。同期メソッド。

        Args:
            user_id: Discord user ID

        Returns:
            str: 表示名
        """
        user_id_str = str(user_id)

        if user_id_str in self.user_id_map:
            return self.user_id_map[user_id_str]

        # プロファイルから直接検索
        for username, profile in self.profiles.items():
            if profile.get("user_id") == user_id_str:
                return profile.get("display_name", username)

        return "不明なメンバー"

    def get_inactive_members_with_topics(
        self,
        topic: str,
        days: int = 30,
    ) -> list[dict]:
        """指定トピックに関連する非活動メンバーを返す。

        nudge機能で使用。

        Args:
            topic: 現在の話題
            days: 非活動日数の閾値

        Returns:
            list[dict]: 関連する非活動メンバーのリスト
        """
        related = []
        topic_lower = topic.lower()

        for username, profile in self.profiles.items():
            # prediction_topicsやexpertiseに含まれるか
            pred_topics = profile.get("prediction_topics", "").lower()
            expertise = profile.get("expertise", "").lower()

            if topic_lower in pred_topics or topic_lower in expertise:
                related.append(profile)

        return related
