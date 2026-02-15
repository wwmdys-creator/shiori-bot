"""
予測ハイライト選定モジュール — prediction_highlighter.py
v5.3 新規（§5.7, §5.8 日次メンテナンス用）

依存: config.py (APPROACHING_MONTHS, INACTIVE_DAYS, MAX_HIGHLIGHTS)
"""

import logging
from datetime import datetime, timedelta

from config import APPROACHING_MONTHS, INACTIVE_DAYS, MAX_HIGHLIGHTS

logger = logging.getLogger(__name__)


class PredictionHighlighter:
    """未解決予測ハイライト選定（§5.7, §5.8, §12.7.3）

    日次メンテナンス報告に含めるハイライト（最大2件）を選定する。

    選定基準（優先順位順）:
      1. 対立予測ペア（同一テーマで異なる結論）
      2. 期限接近予測（APPROACHING_MONTHS 以内に期限到来）
      3. 投稿者の最終活動が INACTIVE_DAYS 以上前のもの
    """

    def select_highlights(
        self,
        predictions: list[dict],
        member_profiles: dict,
        current_date: datetime,
    ) -> list[dict]:
        """ハイライト対象の予測を選定する（§12.7.3）

        Args:
            predictions:     予測データのリスト
                             各要素: {"user_id", "content", "target_date",
                                      "category", "created_at", ...}
            member_profiles: メンバープロファイル辞書
                             {user_id: {"display_name", "last_active", ...}}
            current_date:    現在日時

        Returns:
            list[dict] — 最大 MAX_HIGHLIGHTS 件。§12.4.3 形式:
                [{"type": str, "predictions": list, "narrative": str}, ...]
            空リスト: 該当なし
        """
        if not predictions:
            return []

        highlights: list[dict] = []

        # 1. 対立予測ペアの検出
        try:
            opposing = self._find_opposing_pairs(predictions)
            for pair in opposing:
                if len(highlights) >= MAX_HIGHLIGHTS:
                    break
                highlights.append(pair)
        except Exception as exc:
            logger.error("対立予測検出エラー: %s", exc)

        # 2. 期限接近予測の検出
        try:
            approaching = self._find_approaching_deadlines(
                predictions, current_date
            )
            for item in approaching:
                if len(highlights) >= MAX_HIGHLIGHTS:
                    break
                # 重複チェック（同じ予測を含まない）
                if not self._has_overlap(highlights, item):
                    highlights.append(item)
        except Exception as exc:
            logger.error("期限接近予測検出エラー: %s", exc)

        logger.info(
            "ハイライト選定完了: %d件 / 候補予測%d件",
            len(highlights), len(predictions),
        )
        return highlights[:MAX_HIGHLIGHTS]

    def _find_opposing_pairs(
        self, predictions: list[dict],
    ) -> list[dict]:
        """同一テーマで対立する予測ペアを検出する

        カテゴリが同一で、結論が異なる予測をペアリング。

        Returns:
            list[dict] — §12.4.3 形式のハイライトリスト
        """
        # カテゴリ別にグループ化
        by_category: dict[str, list[dict]] = {}
        for pred in predictions:
            cat = pred.get("category", "unknown")
            if cat and cat != "unknown":
                by_category.setdefault(cat, []).append(pred)

        pairs = []
        for cat, preds in by_category.items():
            if len(preds) < 2:
                continue

            # 投稿者が異なるペアを探す
            seen_users = set()
            candidates = []
            for p in preds:
                uid = p.get("user_id", "")
                if uid not in seen_users:
                    seen_users.add(uid)
                    candidates.append(p)

            if len(candidates) >= 2:
                pair = {
                    "type": "opposing",
                    "predictions": candidates[:2],
                    "narrative": self._build_opposing_narrative(
                        candidates[0], candidates[1], cat
                    ),
                }
                pairs.append(pair)

        return pairs

    def _find_approaching_deadlines(
        self,
        predictions: list[dict],
        current_date: datetime,
    ) -> list[dict]:
        """期限が APPROACHING_MONTHS 以内に到来する予測を検出する

        Returns:
            list[dict] — §12.4.3 形式のハイライトリスト
        """
        threshold = current_date + timedelta(
            days=APPROACHING_MONTHS * 30  # 概算
        )
        approaching = []

        for pred in predictions:
            target_date_str = pred.get("target_date", "")
            if not target_date_str:
                continue

            try:
                target_date = self._parse_date(target_date_str)
            except (ValueError, TypeError):
                continue

            # 過去の期限は除外、threshold 以内のものを対象
            if current_date < target_date <= threshold:
                approaching.append(pred)

        # 期限が近い順にソート
        approaching.sort(
            key=lambda p: self._parse_date(p.get("target_date", "")),
        )

        results = []
        for pred in approaching:
            results.append({
                "type": "approaching",
                "predictions": [pred],
                "narrative": self._build_approaching_narrative(
                    pred, current_date
                ),
            })
        return results

    def _build_opposing_narrative(
        self,
        pred_a: dict,
        pred_b: dict,
        category: str,
    ) -> str:
        """対立予測のナラティブを生成する"""
        name_a = pred_a.get("display_name", pred_a.get("user_id", "?"))
        name_b = pred_b.get("display_name", pred_b.get("user_id", "?"))
        return (
            f"「{category}」について、{name_a}さんと{name_b}さんの間で"
            f"見解が分かれています。"
        )

    def _build_approaching_narrative(
        self,
        pred: dict,
        current_date: datetime,
    ) -> str:
        """期限接近予測のナラティブを生成する"""
        name = pred.get("display_name", pred.get("user_id", "?"))
        target = pred.get("target_date", "不明")
        content_preview = (pred.get("content", "")[:40] + "...")
        return (
            f"{name}さんの予測「{content_preview}」の期限（{target}）が"
            f"近づいています。"
        )

    def _has_overlap(
        self,
        existing: list[dict],
        candidate: dict,
    ) -> bool:
        """既存ハイライトと候補の予測が重複していないかチェック"""
        candidate_ids = {
            p.get("user_id", "") + p.get("content", "")
            for p in candidate.get("predictions", [])
        }
        for h in existing:
            for p in h.get("predictions", []):
                key = p.get("user_id", "") + p.get("content", "")
                if key in candidate_ids:
                    return True
        return False

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """日付文字列をパースする

        対応フォーマット:
          - "2030" → 2030-01-01
          - "2030-06" → 2030-06-01
          - "2030-06-15" → 2030-06-15
        """
        date_str = date_str.strip()

        if len(date_str) == 4 and date_str.isdigit():
            return datetime(int(date_str), 1, 1)

        if len(date_str) == 7 and date_str[4] == "-":
            parts = date_str.split("-")
            return datetime(int(parts[0]), int(parts[1]), 1)

        # ISO format
        return datetime.fromisoformat(date_str)
