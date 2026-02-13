"""predictions.py — 栞（Shiori）予測台帳モジュール

全予測レコードの記録・検索・管理を行う。
内部で T2（カテゴリ）、T3（時間軸）、T4（差分）を順に呼び出す。

COMMON_MISTAKES §10: クラス名は PredictionLedger（PredictionManager ではない）。

依存: llm.py, categories.py, timeline.py
参照: interface_contract.md §2.4, data_schema.md §2, prompt_templates.md T4
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from categories import CategoryManager
from timeline import TimelineAnalyzer

logger = logging.getLogger("shiori.predictions")

JST = timezone(timedelta(hours=9))

# T4 システムプロンプト
T4_SYSTEM_PROMPT = (
    "あなたは予測変化分析アシスタントです。\n"
    "同一人物が過去に行った予測と新しい予測を比較し、変化点を簡潔に要約します。\n"
    "JSONのみを出力してください。説明文は不要です。"
)

# T4 ユーザープロンプトテンプレート
T4_USER_TEMPLATE = """以下の2つの予測を比較し、変化点を要約してください。

過去の予測:
- 番号: {old_prediction_id}
- 内容: {old_prediction_text}
- カテゴリ: {old_category}
- 時間軸: {old_timeline}
- 投稿日: {old_date}

新しい予測:
- 内容: {new_prediction_text}
- カテゴリ: {new_category}
- 時間軸: {new_timeline}
- 投稿日: {new_date}

ルール:
1. 変化の方向性を判定（前倒し/後ろ倒し/楽観化/悲観化/焦点変更/撤回）
2. 差分の要約は20字以内
3. 変化がない場合は is_changed: false

以下のJSON形式で回答してください:
{{"is_changed": true/false, "change_type": "前倒し|後ろ倒し|楽観化|悲観化|焦点変更|撤回", "diff_summary": "差分の要約（20字以内）"}}"""


class PredictionLedger:
    """予測台帳クラス。

    COMMON_MISTAKES §10: クラス名は PredictionLedger。

    Attributes:
        llm: LLMClient インスタンス
        predictions: 予測レコードのリスト
        categories: CategoryManager インスタンス
        timeline: TimelineAnalyzer インスタンス
    """

    def __init__(self, llm):
        self.llm = llm
        self.predictions: list[dict] = []
        self.categories = CategoryManager(llm)
        self.timeline = TimelineAnalyzer(llm)

    async def load(self, filepath: str = "data/predictions.md") -> None:
        """起動時に予測台帳を読み込む。

        内部で categories.md もロードする。

        Args:
            filepath: predictions.md のパス
        """
        # カテゴリマスタも読み込み
        await self.categories.load()

        path = Path(filepath)
        if not path.exists():
            logger.warning(f"File not found: {filepath}. Starting with empty prediction list.")
            return

        content = path.read_text(encoding="utf-8")
        self._parse_predictions(content)
        logger.info(f"PredictionLedger loaded: {len(self.predictions)} predictions")

    def _parse_predictions(self, content: str) -> None:
        """predictions.md をパースして予測リストを構築する。"""
        sections = re.split(r'^## 予測 #', content, flags=re.MULTILINE)

        for section in sections:
            if not section.strip():
                continue
            prediction = self._parse_prediction_section(section)
            if prediction:
                self.predictions.append(prediction)

    def _parse_prediction_section(self, section: str) -> dict | None:
        """予測セクションをパースして辞書を返す。"""
        lines = section.strip().split("\n")
        if not lines:
            return None

        # 予測番号
        id_match = re.match(r'^(\d{4})', lines[0])
        if not id_match:
            return None

        prediction: dict = {
            "id": f"#{id_match.group(1)}",
        }

        for line in lines:
            line = line.strip()
            match = re.match(r'^- \*\*(.+?):\*\*\s*(.+)$', line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()

                field_map = {
                    "投稿者": "author",
                    "投稿日時": "timestamp",
                    "チャンネル": "channel",
                    "内容": "content",
                    "カテゴリ": "category",
                    "時間軸": "timeline",
                    "検出方法": "detection_method",
                    "前回関連予測": "related_prediction",
                    "備考": "notes",
                }

                if key in field_map:
                    mapped_key = field_map[key]
                    prediction[mapped_key] = value

                    # 投稿者から user_id を抽出
                    if key == "投稿者":
                        uid_match = re.search(r'user_id:\s*(\d+)', value)
                        if uid_match:
                            prediction["user_id"] = int(uid_match.group(1))
                        # 表示名を抽出
                        name_match = re.match(r'^(.+?)さん', value)
                        if name_match:
                            prediction["display_name"] = name_match.group(1)

                    # 時間軸から start/end を抽出
                    if key == "時間軸":
                        tl_match = re.match(r'(\d{4}|\?)-(\d{4}|\?)年?', value)
                        if tl_match:
                            prediction["timeline_start"] = tl_match.group(1)
                            prediction["timeline_end"] = tl_match.group(2)

        return prediction if prediction.get("id") else None

    async def record_prediction(
        self,
        message: dict,
        prediction_text: str,
        detection_method: str,
    ) -> dict:
        """新規予測を記録する。

        内部で T2（カテゴリ）、T3（時間軸）、T4（差分）を順に呼び出す。

        Args:
            message: {"user_id": int, "display_name": str,
                      "content": str, "timestamp": str, "channel": str}
            prediction_text: T1出力の prediction_text
            detection_method: "mention" | "passive" | "reply"

        Returns:
            dict: 記録された予測レコード
        """
        import asyncio

        prediction_id = self.get_next_prediction_id()
        user_id = message["user_id"]
        display_name = message["display_name"]

        # T2（カテゴリ）と T3（時間軸）を並列実行
        t2_task = self.categories.classify(prediction_text, display_name)
        t3_task = self.timeline.extract(prediction_text, message["content"])
        t2_result, t3_result = await asyncio.gather(t2_task, t3_task)

        category = t2_result["categories"][0] if t2_result["categories"] else "未分類 / その他"

        # T4（差分検出）: 同一ユーザー・同一カテゴリの過去予測を検索
        related_prediction_str = "なし"
        past_predictions = await self.find_by_user_and_category(user_id, category)

        if past_predictions:
            latest_past = past_predictions[-1]
            old_start = latest_past.get("timeline_start", "?")
            old_end = latest_past.get("timeline_end", "?")
            new_start = t3_result.get("timeline_start", "?")
            new_end = t3_result.get("timeline_end", "?")

            # 時間軸が重複しない場合のみ差分を検出
            if not TimelineAnalyzer.timelines_overlap(old_start, old_end, new_start, new_end):
                t4_result = await self.llm.call_template(
                    template_name="T4",
                    system=T4_SYSTEM_PROMPT,
                    user=T4_USER_TEMPLATE.format(
                        old_prediction_id=latest_past.get("id", "?"),
                        old_prediction_text=latest_past.get("content", ""),
                        old_category=latest_past.get("category", ""),
                        old_timeline=latest_past.get("timeline", ""),
                        old_date=latest_past.get("timestamp", ""),
                        new_prediction_text=prediction_text,
                        new_category=category,
                        new_timeline=t3_result.get("timeline_display", "?-?年"),
                        new_date=message.get("timestamp", ""),
                    ),
                    max_tokens=200,
                    temperature=0.3,
                )

                if t4_result and t4_result.get("is_changed"):
                    diff_summary = t4_result.get("diff_summary", "変化あり")
                    related_prediction_str = (
                        f"{latest_past.get('id', '?')}（差分: {diff_summary}）"
                    )

        # 予測レコード構築
        record = {
            "id": prediction_id,
            "user_id": user_id,
            "display_name": display_name,
            "author": f"{display_name}さん (user_id: {user_id})",
            "timestamp": message.get("timestamp", datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")),
            "channel": message.get("channel", ""),
            "content": prediction_text,
            "category": category,
            "timeline": t3_result.get("timeline_display", "?-?年"),
            "timeline_start": t3_result.get("timeline_start", "?"),
            "timeline_end": t3_result.get("timeline_end", "?"),
            "detection_method": detection_method,
            "related_prediction": related_prediction_str,
            "notes": "なし",
        }

        self.predictions.append(record)
        await self.save()

        logger.info(
            f"Recorded prediction {prediction_id}: "
            f"user={display_name}, category={category}, "
            f"timeline={t3_result.get('timeline_display', '?')}"
        )

        return record

    async def find_by_user_and_category(
        self,
        user_id: int,
        category: str,
    ) -> list[dict]:
        """差分指摘用: 同一ユーザー・同一カテゴリの過去予測を検索する。

        Args:
            user_id: Discord ユーザーID
            category: カテゴリ文字列

        Returns:
            list[dict]: 該当する予測レコードのリスト（時系列順）
        """
        from categories import normalize_category

        norm_cat = normalize_category(category)
        results = [
            p for p in self.predictions
            if p.get("user_id") == user_id
            and normalize_category(p.get("category", "")) == norm_cat
        ]
        return results

    def get_next_prediction_id(self) -> str:
        """次の予測番号を返す（'#0001'形式）。

        Returns:
            str: 次の予測番号
        """
        if not self.predictions:
            return "#0001"

        all_nums = []
        for p in self.predictions:
            pid = p.get("id", "")
            num_match = re.match(r'#(\d+)', pid)
            if num_match:
                all_nums.append(int(num_match.group(1)))

        if not all_nums:
            return "#0001"

        return f"#{max(all_nums) + 1:04d}"

    def format_prediction_record(self, prediction: dict) -> str:
        """予測レコードをMarkdown形式の文字列に変換する。

        Args:
            prediction: 予測レコード辞書

        Returns:
            str: Markdown形式の文字列
        """
        lines = [
            f"## 予測 {prediction.get('id', '#????')}",
            "",
            f"- **投稿者:** {prediction.get('author', '不明')}",
            f"- **投稿日時:** {prediction.get('timestamp', '')}",
            f"- **チャンネル:** {prediction.get('channel', '')}",
            f"- **内容:** 「{prediction.get('content', '')}」",
            f"- **カテゴリ:** {prediction.get('category', '未分類')}",
            f"- **時間軸:** {prediction.get('timeline', '?-?年')}",
            f"- **検出方法:** {prediction.get('detection_method', 'unknown')}",
            f"- **前回関連予測:** {prediction.get('related_prediction', 'なし')}",
            f"- **備考:** {prediction.get('notes', 'なし')}",
            "",
        ]
        return "\n".join(lines)

    async def save(self) -> None:
        """predictions.md と index.md に書き出す。"""
        filepath = Path("data/predictions.md")
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# 予測台帳\n\n"]
        for prediction in self.predictions:
            lines.append(self.format_prediction_record(prediction))
            lines.append("\n---\n\n")

        filepath.write_text("".join(lines), encoding="utf-8")

        # index.md も更新
        await self._update_index()

        logger.debug(f"Saved {len(self.predictions)} predictions to {filepath}")

    async def _update_index(self) -> None:
        """index.md を再構築する。"""
        filepath = Path("data/index.md")
        filepath.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# 横断インデックス\n\n"]

        # メンバー別インデックス
        lines.append("## メンバー別インデックス\n\n")
        by_user: dict[str, list[dict]] = {}
        for p in self.predictions:
            name = p.get("display_name", "不明")
            uid = p.get("user_id", 0)
            key = f"{name} (user_id: {uid})"
            by_user.setdefault(key, []).append(p)

        for user_key, preds in sorted(by_user.items()):
            lines.append(f"### {user_key}\n\n")
            lines.append("| 予測番号 | カテゴリ | 時間軸 | 投稿日 |\n")
            lines.append("|---------|--------|--------|--------|\n")
            for p in preds:
                pid = p.get("id", "")
                cat = p.get("category", "")
                tl = p.get("timeline", "")
                ts = p.get("timestamp", "")[:10]
                lines.append(f"| {pid} | {cat} | {tl} | {ts} |\n")
            lines.append("\n")

        # カテゴリ別インデックス
        lines.append("---\n\n## カテゴリ別インデックス\n\n")
        by_cat: dict[str, list[dict]] = {}
        for p in self.predictions:
            cat = p.get("category", "未分類")
            by_cat.setdefault(cat, []).append(p)

        for cat_key, preds in sorted(by_cat.items()):
            lines.append(f"### {cat_key}\n\n")
            lines.append("| 予測番号 | 投稿者 | 時間軸 | 投稿日 |\n")
            lines.append("|---------|--------|--------|--------|\n")
            for p in preds:
                pid = p.get("id", "")
                name = p.get("display_name", "不明")
                tl = p.get("timeline", "")
                ts = p.get("timestamp", "")[:10]
                lines.append(f"| {pid} | {name} | {tl} | {ts} |\n")
            lines.append("\n")

        filepath.write_text("".join(lines), encoding="utf-8")
