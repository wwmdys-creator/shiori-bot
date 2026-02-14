"""
📎 栞（Shiori）v5.2 — HaikuContextManager
Shiori_v5_2_Interface_Contract.md §6.2 に準拠

Haiku呼び出し用のコンテキスト管理。
F-04: 必ず truncate() を経由してからHaikuに渡す。
F-05: 1回の呼び出しで全部やろうとしない。
"""

from config import (
    HAIKU_MAX_MESSAGE_CHARS,
    HAIKU_MAX_CONTEXT_CHARS,
    HAIKU_MAX_SUMMARY_CHARS,
)


class HaikuContextManager:
    """Haiku呼び出し用のコンテキスト管理"""

    @staticmethod
    def truncate(text: str, max_chars: int) -> str:
        """
        テキストを指定文字数に切り詰め。
        超過時は末尾を「...」に置換。
        """
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        if max_chars <= 3:
            return text[:max_chars]
        return text[: max_chars - 3] + "..."

    @staticmethod
    def summarize_shiori_response(response: str) -> str:
        """
        栞の返信を要約（最初の文のみ抽出）。
        HAIKU_MAX_SUMMARY_CHARS 以下に切り詰め。
        """
        if not response:
            return ""
        # 最初の文を抽出（句点・改行で区切る）
        for delimiter in ("。", "\n", "！", "？"):
            idx = response.find(delimiter)
            if idx != -1:
                first_sentence = response[: idx + 1]
                return HaikuContextManager.truncate(
                    first_sentence, HAIKU_MAX_SUMMARY_CHARS
                )
        # 区切りがない場合はそのまま切り詰め
        return HaikuContextManager.truncate(response, HAIKU_MAX_SUMMARY_CHARS)

    def prepare_cfr_context(
        self,
        shiori_response: str,
        target_message: str,
    ) -> dict:
        """
        CFR判定用の最小コンテキストを準備。

        Returns:
            {
                "shiori_summary": str,  # HAIKU_MAX_SUMMARY_CHARS以下
                "target": str,          # HAIKU_MAX_MESSAGE_CHARS以下
            }
        """
        return {
            "shiori_summary": self.summarize_shiori_response(shiori_response),
            "target": self.truncate(target_message, HAIKU_MAX_MESSAGE_CHARS),
        }

    def prepare_learning_context(
        self,
        message: str,
        category: str,
    ) -> dict:
        """
        動的学習用の最小コンテキストを準備。

        Returns:
            {
                "message": str,   # HAIKU_MAX_MESSAGE_CHARS以下
                "category": str,
            }
        """
        return {
            "message": self.truncate(message, HAIKU_MAX_MESSAGE_CHARS),
            "category": category,
        }
