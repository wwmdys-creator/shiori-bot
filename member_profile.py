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
        self.user_id_map: dict[int, str] = {}
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
            logger.info("members_extended.md not found, using empty profiles")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.profiles = self._parse_profiles(content)
            self._build_user_id_map()
            logger.info(f"Loaded {len(self.profiles)} profiles")
            # デバッグ: ロードしたプロファイル名を出力
            profile_names = list(self.profiles.keys())[:10]
            logger.info(f"Profile names (first 10): {profile_names}")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")

    def _parse_profiles(self, content: str) -> dict[str, dict]:
        """members_extended.md をパースする。

        実際のフォーマット:
        ## Tier-A: コアメンバー
        ---
        ### Rom🧄（katsucurry_apple）
        - **user_id**: katsucurry_apple
        - **表示名**: Rom🧄
        - **ポジション**: サーバー最多投稿者
        
        ### 動的メモ  ← これはスキップ
        """
        profiles = {}

        # メンバーセクション開始位置を見つける（## Tier-の後）
        tier_start = content.find("## Tier-")
        if tier_start == -1:
            # Tierセクションがない場合は全体をパース
            member_content = content
        else:
            member_content = content[tier_start:]

        # H3 ヘッダーパターン: ### DisplayName（username）
        # ただし「動的メモ」「ファイル仕様」などはスキップ
        pattern = r"###\s+([^（\n]+)(?:（([^）]+)）)?\s*\n([\s\S]*?)(?=\n###|\n---|\n## |\Z)"
        matches = re.findall(pattern, member_content)

        for match in matches:
            display_name = match[0].strip()
            username = match[1].strip() if match[1] else display_name  # usernameがなければdisplay_nameを使用
            block = match[2]

            # スキップすべきセクション
            skip_names = ["動的メモ", "ファイル仕様", "使用ガイド", "合意度スケール"]
            if any(skip in display_name for skip in skip_names):
                continue

            profile = {"display_name": display_name}

            # フィールドパターン: - **key**: value
            field_pattern = r"-\s+\*\*([^*]+)\*\*:\s*(.+?)(?=\n-\s+\*\*|\n###|\n---|\n## |\Z)"
            field_matches = re.findall(field_pattern, block, re.DOTALL)

            for key, val in field_matches:
                key = key.strip()
                val = val.strip()

                # 空値や動的メモはスキップ
                if not val or key == "動的メモ":
                    continue

                profile[key] = val

            # 最低限のフィールドがあるプロファイルのみ追加
            if len(profile) > 1:  # display_name以外に何かある
                profiles[username] = profile

        return profiles

    def _build_user_id_map(self) -> None:
        """user_id → username のマッピングを構築。"""
        self.user_id_map = {}
        for username, profile in self.profiles.items():
            user_id = profile.get("user_id")
            if user_id:
                self.user_id_map[user_id] = username

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

        実際のフォーマット（Markdownテーブル）:
        | 用語 | 英語 / 原語 | 意味 | 主な使用者 |
        |------|-------------|------|-----------| 
        | AGI | Artificial General Intelligence | 汎用人工知能 | 全員 |
        """
        lexicon = {}

        # Markdownテーブル形式をパース
        # | 用語 | 英語 | 意味 | 使用者 |
        table_pattern = r"\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
        matches = re.findall(table_pattern, content)

        for match in matches:
            term = match[0].strip()
            english = match[1].strip()
            definition = match[2].strip()
            users = match[3].strip()

            # ヘッダー行や区切り行をスキップ
            if term in ("用語", "---", "------") or term.startswith("-"):
                continue
            if not term or not definition:
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
        - **合意点**: 今この10年の間にAGIは到来する
        - **論争点**: 具体的な年号
        """
        consensus = {}

        # Theme セクションパターン
        theme_pattern = r"## Theme \d+:\s*([^（\n]+)(?:（[^）]+）)?\s*\n([\s\S]*?)(?=\n## Theme|\n## 横断分析|\n## 合意度サマリ|\Z)"
        matches = re.findall(theme_pattern, content)

        for topic, block in matches:
            topic = topic.strip()
            entry = {"topic": topic}

            # 合意度を抽出
            consensus_level_match = re.search(r"\*\*合意度\*\*:\s*(★+☆*)", block)
            if consensus_level_match:
                entry["consensus_level"] = consensus_level_match.group(1)

            # 合意点を抽出
            majority_match = re.search(r"-\s*\*\*合意点\*\*:\s*(.+?)(?:\n|$)", block)
            if majority_match:
                entry["majority"] = majority_match.group(1).strip()

            # 論争点を抽出
            dispute_match = re.search(r"-\s*\*\*論争点\*\*:\s*(.+?)(?:\n|$)", block)
            if dispute_match:
                entry["dispute"] = dispute_match.group(1).strip()

            # 未決着論点を抽出
            unresolved_section = re.search(r"### 未決着論点\s*\n([\s\S]*?)(?=\n###|\n##|\Z)", block)
            if unresolved_section:
                unresolved_items = re.findall(r"-\s*(.+?)(?:\n|$)", unresolved_section.group(1))
                entry["unresolved"] = [item.strip() for item in unresolved_items if item.strip()]

            consensus[topic] = entry

        return consensus

    def get_profile(
        self,
        user_id: int = None,
        username: str = None,
    ) -> dict | None:
        """メンバープロファイルを返す。

        user_idまたはusernameで検索。同期メソッド。

        Args:
            user_id: Discord user ID
            username: Discord username

        Returns:
            dict | None: プロファイル情報。該当なしならNone。
        """
        if user_id and user_id in self.user_id_map:
            username = self.user_id_map[user_id]

        if username and username in self.profiles:
            return self.profiles[username]

        return None

    def search_member(self, query: str) -> list[dict]:
        """名前や表示名でメンバーを検索する。

        部分一致で検索し、関連するプロファイルをリストで返す。

        Args:
            query: 検索クエリ（名前の一部）

        Returns:
            list[dict]: マッチしたプロファイルのリスト
        """
        results = []
        query_lower = query.lower()

        for username, profile in self.profiles.items():
            display_name = profile.get("display_name", profile.get("表示名", ""))
            
            # usernameまたは表示名に部分一致
            if (query_lower in username.lower() or 
                query_lower in display_name.lower()):
                results.append(profile)

        return results

    def get_profile_summary(self, user_id: int = None, username: str = None) -> str:
        """コンテキスト注入用の要約プロファイルを返す（200字以内）。

        同期メソッド。

        Args:
            user_id: Discord user ID
            username: Discord username（user_idがない場合に使用）

        Returns:
            str: 要約プロファイル
        """
        profile = self.get_profile(user_id=user_id, username=username)

        if not profile:
            return "（プロファイル情報なし）"

        parts = []

        name = profile.get("display_name", profile.get("表示名", "不明"))
        parts.append(f"{name}さん")

        tier = profile.get("tier", profile.get("Tier"))
        if tier:
            parts.append(f"(Tier {tier})")

        # 日本語/英語両方のフィールド名に対応
        expertise = profile.get("expertise", profile.get("専門領域", ""))
        if expertise:
            parts.append(f"専門: {expertise}")

        position = profile.get("ポジション", profile.get("position", ""))
        if position:
            parts.append(f"役割: {position}")

        interests = profile.get("関心領域", profile.get("interests", ""))
        if interests:
            parts.append(f"関心: {interests}")

        prediction_topics = profile.get("prediction_topics", profile.get("予測トピック", ""))
        if prediction_topics:
            parts.append(f"予測トピック: {prediction_topics}")

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
            tier = profile.get("tier", profile.get("Tier", ""))
            if tier in ("A", "B"):
                summary = self.get_profile_summary(username=username)
                tier_ab.append(summary)

        if not tier_ab:
            return "（Tier A-Bメンバーなし）"

        return "\n".join(tier_ab)

    def get_all_member_brief(self, limit: int = 40) -> str:
        """全メンバーの簡易一覧を返す（Tier問わず）。

        同期メソッド。

        Args:
            limit: 最大件数

        Returns:
            str: メンバー簡易一覧
        """
        briefs = []
        count = 0
        for username, profile in self.profiles.items():
            # 動的メモや無効なエントリをスキップ
            if username == "動的メモ" or "動的メモ" in username:
                continue
            
            name = profile.get("display_name", username)
            if name == "動的メモ" or "動的メモ" in name:
                continue
                
            # 各種フィールド名に対応（日本語/英語両方）
            position = profile.get("ポジション", profile.get("position", ""))
            interests = profile.get("関心領域", profile.get("interests", ""))
            expertise = profile.get("expertise", "")

            brief = f"- {name}"
            if position:
                brief += f": {position[:60]}"
            elif interests:
                brief += f": {interests[:60]}"
            elif expertise:
                brief += f": {expertise[:60]}"

            briefs.append(brief)
            count += 1
            if count >= limit:
                break

        return "\n".join(briefs) if briefs else ""

    def get_community_knowledge_text(self, compact: bool = False) -> str:
        """コミュニティ知識をテキスト形式で返す。

        Args:
            compact: コンパクト形式にするか

        Returns:
            str: コミュニティ知識テキスト
        """
        lines = []

        # Tier A-Bメンバー（詳細情報）
        tier_ab = self.get_tier_ab_summaries()
        if tier_ab and tier_ab != "（Tier A-Bメンバーなし）":
            lines.append("【主要メンバー（Tier A-B）】")
            lines.append(tier_ab)
            lines.append("")

        # 全メンバー簡易一覧（Tier問わず）
        all_brief = self.get_all_member_brief(limit=40)
        if all_brief:
            lines.append("【サーバーメンバー一覧】")
            lines.append(all_brief)
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
            dict | None: {"term": str, "definition": str, "proposer": str, ...}
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
            dict | None: {"topic": str, "majority": str, "dissenters": list, ...}
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

    def get_display_name(self, user_id: int) -> str:
        """user_idから表示名を返す。

        不明な場合は'不明なメンバー'を返す。同期メソッド。

        Args:
            user_id: Discord user ID

        Returns:
            str: 表示名
        """
        if user_id in self.user_id_map:
            username = self.user_id_map[user_id]
            profile = self.profiles.get(username)
            if profile:
                return profile.get("display_name", username)
            return username

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
            # prediction_topicsに含まれるか
            pred_topics = profile.get("prediction_topics", "").lower()
            expertise = profile.get("expertise", "").lower()

            if topic_lower in pred_topics or topic_lower in expertise:
                related.append(profile)

        return related
