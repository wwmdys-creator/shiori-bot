"""member_profile.py — 栞（Shiori）メンバープロファイル管理モジュール

メンバープロファイル、コミュニティ用語、コンセンサス情報を管理する。

COMMON_MISTAKES §10: 旧名 profiles.py → 現名 member_profile.py
`from profiles import` とするとImportError。

参照: interface_contract.md §2.12

v4.1.1 修正:
- ファイルパス検索を柔軟化（data/ 優先、なければルート直下）
- members_seed.md / members_extended.md 両フォーマットに対応
- 検索ロジック拡張（user_id, username, display_name, 旧名で横断検索）
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("shiori.member_profile")


class MemberProfileManager:
    """メンバープロファイル管理クラス。

    データファイルを統合管理:
    - data/members.md (または members_seed.md): メンバー台帳
    - data/members_extended.md: 詳細プロファイル（補助）
    - data/community_lexicon.md: コミュニティ用語辞典
    - data/consensus_tracker.md: コンセンサストラッカー

    Attributes:
        profiles: username → プロファイル辞書
        user_id_map: user_id → username のマッピング
        display_name_map: display_name → username のマッピング
        alias_map: 旧名・別名 → username のマッピング
        lexicon: 用語名 → 定義辞書
        consensus: トピック → コンセンサス情報辞書
    """

    def __init__(self):
        self.profiles: dict[str, dict] = {}
        self.user_id_map: dict[int, str] = {}
        self.display_name_map: dict[str, str] = {}
        self.alias_map: dict[str, str] = {}
        self.lexicon: dict[str, dict] = {}
        self.consensus: dict[str, dict] = {}

    def _find_file(self, *candidates: str) -> Path | None:
        """候補リストから最初に見つかったファイルを返す。"""
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                logger.debug(f"Found file: {path}")
                return path
        return None

    async def load(self) -> None:
        """起動時にファイルをフルロード。"""
        await self._load_profiles()
        await self._load_lexicon()
        await self._load_consensus()

    async def _load_profiles(self) -> None:
        """メンバープロファイルを読み込む。
        
        優先順位:
        1. data/members.md（運用ファイル）
        2. data/members_seed.md
        3. members_seed.md（ルート直下）
        """
        # メイン台帳
        main_file = self._find_file(
            "data/members.md",
            "data/members_seed.md",
            "members_seed.md",
        )
        
        if main_file:
            try:
                content = main_file.read_text(encoding="utf-8")
                self.profiles = self._parse_members_seed(content)
                logger.info(f"Loaded {len(self.profiles)} profiles from {main_file}")
            except Exception as e:
                logger.error(f"Failed to load {main_file}: {e}")
        
        # 詳細プロファイル（補助、マージ）
        extended_file = self._find_file(
            "data/members_extended.md",
            "members_extended.md",
        )
        
        if extended_file:
            try:
                content = extended_file.read_text(encoding="utf-8")
                extended = self._parse_members_extended(content)
                self._merge_extended_profiles(extended)
                logger.info(f"Merged {len(extended)} extended profiles from {extended_file}")
            except Exception as e:
                logger.error(f"Failed to load {extended_file}: {e}")
        
        # マッピング構築
        self._build_lookup_maps()
        
        if not self.profiles:
            logger.warning("No profiles loaded - check file paths")

    def _parse_members_seed(self, content: str) -> dict[str, dict]:
        """members_seed.md / members.md をパースする。
        
        フォーマット:
        ## メンバー: ○
        
        - **user_id:** 559358257123295242
        - **username:** hashimae
        - **display_name:** ○
        - **tier:** A
        - **expertise:** 仏教哲学, シミュレーション仮説
        ...
        """
        profiles = {}
        
        # ## メンバー: {name} のパターン
        pattern = r"## メンバー: ([^\n]+)\n((?:[-\*].*\n?)*)"
        matches = re.findall(pattern, content)
        
        for header_name, block in matches:
            header_name = header_name.strip()
            profile = {"_header_name": header_name}
            
            for line in block.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                    
                # - **field:** value または - field: value
                match = re.match(r"^[-\*]\s*\*?\*?(\w+)\*?\*?:?\*?\*?\s*(.+)$", line)
                if match:
                    key = match.group(1).strip()
                    val = match.group(2).strip()
                    
                    # user_id は整数に変換（pending以外）
                    if key == "user_id":
                        if val.isdigit():
                            profile[key] = int(val)
                        else:
                            profile[key] = val  # "pending" などはそのまま
                    else:
                        profile[key] = val
            
            # username をキーにする（なければ header_name）
            username = profile.get("username", header_name)
            profiles[username] = profile
        
        return profiles

    def _parse_members_extended(self, content: str) -> dict[str, dict]:
        """members_extended.md をパースする。
        
        フォーマット:
        ### ○（hashimae）
        
        - **user_id**: 559358257123295242
        - **表示名**: ○
        - **投稿数**: 251件
        ...
        """
        profiles = {}
        
        # ### 表示名（username） のパターン
        pattern = r"###\s+([^（\n]+)(?:（([^）]+)）)?\s*\n((?:[-\*].*\n?)*)"
        matches = re.findall(pattern, content)
        
        for display_name, username_hint, block in matches:
            display_name = display_name.strip()
            username = username_hint.strip() if username_hint else display_name
            
            profile = {
                "display_name": display_name,
                "_username_hint": username,
            }
            
            # フィールド名の日本語→英語マッピング
            field_map = {
                "表示名": "display_name",
                "投稿数": "post_count",
                "ポジション": "position",
                "思想的特徴": "ideology",
                "関心領域": "expertise",
                "発言スタイル": "style",
                "代表的主張": "representative_claims",
                "チャンネル横断": "channels",
                "備考": "notes",
            }
            
            for line in block.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # - **field**: value
                match = re.match(r"^[-\*]\s*\*?\*?([^*:]+)\*?\*?:\s*(.+)$", line)
                if match:
                    key_raw = match.group(1).strip()
                    val = match.group(2).strip()
                    
                    # 日本語キーを英語に変換
                    key = field_map.get(key_raw, key_raw)
                    
                    if key == "user_id":
                        if val.isdigit():
                            profile[key] = int(val)
                        else:
                            profile[key] = val
                    else:
                        profile[key] = val
            
            profiles[username] = profile
        
        return profiles

    def _merge_extended_profiles(self, extended: dict[str, dict]) -> None:
        """extended プロファイルをメインにマージする。"""
        for username, ext_profile in extended.items():
            if username in self.profiles:
                # 既存プロファイルに追加情報をマージ
                for key, val in ext_profile.items():
                    if key not in self.profiles[username] or not self.profiles[username][key]:
                        self.profiles[username][key] = val
            else:
                # 新規追加
                self.profiles[username] = ext_profile

    def _build_lookup_maps(self) -> None:
        """各種逆引きマップを構築する。"""
        self.user_id_map = {}
        self.display_name_map = {}
        self.alias_map = {}
        
        for username, profile in self.profiles.items():
            # user_id マップ
            user_id = profile.get("user_id")
            if isinstance(user_id, int):
                self.user_id_map[user_id] = username
            
            # display_name マップ
            display_name = profile.get("display_name")
            if display_name:
                self.display_name_map[display_name] = username
                # 正規化版も追加（小文字、空白除去）
                normalized = display_name.lower().replace(" ", "")
                self.display_name_map[normalized] = username
            
            # header_name も追加
            header_name = profile.get("_header_name")
            if header_name and header_name != display_name:
                self.display_name_map[header_name] = username
            
            # 備考欄から旧名を抽出
            notes = profile.get("notes", "")
            if "以前の表示名" in notes or "旧名" in notes:
                # 「橋」は以前の表示名 → "橋" を抽出
                alias_match = re.search(r"[「『]([^」』]+)[」』].*(?:以前|旧)", notes)
                if alias_match:
                    alias = alias_match.group(1)
                    self.alias_map[alias] = username
            
            # username自体もdisplay_name_mapに追加
            self.display_name_map[username] = username
        
        logger.debug(f"Built maps: {len(self.user_id_map)} user_ids, "
                    f"{len(self.display_name_map)} display_names, "
                    f"{len(self.alias_map)} aliases")

    async def _load_lexicon(self) -> None:
        """community_lexicon.md を読み込む。"""
        filepath = self._find_file(
            "data/community_lexicon.md",
            "community_lexicon.md",
        )

        if not filepath:
            logger.info("community_lexicon.md not found, using empty lexicon")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.lexicon = self._parse_lexicon(content)
            logger.info(f"Loaded {len(self.lexicon)} terms from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load lexicon: {e}")

    def _parse_lexicon(self, content: str) -> dict[str, dict]:
        """community_lexicon.md をパースする。"""
        lexicon = {}

        pattern = r"## ([^\n]+)\n((?:- .+\n?)+)"
        matches = re.findall(pattern, content)

        for term, block in matches:
            term = term.strip()
            entry = {"term": term}

            for line in block.strip().split("\n"):
                if line.startswith("- "):
                    key_val = line[2:].split(": ", 1)
                    if len(key_val) == 2:
                        key, val = key_val
                        entry[key] = val.strip()

            lexicon[term] = entry

        return lexicon

    async def _load_consensus(self) -> None:
        """consensus_tracker.md を読み込む。"""
        filepath = self._find_file(
            "data/consensus_tracker.md",
            "consensus_tracker.md",
        )

        if not filepath:
            logger.info("consensus_tracker.md not found, using empty consensus")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.consensus = self._parse_consensus(content)
            logger.info(f"Loaded {len(self.consensus)} consensus topics from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load consensus: {e}")

    def _parse_consensus(self, content: str) -> dict[str, dict]:
        """consensus_tracker.md をパースする。"""
        consensus = {}

        pattern = r"## ([^\n]+)\n((?:- .+\n?)+)"
        matches = re.findall(pattern, content)

        for topic, block in matches:
            topic = topic.strip()
            entry = {"topic": topic}

            for line in block.strip().split("\n"):
                if line.startswith("- "):
                    key_val = line[2:].split(": ", 1)
                    if len(key_val) == 2:
                        key, val = key_val
                        if key == "dissenters":
                            entry[key] = [d.strip() for d in val.split(",")]
                        else:
                            entry[key] = val.strip()

            consensus[topic] = entry

        return consensus

    def get_profile(
        self,
        user_id: int = None,
        username: str = None,
        display_name: str = None,
    ) -> dict | None:
        """メンバープロファイルを返す。

        user_id、username、display_name のいずれかで検索。
        旧名・別名でも検索可能。同期メソッド。

        Args:
            user_id: Discord user ID
            username: Discord username
            display_name: 表示名（旧名含む）

        Returns:
            dict | None: プロファイル情報。該当なしならNone。
        """
        # 1. user_id で検索
        if user_id and user_id in self.user_id_map:
            username = self.user_id_map[user_id]
            return self.profiles.get(username)
        
        # 2. username で直接検索
        if username and username in self.profiles:
            return self.profiles[username]
        
        # 3. display_name で検索
        search_name = display_name or username
        if search_name:
            # 完全一致
            if search_name in self.display_name_map:
                uname = self.display_name_map[search_name]
                return self.profiles.get(uname)
            
            # 正規化版で検索
            normalized = search_name.lower().replace(" ", "")
            if normalized in self.display_name_map:
                uname = self.display_name_map[normalized]
                return self.profiles.get(uname)
            
            # 別名・旧名で検索
            if search_name in self.alias_map:
                uname = self.alias_map[search_name]
                return self.profiles.get(uname)
            
            # 部分一致（最終手段）
            for dn, uname in self.display_name_map.items():
                if search_name in dn or dn in search_name:
                    return self.profiles.get(uname)

        return None

    def get_profile_summary(self, user_id: int) -> str:
        """コンテキスト注入用の要約プロファイルを返す（200字以内）。

        COMMON_MISTAKES §10: 引数は user_id: int の1つのみ。

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
            parts.append(f"専門: {expertise}")

        prediction_topics = profile.get("prediction_topics")
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
            tier = profile.get("tier", "")
            if tier in ("A", "B"):
                summary = self.get_profile_summary(profile.get("user_id", 0))
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
    
    def search_members(self, query: str) -> list[dict]:
        """クエリに一致するメンバーを検索する。
        
        display_name、username、expertise、notesを横断検索。
        
        Args:
            query: 検索クエリ
            
        Returns:
            list[dict]: マッチしたプロファイルのリスト
        """
        results = []
        query_lower = query.lower()
        
        for username, profile in self.profiles.items():
            # 各フィールドで検索
            searchable = [
                profile.get("display_name", ""),
                profile.get("username", username),
                profile.get("_header_name", ""),
                profile.get("expertise", ""),
                profile.get("notes", ""),
                profile.get("position", ""),
            ]
            
            combined = " ".join(str(s) for s in searchable).lower()
            
            if query_lower in combined:
                results.append(profile)
        
        return results
