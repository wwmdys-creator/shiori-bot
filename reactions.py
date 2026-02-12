"""
reactions.py - 絵文字リアクション管理モジュール

栞が使用する絵文字リアクションを管理。
Q25決定: 複数の絵文字を状況に応じて使用（C案）

絵文字一覧:
- 📎: 予測を記録したとき（「しおり挟みました」）
- 📓: 議論まとめ・週報時（「フィールドノートに記録」）
- ❓: プレモーテム質問時（「確認したいことがあります」）
- ✅: 的中判定完了時（「記録完了」）
- 📖: 高信頼度メンバーへの特別反応（「研究協力者認定」）
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class ReactionType(Enum):
    """リアクションの種類"""
    BOOKMARK = "bookmark"           # 📎 予測記録
    FIELD_NOTE = "field_note"       # 📓 議論まとめ・週報
    QUESTION = "question"           # ❓ プレモーテム質問
    COMPLETE = "complete"           # ✅ 判定完了
    RESEARCH_PARTNER = "research"   # 📖 高信頼度メンバー
    THINKING = "thinking"           # 🤔 考え中
    SURPRISE = "surprise"           # 😲 驚き
    PARADOX = "paradox"            # 🤐 パラドックス回避


@dataclass
class ReactionConfig:
    """リアクション設定"""
    emoji: str
    name: str
    description: str
    min_trust_level: int = 1  # このリアクションを使用する最低信頼度
    
    def __str__(self) -> str:
        return self.emoji


# リアクション定義
REACTIONS: Dict[ReactionType, ReactionConfig] = {
    ReactionType.BOOKMARK: ReactionConfig(
        emoji="📎",
        name="しおり",
        description="予測を記録したとき",
    ),
    ReactionType.FIELD_NOTE: ReactionConfig(
        emoji="📓",
        name="フィールドノート",
        description="議論まとめ・週報時",
    ),
    ReactionType.QUESTION: ReactionConfig(
        emoji="❓",
        name="質問",
        description="プレモーテム質問時",
    ),
    ReactionType.COMPLETE: ReactionConfig(
        emoji="✅",
        name="完了",
        description="的中判定完了時",
    ),
    ReactionType.RESEARCH_PARTNER: ReactionConfig(
        emoji="📖",
        name="研究協力者",
        description="高信頼度メンバーへの特別反応",
        min_trust_level=4,  # Lv4以上
    ),
    ReactionType.THINKING: ReactionConfig(
        emoji="🤔",
        name="考え中",
        description="分析や検討中を表す",
    ),
    ReactionType.SURPRISE: ReactionConfig(
        emoji="😲",
        name="驚き",
        description="予想外の情報に対する反応",
    ),
    ReactionType.PARADOX: ReactionConfig(
        emoji="🤐",
        name="パラドックス",
        description="未来の情報を漏らしそうになったとき",
    ),
}


class ReactionManager:
    """リアクション管理クラス"""
    
    def __init__(self):
        self.reactions = REACTIONS
    
    def get_reaction(self, reaction_type: ReactionType) -> ReactionConfig:
        """リアクション設定を取得"""
        return self.reactions.get(reaction_type)
    
    def get_emoji(self, reaction_type: ReactionType) -> str:
        """絵文字を取得"""
        config = self.get_reaction(reaction_type)
        return config.emoji if config else ""
    
    def can_use_reaction(
        self,
        reaction_type: ReactionType,
        trust_level: int = 1
    ) -> bool:
        """
        指定した信頼度でこのリアクションを使用できるか判定
        """
        config = self.get_reaction(reaction_type)
        if not config:
            return False
        return trust_level >= config.min_trust_level
    
    def get_available_reactions(self, trust_level: int = 1) -> Dict[ReactionType, ReactionConfig]:
        """使用可能なリアクション一覧を取得"""
        return {
            rt: config
            for rt, config in self.reactions.items()
            if trust_level >= config.min_trust_level
        }
    
    # === 便利メソッド（直接絵文字を返す） ===
    
    @property
    def bookmark(self) -> str:
        """📎 予測記録"""
        return self.get_emoji(ReactionType.BOOKMARK)
    
    @property
    def field_note(self) -> str:
        """📓 フィールドノート"""
        return self.get_emoji(ReactionType.FIELD_NOTE)
    
    @property
    def question(self) -> str:
        """❓ 質問"""
        return self.get_emoji(ReactionType.QUESTION)
    
    @property
    def complete(self) -> str:
        """✅ 完了"""
        return self.get_emoji(ReactionType.COMPLETE)
    
    @property
    def research_partner(self) -> str:
        """📖 研究協力者"""
        return self.get_emoji(ReactionType.RESEARCH_PARTNER)
    
    @property
    def thinking(self) -> str:
        """🤔 考え中"""
        return self.get_emoji(ReactionType.THINKING)
    
    @property
    def surprise(self) -> str:
        """😲 驚き"""
        return self.get_emoji(ReactionType.SURPRISE)
    
    @property
    def paradox(self) -> str:
        """🤐 パラドックス"""
        return self.get_emoji(ReactionType.PARADOX)
    
    # === 文脈に応じたリアクション選択 ===
    
    def for_prediction_recorded(self) -> str:
        """予測を記録したとき"""
        return f"{self.bookmark} 予測記録"
    
    def for_discussion_summary(self) -> str:
        """議論まとめ"""
        return f"{self.field_note} 議論まとめ"
    
    def for_weekly_report(self) -> str:
        """週次レポート"""
        return f"{self.field_note} 今週のフィールドノート"
    
    def for_premortem(self) -> str:
        """プレモーテム質問"""
        return f"{self.question} プレモーテムメモ"
    
    def for_judgment_complete(self, is_hit: bool) -> str:
        """的中判定完了"""
        result = "的中" if is_hit else "外れ"
        return f"{self.complete} 予測結果: {result}"
    
    def for_high_trust_member(self, display_name: str) -> str:
        """高信頼度メンバーへの反応"""
        return f"{self.research_partner} {display_name}さん"
    
    def for_paradox_avoidance(self) -> str:
        """パラドックス回避"""
        return f"{self.paradox} ……あ、いえ、なんでもないです"
    
    def for_surprise(self, message: str = "") -> str:
        """驚き"""
        if message:
            return f"{self.surprise} {message}"
        return f"{self.surprise} えっ、それ本当ですか！？"
    
    def for_thinking(self, topic: str = "") -> str:
        """考え中"""
        if topic:
            return f"{self.thinking} {topic}について考え中..."
        return f"{self.thinking} 考え中..."


# シングルトンインスタンス
_reaction_manager: Optional[ReactionManager] = None


def get_reaction_manager() -> ReactionManager:
    """ReactionManagerのシングルトンインスタンスを取得"""
    global _reaction_manager
    if _reaction_manager is None:
        _reaction_manager = ReactionManager()
    return _reaction_manager


# 便利関数（直接インポートして使える）
def bookmark() -> str:
    """📎"""
    return get_reaction_manager().bookmark


def field_note() -> str:
    """📓"""
    return get_reaction_manager().field_note


def question() -> str:
    """❓"""
    return get_reaction_manager().question


def complete() -> str:
    """✅"""
    return get_reaction_manager().complete


def research_partner() -> str:
    """📖"""
    return get_reaction_manager().research_partner


# テスト用コード
if __name__ == "__main__":
    manager = get_reaction_manager()
    
    print("=== 利用可能なリアクション ===")
    for rt, config in manager.reactions.items():
        print(f"{config.emoji} {config.name}: {config.description}")
    
    print("\n=== 使用例 ===")
    print(manager.for_prediction_recorded())
    print(manager.for_discussion_summary())
    print(manager.for_premortem())
    print(manager.for_judgment_complete(is_hit=True))
    print(manager.for_judgment_complete(is_hit=False))
    print(manager.for_high_trust_member("そいやっさ"))
    print(manager.for_paradox_avoidance())
    print(manager.for_surprise("2027年にAGI！？"))
    
    print("\n=== 信頼度別の利用可能リアクション ===")
    for level in [1, 3, 4, 5]:
        available = manager.get_available_reactions(level)
        emojis = " ".join(c.emoji for c in available.values())
        print(f"Lv{level}: {emojis}")
