"""
response_mode.py - 応答モード判定（Record/Free Mode Router）

Shiori v5.3 - §3.3 応答モード判定（記録モード／自由モード）
Interface Contract: §12.7.1
Error Pattern: F-15（応答タイプ判定の過信）

メンション時の応答を「記録モード」と「自由モード」に分離し、
メッセージの内容に応じて適切なモードを選択する。

記録モード: 構造化フォーマットを用いた予測記録応答
自由モード: 会話形式の自然な応答（栞のキャラクターが前面に出る）
"""

import re
import logging

import discord

logger = logging.getLogger(__name__)


# =====================================================================
# 定数: トリガーパターン
# =====================================================================

# --- 年号パターン ---
# 2025以降の4桁年号を検出
_YEAR_PATTERN = re.compile(
    r'(?:20[2-9]\d|2[1-9]\d{2})\s*年'
)

# --- 予測的キーワード ---
# 年号と組み合わせて記録モードを判定する
_PREDICTION_KEYWORDS = re.compile(
    r'(?:'
    r'になる|になっている|が実現|が完成|が登場|が普及|が達成'
    r'|が可能|ができる|が始まる|が起こる|が発生|が到来'
    r'|だろう|でしょう|と思う|と予想|と予測|と考え'
    r'|するはず|している|されている|が来る|を超える|を達成'
    r'|までに|以降|頃には|代には|代半ば|年代'
    r')',
    re.IGNORECASE
)

# --- 記録系明示キーワード ---
# これ単体で記録モードをトリガーする
_RECORD_EXPLICIT_KEYWORDS = re.compile(
    r'(?:'
    r'記録して|メモして|残して|予測として|台帳に|予測記録'
    r'|記録お願い|記録よろしく|予測登録'
    r')',
    re.IGNORECASE
)

# --- 過去予測参照キーワード ---
# 過去の予測データへの参照を示す
_PAST_PREDICTION_KEYWORDS = re.compile(
    r'(?:'
    r'前の予測|前回の予測|過去の予測|前に言った|前回何|前回なん'
    r'|以前の予測|最初の予測|前回と比べ|前と比べ'
    r')',
    re.IGNORECASE
)

# --- 自由モード強制トリガー ---
# 予測要素があっても自由モードにする会話的パターン
_FREE_MODE_INDICATORS = re.compile(
    r'(?:'
    r'どう思う|どう考える|意見|感想|教えて|質問'
    r'|みんな|皆|どうですか|どうかな|ですかね'
    r'|なんだけど|んだけど|けどさ|だよね|よね'
    r')',
    re.IGNORECASE
)


# =====================================================================
# 公開API
# =====================================================================

def determine_response_mode(message_content: str) -> str:
    """メッセージ内容から応答モードを判定する（§3.3参照）

    Args:
        message_content: [必須] メッセージ内容（メンション部分は除去済み）

    Returns:
        "record": 記録モード（年号＋予測キーワード、記録系キーワード等）
        "free":   自由モード（上記以外すべて）

    ⚠️ Q2決定: 記録トリガーと自由トリガーの両方に該当する場合は "free" を返す
    ⚠️ 本関数はメンション応答のみで使用する（CFR応答やリアクションでは不使用）

    判定フロー:
        1. 記録系明示キーワードの検出 → "record"候補
        2. 過去予測参照キーワードの検出 → "record"候補
        3. 年号＋予測キーワードの組み合わせ検出 → "record"候補
        4. 自由モード強制トリガーが同時に存在 → "free"（Q2決定: 競合時は自由モード優先）
        5. record候補が確定していれば "record"
        6. 上記いずれにも該当しなければ "free"
    """
    if not message_content or not message_content.strip():
        return "free"

    content = message_content.strip()
    is_record_candidate = False

    # Step 1: 記録系明示キーワード
    if _RECORD_EXPLICIT_KEYWORDS.search(content):
        is_record_candidate = True
        logger.debug(f"[ResponseMode] Record trigger: explicit keyword")

    # Step 2: 過去予測参照キーワード
    if _PAST_PREDICTION_KEYWORDS.search(content):
        is_record_candidate = True
        logger.debug(f"[ResponseMode] Record trigger: past prediction ref")

    # Step 3: 年号＋予測キーワードの組み合わせ
    if _YEAR_PATTERN.search(content) and _PREDICTION_KEYWORDS.search(content):
        is_record_candidate = True
        logger.debug(f"[ResponseMode] Record trigger: year + prediction kw")

    # Step 4: Q2決定 — 自由モードトリガーとの競合チェック
    # 両方に該当する場合は「自由モード」を優先
    if is_record_candidate and _FREE_MODE_INDICATORS.search(content):
        logger.info(
            f"[ResponseMode] Conflict detected: "
            f"record + free triggers → resolved to 'free' (Q2 decision)"
        )
        return "free"

    # Step 5: 記録候補が残っていれば "record"
    if is_record_candidate:
        logger.info(f"[ResponseMode] Mode: record")
        return "record"

    # Step 6: デフォルトは自由モード
    logger.debug(f"[ResponseMode] Mode: free (default)")
    return "free"


def has_prediction_content(message_content: str) -> bool:
    """メッセージに予測的内容が含まれるかを簡易判定する

    自由モード応答時に、予測部分を内部記録すべきかの判定に使用。
    determine_response_mode() とは独立した判定で、
    年号＋予測キーワードの存在のみをチェックする。

    Args:
        message_content: [必須] メッセージ内容

    Returns:
        bool: 予測的内容が含まれる場合 True
    """
    if not message_content:
        return False
    content = message_content.strip()
    return bool(
        _YEAR_PATTERN.search(content) and _PREDICTION_KEYWORDS.search(content)
    )


async def _silent_record_prediction(
    message: discord.Message,
    record_callback=None,
) -> None:
    """自由モード時に予測部分のみを内部記録する

    自由モード応答が選択されたが、メッセージに予測的内容が含まれる場合に
    呼び出す。フォーマット型の応答は出力せず、内部データのみを更新する。

    Args:
        message:          [必須] Discord メッセージオブジェクト
        record_callback:  [任意] 予測記録を実行するコールバック関数
                          シグネチャ: async def callback(message) -> None
                          Noneの場合は記録をスキップ（テスト用）

    ⚠️ フォーマット型の応答は出力しない
    ⚠️ 記録が失敗しても応答処理をブロックしない（独立try/except）
    """
    try:
        if record_callback is not None:
            await record_callback(message)
            logger.info(
                f"[SilentRecord] Prediction silently recorded "
                f"for {message.author.display_name} (msg:{message.id})"
            )
        else:
            logger.debug(
                f"[SilentRecord] No record_callback provided, "
                f"skipping silent record for msg:{message.id}"
            )
    except Exception as e:
        # 記録失敗は応答処理をブロックしない（エラー隔離原則）
        logger.error(
            f"[SilentRecord] Failed for msg:{message.id}: {e}"
        )
