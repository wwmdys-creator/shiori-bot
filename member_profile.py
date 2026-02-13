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
        # v4.5: data/サブディレクトリがない場合はルートから読み込む
        filepath = Path("data/members_extended.md")
        if not filepath.exists():
            filepath = Path("members_extended.md")

        if not filepath.exists():
            logger.info("members_extended.md not found, using empty profiles")
            return

        try:
            content = filepath.read_text(encoding="utf-8")
            self.profiles = self._parse_profiles(content)
            self._build_user_id_map()
            logger.info(f"Loaded {len(self.profiles)} profiles from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")

    def _parse_profiles(self, content: str) -> dict[str, dict]:
        """members_extended.md をパースする。
        
        v4.5対応: 実際のmembers_extended.mdフォーマットに対応
        """
        profiles = {}

        # フォーマット例（v4.5 members_extended.md）:
        # ### Rom🧄（katsucurry_apple）
        # 
        # - **user_id**: katsucurry_apple
        # - **表示名**: Rom🧄
        # - **投稿数**: 907件（未来予測ch）
        # - **ポジション**: サーバー最多投稿者...
        # - **思想的特徴**: 楽観的だが...
        # - **関心領域**: トランスヒューマニズム、...
        # - **発言スタイル**: 語尾に「〜っピ」...
        # - **代表的主張**: ...
        # - **栞の役割保護**: ...

        # ### で始まるセクションを抽出（Tier見出しは除外）
        # 「### 動的メモ」や「## Tier-」は除外
        pattern = r"### ([^（\n]+)(?:（([^）]+)）)?\n\n((?:- .+\n?)+)"
        matches = re.findall(pattern, content)

        for display_name, username, block in matches:
            display_name = display_name.strip()
            username = username.strip() if username else display_name
            
            # 「動的メモ」セクションはスキップ
            if display_name == "動的メモ":
                continue
            
            profile = {
                "display_name": display_name,
                "username": username,
            }

            for line in block.strip().split("\n"):
                if line.startswith("- "):
                    # "- **key**: value" 形式をパース
                    line_content = line[2:]  # "- " を除去
                    
                    # **key**: value 形式
                    bold_match = re.match(r"\*\*([^*]+)\*\*:\s*(.+)", line_content)
                    if bold_match:
                        key = bold_match.group(1).strip()
                        val = bold_match.group(2).strip()
                    else:
                        # key: value 形式（フォールバック）
                        key_val = line_content.split(": ", 1)
                        if len(key_val) == 2:
                            key, val = key_val
                            key = key.strip()
                            val = val.strip()
                        else:
                            continue
                    
                    # キー名を正規化
                    key_mapping = {
                        "user_id": "user_id",
                        "表示名": "display_name",
                        "投稿数": "post_count",
                        "ポジション": "position",
                        "思想的特徴": "ideology",
                        "関心領域": "expertise",  # expertiseにマッピング
                        "発言スタイル": "style",
                        "代表的主張": "claims",
                        "栞の役割保護": "protection",
                        "チャンネル横断": "channels",
                        "通称": "nickname",
                        "愛称": "nickname",
                        # v4.1以前のキーもサポート
                        "tier": "tier",
                        "expertise": "expertise",
                        "prediction_topics": "prediction_topics",
                        "notes": "notes",
                    }
                    
                    normalized_key = key_mapping.get(key, key.lower().replace(" ", "_"))
                    profile[normalized_key] = val

            # display_nameをキーにして保存（usernameでも検索可能にする）
            profiles[display_name] = profile
            if username and username != display_name:
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
        # v4.5: data/サブディレクトリがない場合はルートから読み込む
        filepath = Path("data/community_lexicon.md")
        if not filepath.exists():
            filepath = Path("community_lexicon.md")

        if not filepath.exists():
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
        # v4.5: data/サブディレクトリがない場合はルートから読み込む
        filepath = Path("data/consensus_tracker.md")
        if not filepath.exists():
            filepath = Path("consensus_tracker.md")

        if not filepath.exists():
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
            lines.append("※メンバーについて聞かれたら、以下の情報を「フィールドノートの観察所見」または「栞の個人的印象」として紹介すること")
            lines.append("")
            
            # 重複を除去（display_nameとusernameの両方でエントリがある場合）
            seen_profiles = set()
            unique_profiles = []
            for name, profile in self.profiles.items():
                profile_id = id(profile)  # 同じdictオブジェクトを参照しているか
                if profile_id not in seen_profiles:
                    seen_profiles.add(profile_id)
                    unique_profiles.append((name, profile))
            
            for name, profile in unique_profiles:
                display_name = profile.get("display_name", name)
                
                # 基本情報
                member_line = f"- {display_name}さん"
                
                # ポジション（役割）
                position = profile.get("position", "")
                if position:
                    member_line += f": {position}"
                
                # 関心領域 / 専門
                expertise = profile.get("expertise", "")
                if expertise and not compact:
                    member_line += f" / 関心: {expertise}"
                
                # 発言スタイル
                style = profile.get("style", "")
                if style and not compact:
                    # 長すぎる場合は切り詰め
                    if len(style) > 50:
                        style = style[:47] + "..."
                    member_line += f" / スタイル: {style}"
                
                # 代表的主張（compactでない場合のみ）
                claims = profile.get("claims", "")
                if claims and not compact:
                    # 長すぎる場合は切り詰め
                    if len(claims) > 80:
                        claims = claims[:77] + "..."
                    member_line += f" / 主張: {claims}"
                
                # 思想的特徴（印象応答用）
                ideology = profile.get("ideology", "")
                if ideology and not compact:
                    if len(ideology) > 60:
                        ideology = ideology[:57] + "..."
                    member_line += f" / 特徴: {ideology}"
                
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
