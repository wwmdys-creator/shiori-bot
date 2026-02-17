"""
📎 栞（Shiori）v5.3 — カスタム例外（リダイレクトモジュール）

v5.3-P0P1-v3: ShioriError の重複定義を解消。
  - errors.py の ShioriError（error_type引数付き）が正式定義
  - 本ファイルは後方互換のため errors.py から再エクスポートするのみ
  - ContextLimitExceeded, MemberNotFound, CFRContextExpired は
    現在どこからも import されていないデッドコード（削除）

旧定義（v5.2）:
  exceptions.py: ShioriError(Exception) — 引数なし
  errors.py:126: ShioriError(Exception) — error_type, detail 引数

統合方針: errors.py 側を正とし、本ファイルは互換リダイレクトのみ残す。
"""

# errors.py の ShioriError を再エクスポート（後方互換）
from errors import ShioriError, LinkFetchError, TimeoutError, APILimitError

__all__ = ["ShioriError", "LinkFetchError", "TimeoutError", "APILimitError"]
