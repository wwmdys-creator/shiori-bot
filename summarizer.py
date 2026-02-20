"""summarizer.py — 栞（Shiori）リンク要約モジュール

URLの内容を取得し、T5テンプレートでLLMを使い要約する。
aiohttp + BeautifulSoup でページ取得。

依存: llm.py, errors.py
参照: interface_contract.md §2.8, prompt_templates.md T5
"""

import re
import logging
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from errors import format_error_message

logger = logging.getLogger("shiori.summarizer")

# T5 システムプロンプト
T5_SYSTEM_PROMPT = (
    "あなたはリンク要約アシスタントです。\n"
    "ウェブページの内容を「索引レベル」の簡潔さで要約します。\n"
    "深い解説は不要です。要点のみを箇条書きにしてください。\n"
    "JSONのみを出力してください。"
)

# T5 ユーザープロンプトテンプレート
T5_USER_TEMPLATE = """以下のウェブページ内容を要約してください。

URL: {url}
ページタイトル: {page_title}
ページ本文（抜粋）:
{page_text_truncated}

ルール:
1. 要点を3つ以内に絞る
2. 各要点は1文（40字以内）
3. 「索引レベル」の簡潔さ（詳細解説はしない）
4. 予測台帳の既存レコードとの関連があれば示唆する

関連しうる既存予測キーワード: {related_keywords}

以下のJSON形式で回答してください:
{{"title": "ページタイトル", "domain": "ドメイン名", "points": ["要点1", "要点2", "要点3"], "related_prediction_hint": "関連予測のヒント（なければnull）"}}"""

# ページ本文の最大文字数
MAX_PAGE_TEXT_CHARS = 3000

# aiohttp タイムアウト秒数
FETCH_TIMEOUT_SECONDS = 15


class LinkSummarizer:
    """リンク要約クラス。

    Attributes:
        llm: LLMClient インスタンス
    """

    def __init__(self, llm):
        self.llm = llm

    async def summarize_url(
        self,
        url: str,
        related_keywords: list[str] | None = None,
    ) -> dict | None:
        """URLの内容を取得し、T5テンプレートで要約する。

        Args:
            url: 要約対象のURL
            related_keywords: 予測台帳から関連しうるキーワード

        Returns:
            dict | None: {"title": str, "domain": str,
                          "points": list[str],
                          "related_prediction_hint": str | None} | None
        """
        # ページ取得
        page = await self._fetch_page(url)
        if page is None:
            return None

        # ドメイン抽出
        parsed = urlparse(url)
        domain = parsed.netloc or "不明"

        # キーワード文字列化
        keywords_str = "、".join(related_keywords) if related_keywords else "なし"

        # 本文を最大文字数に切り詰め
        page_text = page["text"][:MAX_PAGE_TEXT_CHARS]

        user_prompt = T5_USER_TEMPLATE.format(
            url=url,
            page_title=page["title"],
            page_text_truncated=page_text,
            related_keywords=keywords_str,
        )

        result = await self.llm.call_template(
            template_name="T5",
            system=T5_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=300,
            temperature=0.5,
            use_sonnet=True,  # T5: リンク要約はSonnetで実行
        )

        if result is None:
            logger.warning(f"T5 summarization failed for {url}")
            return None

        # デフォルト値補完
        return {
            "title": result.get("title", page["title"]),
            "domain": result.get("domain", domain),
            "points": result.get("points", []),
            "related_prediction_hint": result.get("related_prediction_hint"),
        }

    async def _fetch_page(self, url: str) -> dict | None:
        """ページを取得してタイトルと本文テキストを返す。

        Args:
            url: 取得対象のURL

        Returns:
            dict | None: {"title": str, "text": str} | None（失敗時）
        """
        try:
            timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Fetch failed: {url} (status={response.status})"
                        )
                        return None

                    html = await response.text(errors="replace")

        except aiohttp.ClientError as e:
            logger.warning(f"HTTP error fetching {url}: {e}")
            return None
        except TimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return None

        # BeautifulSoup でパース
        soup = BeautifulSoup(html, "html.parser")

        # タイトル抽出
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "タイトル不明"

        # 本文抽出（script/style除去）
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        # 空行の圧縮
        text = re.sub(r'\n{3,}', '\n\n', text)

        return {"title": title, "text": text}

    def format_summary(self, result: dict) -> str:
        """T5結果を栞の応答形式にフォーマットする。同期メソッド。

        Args:
            result: summarize_url() の戻り値

        Returns:
            str: フォーマット済みの要約テキスト
        """
        title = result.get("title", "タイトル不明")
        domain = result.get("domain", "不明")
        points = result.get("points", [])
        hint = result.get("related_prediction_hint")

        lines = [
            f"📎 リンク要約",
            f"出典: {title} ({domain})",
        ]

        if points:
            points_str = " ".join(
                f"{'①②③④⑤'[i]}{p}" for i, p in enumerate(points[:5])
            )
            lines.append(f"要点: {points_str}")

        if hint:
            lines.append(f"予測台帳との関連: {hint}")

        return "\n".join(lines)
