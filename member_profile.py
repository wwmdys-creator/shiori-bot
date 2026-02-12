"""
profiles.py - メンバープロファイル管理モジュール

既存のユーザープロファイル（15ユーザー分）の管理と、
新規メンバーのプロファイル作成を担当。

Q11決定: Bot起動初日に既存プロファイルをフルロード（A案）
Q26決定: サーバー離脱メンバーのデータは匿名化して保持（B案）
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


@dataclass
class MemberProfile:
    """メンバープロファイル"""
    user_id: str
    username: str
    display_name: str
    
    # サーバー内での役割・特徴
    position: str = ""  # サーバー内でのポジション
    ideology: str = ""  # 思想的特徴
    interests: List[str] = field(default_factory=list)  # 関心領域
    style: str = ""  # 発言スタイル
    representative_claims: List[str] = field(default_factory=list)  # 代表的主張
    
    # 投稿統計
    post_count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    
    # 栞との関係性
    relationship_note: str = ""  # 栞との想定リレーション
    
    # メタデータ
    is_active: bool = True
    is_anonymized: bool = False
    anonymized_id: str = ""  # 匿名化された場合のID
    
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemberProfile':
        """辞書形式から復元"""
        return cls(**data)
    
    def update_last_seen(self):
        """最終確認日時を更新"""
        self.last_seen = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def get_summary_for_llm(self) -> str:
        """LLMコンテキスト用のサマリーを生成"""
        lines = [f"【{self.display_name}さん】"]
        
        if self.position:
            lines.append(f"ポジション: {self.position}")
        
        if self.interests:
            lines.append(f"関心領域: {', '.join(self.interests[:5])}")
        
        if self.style:
            lines.append(f"発言スタイル: {self.style}")
        
        if self.relationship_note:
            lines.append(f"栞との関係: {self.relationship_note}")
        
        if self.post_count > 0:
            lines.append(f"投稿数: {self.post_count}件")
        
        return "\n".join(lines)


# 既存メンバーの初期プロファイルデータ（discord_user_profiling.mdより）
INITIAL_PROFILES: List[Dict[str, Any]] = [
    {
        "user_id": "katsucurry_apple",
        "username": "katsucurry_apple",
        "display_name": "Rom🧄",
        "position": "サーバー最多投稿者。AI業界ニュースのキュレーター兼解説者。",
        "ideology": "楽観的だが地に足のついたテクノロジスト。AGIの実現は認めつつも、シンギュラリティへの到達には慎重なタイムライン。",
        "interests": ["トランスヒューマニズム", "ポストヒューマニズム", "AIアライメント", "AI企業競争分析"],
        "style": "語尾に「〜っピ」をつける独特のキャラクター語尾。X投稿を大量に引用し翻訳要約を添える形式。",
        "representative_claims": [
            "AnthropicとOpenAIはLevel 3エージェント段階、GoogleはLevel 1-2",
            "AGIができてもUBIやLEVの実現は2030年代半ば",
        ],
        "post_count": 907,
        "relationship_note": "最大の情報提供者。栞が最も頻繁に記録するのは彼の投稿。",
    },
    {
        "user_id": "kaesar0809",
        "username": "kaesar0809",
        "display_name": "そいやっさ",
        "position": "サーバーのディープシンカー。宇宙進出・文明論・ASIリスクに関する長文考察を展開する論客。",
        "ideology": "宇宙工学的視点からのAIリスク論者。ミスアライメントASIが人類を地球に閉じ込めるシナリオを検討。",
        "interests": ["宇宙進出戦略", "軌道エレベーター", "カルダシェフ・スケール", "PSS"],
        "style": "長文で論理的。他メンバーの過去発言を正確に記憶して引用し、論理的矛盾を指摘。",
        "representative_claims": [
            "カルダシェフ・スケール タイプ1は地球上では0.9以上は困難",
            "重力井戸の優位性によりカーマンライン外は質量攻撃に対して有利",
        ],
        "post_count": 705,
        "relationship_note": "「先生」的存在。栞が一番質問しに行く相手。",
    },
    {
        "user_id": "_upaa",
        "username": "_upaa",
        "display_name": "paupau",
        "position": "実践派のAIオプティミスト。AIツールを実際に触って検証し、結果をコミュニティに共有する行動派。",
        "ideology": "「恩恵はすでに来ている」派。多くの人がまだ気づいていないだけという立場。",
        "interests": ["AI漫画生成", "エッジデバイス推論", "電力問題", "ロボティクス", "UBI", "LEV"],
        "style": "カジュアルで親しみやすい。絵文字を多用。「やってみた」系の共有が多い。",
        "representative_claims": [
            "AIは能力を持っているが、人間が引き出し方を追求できていないだけ",
            "2035年には翻訳こんにゃく的デバイスは当たり前",
        ],
        "post_count": 640,
        "relationship_note": "実験パートナー。「やってみた」報告を栞が記録する。",
    },
    {
        "user_id": "l.n8422",
        "username": "l.n8422",
        "display_name": "L.N（＃8422）",
        "position": "自虐的リアリストのFIRE志望者。JTC文化への鬱屈とAGI時代への期待が交差。",
        "ideology": "社会構造への不満とAGI到来への希望が共存。UBI実現を2030〜2035年と予想。",
        "interests": ["FIRE", "UBI", "投資", "日本の労働問題", "自動運転", "ロボット産業"],
        "style": "短文で歯切れがよい。スラングや顔文字を多用。自虐と希望が交互に現れる。",
        "representative_claims": [
            "2030-2035年にかけて段階的にUBIが充実",
            "JTC・金融・行政は無駄な仕事を増やして忙しくなる",
        ],
        "post_count": 498,
        "relationship_note": "同世代感覚の共感相手。生活目線の予測を真剣に聞く。",
    },
    {
        "user_id": "k32ja",
        "username": "k32ja",
        "display_name": "ろーる",
        "position": "若手の漫画家志望×AGI懐疑派。サーバー内では「AGIはまだ遠い」と主張する数少ない慎重派。",
        "ideology": "AGIが早く来すぎると漫画家キャリアが無意味になる恐怖を率直に語る。確証バイアスへの警戒心が強い。",
        "interests": ["AI漫画・創作応用", "AGIタイムライン論争", "電力ボトルネック", "言語学習", "身体改造"],
        "style": "直球で歯に衣着せない。自分のタイムライン予測を堂々と書き出す。",
        "representative_claims": [
            "AGIは2029〜2032年。サーバーの主流意見は確証バイアスで早すぎる",
            "AI漫画はまだGPT-3.5レベル。商業レベルは2030年頃",
        ],
        "post_count": 299,
        "relationship_note": "大事な「反対意見の供給源」。彼の慎重論を意図的に拾う。",
    },
    {
        "user_id": "accelerator2045",
        "username": "accelerator2045",
        "display_name": "特異 天exアクセラレータ「シンギュラリティ案内人」",
        "position": "サーバーの「船長」。コミュニティの主催者/モデレーター的存在。バランスの取れた楽観主義者。",
        "ideology": "シンギュラリティを信じつつも、具体的な生活レベルのアドバイスを重視する実務的楽観主義者。",
        "interests": ["継続学習", "自己改善AI", "海水淡水化", "太陽光発電", "オービタルリング"],
        "style": "丁寧でコミュニティをまとめる語り口。「AIと一緒に学ぶ」スタイル。",
        "representative_claims": [
            "継続学習は今年のキーワード",
            "何かが来てから素早く対応するために早く決断する能力を磨くべき",
        ],
        "post_count": 235,
        "relationship_note": "「上司」的存在。サーバーの方向性について相談する。",
    },
    {
        "user_id": "tomoyama",
        "username": "tomoyama",
        "display_name": "トモヤマ",
        "position": "クリエイター視点からのAI論客。AI開発の「手触り」を語れる内部者的視座を持つ。",
        "ideology": "AGI定義論争には懐疑的で、能力ベースで年度ごとの具体的予測を提示。",
        "interests": ["AI創作", "AGIの創造性獲得", "コンテンツ産業の未来", "フィジカルAI"],
        "style": "全角アルファベット使用。感情的だが洞察力のある文章。",
        "representative_claims": [
            "2027年にそれなりに創作できるAI、2029年に生産性爆増AI",
            "AIのレコメンドで超ニッチ作品が売れる2極化時代が来る",
        ],
        "post_count": 128,
        "relationship_note": "創作論の議論相手。AIの創造性について栞が最も食いつくテーマ。",
    },
    {
        "user_id": "akipon345",
        "username": "akipon345",
        "display_name": "akipon345",
        "position": "冷静な分析者。80年周期説などのマクロ歴史観からAI時代を読み解く。",
        "ideology": "技術進歩の予測が想像と異なる方向に進むことに敏感。",
        "interests": ["周期説", "ベンチマーク論", "破滅的忘却問題", "世界モデル", "AtCoder"],
        "style": "冷静で分析的。データに基づいた議論を好む。",
        "representative_claims": [
            "80年周期説でWW2戦後のような上昇期が来る",
            "世界モデルはDeepMindのAny-to-Anyマルチモーダル化で創発する可能性",
        ],
        "post_count": 106,
        "relationship_note": "分析手法の相談相手。周期説などマクロ視点を教わる。",
    },
    {
        "user_id": "hnishi",
        "username": "hnishi",
        "display_name": "hn",
        "position": "現役研究者。15年超の研究実務経験に基づく実証的な発言が特徴。",
        "ideology": "科学研究のAI活用に最も実践的な知見を持つ。継続学習の必要性に対して独自の見解。",
        "interests": ["AIサイエンティスト", "Kosmos", "継続学習vs長期記憶", "実験自動化"],
        "style": "実証的で経験に裏打ちされた発言。",
        "representative_claims": [
            "科学研究に必要なのはベースの賢さと長期記憶で、継続学習は要らないかもしれない",
            "GPT5.2 Proは閾値を越えた",
        ],
        "post_count": 93,
        "relationship_note": "畏敬の対象。研究者としての先輩。",
    },
    {
        "user_id": "slowbird20009259",
        "username": "slowbird20009259",
        "display_name": "slowbird2000",
        "position": "SFに造詣の深い本職エンジニア。宇宙工学・産業工学的視点からの考察が光る。",
        "ideology": "A・C・クラークなどのSF知識と、エンジニアとしての実務経験を融合させた独自の視座。",
        "interests": ["軌道エレベーター", "イーロン・マスクの構想", "AIサイエンティスト評価", "BMI"],
        "style": "SF知識と実務経験を融合。技術的詳細に強い。",
        "representative_claims": [
            "軌道エレベータSFの元祖クラークの『楽園の泉』に因んだ命名を推奨",
            "米中に比べて日本のロボット開発は2年遅い",
        ],
        "post_count": 82,
        "relationship_note": "SF談義の相手。クラーク作品の話で盛り上がれる。",
    },
]


class ProfileManager:
    """メンバープロファイル管理クラス"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = self.data_dir / "profiles.json"
        self.profiles: Dict[str, MemberProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """プロファイルをファイルから読み込み"""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, profile_data in data.items():
                        self.profiles[user_id] = MemberProfile.from_dict(profile_data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[ProfileManager] プロファイル読み込みエラー: {e}")
                self.profiles = {}
    
    def _save_profiles(self):
        """プロファイルをファイルに保存"""
        data = {
            user_id: profile.to_dict()
            for user_id, profile in self.profiles.items()
        }
        with open(self.profiles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def initialize_with_existing_profiles(self) -> int:
        """
        既存プロファイルで初期化（Q11: A案）
        
        Returns:
            初期化されたプロファイル数
        """
        initialized_count = 0
        
        for profile_data in INITIAL_PROFILES:
            user_id = profile_data["user_id"]
            
            # 既に存在する場合はスキップ
            if user_id in self.profiles:
                continue
            
            # 新規プロファイル作成
            profile = MemberProfile(
                user_id=user_id,
                username=profile_data.get("username", user_id),
                display_name=profile_data.get("display_name", user_id),
                position=profile_data.get("position", ""),
                ideology=profile_data.get("ideology", ""),
                interests=profile_data.get("interests", []),
                style=profile_data.get("style", ""),
                representative_claims=profile_data.get("representative_claims", []),
                post_count=profile_data.get("post_count", 0),
                relationship_note=profile_data.get("relationship_note", ""),
                first_seen=datetime.now().isoformat(),
                last_seen=datetime.now().isoformat(),
            )
            
            self.profiles[user_id] = profile
            initialized_count += 1
        
        if initialized_count > 0:
            self._save_profiles()
        
        return initialized_count
    
    def get_profile(self, user_id: str) -> Optional[MemberProfile]:
        """プロファイルを取得"""
        return self.profiles.get(user_id)
    
    def get_or_create_profile(
        self,
        user_id: str,
        username: str,
        display_name: str = ""
    ) -> MemberProfile:
        """プロファイルを取得、なければ作成"""
        if user_id in self.profiles:
            profile = self.profiles[user_id]
            profile.update_last_seen()
            self._save_profiles()
            return profile
        
        # 新規作成
        profile = MemberProfile(
            user_id=user_id,
            username=username,
            display_name=display_name or username,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
        )
        
        self.profiles[user_id] = profile
        self._save_profiles()
        return profile
    
    def update_profile(
        self,
        user_id: str,
        **updates
    ) -> Optional[MemberProfile]:
        """プロファイルを更新"""
        if user_id not in self.profiles:
            return None
        
        profile = self.profiles[user_id]
        
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now().isoformat()
        self._save_profiles()
        return profile
    
    def increment_post_count(self, user_id: str) -> Optional[MemberProfile]:
        """投稿カウントをインクリメント"""
        if user_id not in self.profiles:
            return None
        
        profile = self.profiles[user_id]
        profile.post_count += 1
        profile.update_last_seen()
        self._save_profiles()
        return profile
    
    def anonymize_profile(self, user_id: str) -> Optional[str]:
        """
        プロファイルを匿名化（Q26: B案）
        
        Returns:
            匿名化ID（例: "元メンバー#001"）
        """
        if user_id not in self.profiles:
            return None
        
        profile = self.profiles[user_id]
        
        if profile.is_anonymized:
            return profile.anonymized_id
        
        # 次の匿名化番号を取得
        anonymized_count = sum(
            1 for p in self.profiles.values()
            if p.is_anonymized
        )
        anonymized_id = f"元メンバー#{anonymized_count + 1:03d}"
        
        # 匿名化
        profile.is_anonymized = True
        profile.is_active = False
        profile.anonymized_id = anonymized_id
        profile.display_name = anonymized_id
        profile.username = anonymized_id
        # 個人情報をクリア
        profile.relationship_note = ""
        
        profile.updated_at = datetime.now().isoformat()
        self._save_profiles()
        
        return anonymized_id
    
    def get_active_profiles(self) -> List[MemberProfile]:
        """アクティブなプロファイル一覧を取得"""
        return [
            p for p in self.profiles.values()
            if p.is_active and not p.is_anonymized
        ]
    
    def get_top_contributors(self, limit: int = 10) -> List[MemberProfile]:
        """投稿数上位のプロファイルを取得"""
        active = self.get_active_profiles()
        return sorted(active, key=lambda p: p.post_count, reverse=True)[:limit]
    
    def get_profile_by_display_name(self, display_name: str) -> Optional[MemberProfile]:
        """表示名でプロファイルを検索"""
        for profile in self.profiles.values():
            if profile.display_name == display_name:
                return profile
        return None
    
    def get_profiles_for_llm_context(self, user_ids: List[str] = None) -> str:
        """
        LLMコンテキスト用のプロファイルサマリーを生成
        
        Args:
            user_ids: 対象のユーザーID（Noneなら上位投稿者）
        """
        if user_ids:
            profiles = [
                self.profiles[uid]
                for uid in user_ids
                if uid in self.profiles
            ]
        else:
            profiles = self.get_top_contributors(10)
        
        if not profiles:
            return ""
        
        summaries = [p.get_summary_for_llm() for p in profiles]
        return "\n\n".join(summaries)
    
    def search_by_interest(self, keyword: str) -> List[MemberProfile]:
        """関心領域でプロファイルを検索"""
        results = []
        keyword_lower = keyword.lower()
        
        for profile in self.get_active_profiles():
            for interest in profile.interests:
                if keyword_lower in interest.lower():
                    results.append(profile)
                    break
        
        return results
    
    def get_inactive_members(self, days: int = 30) -> List[MemberProfile]:
        """指定日数以上アクティブでないメンバーを取得"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        inactive = []
        
        for profile in self.get_active_profiles():
            if profile.last_seen:
                try:
                    last_seen = datetime.fromisoformat(profile.last_seen)
                    if last_seen < cutoff:
                        inactive.append(profile)
                except ValueError:
                    pass
        
        return inactive


# シングルトンインスタンス
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """ProfileManagerのシングルトンインスタンスを取得"""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


# テスト用コード
if __name__ == "__main__":
    manager = get_profile_manager()
    
    # 既存プロファイルで初期化
    count = manager.initialize_with_existing_profiles()
    print(f"初期化されたプロファイル: {count}件")
    
    # 上位投稿者を表示
    print("\n--- 上位投稿者 ---")
    for profile in manager.get_top_contributors(5):
        print(f"{profile.display_name}: {profile.post_count}件 - {profile.position[:30]}...")
    
    # LLMコンテキスト用サマリー
    print("\n--- LLMコンテキスト ---")
    print(manager.get_profiles_for_llm_context()[:500] + "...")
