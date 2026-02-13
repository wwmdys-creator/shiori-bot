"""member_profile.py — 栞（Shiori）メンバープロファイル管理モジュール

メンバープロファイル、コミュニティ用語、コンセンサス情報を管理する。

COMMON_MISTAKES §10: 旧名 profiles.py → 現名 member_profile.py
`from profiles import` とするとImportError。

参照: interface_contract.md §2.12

v4.1.2: ファイルパスを柔軟化、検索ロジックを拡張（display_name対応）
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
        display_name_map: display_name → username のマッピング
        lexicon: 用語名 → 定義辞書
        consensus: トピック → コンセンサス情報辞書
    """

    def __init__(self):
        self.profiles = {}
        self.user_id_map = {}
        self.display_name_map = {}
        self.lexicon = {}
        self.consensus = {}

    def _find_file(self, *candidates):
        """候補リストから最初に見つかったファイルを返す。"""
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return path
        return None

    async def load(self):
        """起動時に3ファイルをフルロード。"""
        await self._load_profiles()
        await self._load_lexicon()
        await self._load_consensus()

    async def _load_profiles(self):
        """members_seed.md と members_extended.md を読み込む。"""
        # まず members_seed.md から基本情報を読み込む
        # 注意: data/members.md はボリュームに空ファイルが残る可能性があるため除外
        seed_file = self._find_file(
            "data/members_seed.md",
            "members_seed.md",
        )
        
        # seed_file が見つからない、または空の場合は members.md を試す
        if seed_file:
            content = seed_file.read_text(encoding="utf-8")
            if len(content.strip()) < 100:  # ほぼ空のファイル
                logger.warning(f"{seed_file} is empty or too small, trying alternatives")
                seed_file = None
        
        if not seed_file:
            # フォールバック: members.md を試す
            fallback = self._find_file("data/members.md")
            if fallback:
                content = fallback.read_text(encoding="utf-8")
                if len(content.strip()) >= 100:
                    seed_file = fallback
        
        if seed_file:
            try:
                content = seed_file.read_text(encoding="utf-8")
                self.profiles = self._parse_members_seed(content)
                logger.info(f"Loaded {len(self.profiles)} profiles from {seed_file}")
            except Exception as e:
                logger.error(f"Failed to load seed profiles: {e}")

        # 次に members_extended.md から詳細情報をマージ
        extended_file = self._find_file(
            "data/members_extended.md",
            "members_extended.md",
        )

        if extended_file:
            try:
                content = extended_file.read_text(encoding="utf-8")
                extended = self._parse_profiles(content)
                # マージ
                for username, ext_profile in extended.items():
                    if username in self.profiles:
                        # 既存に追加
                        for k, v in ext_profile.items():
                            if k not in self.profiles[username] or not self.profiles[username].get(k):
                                self.profiles[username][k] = v
                    else:
                        self.profiles[username] = ext_profile
                logger.info(f"Merged {len(extended)} extended profiles from {extended_file}")
            except Exception as e:
                logger.error(f"Failed to load extended profiles: {e}")
        
        if not self.profiles:
            logger.warning("No profiles loaded")
            return
            
        self._build_lookup_maps()

    def _parse_members_seed(self, content):
        """members_seed.md をパースする。"""
        profiles = {}
        
        # コードブロックを除去
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        
        # ## メンバー: 名前 で分割
        sections = re.split(r'\n(?=## メンバー:)', content)
        
        for section in sections:
            if not section.strip():
                continue
            
            # ヘッダーを探す
            header_match = re.match(r"## メンバー:\s*([^\n]+)", section)
            if not header_match:
                continue
            
            header_name = header_match.group(1).strip()
            if not header_name or header_name.startswith('('):
                continue
            
            profile = {"_header_name": header_name}
            
            # フィールドをパース
            for line in section.split("\n"):
                line = line.strip()
                if line.startswith("###") or line.startswith("|"):
                    break  # 信頼度変動履歴などはスキップ
                if not line.startswith("-"):
                    continue
                
                # - **field:** value
                match = re.match(r"^-\s+\*\*([^*:]+):\*\*\s*(.*)$", line)
                if match:
                    key = match.group(1).strip()
                    val = match.group(2).strip()
                    
                    # user_id は Snowflake ID（17桁以上）のみ整数化
                    if key == "user_id" and val.isdigit() and len(val) >= 17:
                        profile[key] = int(val)
                    elif val:
                        profile[key] = val
            
            # username をキーに
            username = profile.get("username", header_name)
            if not profile.get("display_name"):
                profile["display_name"] = header_name
            profiles[username] = profile
        
        return profiles

    def _parse_profiles(self, content):
        """members_extended.md をパースする。"""
        profiles = {}

        # フォーマット1: ## Rom🧄 (旧形式)
        # フォーマット2: ### ○（hashimae）(新形式)
        
        # 新形式を試す: ### 表示名（username）
        pattern_new = r"###\s+([^（\n]+)(?:（([^）]+)）)?"
        
        # セクションごとに分割
        sections = re.split(r'\n(?=###\s+[^#])', content)
        
        for section in sections:
            if not section.strip():
                continue
                
            # ヘッダー行を探す
            header_match = re.match(r"###\s+([^（\n]+)(?:（([^）]+)）)?", section)
            if not header_match:
                # 旧形式を試す: ## 名前
                header_match = re.match(r"##\s+([^\n]+)", section)
                if not header_match:
                    continue
                display_name = header_match.group(1).strip()
                username = display_name
            else:
                display_name = header_match.group(1).strip()
                username = header_match.group(2).strip() if header_match.group(2) else display_name
            
            profile = {"display_name": display_name, "username": username}

            # フィールドをパース
            for line in section.split("\n"):
                line = line.strip()
                if not line.startswith("-"):
                    continue
                    
                # - **field**: value または - field: value
                match = re.match(r"^-\s+\*?\*?([^*:]+)\*?\*?:?\s*(.*)$", line)
                if match:
                    key = match.group(1).strip()
                    val = match.group(2).strip()
                    
                    # user_id は Snowflake ID（17桁以上）のみ整数化
                    if key == "user_id" and val.isdigit() and len(val) >= 17:
                        profile[key] = int(val)
                    elif val:  # 空でない値のみ
                        profile[key] = val

            if username:
                profiles[username] = profile

        return profiles

    def _build_lookup_maps(self):
        """user_id → username, display_name → username のマッピングを構築。"""
        self.user_id_map = {}
        self.display_name_map = {}
        
        for username, profile in self.profiles.items():
            # user_id マップ
            user_id = profile.get("user_id")
            if isinstance(user_id, int):
                self.user_id_map[user_id] = username
            
            # display_name マップ
            display_name = profile.get("display_name")
            if display_name:
                self.display_name_map[display_name] = username
            
            # username自体も追加
            self.display_name_map[username] = username
            
            # 備考から旧名を抽出
            notes = profile.get("備考", "")
            if notes and "以前" in notes:
                alias_match = re.search(r"[「『]([^」』]+)[」』]", notes)
                if alias_match:
                    alias = alias_match.group(1)
                    self.display_name_map[alias] = username
        
        logger.debug(f"Built {len(self.user_id_map)} user_id mappings, "
                    f"{len(self.display_name_map)} display_name mappings")

    async def _load_lexicon(self):
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
            logger.info(f"Loaded {len(self.lexicon)} terms")
        except Exception as e:
            logger.error(f"Failed to load lexicon: {e}")

    def _parse_lexicon(self, content):
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

    async def _load_consensus(self):
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
            logger.info(f"Loaded {len(self.consensus)} consensus topics")
        except Exception as e:
            logger.error(f"Failed to load consensus: {e}")

    def _parse_consensus(self, content):
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

    def get_profile(self, user_id=None, username=None, display_name=None):
        """メンバープロファイルを返す。

        user_id、username、display_nameのいずれかで検索。同期メソッド。

        Args:
            user_id: Discord user ID
            username: Discord username
            display_name: 表示名（旧名含む）

        Returns:
            dict or None: プロファイル情報。該当なしならNone。
        """
        # 1. user_id で検索
        if user_id and user_id in self.user_id_map:
            uname = self.user_id_map[user_id]
            return self.profiles.get(uname)

        # 2. username で直接検索
        if username and username in self.profiles:
            return self.profiles[username]

        # 3. display_name で検索
        search_name = display_name or username
        if search_name and search_name in self.display_name_map:
            uname = self.display_name_map[search_name]
            return self.profiles.get(uname)

        return None

    def get_profile_summary(self, user_id):
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

    def get_tier_ab_summaries(self):
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

    def get_community_knowledge_text(self, compact=False):
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

    def lookup_term(self, term):
        """community_lexicon.md から用語を検索する。

        同期メソッド。

        Args:
            term: 検索する用語

        Returns:
            dict or None: {"term": str, "definition": str, "proposer": str, ...}
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

    def lookup_consensus(self, topic):
        """consensus_tracker.md からトピックのコンセンサスを検索する。

        同期メソッド。

        Args:
            topic: 検索するトピック

        Returns:
            dict or None: {"topic": str, "majority": str, "dissenters": list, ...}
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

    def get_display_name(self, user_id):
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

    def get_inactive_members_with_topics(self, topic, days=30):
        """指定トピックに関連する非活動メンバーを返す。

        nudge機能で使用。

        Args:
            topic: 現在の話題
            days: 非活動日数の閾値

        Returns:
            list: 関連する非活動メンバーのリスト
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

    def get_member_summary_for_highlight(self, name):
        """メンバー名からハイライト用の要約を返す。

        メンバーについて質問された時にコンテキストとして使用。

        Args:
            name: メンバー名（display_name, username, または旧名）

        Returns:
            str or None: メンバーの要約。見つからない場合はNone。
        """
        # 名前でプロファイルを検索
        profile = self.get_profile(display_name=name)
        
        if not profile:
            return None
        
        # 要約を構築
        parts = []
        
        display_name = profile.get("display_name", name)
        parts.append(f"【{display_name}】")
        
        # Tier
        tier = profile.get("tier")
        if tier:
            parts.append(f"Tier {tier}")
        
        # ポジション/役割
        position = profile.get("position")
        if position:
            parts.append(position)
        
        # 専門領域
        expertise = profile.get("expertise")
        if expertise:
            # 長すぎる場合は切り詰め
            if len(expertise) > 100:
                expertise = expertise[:97] + "..."
            parts.append(f"関心領域: {expertise}")
        
        # 思想的特徴
        ideology = profile.get("ideology")
        if ideology:
            if len(ideology) > 150:
                ideology = ideology[:147] + "..."
            parts.append(f"思想: {ideology}")
        
        # 発言スタイル
        style = profile.get("style")
        if style:
            if len(style) > 100:
                style = style[:97] + "..."
            parts.append(f"スタイル: {style}")
        
        # notes（補足情報）
        notes = profile.get("notes")
        if notes and len(notes) < 100:
            parts.append(f"備考: {notes}")
        
        return " / ".join(parts) if len(parts) > 1 else None
