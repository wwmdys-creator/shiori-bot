"""prediction_highlighter.py — 未解決予測ハイライト選定

§5.7, §5.8 準拠。日次報告に含める「期限接近」「対立予測ペア」を選定する。

インターフェース契約: §12.7.3
依存: config.py（定数）
呼び出し元: daily_maintenance.py

COMMON_MISTAKES対応:
  §10: select_highlights() のシグネチャは §12.7.3 に厳密に準拠
  §13: 本モジュールはasync不要（sync関数のみ）
  §15: 全メソッドに最低限の動作実装あり（スタブなし）
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("shiori.prediction_highlighter")

# --- 定数（config.py から参照。ここではフォールバック値を定義） ---
# 実運用では config.py の値を使う。テスト容易性のためクラス属性で保持。
_DEFAULT_APPROACHING_MONTHS = 6
_DEFAULT_INACTIVE_DAYS = 30
_DEFAULT_MAX_HIGHLIGHTS = 2


class PredictionHighlighter:
    """未解決予測ハイライト選定（§5.7, §5.8 詳細参照）

    日次報告(§5)の「📌 気になる予測メモ」セクション用に、
    注目すべき予測を最大2件選定する。
    """

    def __init__(
        self,
        approaching_months: int = _DEFAULT_APPROACHING_MONTHS,
        inactive_days: int = _DEFAULT_INACTIVE_DAYS,
        max_highlights: int = _DEFAULT_MAX_HIGHLIGHTS,
    ) -> None:
        """
        Args:
            approaching_months: 期限接近判定の月数（config.APPROACHING_MONTHS）
            inactive_days: 非活動判定の日数（config.INACTIVE_DAYS）
            max_highlights: 1回あたりの最大ハイライト数（config.MAX_HIGHLIGHTS）
        """
        self.approaching_months = approaching_months
        self.inactive_days = inactive_days
        self.max_highlights = max_highlights

    def select_highlights(
        self,
        predictions: list[dict],
        member_profiles: dict,
        current_date: datetime,
    ) -> list[dict]:
        """ハイライト対象の予測を選定する

        選定基準（優先順位順）:
            1. 対立予測ペア（同一テーマで異なる結論）
            2. 期限接近予測（approaching_months以内に期限到来）
            3. 投稿者の最終活動がinactive_days以上前のもの

        Args:
            predictions: 予測データのリスト。各要素は以下を含む:
                - "id": str (予測ID、例: "#0032")
                - "author": str (投稿者username)
                - "author_display_name": str (投稿者表示名)
                - "content": str (予測内容)
                - "category": str (カテゴリ)
                - "timeline_start": str | None (開始年 "YYYY" or "?")
                - "timeline_end": str | None (終了年 "YYYY" or "?")
                - "status": str ("active" | "resolved" | "expired")
            member_profiles: メンバープロファイル辞書 (username -> profile)
                各profileは "last_active" (datetime | None) を含みうる
            current_date: 現在日時（JST）

        Returns:
            list[dict] — 最大 max_highlights 件。§12.4.3 形式:
                [{"type": str, "predictions": list, "narrative": str}, ...]
            空リスト: 該当なし

        ⚠️ len(result) <= self.max_highlights
        """
        highlights: list[dict] = []

        # 未解決予測のみを対象
        active_predictions = [
            p for p in predictions
            if p.get("status", "active") == "active"
        ]

        if not active_predictions:
            logger.debug("[PredictionHighlighter] No active predictions found")
            return []

        # --- 優先度1: 対立予測ペア ---
        try:
            opposing = self._find_opposing_pairs(active_predictions)
            for pair in opposing:
                if len(highlights) >= self.max_highlights:
                    break
                highlights.append(pair)
        except Exception as e:
            logger.error(
                f"[PredictionHighlighter] Opposing pair detection failed: {e}"
            )
            # エラー隔離: 対立ペア検出失敗でも次の選定に進む

        # --- 優先度2: 期限接近予測 ---
        if len(highlights) < self.max_highlights:
            try:
                approaching = self._find_approaching_predictions(
                    active_predictions, current_date
                )
                for pred_highlight in approaching:
                    if len(highlights) >= self.max_highlights:
                        break
                    # 既にハイライト済みの予測IDと重複しないかチェック
                    existing_ids = self._get_highlighted_ids(highlights)
                    pred_ids = {
                        p.get("id")
                        for p in pred_highlight.get("predictions", [])
                    }
                    if not pred_ids & existing_ids:
                        highlights.append(pred_highlight)
            except Exception as e:
                logger.error(
                    f"[PredictionHighlighter] Approaching detection failed: {e}"
                )

        # --- 優先度3: 長期未更新メンバーの予測 ---
        if len(highlights) < self.max_highlights:
            try:
                inactive = self._find_inactive_member_predictions(
                    active_predictions, member_profiles, current_date
                )
                for pred_highlight in inactive:
                    if len(highlights) >= self.max_highlights:
                        break
                    existing_ids = self._get_highlighted_ids(highlights)
                    pred_ids = {
                        p.get("id")
                        for p in pred_highlight.get("predictions", [])
                    }
                    if not pred_ids & existing_ids:
                        highlights.append(pred_highlight)
            except Exception as e:
                logger.error(
                    f"[PredictionHighlighter] Inactive member detection failed: {e}"
                )

        logger.info(
            f"[PredictionHighlighter] Selected {len(highlights)} highlights"
        )
        return highlights[:self.max_highlights]

    # ===== 内部メソッド =====

    def _find_opposing_pairs(
        self, predictions: list[dict]
    ) -> list[dict]:
        """同一カテゴリで異なるタイムラインを持つ対立ペアを検出"""
        pairs: list[dict] = []

        # カテゴリ別にグルーピング
        by_category: dict[str, list[dict]] = {}
        for pred in predictions:
            cat = pred.get("category", "")
            if cat:
                by_category.setdefault(cat, []).append(pred)

        for cat, cat_preds in by_category.items():
            if len(cat_preds) < 2:
                continue

            # タイムライン終了年でソートし、最も差が大きいペアを選定
            with_timeline = [
                p for p in cat_preds
                if p.get("timeline_end") and p["timeline_end"] != "?"
            ]
            if len(with_timeline) < 2:
                continue

            with_timeline.sort(
                key=lambda p: int(p.get("timeline_end", "9999"))
            )
            earliest = with_timeline[0]
            latest = with_timeline[-1]

            # 少なくとも3年差がある場合のみ「対立」とみなす
            try:
                diff = int(latest["timeline_end"]) - int(earliest["timeline_end"])
                if diff >= 3:
                    display_text = (
                        f"{earliest.get('id', '?')} "
                        f"{earliest.get('author_display_name', '?')}さんの予測"
                        f"（{earliest.get('timeline_end')}年）vs "
                        f"{latest.get('id', '?')} "
                        f"{latest.get('author_display_name', '?')}さんの予測"
                        f"（{latest.get('timeline_end')}年）"
                    )
                    pairs.append({
                        "type": "opposing",
                        "predictions": [earliest, latest],
                        "narrative": display_text,
                    })
            except (ValueError, TypeError):
                continue

        return pairs

    def _find_approaching_predictions(
        self, predictions: list[dict], current_date: datetime
    ) -> list[dict]:
        """期限が approaching_months 以内に到来する予測を検出"""
        results: list[dict] = []
        cutoff = current_date + timedelta(days=self.approaching_months * 30)
        cutoff_year = cutoff.year

        for pred in predictions:
            timeline_end = pred.get("timeline_end")
            if not timeline_end or timeline_end == "?":
                continue
            try:
                end_year = int(timeline_end)
                if current_date.year <= end_year <= cutoff_year:
                    display_name = pred.get("author_display_name", "?")
                    display_text = (
                        f"{pred.get('id', '?')}の予測"
                        f"（{display_name}さん、{end_year}年期限）"
                        f"がまもなく検証時期です"
                    )
                    results.append({
                        "type": "approaching",
                        "predictions": [pred],
                        "narrative": display_text,
                    })
            except (ValueError, TypeError):
                continue

        return results

    def _find_inactive_member_predictions(
        self,
        predictions: list[dict],
        member_profiles: dict,
        current_date: datetime,
    ) -> list[dict]:
        """投稿者が inactive_days 以上未活動の予測を検出"""
        results: list[dict] = []
        cutoff_date = current_date - timedelta(days=self.inactive_days)

        for pred in predictions:
            author = pred.get("author", "")
            if not author:
                continue

            profile = member_profiles.get(author, {})
            last_active = profile.get("last_active")

            if last_active is None:
                # last_active情報がない場合はスキップ
                continue

            # last_active が datetime でなければ変換を試みる
            if isinstance(last_active, str):
                try:
                    last_active = datetime.fromisoformat(last_active)
                except (ValueError, TypeError):
                    continue

            if last_active < cutoff_date:
                display_name = pred.get("author_display_name", author)
                display_text = (
                    f"{pred.get('id', '?')}の予測、"
                    f"最近お見かけしない{display_name}さん"
                    f"はどうお考えか気になります"
                )
                results.append({
                    "type": "inactive_member",
                    "predictions": [pred],
                    "narrative": display_text,
                })

        return results

    @staticmethod
    def _get_highlighted_ids(highlights: list[dict]) -> set[str]:
        """既存ハイライトに含まれる予測IDを集める"""
        ids: set[str] = set()
        for h in highlights:
            for p in h.get("predictions", []):
                pid = p.get("id")
                if pid:
                    ids.add(pid)
        return ids
