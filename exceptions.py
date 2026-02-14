"""
📎 栞（Shiori）v5.2 — カスタム例外
Shiori_v5_2_Interface_Contract.md §9 に準拠
"""


class ShioriError(Exception):
    """Shiori基底例外"""
    pass


class ContextLimitExceeded(ShioriError):
    """コンテキスト文字数制限超過"""

    def __init__(self, actual: int, limit: int):
        self.actual = actual
        self.limit = limit
        super().__init__(f"Context limit exceeded: {actual} > {limit}")


class MemberNotFound(ShioriError):
    """メンバーが見つからない"""

    def __init__(self, query: str):
        self.query = query
        super().__init__(f"Member not found: {query}")


class CFRContextExpired(ShioriError):
    """CFRコンテキスト期限切れ"""
    pass
