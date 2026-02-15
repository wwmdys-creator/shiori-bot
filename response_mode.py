"""
応答モード判定モジュール — response_mode.py
v5.3 新規（§3.3 記録モード / 自由モード分離）

外部依存: なし（純粋関数）
"""

import re
import logging

logger = logging.getLogger(__name__)

# =====================================================================
#  トリガーパターン定義
# =====================================================================

# 年号パターン: 西暦4桁（2020〜2099）
_YEAR_PATTERN = re.compile(r"20[2-9]\d")

# 予測キーワード: 年号と組み合わせて記録モードを発動
_PREDICTION_KEYWORDS = [
    "なる", "になる", "できる", "完成", "実現", "達成", "到達",
    "届く", "超える", "突破", "普及", "登場", "誕生", "消滅",
    "なくなる", "消える", "崩壊", "終わる", "始まる", "開始",
    "予測", "予想", "予言", "見通し",
]
_PREDICTION_KEYWORDS_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _PREDICTION_KEYWORDS)
)

# 記録系明示キーワード: 単独で記録モードを発動
_RECORD_EXPLICIT_KEYWORDS = [
    "記録して", "記録しておいて", "記録お願い",
    "メモして", "メモしておいて", "メモお願い",
    "予測として残して", "予測として記録",
    "予測を登録", "予測登録",
]
_RECORD_EXPLICIT_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _RECORD_EXPLICIT_KEYWORDS)
)

# 過去予測参照: 記録モードを発動
_PAST_PREDICTION_KEYWORDS = [
    "前の予測と比べて", "前回何て言った", "前回なんて言った",
    "以前の予測", "過去の予測", "前に言った予測",
    "前の予測", "予測を振り返",
]
_PAST_PREDICTION_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _PAST_PREDICTION_KEYWORDS)
)

# 自由モード（会話）のシグナル: 質問・意見・雑談
_FREE_MODE_SIGNALS = [
    "どう思う", "どう考える", "意見", "感想",
    "教えて", "何が", "なぜ", "どうして",
    "みんなどう", "みんなは", "皆さん",
    "雑談", "聞きたい", "質問",
]
_FREE_MODE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _FREE_MODE_SIGNALS)
)


# =====================================================================
#  公開関数
# =====================================================================

def determine_response_mode(message_content: str) -> str:
    """メッセージ内容から応答モードを判定する（§3.3）

    Args:
        message_content: メッセージ内容（メンション部分は除去済み）

    Returns:
        "record": 記録モード（構造化フォーマットで記録確認）
        "free":   自由モード（自然な会話として応答）

    Q2決定: 記録トリガーと自由トリガーの両方に該当 → "free" を優先
    """
    content = message_content.strip()

    if not content:
        return "free"

    has_record_trigger = _check_record_triggers(content)
    has_free_trigger = _check_free_triggers(content)

    # Q2決定: 両方該当 → 自由モード優先（予測は内部記録）
    if has_record_trigger and has_free_trigger:
        logger.info(
            "応答モード判定: 両方該当 → free優先（予測は内部記録）"
        )
        return "free"

    if has_record_trigger:
        logger.info("応答モード判定: record")
        return "record"

    # デフォルトは自由モード
    return "free"


# =====================================================================
#  内部関数
# =====================================================================

def _check_record_triggers(content: str) -> bool:
    """記録モードのトリガーをチェック

    トリガー条件（いずれかに該当）:
      1. 年号 + 予測キーワードの組み合わせ
      2. 記録系明示キーワード
      3. 過去予測参照キーワード
    """
    # 1. 年号＋予測キーワード
    if _YEAR_PATTERN.search(content) and _PREDICTION_KEYWORDS_PATTERN.search(content):
        return True

    # 2. 記録系明示キーワード
    if _RECORD_EXPLICIT_PATTERN.search(content):
        return True

    # 3. 過去予測参照
    if _PAST_PREDICTION_PATTERN.search(content):
        return True

    return False


def _check_free_triggers(content: str) -> bool:
    """自由モード（会話）のシグナルをチェック"""
    return bool(_FREE_MODE_PATTERN.search(content))
