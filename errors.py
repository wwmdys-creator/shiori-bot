"""errors.py — 栞（Shiori）エラーハンドリングモジュール

エラー種別に応じたキャラクター口調のエラーメッセージを生成する（Q23: B案）。

参照: interface_contract.md §2.13, system_prompt.txt §9
"""

import logging
import random

logger = logging.getLogger("shiori.errors")

# エラーメッセージテンプレート（複数バリエーション）
ERROR_MESSAGES = {
    "link_fetch_failed": [
        "あっ、すみません……このリンク、うまく開けませんでした📎💦 URLが正しいか確認してもらえますか？",
        "ごめんなさい、リンク先にアクセスできませんでした……💦 もしかしてリンク切れかもしれません",
        "あれ、このURL開けないです……📎 別のリンクがあれば試してみますか？",
    ],
    "timeout": [
        "ページの読み込みに時間がかかりすぎちゃいました……後でもう一度試してみますね",
        "すみません、ちょっと処理に時間がかかりすぎてしまって……💦 少し待ってから再度お願いします",
        "タイムアウトしちゃいました📎💦 ネットワークが混んでるのかも……",
    ],
    "api_limit": [
        "ごめんなさい、今ちょっと処理が混み合っていて……少し時間を置いてから呼んでください🙏",
        "あっ、今リクエストが多くて処理が追いつかないみたいです……少々お待ちを💦",
        "すみません、一時的に処理能力の上限に達してしまいました……しばらくしてからお願いします🙏",
    ],
    "unknown": [
        "えっと……すみません、ちょっと何かうまくいかなかったみたいです。もう一度試してもらえますか？",
        "あれ、なんだかエラーが出ちゃいました……📎💦 もう一度お願いできますか？",
        "ごめんなさい、予期しないエラーが起きました……もう一度試してみてください🙏",
    ],
    "permission_denied": [
        "あっ、このチャンネルでは発言する権限がないみたいです……📎💦",
        "すみません、ここでは応答できないようです……別のチャンネルで呼んでもらえますか？",
    ],
    "invalid_input": [
        "えっと……入力の形式がちょっと違うみたいです。もう一度確認してもらえますか？📎",
        "あれ、ちょっと理解できませんでした……別の言い方でお願いできますか？💦",
    ],
    "not_found": [
        "探してみたんですけど、見つかりませんでした……📎💦",
        "すみません、該当するものが見当たらないです……条件を変えて探してみますか？",
    ],
    "rate_limited": [
        "あっ、ちょっと呼びすぎかも……少し間を置いてからお願いします🙏",
        "すみません、クールダウン中です💦 もう少々お待ちください📎",
    ],
}


def format_error_message(error_type: str) -> str:
    """エラー種別に応じたキャラクター口調のエラーメッセージを返す。

    同期関数（Q23: B案）。

    Args:
        error_type: エラー種別
            - "link_fetch_failed": リンク取得失敗
            - "timeout": タイムアウト
            - "api_limit": API制限
            - "unknown": 汎用エラー
            - "permission_denied": 権限エラー
            - "invalid_input": 入力エラー
            - "not_found": 見つからない
            - "rate_limited": レート制限

    Returns:
        str: 栞のキャラクター口調のエラーメッセージ
    """
    messages = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown"])
    selected = random.choice(messages)

    logger.debug(f"[format_error_message] type={error_type}, msg={selected[:30]}...")

    return selected


def format_api_error(error: Exception) -> str:
    """API例外からエラーメッセージを生成する。

    Args:
        error: 発生した例外

    Returns:
        str: エラーメッセージ
    """
    error_str = str(error).lower()

    if "timeout" in error_str:
        return format_error_message("timeout")
    elif "rate" in error_str or "limit" in error_str:
        return format_error_message("api_limit")
    elif "permission" in error_str or "forbidden" in error_str:
        return format_error_message("permission_denied")
    elif "not found" in error_str or "404" in error_str:
        return format_error_message("not_found")
    else:
        return format_error_message("unknown")


def format_network_error(url: str, error: Exception) -> str:
    """ネットワークエラーからエラーメッセージを生成する。

    Args:
        url: 対象URL
        error: 発生した例外

    Returns:
        str: エラーメッセージ
    """
    error_str = str(error).lower()

    if "timeout" in error_str:
        return format_error_message("timeout")
    elif "ssl" in error_str or "certificate" in error_str:
        return "あっ、セキュリティ証明書の問題でアクセスできないみたいです……📎💦"
    elif "dns" in error_str or "resolve" in error_str:
        return "えっと、このURLのサーバーが見つからないです……アドレスを確認してもらえますか？📎"
    else:
        return format_error_message("link_fetch_failed")


class ShioriError(Exception):
    """栞専用のエラークラス。"""

    def __init__(self, error_type: str, detail: str = ""):
        self.error_type = error_type
        self.detail = detail
        self.message = format_error_message(error_type)
        super().__init__(self.message)


class LinkFetchError(ShioriError):
    """リンク取得エラー。"""

    def __init__(self, url: str, detail: str = ""):
        self.url = url
        super().__init__("link_fetch_failed", detail)


class TimeoutError(ShioriError):
    """タイムアウトエラー。"""

    def __init__(self, detail: str = ""):
        super().__init__("timeout", detail)


class APILimitError(ShioriError):
    """API制限エラー。"""

    def __init__(self, detail: str = ""):
        super().__init__("api_limit", detail)
