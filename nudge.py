"""
Nudge Manager - 低活動メンバーへのさりげない言及システム
Q8決定: 応答内でさりげなく低活動メンバーに言及し、参加を促す
"""

import discord
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
import random


class NudgeManager:
    """低活動メンバーへのさりげない nudge システム"""
    
    def __init__(self, bot):
        self.bot = bot
        self.last_activity: Dict[int, datetime] = {}  # user_id -> last_activity_time
        self.nudge_cooldown: Dict[int, datetime] = {}  # user_id -> last_nudge_time
        self.INACTIVITY_THRESHOLD_DAYS = 14  # 14日間活動なしで低活動と判定
        self.NUDGE_COOLDOWN_DAYS = 7  # 同じメンバーへのnudgeは7日に1回まで
    
    def update_activity(self, user_id: int):
        """メンバーの活動を記録"""
        self.last_activity[user_id] = datetime.now(timezone.utc)
    
    def build_nudge_hint(self) -> Optional[str]:
        """
        さりげないnudgeヒントを生成
        低活動メンバーがいれば、応答に含めるための文字列を返す
        
        Returns:
            str or None: nudgeヒント文字列（なければNone）
        """
        now = datetime.now(timezone.utc)
        inactive_threshold = now - timedelta(days=self.INACTIVITY_THRESHOLD_DAYS)
        
        # 低活動メンバーを収集
        inactive_members = []
        for user_id, last_time in self.last_activity.items():
            if last_time < inactive_threshold:
                # nudge cooldown チェック
                if user_id in self.nudge_cooldown:
                    if now - self.nudge_cooldown[user_id] < timedelta(days=self.NUDGE_COOLDOWN_DAYS):
                        continue  # まだクールダウン中
                
                # メンバー情報を取得
                member = self._get_member_info(user_id)
                if member:
                    inactive_members.append(member)
        
        if not inactive_members:
            return None
        
        # ランダムに1人選択
        chosen = random.choice(inactive_members)
        
        # nudge cooldownを更新
        self.nudge_cooldown[chosen['user_id']] = now
        
        # さりげないヒント文を生成
        return self._generate_nudge_text(chosen)
    
    def _get_member_info(self, user_id: int) -> Optional[Dict]:
        """メンバー情報を取得"""
        try:
            # bot.guildsから最初のguildを取得（複数guildsがある場合は調整が必要）
            if not self.bot.guilds:
                return None
            
            guild = self.bot.guilds[0]
            member = guild.get_member(user_id)
            
            if not member:
                return None
            
            return {
                'user_id': user_id,
                'name': member.display_name,
                'username': member.name
            }
        except Exception:
            return None
    
    def _generate_nudge_text(self, member: Dict) -> str:
        """
        さりげないnudgeテキストを生成
        
        Q8で決定された「応答内でさりげなく言及」を実装
        """
        templates = [
            f"（そういえば、最近{member['name']}さんをお見かけしませんね……ご意見聞きたいところです）",
            f"この話題、以前{member['name']}さんが関連する発言をされていたような……最近どうされているんでしょうか",
            f"……あ、{member['name']}さんもこの議論に参加してくださったら面白くなりそうですね",
        ]
        
        return "\n\n" + random.choice(templates)
    
    def should_nudge(self, context: str = "") -> bool:
        """
        現在の状況でnudgeを実施すべきか判定
        
        Args:
            context: 現在の会話の文脈（将来の拡張用）
        
        Returns:
            bool: nudgeすべきならTrue
        """
        # 20%の確率でnudgeを試行
        if random.random() > 0.2:
            return False
        
        # 低活動メンバーがいるかチェック
        hint = self.build_nudge_hint()
        return hint is not None
