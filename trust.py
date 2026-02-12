"""
trust.py - 信頼度管理モジュール

栞（Shiori）Bot用の5段階信頼度システム
信頼度は口調のみに影響し、機能品質は全メンバー平等（Q5: A案）
全員Lv1からスタート（Q14: C案）
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import IntEnum


class TrustLevel(IntEnum):
    """信頼度レベル定義"""
    FIRST_MEETING = 1   # 📎 初対面 (0-19)
    COOPERATOR = 2      # 📓 協力者 (20-49)
    REGULAR = 3         # 🔖 常連情報源 (50-79)
    RESEARCHER = 4      # 📖 研究協力者 (80-99)
    MENTOR = 5          # 📚 恩師 (100)


# スコアからレベルへの変換テーブル
SCORE_TO_LEVEL = [
    (0, 19, TrustLevel.FIRST_MEETING),
    (20, 49, TrustLevel.COOPERATOR),
    (50, 79, TrustLevel.REGULAR),
    (80, 99, TrustLevel.RESEARCHER),
    (100, 100, TrustLevel.MENTOR),
]


# スコア変動ルール
SCORE_CHANGES = {
    # 上昇要因
    "talk_to_shiori": 3,        # 栞に話しかける
    "post_prediction": 2,        # 予測投稿
    "answer_question": 5,        # 質問に回答
    "self_review": 7,           # 過去予測の自発的振り返り
    "correct_record": 5,         # 記録の誤り訂正
    "request_summary": 2,        # 要約依頼
    "explain_concept": 4,        # 概念の説明
    "judgment_cooperation": 5,   # 的中判定への協力
    
    # 下降要因
    "inactive_30days": -10,      # 30日間反応なし
    "refuse_review": -3,         # 答え合わせ拒否
    "aggressive": -5,            # 攻撃的発言
}


# 信頼度レベルごとの口調ガイダンス
TONE_GUIDANCE = {
    1: """完全な丁寧語で応答してください。
「〇〇さん」と必ずさん付けで呼び、初対面の礼儀正しさを維持してください。
専門用語には必ず説明を添え、相手の理解を確認しながら進めてください。""",
    
    2: """丁寧語を基本としつつ、積極的に質問を投げかけてください。
「〇〇さんは以前〜とおっしゃっていましたが...」のように過去の発言に軽く触れることができます。
記録に協力してくださっていることへの感謝を時折表現してください。""",
    
    3: """やや砕けた表現が混じっても構いません。
過去の発言を引用して「前回のしおりと見比べると...」のような言い方ができます。
専門的な話題では相手の知識レベルを信頼して、詳しい説明を省くこともできます。
「あれ」「えっと」などの口語的表現も使えます。""",
    
    4: """卒論の章に言及する形で親しみを表現してください。
「これ、卒論の第3章で使わせてください！」のような発言が自然です。
タイムパラドックス寸止めのヒントとして「……あ、いえ、なんでもないです」と意味深に濁すことができます。
相手の洞察力を高く評価していることを示してください。""",
    
    5: """パラドックスぎりぎりのヒントを出すことができます。
「うーん、それについては...（長い沈黙）...やっぱり言えないです」のような演出が可能です。
「〇〇さんの考察、わたしの時代の教科書に載ってる理論と驚くほど近いです」のような最上級の評価を表現できます。
「恩師」として深い敬意と親しみを込めた口調で接してください。"""
}


@dataclass
class MemberTrust:
    """メンバーの信頼度情報"""
    user_id: str
    username: str
    display_name: str
    score: int = 0
    level: int = 1
    last_interaction: Optional[str] = None
    history: list = field(default_factory=list)
    specialties: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "MemberTrust":
        return cls(**data)


class TrustManager:
    """信頼度管理クラス"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.data_file = os.path.join(data_dir, "members.json")
        self.members: dict[str, MemberTrust] = {}
        self._load()
    
    def _load(self):
        """データファイルから読み込み"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, member_data in data.items():
                        self.members[user_id] = MemberTrust.from_dict(member_data)
            except Exception as e:
                print(f"信頼度データ読み込みエラー: {e}")
    
    def _save(self):
        """データファイルに保存"""
        os.makedirs(self.data_dir, exist_ok=True)
        data = {
            user_id: member.to_dict() 
            for user_id, member in self.members.items()
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_or_create_member(
        self, 
        user_id: str, 
        username: str = "",
        display_name: str = ""
    ) -> MemberTrust:
        """メンバーを取得または新規作成（全員Lv1スタート）"""
        if user_id not in self.members:
            self.members[user_id] = MemberTrust(
                user_id=user_id,
                username=username,
                display_name=display_name or username,
                score=0,
                level=1
            )
            self._save()
        return self.members[user_id]
    
    def get_member(self, user_id: str) -> Optional[MemberTrust]:
        """メンバーを取得"""
        return self.members.get(user_id)
    
    def get_level(self, user_id: str) -> int:
        """
        メンバーの信頼度レベルを取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            信頼度レベル（1-5）、存在しない場合は1
        """
        member = self.members.get(user_id)
        return member.level if member else 1
    
    def get_tone_guidance(self, user_id: str) -> str:
        """
        信頼度に応じた口調ガイダンスを取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            LLMプロンプトに含めるべき口調ガイダンス
        """
        level = self.get_level(user_id)
        member = self.members.get(user_id)
        display_name = member.display_name if member else "この方"
        
        base_guidance = TONE_GUIDANCE.get(level, TONE_GUIDANCE[1])
        
        # レベル3以上の場合、メンバーの専門分野情報も追加
        specialty_note = ""
        if level >= 3 and member and member.specialties:
            specialties = "、".join(member.specialties)
            specialty_note = f"\n\n{display_name}さんの専門分野: {specialties}\nこれらの話題では相手の専門性を信頼して話してください。"
        
        return f"""## 信頼度レベル: {level} ({self._get_level_name(level)})

{base_guidance}{specialty_note}"""
    
    def record_interaction(self, user_id: str, interaction_type: str):
        """
        インタラクションを記録（bot.pyからの呼び出し用）
        
        Args:
            user_id: ユーザーID
            interaction_type: インタラクションの種類
                - "mention": メンション（話しかける）
                - "reply": 返信
                - その他のアクションタイプ
        """
        # メンバーが存在しない場合は作成
        if user_id not in self.members:
            self.get_or_create_member(user_id)
        
        # interaction_typeをaction名にマッピング
        action_mapping = {
            "mention": "talk_to_shiori",
            "reply": "talk_to_shiori",
            "prediction": "post_prediction",
            "answer": "answer_question",
            "summary_request": "request_summary",
        }
        
        action = action_mapping.get(interaction_type, "talk_to_shiori")
        self.update_score(user_id, action, reason=f"{interaction_type}による記録")
    
    def update_score(
        self, 
        user_id: str, 
        action: str,
        reason: str = ""
    ) -> tuple[int, int, bool]:
        """
        スコアを更新
        
        Returns:
            (新スコア, 新レベル, レベル変化があったか)
        """
        member = self.members.get(user_id)
        if not member:
            return (0, 1, False)
        
        change = SCORE_CHANGES.get(action, 0)
        old_level = member.level
        
        # スコア更新（0-100の範囲に制限）
        member.score = max(0, min(100, member.score + change))
        
        # レベル再計算
        member.level = self._calculate_level(member.score)
        
        # 最終インタラクション時刻更新
        member.last_interaction = datetime.now().isoformat()
        
        # 履歴追加
        member.history.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "change": change,
            "reason": reason,
            "new_score": member.score,
            "new_level": member.level
        })
        
        # 履歴は最新50件のみ保持
        if len(member.history) > 50:
            member.history = member.history[-50:]
        
        self._save()
        
        level_changed = old_level != member.level
        return (member.score, member.level, level_changed)
    
    def _calculate_level(self, score: int) -> int:
        """スコアからレベルを計算"""
        for min_score, max_score, level in SCORE_TO_LEVEL:
            if min_score <= score <= max_score:
                return level
        return TrustLevel.FIRST_MEETING
    
    def check_inactive_members(self) -> list[str]:
        """
        30日間非アクティブなメンバーをチェックしスコア減少
        
        Returns:
            スコアが減少したメンバーのuser_idリスト
        """
        affected = []
        threshold = datetime.now() - timedelta(days=30)
        
        for user_id, member in self.members.items():
            if member.last_interaction:
                last = datetime.fromisoformat(member.last_interaction)
                if last < threshold:
                    self.update_score(user_id, "inactive_30days", "30日間非アクティブ")
                    affected.append(user_id)
        
        return affected
    
    def add_specialty(self, user_id: str, specialty: str):
        """専門分野を追加"""
        member = self.members.get(user_id)
        if member and specialty not in member.specialties:
            member.specialties.append(specialty)
            self._save()
    
    def get_member_info(self, user_id: str) -> Optional[dict]:
        """LLMコンテキスト用のメンバー情報を取得"""
        member = self.members.get(user_id)
        if not member:
            return None
        
        return {
            "user_id": member.user_id,
            "display_name": member.display_name,
            "trust_level": member.level,
            "trust_score": member.score,
            "specialties": member.specialties,
            "level_name": self._get_level_name(member.level)
        }
    
    def _get_level_name(self, level: int) -> str:
        """レベル名を取得"""
        names = {
            1: "📎 初対面",
            2: "📓 協力者",
            3: "🔖 常連情報源",
            4: "📖 研究協力者",
            5: "📚 恩師"
        }
        return names.get(level, "📎 初対面")
    
    def anonymize_member(self, user_id: str, anonymous_id: str):
        """
        メンバーを匿名化（離脱時処理 Q26: B案）
        
        Args:
            user_id: 元のユーザーID
            anonymous_id: 匿名ID（例: "元メンバー#001"）
        """
        member = self.members.get(user_id)
        if member:
            # 匿名化
            member.username = anonymous_id
            member.display_name = anonymous_id
            member.specialties = []
            member.history = []
            
            # IDを変更して保存
            del self.members[user_id]
            self.members[anonymous_id] = member
            member.user_id = anonymous_id
            
            self._save()
    
    def get_all_members_summary(self) -> list[dict]:
        """全メンバーのサマリーを取得"""
        return [
            {
                "display_name": m.display_name,
                "level": m.level,
                "level_name": self._get_level_name(m.level),
                "score": m.score
            }
            for m in sorted(
                self.members.values(),
                key=lambda x: x.score,
                reverse=True
            )
        ]


# シングルトンインスタンス
_trust_manager: Optional[TrustManager] = None


def get_trust_manager(data_dir: str = "data") -> TrustManager:
    """TrustManagerインスタンスを取得"""
    global _trust_manager
    if _trust_manager is None:
        _trust_manager = TrustManager(data_dir)
    return _trust_manager
