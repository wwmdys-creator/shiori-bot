"""
📎 栞（Shiori）v5.2 — メンバー質問検出
Shiori_v5_2_Interface_Contract.md §8.1 に準拠

F-15: 正規表現プレチェックでメンバー質問を検出してからHaiku分類。
"""

import logging
import re

logger = logging.getLogger("shiori.member_query")


class MemberQueryDetector:
    """メンバー質問検出"""

    QUERY_PATTERNS: list[re.Pattern] = [
        re.compile(r"([^\s]+?)さん(?:について|って|の(?:印象|こと|紹介))"),
        re.compile(r"([^\s]+?)(?:について|って誰|とは|ってどんな)"),
    ]

    def detect_queried_member(self, message: str) -> str | None:
        """
        質問されているメンバー名を検出。

        Returns:
            str: メンバー名
            None: メンバー質問ではない
        """
        for pattern in self.QUERY_PATTERNS:
            match = pattern.search(message)
            if match:
                name = match.group(1).strip()
                # 明らかに短すぎるor一般的な語は除外
                if len(name) < 2:
                    continue
                # 「それ」「これ」「あれ」等の指示語は除外
                if name in ("それ", "これ", "あれ", "どれ", "何"):
                    continue
                logger.debug("Member query detected: '%s'", name)
                return name
        return None

    def build_highlight(self, member_profile: dict) -> str:
        """
        ハイライトブロックを生成。

        Args:
            member_profile: メンバープロファイル辞書
                keys: display_name, position, interests, dynamic_memos

        Returns:
            ハイライトフォーマットされた文字列
        """
        name = member_profile.get("display_name", "不明")
        position = member_profile.get("position", "")
        interests = member_profile.get("interests", [])
        memos = member_profile.get("dynamic_memos", [])

        parts = [f"【{name}さんのプロフィール】"]
        if position:
            parts.append(f"ポジション: {position}")
        if interests:
            parts.append(f"関心領域: {', '.join(interests[:5])}")
        if memos:
            # 最新3件のみ
            recent = memos[-3:]
            parts.append("最近のメモ: " + " / ".join(recent))

        return "\n".join(parts)
