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
        filepath = Path("data/members_extended.md")

        if not filepath.exists():
            logger.info("members_extended.md not found, using empty profiles")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.profiles = self._parse_profiles(content)
            self._build_user_id_map()
            logger.info(f"Loaded {len(self.profiles)} profiles")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")

    def _parse_profiles(self, content: str) -> dict[str, dict]:
        """members_extended.md をパースする。"""
        profiles = {}

        # フォーマット例:
        # ## Rom🧄
        # - user_id: 123456789
        # - tier: A
        # - expertise: ニュースキュレーション、AI動向
        # - prediction_topics: AGI時期、AI規制
        # - notes: 毎日ニュースを投稿。情報の早さに定評

        pattern = r"## ([^\n]+)\n((?:- .+\n?)+)"
        matches = re.findall(pattern, content)

        for username, block in matches:
            username = username.strip()
            profile = {"display_name": username}

            for line in block.strip().split("\n"):
                if line.startswith("- "):
                    key_val = line[2:].split(": ", 1)
                    if len(key_val) == 2:
                        key, val = key_val
                        if key == "user_id":
                            profile[key] = int(val)
                        else:
                            profile[key] = val.strip()

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
        """community_lexicon.md をパースする。"""
        lexicon = {}

        # フォーマット例:
        # ## シンギュラリティ
        # - definition: 技術的特異点。AIが人間の知能を超える瞬間
        # - proposer: 不明（カーツワイル由来）
        # - related: AGI, ASI

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
        """consensus_tracker.md をパースする。"""
        consensus = {}

        # フォーマット例:
        # ## AGI到達時期
        # - majority: 2030-2035年
        # - dissenters: ろーる（懐疑派、2040年以降）
        # - updated: 2025-01

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
                            # リスト化
                            entry[key] = [d.strip() for d in val.split(",")]
                        else:
                            entry[key] = val.strip()

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

        # メンバープロファイル（§6.6 メンバー質問応答に必須）
        if self.profiles:
            lines.append("【メンバープロファイル】")
            lines.append("※メンバーについて聞かれたら、以下の情報を「フィールドノートの観察所見」として紹介すること")
            lines.append("")
            
            # Tier順にソート（A→B→C→D）
            tier_order = {"A": 0, "B": 1, "C": 2, "D": 3}
            sorted_profiles = sorted(
                self.profiles.items(),
                key=lambda x: tier_order.get(x[1].get("tier", "D"), 3)
            )
            
            for username, profile in sorted_profiles:
                display_name = profile.get("display_name", username)
                tier = profile.get("tier", "")
                expertise = profile.get("expertise", "")
                prediction_topics = profile.get("prediction_topics", "")
                notes = profile.get("notes", "")
                
                member_line = f"- {display_name}さん"
                if tier:
                    member_line += f" (Tier {tier})"
                if expertise:
                    member_line += f": {expertise}"
                if prediction_topics and not compact:
                    member_line += f" / 予測: {prediction_topics}"
                if notes and not compact:
                    member_line += f" / {notes}"
                
                lines.append(member_line)
            
            lines.append("")

        # 用語辞典
        if self.lexicon and not compact:
            lines.append("【サーバー固有用語】")
            for term, info in list(self.lexicon.items())[:10]:
                definition = info.get("definition", "")
                proposer = info.get("proposer", "")
                term_line = f"- {term}: {definition}"
                if proposer:
                    term_line += f"（提唱: {proposer}）"
                lines.append(term_line)
            lines.append("")

        # コンセンサス情報
        if self.consensus:
            lines.append("【サーバーのコンセンサス】")
            for topic, info in list(self.consensus.items())[:5]:
                majority = info.get("majority", "不明")
                dissenters = info.get("dissenters", [])
                consensus_line = f"- {topic}: 主流派={majority}"
                if dissenters:
                    consensus_line += f" / 異論={', '.join(dissenters)}"
                lines.append(consensus_line)
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
