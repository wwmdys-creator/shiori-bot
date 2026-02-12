"""
predictions.py - 予測台帳モジュール

栞（Shiori）Bot用の予測記録・検索・差分検出機能
時間軸は範囲として記録（Q21: C案）
差分指摘は範囲が重複しなくなったら（Q22: C案）
"""

import os
import json
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TimelineRange:
    """時間軸の範囲"""
    start: Optional[int] = None  # 開始年（不明ならNone）
    end: Optional[int] = None    # 終了年（不明ならNone）
    
    def __str__(self) -> str:
        start_str = str(self.start) if self.start else "?"
        end_str = str(self.end) if self.end else "?"
        return f"{start_str}-{end_str}年"
    
    def overlaps(self, other: "TimelineRange") -> bool:
        """別の範囲と重複するか判定（Q22: C案）"""
        # どちらかが完全に不明な場合は重複ありとみなす
        if (self.start is None and self.end is None) or \
           (other.start is None and other.end is None):
            return True
        
        # 片方だけ不明な場合の処理
        self_start = self.start or 1900
        self_end = self.end or 2100
        other_start = other.start or 1900
        other_end = other.end or 2100
        
        # 重複判定
        return not (self_end < other_start or other_end < self_start)
    
    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end}
    
    @classmethod
    def from_dict(cls, data: dict) -> "TimelineRange":
        return cls(start=data.get("start"), end=data.get("end"))
    
    @classmethod
    def parse(cls, text: str) -> "TimelineRange":
        """
        テキストから時間軸を解析（Q21: C案）
        
        Examples:
            "2030年にAGI" → 2030-2030年
            "2030年代半ば" → 2034-2036年
            "2030〜2035年" → 2030-2035年
            "2030年までに" → ?-2030年
            "2030年以降" → 2030-?年
        """
        # 年号パターン
        year_pattern = r'20[2-9]\d'
        
        # 範囲パターン（2030〜2035年、2030-2035年）
        range_match = re.search(
            rf'({year_pattern})\s*[〜～\-−]\s*({year_pattern})', 
            text
        )
        if range_match:
            return cls(
                start=int(range_match.group(1)),
                end=int(range_match.group(2))
            )
        
        # 「〜年代半ば」パターン
        mid_decade_match = re.search(rf'({year_pattern[:-1]})0年代半ば', text)
        if mid_decade_match:
            decade = int(mid_decade_match.group(1) + "0")
            return cls(start=decade + 4, end=decade + 6)
        
        # 「〜年代前半」パターン
        early_decade_match = re.search(rf'({year_pattern[:-1]})0年代前半', text)
        if early_decade_match:
            decade = int(early_decade_match.group(1) + "0")
            return cls(start=decade, end=decade + 4)
        
        # 「〜年代後半」パターン
        late_decade_match = re.search(rf'({year_pattern[:-1]})0年代後半', text)
        if late_decade_match:
            decade = int(late_decade_match.group(1) + "0")
            return cls(start=decade + 5, end=decade + 9)
        
        # 「〜年代」パターン
        decade_match = re.search(rf'({year_pattern[:-1]})0年代', text)
        if decade_match:
            decade = int(decade_match.group(1) + "0")
            return cls(start=decade, end=decade + 9)
        
        # 「〜年までに」パターン
        by_year_match = re.search(rf'({year_pattern})年まで', text)
        if by_year_match:
            return cls(start=None, end=int(by_year_match.group(1)))
        
        # 「〜年以降」パターン
        after_year_match = re.search(rf'({year_pattern})年以降', text)
        if after_year_match:
            return cls(start=int(after_year_match.group(1)), end=None)
        
        # 単一年号パターン
        single_match = re.search(rf'({year_pattern})年?', text)
        if single_match:
            year = int(single_match.group(1))
            return cls(start=year, end=year)
        
        return cls()


@dataclass
class Prediction:
    """予測レコード"""
    id: int
    user_id: str
    username: str
    content: str
    category: str
    timeline: TimelineRange
    created_at: str
    message_id: str
    channel_id: str
    related_prediction_id: Optional[int] = None
    diff_note: Optional[str] = None
    result: str = "未判定"  # 未判定 / 的中 / 外れ / 部分的中
    result_note: Optional[str] = None
    result_date: Optional[str] = None
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["timeline"] = self.timeline.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Prediction":
        timeline_data = data.pop("timeline", {})
        data["timeline"] = TimelineRange.from_dict(timeline_data)
        return cls(**data)
    
    def format_record(self) -> str:
        """フォーマットされた記録文字列を生成"""
        lines = [
            f"📎 予測記録 #{self.id:04d}",
            f"投稿者: {self.username}さん / {self.created_at[:10]}",
            f"内容: 「{self.content}」",
            f"カテゴリ: {self.category}",
            f"時間軸: {self.timeline}",
        ]
        
        if self.related_prediction_id:
            lines.append(f"前回関連予測: #{self.related_prediction_id:04d}（{self.diff_note}）")
        
        if self.result != "未判定":
            result_emoji = {"的中": "✅", "外れ": "❌", "部分的中": "🔶"}.get(self.result, "")
            lines.append(f"結果: {result_emoji} {self.result}")
            if self.result_note:
                lines.append(f"備考: {self.result_note}")
        
        return "\n".join(lines)


class PredictionLedger:
    """予測台帳管理クラス"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.data_file = os.path.join(data_dir, "predictions.json")
        self.predictions: list[Prediction] = []
        self.next_id = 1
        self._load()
    
    def _load(self):
        """データファイルから読み込み"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.predictions = [
                        Prediction.from_dict(p) for p in data.get("predictions", [])
                    ]
                    self.next_id = data.get("next_id", 1)
            except Exception as e:
                print(f"予測データ読み込みエラー: {e}")
    
    def _save(self):
        """データファイルに保存"""
        os.makedirs(self.data_dir, exist_ok=True)
        data = {
            "predictions": [p.to_dict() for p in self.predictions],
            "next_id": self.next_id
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_prediction(
        self,
        user_id: str,
        username: str,
        content: str,
        category: str,
        timeline: TimelineRange,
        message_id: str,
        channel_id: str
    ) -> tuple[Prediction, Optional[Prediction], Optional[str]]:
        """
        予測を追加
        
        Returns:
            (新規予測, 関連する過去予測, 差分メモ)
        """
        # 関連する過去予測を検索
        related, diff_note = self._find_related_prediction(
            user_id, category, timeline
        )
        
        prediction = Prediction(
            id=self.next_id,
            user_id=user_id,
            username=username,
            content=content,
            category=category,
            timeline=timeline,
            created_at=datetime.now().isoformat(),
            message_id=message_id,
            channel_id=channel_id,
            related_prediction_id=related.id if related else None,
            diff_note=diff_note
        )
        
        self.predictions.append(prediction)
        self.next_id += 1
        self._save()
        
        return (prediction, related, diff_note)
    
    def _find_related_prediction(
        self,
        user_id: str,
        category: str,
        new_timeline: TimelineRange
    ) -> tuple[Optional[Prediction], Optional[str]]:
        """
        関連する過去予測を検索し、差分があれば指摘（Q22: C案）
        """
        # 同一ユーザー・同一カテゴリの最新予測を検索
        related = None
        for p in reversed(self.predictions):
            if p.user_id == user_id and p.category == category:
                related = p
                break
        
        if not related:
            return (None, None)
        
        # 時間軸の重複チェック
        if not new_timeline.overlaps(related.timeline):
            # 重複なし = 差分あり
            if self._is_earlier(new_timeline, related.timeline):
                diff_note = f"前倒し: {related.timeline} → {new_timeline}"
            else:
                diff_note = f"後退: {related.timeline} → {new_timeline}"
            return (related, diff_note)
        
        return (related, None)
    
    def _is_earlier(
        self, 
        new: TimelineRange, 
        old: TimelineRange
    ) -> bool:
        """新しい時間軸が古い時間軸より早いか判定"""
        new_center = self._get_center(new)
        old_center = self._get_center(old)
        return new_center < old_center
    
    def _get_center(self, timeline: TimelineRange) -> float:
        """時間軸の中心を取得"""
        start = timeline.start or 2020
        end = timeline.end or 2050
        return (start + end) / 2
    
    def get_prediction(self, prediction_id: int) -> Optional[Prediction]:
        """IDで予測を取得"""
        for p in self.predictions:
            if p.id == prediction_id:
                return p
        return None
    
    def get_user_predictions(
        self, 
        user_id: str,
        limit: int = 10
    ) -> list[Prediction]:
        """ユーザーの予測を取得"""
        user_preds = [p for p in self.predictions if p.user_id == user_id]
        return sorted(user_preds, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def get_category_predictions(
        self,
        category: str,
        limit: int = 10
    ) -> list[Prediction]:
        """カテゴリ別の予測を取得"""
        cat_preds = [p for p in self.predictions if category in p.category]
        return sorted(cat_preds, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def get_pending_judgments(self, user_id: str) -> list[Prediction]:
        """
        期限到来で未判定の予測を取得（Q27: C案）
        """
        current_year = datetime.now().year
        pending = []
        
        for p in self.predictions:
            if p.user_id != user_id:
                continue
            if p.result != "未判定":
                continue
            
            # 終了年が今年以前なら期限到来
            if p.timeline.end and p.timeline.end <= current_year:
                pending.append(p)
        
        return pending
    
    def record_judgment(
        self,
        prediction_id: int,
        result: str,
        note: str = ""
    ) -> Optional[Prediction]:
        """
        的中判定を記録（Q27: C案）
        
        Args:
            prediction_id: 予測ID
            result: 的中 / 外れ / 部分的中
            note: 備考
        """
        prediction = self.get_prediction(prediction_id)
        if not prediction:
            return None
        
        prediction.result = result
        prediction.result_note = note
        prediction.result_date = datetime.now().isoformat()
        
        self._save()
        return prediction
    
    def search(
        self,
        query: str = "",
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 20
    ) -> list[Prediction]:
        """予測を検索"""
        results = []
        
        for p in self.predictions:
            # ユーザーフィルター
            if user_id and p.user_id != user_id:
                continue
            
            # カテゴリフィルター
            if category and category not in p.category:
                continue
            
            # 年フィルター
            if year:
                if p.timeline.start and p.timeline.start > year:
                    continue
                if p.timeline.end and p.timeline.end < year:
                    continue
            
            # テキスト検索
            if query and query.lower() not in p.content.lower():
                continue
            
            results.append(p)
        
        return sorted(results, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def get_statistics(self) -> dict:
        """統計情報を取得"""
        total = len(self.predictions)
        by_result = {"未判定": 0, "的中": 0, "外れ": 0, "部分的中": 0}
        by_category = {}
        by_user = {}
        
        for p in self.predictions:
            by_result[p.result] = by_result.get(p.result, 0) + 1
            by_category[p.category] = by_category.get(p.category, 0) + 1
            by_user[p.username] = by_user.get(p.username, 0) + 1
        
        return {
            "total": total,
            "by_result": by_result,
            "by_category": dict(sorted(
                by_category.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]),
            "by_user": dict(sorted(
                by_user.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            "accuracy_rate": (
                by_result["的中"] / (by_result["的中"] + by_result["外れ"])
                if (by_result["的中"] + by_result["外れ"]) > 0
                else None
            )
        }
    
    def anonymize_user(self, user_id: str, anonymous_id: str):
        """ユーザーの予測を匿名化（Q26: B案）"""
        for p in self.predictions:
            if p.user_id == user_id:
                p.user_id = anonymous_id
                p.username = anonymous_id
        self._save()


# シングルトンインスタンス
_prediction_ledger: Optional[PredictionLedger] = None


def get_prediction_ledger(data_dir: str = "data") -> PredictionLedger:
    """PredictionLedgerインスタンスを取得"""
    global _prediction_ledger
    if _prediction_ledger is None:
        _prediction_ledger = PredictionLedger(data_dir)
    return _prediction_ledger
