"""
judgments.py - 的中判定管理モジュール

Q27決定: 予測の答え合わせ（的中/外れ）を栞が提案する
- メンション時に、関連する期限到来予測があれば「ついでに」確認
- 完全な自発的投稿は行わない（Q1整合性）

判定結果:
- ✅ 的中（HIT）
- ❌ 外れ（MISS）
- ⏳ 部分的中（PARTIAL）
- 🔄 判定保留（PENDING）
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class JudgmentResult(Enum):
    """判定結果の種類"""
    HIT = "hit"           # ✅ 的中
    MISS = "miss"         # ❌ 外れ
    PARTIAL = "partial"   # ⏳ 部分的中
    PENDING = "pending"   # 🔄 判定保留
    UNKNOWN = "unknown"   # 未判定


@dataclass
class Judgment:
    """的中判定レコード"""
    judgment_id: str              # 判定ID（J0001形式）
    prediction_id: str            # 対象予測ID（#0001形式）
    user_id: int                  # 判定を行ったユーザーID
    result: str                   # 判定結果（JudgmentResult.value）
    judged_at: str                # 判定日時（ISO形式）
    notes: str                    # 備考
    evidence_url: Optional[str]   # 根拠URL（任意）
    proposed_by: str              # 提案者（"shiori" or user_id）
    confirmed: bool               # 確定済みフラグ
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Judgment':
        return cls(**data)


class JudgmentManager:
    """的中判定管理クラス"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.judgments_file = self.data_dir / "judgments.json"
        self.judgments: Dict[str, Judgment] = {}
        self._lock = asyncio.Lock()
        self._load_judgments()
    
    def _load_judgments(self) -> None:
        """判定データを読み込み"""
        if self.judgments_file.exists():
            try:
                with open(self.judgments_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.judgments = {
                        k: Judgment.from_dict(v) 
                        for k, v in data.get('judgments', {}).items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[JudgmentManager] Failed to load judgments: {e}")
                self.judgments = {}
        else:
            self.judgments = {}
    
    async def _save_judgments(self) -> None:
        """判定データを保存"""
        async with self._lock:
            data = {
                'judgments': {k: v.to_dict() for k, v in self.judgments.items()},
                'updated_at': datetime.now().isoformat()
            }
            with open(self.judgments_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_judgment_id(self) -> str:
        """新しい判定IDを生成"""
        existing_ids = [
            int(jid[1:]) for jid in self.judgments.keys() 
            if jid.startswith('J') and jid[1:].isdigit()
        ]
        next_num = max(existing_ids, default=0) + 1
        return f"J{next_num:04d}"
    
    async def create_judgment(
        self,
        prediction_id: str,
        user_id: int,
        result: JudgmentResult,
        notes: str = "",
        evidence_url: Optional[str] = None,
        proposed_by: str = "shiori",
        confirmed: bool = False
    ) -> Judgment:
        """
        新しい判定を作成
        
        Args:
            prediction_id: 対象予測ID
            user_id: 判定を行ったユーザーID
            result: 判定結果
            notes: 備考
            evidence_url: 根拠URL
            proposed_by: 提案者
            confirmed: 確定済みフラグ
        
        Returns:
            作成されたJudgment
        """
        judgment_id = self._generate_judgment_id()
        
        judgment = Judgment(
            judgment_id=judgment_id,
            prediction_id=prediction_id,
            user_id=user_id,
            result=result.value,
            judged_at=datetime.now().isoformat(),
            notes=notes,
            evidence_url=evidence_url,
            proposed_by=proposed_by,
            confirmed=confirmed
        )
        
        self.judgments[judgment_id] = judgment
        await self._save_judgments()
        
        return judgment
    
    async def confirm_judgment(
        self,
        judgment_id: str,
        confirmed_by: int,
        notes: Optional[str] = None
    ) -> Optional[Judgment]:
        """
        判定を確定する
        
        Args:
            judgment_id: 判定ID
            confirmed_by: 確定したユーザーID
            notes: 追加備考（任意）
        
        Returns:
            更新されたJudgment、または見つからない場合None
        """
        if judgment_id not in self.judgments:
            return None
        
        judgment = self.judgments[judgment_id]
        judgment.confirmed = True
        judgment.user_id = confirmed_by
        
        if notes:
            judgment.notes = f"{judgment.notes}\n[確定時追記] {notes}".strip()
        
        await self._save_judgments()
        return judgment
    
    async def update_judgment_result(
        self,
        judgment_id: str,
        new_result: JudgmentResult,
        notes: str = ""
    ) -> Optional[Judgment]:
        """
        判定結果を更新
        
        Args:
            judgment_id: 判定ID
            new_result: 新しい判定結果
            notes: 更新理由
        
        Returns:
            更新されたJudgment
        """
        if judgment_id not in self.judgments:
            return None
        
        judgment = self.judgments[judgment_id]
        old_result = judgment.result
        judgment.result = new_result.value
        
        if notes:
            judgment.notes = f"{judgment.notes}\n[結果更新 {old_result}→{new_result.value}] {notes}".strip()
        
        await self._save_judgments()
        return judgment
    
    def get_judgment(self, judgment_id: str) -> Optional[Judgment]:
        """判定を取得"""
        return self.judgments.get(judgment_id)
    
    def get_judgments_for_prediction(self, prediction_id: str) -> List[Judgment]:
        """特定の予測に対する全判定を取得"""
        return [
            j for j in self.judgments.values()
            if j.prediction_id == prediction_id
        ]
    
    def get_latest_judgment_for_prediction(self, prediction_id: str) -> Optional[Judgment]:
        """特定の予測に対する最新の判定を取得"""
        judgments = self.get_judgments_for_prediction(prediction_id)
        if not judgments:
            return None
        return max(judgments, key=lambda j: j.judged_at)
    
    def get_user_judgments(self, user_id: int) -> List[Judgment]:
        """ユーザーに関連する全判定を取得"""
        return [
            j for j in self.judgments.values()
            if j.user_id == user_id
        ]
    
    def get_pending_judgments(self) -> List[Judgment]:
        """未確定の判定を取得"""
        return [
            j for j in self.judgments.values()
            if not j.confirmed
        ]
    
    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """
        ユーザーの判定統計を取得
        
        Returns:
            {
                'total': 総判定数,
                'hit': 的中数,
                'miss': 外れ数,
                'partial': 部分的中数,
                'pending': 保留数
            }
        """
        judgments = self.get_user_judgments(user_id)
        confirmed_judgments = [j for j in judgments if j.confirmed]
        
        stats = {
            'total': len(confirmed_judgments),
            'hit': 0,
            'miss': 0,
            'partial': 0,
            'pending': 0
        }
        
        for j in confirmed_judgments:
            if j.result in stats:
                stats[j.result] += 1
        
        return stats
    
    def calculate_accuracy(self, user_id: int) -> Optional[float]:
        """
        ユーザーの的中率を計算
        
        Returns:
            的中率（0.0〜1.0）、判定がない場合はNone
        """
        stats = self.get_user_stats(user_id)
        
        # 的中・外れのみカウント（部分的中は0.5として計算）
        total_judged = stats['hit'] + stats['miss'] + stats['partial']
        if total_judged == 0:
            return None
        
        score = stats['hit'] + (stats['partial'] * 0.5)
        return score / total_judged


class DueDateChecker:
    """
    期限到来予測チェッカー
    
    Q27整合性: メンション応答時に「ついでに」確認する形式
    """
    
    def __init__(self, predictions_manager, judgment_manager: JudgmentManager):
        """
        Args:
            predictions_manager: PredictionManagerインスタンス
            judgment_manager: JudgmentManagerインスタンス
        """
        self.predictions = predictions_manager
        self.judgments = judgment_manager
    
    def check_due_predictions(
        self,
        user_id: int,
        check_window_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        期限到来した予測をチェック
        
        Args:
            user_id: チェック対象のユーザーID
            check_window_days: 期限到来とみなす日数（期限から何日後まで）
        
        Returns:
            期限到来した予測のリスト
        """
        now = datetime.now()
        due_predictions = []
        
        # ユーザーの予測を取得
        user_predictions = self.predictions.get_user_predictions(user_id)
        
        for pred in user_predictions:
            # 既に判定済みの予測はスキップ
            existing_judgment = self.judgments.get_latest_judgment_for_prediction(
                pred.prediction_id
            )
            if existing_judgment and existing_judgment.confirmed:
                continue
            
            # 時間軸をチェック
            timeline = pred.timeline
            if not timeline:
                continue
            
            # end_year が存在し、現在年以前の場合は期限到来
            end_year = timeline.get('end_year')
            if end_year and end_year != '?':
                try:
                    end_year_int = int(end_year)
                    # 期限年の年末を基準に判定
                    deadline = datetime(end_year_int, 12, 31)
                    days_since_deadline = (now - deadline).days
                    
                    # 期限を過ぎて check_window_days 以内なら通知対象
                    if 0 <= days_since_deadline <= check_window_days:
                        due_predictions.append({
                            'prediction': pred,
                            'deadline': deadline,
                            'days_overdue': days_since_deadline
                        })
                except ValueError:
                    continue
        
        return due_predictions
    
    def get_oldest_due_prediction(
        self,
        user_id: int,
        check_window_days: int = 90
    ) -> Optional[Dict[str, Any]]:
        """
        最も古い期限到来予測を1件取得（メンション応答で「ついでに」聞くため）
        
        Args:
            user_id: チェック対象のユーザーID
            check_window_days: 期限到来とみなす日数
        
        Returns:
            最も古い期限到来予測、またはNone
        """
        due_predictions = self.check_due_predictions(user_id, check_window_days)
        
        if not due_predictions:
            return None
        
        # 最も期限が古いものを返す
        return min(due_predictions, key=lambda p: p['deadline'])
    
    def format_due_reminder(self, due_info: Dict[str, Any]) -> str:
        """
        期限到来リマインダーを栞の口調でフォーマット
        
        Args:
            due_info: check_due_predictions()の戻り値の1要素
        
        Returns:
            栞の口調でフォーマットされたリマインダー
        """
        pred = due_info['prediction']
        days = due_info['days_overdue']
        
        # 日数に応じた表現
        if days == 0:
            time_expr = "ちょうど期限"
        elif days <= 7:
            time_expr = "そろそろ期限"
        elif days <= 30:
            time_expr = "期限から少し経ちました"
        else:
            time_expr = f"期限から{days}日ほど経っています"
        
        # 予測内容の短縮表示
        content = pred.content
        if len(content) > 50:
            content = content[:47] + "..."
        
        reminder = (
            f"あ、それと📎、{pred.user_name}さんの予測 {pred.prediction_id}"
            f"『{content}』、{time_expr}ですね。結果はどうでしたか？"
        )
        
        return reminder


# 判定結果を栞の口調で表現するヘルパー
def format_judgment_response(judgment: Judgment, prediction_content: str) -> str:
    """
    判定記録完了メッセージを生成
    
    Args:
        judgment: 記録された判定
        prediction_content: 予測の内容
    
    Returns:
        栞の口調でフォーマットされたメッセージ
    """
    result_emoji = {
        'hit': '✅',
        'miss': '❌',
        'partial': '⏳',
        'pending': '🔄',
        'unknown': '❓'
    }
    
    result_text = {
        'hit': '的中',
        'miss': '外れ',
        'partial': '部分的中',
        'pending': '判定保留',
        'unknown': '未判定'
    }
    
    emoji = result_emoji.get(judgment.result, '❓')
    text = result_text.get(judgment.result, '未判定')
    
    # 予測内容の短縮
    if len(prediction_content) > 40:
        prediction_content = prediction_content[:37] + "..."
    
    response = (
        f"📎 予測結果 {judgment.prediction_id}\n"
        f"内容: 「{prediction_content}」\n"
        f"結果: {emoji} {text}（{judgment.judged_at[:10]}）"
    )
    
    if judgment.notes:
        response += f"\n備考: {judgment.notes}"
    
    return response


# モジュールテスト用
if __name__ == "__main__":
    import asyncio
    
    async def test_judgments():
        manager = JudgmentManager(data_dir="data")
        
        # テスト判定の作成
        judgment = await manager.create_judgment(
            prediction_id="#0001",
            user_id=123456789,
            result=JudgmentResult.HIT,
            notes="GPT-5 turbo発表により的中",
            proposed_by="shiori"
        )
        
        print(f"Created judgment: {judgment.judgment_id}")
        print(f"Result: {judgment.result}")
        
        # 統計の確認
        stats = manager.get_user_stats(123456789)
        print(f"User stats: {stats}")
        
        # 的中率
        accuracy = manager.calculate_accuracy(123456789)
        print(f"Accuracy: {accuracy}")
    
    asyncio.run(test_judgments())
