"""
passive_monitor.py - 受動監視モジュール

栞（Shiori）Bot用のバックグラウンド予測検出機能
メンションなしでも予測投稿を内部的に監視・記録（Q3: A案）
監視範囲はMAIN CHANNELカテゴリのみ（Q4: B案）
"""

import re
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from predictions import TimelineRange


@dataclass
class DetectedPrediction:
    """検出された予測"""
    message_id: str
    channel_id: str
    user_id: str
    username: str
    content: str
    timeline: TimelineRange
    detected_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    processed: bool = False  # 予測台帳に登録済みか


class PassiveMonitor:
    """受動監視クラス"""
    
    # 予測的キーワードパターン
    PREDICTION_PATTERNS = [
        r'になる',
        r'になっている',
        r'が実現',
        r'が達成',
        r'が完成',
        r'が登場',
        r'が普及',
        r'が可能',
        r'までに',
        r'以降',
        r'頃に',
        r'くらいに',
        r'と予想',
        r'と予測',
        r'だろう',
        r'はず',
        r'見込み',
        r'かもしれない',
        r'であろう',
    ]
    
    # 年号パターン
    YEAR_PATTERN = r'20[2-9]\d'
    
    def __init__(self, main_category_id: Optional[str] = None):
        """
        初期化
        
        Args:
            main_category_id: 監視対象のカテゴリID
        """
        self.main_category_id = main_category_id or os.getenv(
            "MAIN_CHANNEL_CATEGORY_ID"
        )
        self.detected_predictions: list[DetectedPrediction] = []
        self._llm = None
    
    @property
    def llm(self):
        """LLMモジュールを遅延読み込み"""
        if self._llm is None:
            from llm import get_llm
            self._llm = get_llm()
        return self._llm
    
    def should_monitor_channel(
        self, 
        channel_id: str,
        category_id: Optional[str] = None
    ) -> bool:
        """
        このチャンネルを監視すべきか判定（Q4: B案）
        
        Args:
            channel_id: チャンネルID
            category_id: チャンネルのカテゴリID
        """
        if not self.main_category_id:
            # カテゴリIDが設定されていない場合は全チャンネル監視
            return True
        
        return category_id == self.main_category_id
    
    def detect_prediction(self, content: str) -> bool:
        """
        メッセージに予測が含まれるか判定
        
        Args:
            content: メッセージ内容
        
        Returns:
            予測が含まれる場合True
        """
        # 年号が含まれているか
        if not re.search(self.YEAR_PATTERN, content):
            return False
        
        # 予測的キーワードが含まれているか
        for pattern in self.PREDICTION_PATTERNS:
            if re.search(pattern, content):
                return True
        
        return False
    
    def extract_timeline(self, content: str) -> Optional[TimelineRange]:
        """
        メッセージから時間軸を抽出
        
        Args:
            content: メッセージ内容
        
        Returns:
            抽出された時間軸（抽出できない場合None）
        """
        if not re.search(self.YEAR_PATTERN, content):
            return None
        
        return TimelineRange.parse(content)
    
    def process_message(
        self,
        message_id: str,
        channel_id: str,
        category_id: Optional[str],
        user_id: str,
        username: str,
        content: str,
        is_mention: bool = False
    ) -> Optional[DetectedPrediction]:
        """
        メッセージを処理
        
        Args:
            message_id: メッセージID
            channel_id: チャンネルID
            category_id: カテゴリID
            user_id: ユーザーID
            username: ユーザー名
            content: メッセージ内容
            is_mention: 栞へのメンションか
        
        Returns:
            予測が検出された場合、DetectedPrediction
        """
        # 監視対象チャンネルかチェック
        if not self.should_monitor_channel(channel_id, category_id):
            return None
        
        # 予測を検出
        if not self.detect_prediction(content):
            return None
        
        # 時間軸を抽出
        timeline = self.extract_timeline(content)
        if not timeline:
            return None
        
        # 検出結果を記録
        detected = DetectedPrediction(
            message_id=message_id,
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            content=content,
            timeline=timeline
        )
        
        self.detected_predictions.append(detected)
        
        # 最大保持数を超えたら古いものを削除
        if len(self.detected_predictions) > 1000:
            self.detected_predictions = self.detected_predictions[-500:]
        
        return detected
    
    def get_unprocessed(
        self, 
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> list[DetectedPrediction]:
        """
        未処理の検出予測を取得
        
        Args:
            user_id: 特定ユーザーのみ取得する場合
            limit: 最大取得数
        """
        results = []
        
        for dp in reversed(self.detected_predictions):
            if dp.processed:
                continue
            
            if user_id and dp.user_id != user_id:
                continue
            
            results.append(dp)
            
            if len(results) >= limit:
                break
        
        return results
    
    def mark_processed(self, message_id: str):
        """検出予測を処理済みにする"""
        for dp in self.detected_predictions:
            if dp.message_id == message_id:
                dp.processed = True
                break
    
    def get_detection_by_message(
        self, 
        message_id: str
    ) -> Optional[DetectedPrediction]:
        """メッセージIDで検出予測を取得"""
        for dp in self.detected_predictions:
            if dp.message_id == message_id:
                return dp
        return None
    
    async def analyze_and_register(
        self,
        detected: DetectedPrediction
    ) -> dict:
        """
        検出された予測をLLMで分析して予測台帳に登録
        
        Args:
            detected: 検出された予測
        
        Returns:
            登録結果（予測ID、カテゴリ等）
        """
        from categories import get_category_manager
        from predictions import get_prediction_ledger
        
        # LLMで分析
        analysis = await self.llm.analyze_prediction(detected.content)
        
        # カテゴリを決定
        category_manager = get_category_manager()
        category = await category_manager.categorize(
            detected.content,
            self.llm
        )
        
        # 予測台帳に登録
        ledger = get_prediction_ledger()
        prediction, related, diff_note = ledger.add_prediction(
            user_id=detected.user_id,
            username=detected.username,
            content=detected.content,
            category=category,
            timeline=detected.timeline,
            message_id=detected.message_id,
            channel_id=detected.channel_id
        )
        
        # 処理済みにマーク
        self.mark_processed(detected.message_id)
        
        return {
            "prediction_id": prediction.id,
            "category": category,
            "timeline": str(prediction.timeline),
            "related_prediction": related,
            "diff_note": diff_note
        }
    
    def format_detection_summary(
        self,
        detected: DetectedPrediction,
        registration_result: Optional[dict] = None
    ) -> str:
        """検出結果をDiscord投稿用にフォーマット"""
        lines = [
            f"📎 予測記録 #{registration_result['prediction_id']}" 
            if registration_result else "📎 予測を検出しました"
        ]
        
        lines.append(f"投稿者: {detected.username}さん")
        lines.append(f"内容: 「{detected.content[:100]}{'...' if len(detected.content) > 100 else ''}」")
        
        if registration_result:
            lines.append(f"カテゴリ: {registration_result['category']}")
            lines.append(f"時間軸: {registration_result['timeline']}")
            
            if registration_result.get("diff_note"):
                lines.append(f"前回との差分: {registration_result['diff_note']}")
        else:
            lines.append(f"時間軸: {detected.timeline}")
        
        return "\n".join(lines)
    
    def get_statistics(self) -> dict:
        """統計情報を取得"""
        total = len(self.detected_predictions)
        processed = sum(1 for dp in self.detected_predictions if dp.processed)
        unprocessed = total - processed
        
        # ユーザー別統計
        by_user = {}
        for dp in self.detected_predictions:
            by_user[dp.username] = by_user.get(dp.username, 0) + 1
        
        return {
            "total_detected": total,
            "processed": processed,
            "unprocessed": unprocessed,
            "by_user": dict(sorted(
                by_user.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
        }


# シングルトンインスタンス
_passive_monitor: Optional[PassiveMonitor] = None


def get_passive_monitor(
    main_category_id: Optional[str] = None
) -> PassiveMonitor:
    """PassiveMonitorインスタンスを取得"""
    global _passive_monitor
    if _passive_monitor is None:
        _passive_monitor = PassiveMonitor(main_category_id)
    return _passive_monitor
