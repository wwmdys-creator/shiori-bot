"""
errors.py - キャラクター口調エラーメッセージモジュール

Q23: B案 - キャラクター口調でエラーメッセージを返す
"""

from enum import Enum
from typing import Optional
import random


class ErrorType(Enum):
    """エラーの種類"""
    LINK_FETCH_FAILED = "link_fetch_failed"
    LINK_TIMEOUT = "link_timeout"
    API_RATE_LIMIT = "api_rate_limit"
    API_ERROR = "api_error"
    PARSE_ERROR = "parse_error"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_INPUT = "invalid_input"
    DATABASE_ERROR = "database_error"
    UNKNOWN = "unknown"


# エラータイプごとのキャラクター口調メッセージ
ERROR_MESSAGES = {
    ErrorType.LINK_FETCH_FAILED: [
        "あっ、すみません……このリンク、うまく開けませんでした📎💦 URLが正しいか確認してもらえますか？",
        "ごめんなさい、このページにアクセスできませんでした……🙏 リンクが有効か確認してもらえると助かります",
        "うーん、このURLは読み込めないみたいです……📎 もしかしてリンク切れでしょうか？",
    ],
    
    ErrorType.LINK_TIMEOUT: [
        "ページの読み込みに時間がかかりすぎちゃいました……後でもう一度試してみますね📎",
        "あっ、タイムアウトしてしまいました……💦 サーバーが混んでいるのかもしれません",
        "すみません、ページの応答が遅くて断念しました……🙏 少し時間を置いて再度お願いできますか？",
    ],
    
    ErrorType.API_RATE_LIMIT: [
        "ごめんなさい、今ちょっと処理が混み合っていて……少し時間を置いてから呼んでください🙏",
        "あっ、リクエストが多すぎたみたいです……📎💦 少し休憩してからまた呼んでもらえますか？",
        "処理の制限に引っかかっちゃいました……🙏 数分待ってから再度試してみてください",
    ],
    
    ErrorType.API_ERROR: [
        "あっ、なにかエラーが起きてしまいました……📎💦 すみません、もう一度試してもらえますか？",
        "ごめんなさい、処理中にエラーが発生しました……🙏 お手数ですがもう一度お願いできますか？",
        "うーん、うまく処理できませんでした……📎 申し訳ないですが、再度お試しください",
    ],
    
    ErrorType.PARSE_ERROR: [
        "あっ、データの解析がうまくいきませんでした……📎💦 形式が想定と違うのかもしれません",
        "ごめんなさい、内容を正しく読み取れませんでした……🙏",
        "うーん、このデータはちょっと読み取りにくいみたいです……📎",
    ],
    
    ErrorType.NOT_FOUND: [
        "あれ、探してみたんですが見つかりませんでした……📎 検索条件を変えてみますか？",
        "うーん、該当するデータが見つかりません……🙏 別のキーワードで試してみましょうか？",
        "ごめんなさい、その記録は見当たりませんでした……📎💦",
    ],
    
    ErrorType.PERMISSION_DENIED: [
        "あっ、この操作はわたしには許可されていないみたいです……📎💦",
        "ごめんなさい、権限がなくてできませんでした……🙏",
        "うーん、アクセス権限の問題みたいです……📎",
    ],
    
    ErrorType.INVALID_INPUT: [
        "あっ、入力の形式がちょっと違うみたいです……📎 もう少し詳しく教えてもらえますか？",
        "ごめんなさい、うまく理解できませんでした……🙏 別の言い方で教えてもらえますか？",
        "うーん、ちょっとわかりにくかったです……📎 具体的に教えてもらえると助かります",
    ],
    
    ErrorType.DATABASE_ERROR: [
        "あっ、記録の保存でエラーが起きてしまいました……📎💦 お手数ですがもう一度お願いします",
        "ごめんなさい、データベースの問題みたいです……🙏 しばらくしてから再度お試しください",
        "うーん、フィールドノートの書き込みに失敗しました……📎💦",
    ],
    
    ErrorType.UNKNOWN: [
        "あっ、予期しないエラーが発生しました……📎💦 すみません、もう一度試してもらえますか？",
        "ごめんなさい、なにか問題が起きたみたいです……🙏 お手数ですが再度お願いできますか？",
        "うーん、よくわからないエラーです……📎 申し訳ないですが、しばらくしてからお試しください",
    ],
}


def get_error_message(
    error_type: ErrorType,
    details: Optional[str] = None,
    trust_level: int = 1
) -> str:
    """
    エラータイプに応じたキャラクター口調のエラーメッセージを取得
    
    Args:
        error_type: エラーの種類
        details: エラーの詳細（あれば追加）
        trust_level: 信頼度レベル（1-5）、高いほどカジュアルに
    
    Returns:
        キャラクター口調のエラーメッセージ
    """
    messages = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES[ErrorType.UNKNOWN])
    message = random.choice(messages)
    
    # 信頼度が高い場合は少しカジュアルな追加
    if trust_level >= 4 and details:
        message += f"\n（技術的には：{details}）"
    
    return message


def format_link_error(url: str, error_type: ErrorType) -> str:
    """
    リンク関連エラーのフォーマット
    
    Args:
        url: 問題のURL
        error_type: エラーの種類
    
    Returns:
        フォーマットされたエラーメッセージ
    """
    base_message = get_error_message(error_type)
    
    # URLが長すぎる場合は省略
    display_url = url
    if len(url) > 50:
        display_url = url[:47] + "..."
    
    return f"{base_message}\n\n対象URL: {display_url}"


def format_prediction_error(
    action: str,
    prediction_id: Optional[str] = None
) -> str:
    """
    予測記録関連エラーのフォーマット
    
    Args:
        action: 失敗した操作（"記録", "検索", "更新" など）
        prediction_id: 予測ID（あれば）
    
    Returns:
        フォーマットされたエラーメッセージ
    """
    base_message = get_error_message(ErrorType.DATABASE_ERROR)
    
    if prediction_id:
        return f"{base_message}\n\n操作: 予測 #{prediction_id} の{action}"
    else:
        return f"{base_message}\n\n操作: 予測の{action}"


class ShioriError(Exception):
    """栞Bot用のカスタム例外"""
    
    def __init__(
        self,
        error_type: ErrorType,
        message: str = "",
        details: Optional[str] = None
    ):
        self.error_type = error_type
        self.details = details
        self.character_message = get_error_message(error_type, details)
        super().__init__(message or self.character_message)
    
    def get_user_message(self, trust_level: int = 1) -> str:
        """ユーザーに表示するメッセージを取得"""
        return get_error_message(self.error_type, self.details, trust_level)


# よく使うエラーのショートカット
class LinkFetchError(ShioriError):
    def __init__(self, url: str, details: Optional[str] = None):
        self.url = url
        super().__init__(ErrorType.LINK_FETCH_FAILED, f"Failed to fetch: {url}", details)


class TimeoutError(ShioriError):
    def __init__(self, operation: str = "operation", details: Optional[str] = None):
        super().__init__(ErrorType.LINK_TIMEOUT, f"Timeout during {operation}", details)


class RateLimitError(ShioriError):
    def __init__(self, details: Optional[str] = None):
        super().__init__(ErrorType.API_RATE_LIMIT, "Rate limit exceeded", details)


class PredictionNotFoundError(ShioriError):
    def __init__(self, query: str = "", details: Optional[str] = None):
        super().__init__(ErrorType.NOT_FOUND, f"Prediction not found: {query}", details)
