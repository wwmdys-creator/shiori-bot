"""
prediction_highlighter.py - 未解決予測ハイライト選定

Shiori v5.3 - §5.7 未解決予測ハイライト, §5.8 ハイライト選定ロジック, §5.9 文体
Interface Contract: §12.7.3

COMMON_MISTAKES §10: クラス名・メソッド名を §12.7.3 に厳密一致させる。
COMMON_MISTAKES §13: select_highlights() は sync 関数。LLM呼び出しなし。
COMMON_MISTAKES §15: 全公開メソッドが実装済みであること。
COMMON_MISTAKES §14: predictions.md 内部表現と API フォーマットの変換を明示。

設計方針:
  - LLM呼び出しを行わない純粋な選定ロジック
  - narrative は固定テンプレートで生成（Sonnet呼び出し不要）
  - daily_maintenance.py から呼ばれ、結果は日次報告に埋め込まれる
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from config import APPROACHING_MONTHS, INACTIVE_DAYS, MAX_HIGHLIGHTS

JST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)


class PredictionHighlighter:
    """未解決予測ハイライト選定（§5.7, §5.8 詳細参照）

    日次報告で「期限接近」「対立予測ペア」「長期未更新」を
    最大2件紹介するための選定ロジック。

    Public API (Interface Contract §12.7.3):
        - select_highlights(predictions, member_profiles, current_date) -> list[dict]

    ⚠️ メンション禁止: Discord @メンション は使わない。「〇〇さん」表記。
    ⚠️ 予測番号必須: ナラティブに #NNNN を必ず含める。
    ⚠️ 結論・正否判定禁止: 「どちらが正しい」とは言わない。
    """

    def select_highlights(
        self,
        predictions: list[dict],
        member_profiles: dict,
        current_date: datetime,
    ) -> list[dict]:
        """ハイライト対象の予測を選定する

        Args:
            predictions: 予測データのリスト。各要素は以下のキーを持つ:
                - prediction_id: str  (例: "#0032")
                - author_display_name: str
                - author_user_id: str
                - content: str  (予測内容テキスト)
                - category: str  (例: "AI技術 / AGI")
                - timeline_start: str  (例: "2029" or "?")
                - timeline_end: str  (例: "2035" or "?")
                - posted_at: datetime
            member_profiles: メンバープロファイル辞書。キー=user_id。
                各要素に last_active: datetime を含む。
            current_date: 現在日時（JST）

        Returns:
            list[dict] — 最大2件。各要素:
                type: "conflict" | "approaching" | "inactive"
                predictions: 対象予測のリスト
                narrative: 表示テキスト（§5.9 文体準拠）
            空リスト: 該当なし

        ⚠️ len(result) <= MAX_HIGHLIGHTS
        """
        if not predictions:
            return []

        highlights = []

        # Priority 1: 対立予測ペア（§5.8 優先度1）
        try:
            conflicts = self._find_conflicting_pairs(predictions)
            for pair in conflicts[:1]:  # 最大1ペア
                highlights.append({
                    "type": "conflict",
                    "predictions": pair,
                    "narrative": self._build_conflict_narrative(pair),
                })
        except Exception as e:
            logger.error(f"[Highlighter] Conflict detection failed: {e}")

        if len(highlights) >= MAX_HIGHLIGHTS:
            return highlights

        # Priority 2: 期限接近（§5.8 優先度2）
        try:
            approaching = self._find_approaching(predictions, current_date)
            for pred in approaching[:1]:
                highlights.append({
                    "type": "approaching",
                    "predictions": [pred],
                    "narrative": self._build_approaching_narrative(pred),
                })
        except Exception as e:
            logger.error(f"[Highlighter] Approaching detection failed: {e}")

        if len(highlights) >= MAX_HIGHLIGHTS:
            return highlights

        # Priority 3: 長期未更新メンバーの予測（§5.8 優先度3）
        try:
            inactive = self._find_inactive_member_predictions(
                predictions, member_profiles, current_date
            )
            for pred in inactive[:1]:
                highlights.append({
                    "type": "inactive",
                    "predictions": [pred],
                    "narrative": self._build_inactive_narrative(pred),
                })
        except Exception as e:
            logger.error(f"[Highlighter] Inactive detection failed: {e}")

        return highlights[:MAX_HIGHLIGHTS]

    # ===== 内部メソッド: 検出 =====

    def _find_conflicting_pairs(
        self, predictions: list[dict]
    ) -> list[list[dict]]:
        """同一カテゴリで異なるタイムラインを持つ対立ペアを検出する

        §5.8 優先度1: 同一テーマで異なるタイムラインを持つ2件

        Returns:
            list[list[dict]]: 各要素は [pred_a, pred_b] の2件ペア
        """
        pairs = []
        # カテゴリ別にグループ化
        by_category: dict[str, list[dict]] = {}
        for pred in predictions:
            cat = pred.get("category", "")
            if not cat:
                continue
            # 大分類で比較（"AI技術 / AGI" → "AI技術"）
            major_cat = cat.split("/")[0].strip()
            if major_cat not in by_category:
                by_category[major_cat] = []
            by_category[major_cat].append(pred)

        for cat, preds in by_category.items():
            if len(preds) < 2:
                continue
            # 異なる投稿者＋異なるタイムラインのペアを探す
            for i in range(len(preds)):
                for j in range(i + 1, len(preds)):
                    a, b = preds[i], preds[j]
                    # 同一投稿者は対立ペアとしない
                    if a.get("author_user_id") == b.get("author_user_id"):
                        continue
                    # タイムラインが異なるか確認
                    if self._has_timeline_difference(a, b):
                        pairs.append([a, b])
                        if len(pairs) >= 1:
                            return pairs
        return pairs

    def _has_timeline_difference(
        self, pred_a: dict, pred_b: dict
    ) -> bool:
        """2つの予測のタイムラインに意味のある差があるか判定する

        Returns:
            bool: タイムラインが非重複ならTrue
        """
        a_start = pred_a.get("timeline_start", "?")
        a_end = pred_a.get("timeline_end", "?")
        b_start = pred_b.get("timeline_start", "?")
        b_end = pred_b.get("timeline_end", "?")

        # "?" を含む場合は差があるとは判定しない
        if "?" in (a_start, a_end, b_start, b_end):
            return False

        try:
            # 範囲が重複しなければ「差がある」
            return not (
                int(a_start) <= int(b_end) and int(b_start) <= int(a_end)
            )
        except (ValueError, TypeError):
            return False

    def _find_approaching(
        self, predictions: list[dict], current_date: datetime
    ) -> list[dict]:
        """タイムライン開始が6ヶ月以内の予測を検出する

        §5.8 優先度2: APPROACHING_MONTHS以内に期限到来

        Returns:
            list[dict]: 期限接近予測のリスト（接近順）
        """
        approaching = []
        threshold_date = current_date + timedelta(days=APPROACHING_MONTHS * 30)

        for pred in predictions:
            start = pred.get("timeline_start", "?")
            if start == "?":
                continue
            try:
                start_year = int(start)
                # 開始年の1月1日を期限とみなす（JST aware）
                deadline = datetime(start_year, 1, 1, tzinfo=JST)
                if current_date <= deadline <= threshold_date:
                    approaching.append(pred)
            except (ValueError, TypeError):
                continue

        # 期限が近い順にソート
        approaching.sort(
            key=lambda p: int(p.get("timeline_start", "9999"))
        )
        return approaching

    def _find_inactive_member_predictions(
        self,
        predictions: list[dict],
        member_profiles: dict,
        current_date: datetime,
    ) -> list[dict]:
        """30日以上発言なしのメンバーの有効な予測を検出する

        §5.8 優先度3: 投稿者が30日以上発言なし＋有効な予測あり

        Returns:
            list[dict]: 非活動メンバーの予測リスト
        """
        inactive_threshold = current_date - timedelta(days=INACTIVE_DAYS)
        result = []

        for pred in predictions:
            user_id = pred.get("author_user_id", "")
            if not user_id:
                continue

            profile = member_profiles.get(user_id)
            if profile is None:
                continue

            last_active = profile.get("last_active")
            if last_active is None:
                continue

            # last_active が文字列の場合に対応
            if isinstance(last_active, str):
                try:
                    last_active = datetime.fromisoformat(last_active)
                except (ValueError, TypeError):
                    continue

            # timezone-naive → JST に統一（aware化）
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=JST)

            if last_active < inactive_threshold:
                result.append(pred)

        return result

    # ===== 内部メソッド: ナラティブ生成（§5.9 文体） =====

    def _build_conflict_narrative(self, pair: list[dict]) -> str:
        """対立予測ペアのナラティブを生成する

        §5.9 文体例:
        「そういえば、カエサルさんの#0032（AGI 2029年）と
         L.Nさんの#0087（2035年）……どちらに近づいているんでしょうね。
         わたしの時代の記録だと……あ、これは言えないやつですね📎」

        ⚠️ @メンション禁止。「〇〇さん」表記。
        ⚠️ 結論・正否判定禁止。
        """
        a, b = pair[0], pair[1]
        a_id = a.get("prediction_id", "?")
        b_id = b.get("prediction_id", "?")
        a_name = a.get("author_display_name", "???")
        b_name = b.get("author_display_name", "???")
        a_timeline = self._format_timeline(a)
        b_timeline = self._format_timeline(b)
        category = a.get("category", "")

        return (
            f"そういえば、{a_name}さんの{a_id}（{a_timeline}）と"
            f"{b_name}さんの{b_id}（{b_timeline}）……"
            f"どちらに近づいているんでしょうね。"
            f"わたしの時代の記録だと……あ、これは言えないやつですね📎"
        )

    def _build_approaching_narrative(self, pred: dict) -> str:
        """期限接近予測のナラティブを生成する

        §5.9 文体例:
        「#0055のロボット予測、akipon345さんが2026年前半って
         書いてましたよね。そろそろ答え合わせの時期ですね」
        """
        pred_id = pred.get("prediction_id", "?")
        name = pred.get("author_display_name", "???")
        content = pred.get("content", "")
        timeline = self._format_timeline(pred)

        # 内容を短縮（30字以内）
        short_content = content[:30] + ("…" if len(content) > 30 else "")

        return (
            f"{pred_id}の予測、{name}さんが{timeline}って"
            f"書いてましたよね。そろそろ答え合わせの時期ですね"
        )

    def _build_inactive_narrative(self, pred: dict) -> str:
        """長期未更新メンバーの予測ナラティブを生成する

        §5.9 文体例:
        「#0071の宇宙エレベーター予測、slowbird2000さん最近
         お見かけしないけど、今もあの予測のままなのかな……」
        """
        pred_id = pred.get("prediction_id", "?")
        name = pred.get("author_display_name", "???")
        content = pred.get("content", "")

        # 内容を短縮（20字以内）
        short_content = content[:20] + ("…" if len(content) > 20 else "")

        return (
            f"{pred_id}の{short_content}予測、"
            f"{name}さん最近お見かけしないけど、"
            f"今もあの予測のままなのかな……"
        )

    def _format_timeline(self, pred: dict) -> str:
        """予測のタイムラインを表示用文字列にフォーマットする

        Returns:
            str: 例 "2029年", "2030-2035年", "2030年以降"
        """
        start = pred.get("timeline_start", "?")
        end = pred.get("timeline_end", "?")

        if start == "?" and end == "?":
            return "時期不明"
        elif start == "?":
            return f"{end}年まで"
        elif end == "?":
            return f"{start}年以降"
        elif start == end:
            return f"{start}年"
        else:
            return f"{start}-{end}年"
