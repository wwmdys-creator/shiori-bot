"""
summarizer.py - リンク要約モジュール

栞（Shiori）Bot用のリンク取得・要約機能
要点は3つ以内で「索引レベル」に留める（Q15: A案）
Rom🧄の深い解説とは差別化
"""

import re
import asyncio
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from errors import ErrorType, get_error_message, LinkFetchError, TimeoutError


@dataclass
class LinkSummary:
    """リンク要約結果"""
    url: str
    title: str
    domain: str
    summary_points: list[str]  # 最大3つ
    related_prediction_ids: list[int]  # 関連する予測ID
    success: bool
    error_message: Optional[str] = None


class Summarizer:
    """リンク要約クラス"""
    
    # 取得タイムアウト（秒）
    FETCH_TIMEOUT = 15
    
    # 最大コンテンツ長（文字）
    MAX_CONTENT_LENGTH = 15000
    
    # 要約ポイント数
    MAX_SUMMARY_POINTS = 3
    
    def __init__(self):
        self._llm = None
    
    @property
    def llm(self):
        """LLMモジュールを遅延読み込み"""
        if self._llm is None:
            from llm import get_llm
            self._llm = get_llm()
        return self._llm
    
    async def summarize_link(
        self,
        url: str,
        trust_level: int = 1
    ) -> LinkSummary:
        """
        リンクを取得して要約
        
        Args:
            url: 要約対象URL
            trust_level: 信頼度レベル（エラーメッセージのトーンに影響）
        
        Returns:
            LinkSummary: 要約結果
        """
        domain = self._extract_domain(url)
        
        # URLの検証
        if not self._is_valid_url(url):
            return LinkSummary(
                url=url,
                title="",
                domain=domain,
                summary_points=[],
                related_prediction_ids=[],
                success=False,
                error_message=get_error_message(
                    ErrorType.INVALID_INPUT,
                    trust_level,
                    context="このURL、形式がおかしいかもしれません"
                )
            )
        
        # ページ取得
        try:
            html_content = await self._fetch_page(url)
        except TimeoutError:
            return LinkSummary(
                url=url,
                title="",
                domain=domain,
                summary_points=[],
                related_prediction_ids=[],
                success=False,
                error_message=get_error_message(
                    ErrorType.LINK_TIMEOUT,
                    trust_level
                )
            )
        except LinkFetchError as e:
            return LinkSummary(
                url=url,
                title="",
                domain=domain,
                summary_points=[],
                related_prediction_ids=[],
                success=False,
                error_message=get_error_message(
                    ErrorType.LINK_FETCH_FAILED,
                    trust_level,
                    context=str(e)
                )
            )
        
        # HTMLパース
        title, text_content = self._parse_html(html_content)
        
        if not text_content:
            return LinkSummary(
                url=url,
                title=title,
                domain=domain,
                summary_points=[],
                related_prediction_ids=[],
                success=False,
                error_message=get_error_message(
                    ErrorType.PARSE_ERROR,
                    trust_level,
                    context="ページの内容を読み取れませんでした"
                )
            )
        
        # LLMで要約生成
        try:
            summary_points = await self._generate_summary(
                title, 
                text_content, 
                url
            )
        except Exception as e:
            return LinkSummary(
                url=url,
                title=title,
                domain=domain,
                summary_points=[],
                related_prediction_ids=[],
                success=False,
                error_message=get_error_message(
                    ErrorType.API_ERROR,
                    trust_level,
                    context=f"要約生成でエラー: {str(e)[:50]}"
                )
            )
        
        # 関連予測を検索
        related_ids = await self._find_related_predictions(
            title, 
            text_content
        )
        
        return LinkSummary(
            url=url,
            title=title,
            domain=domain,
            summary_points=summary_points,
            related_prediction_ids=related_ids,
            success=True
        )
    
    async def _fetch_page(self, url: str) -> str:
        """ページを取得"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; ShioriBot/1.0; "
                "+https://github.com/shiori-bot)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en;q=0.9"
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.FETCH_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise LinkFetchError(
                            f"HTTPステータス: {response.status}"
                        )
                    return await response.text()
        except asyncio.TimeoutError:
            raise TimeoutError("ページ取得がタイムアウトしました")
        except aiohttp.ClientError as e:
            raise LinkFetchError(f"接続エラー: {str(e)[:50]}")
    
    def _parse_html(self, html: str) -> tuple[str, str]:
        """HTMLをパースしてタイトルと本文を抽出"""
        soup = BeautifulSoup(html, "html.parser")
        
        # タイトル取得
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        
        # 不要な要素を削除
        for element in soup.find_all(
            ["script", "style", "nav", "header", "footer", 
             "aside", "form", "iframe", "noscript"]
        ):
            element.decompose()
        
        # 本文抽出
        # 優先順位: article > main > body
        content_element = (
            soup.find("article") or 
            soup.find("main") or 
            soup.find("body")
        )
        
        if content_element:
            text = content_element.get_text(separator="\n", strip=True)
            # 連続する空行を削除
            text = re.sub(r'\n{3,}', '\n\n', text)
            # 最大長で切り詰め
            if len(text) > self.MAX_CONTENT_LENGTH:
                text = text[:self.MAX_CONTENT_LENGTH] + "..."
            return (title, text)
        
        return (title, "")
    
    async def _generate_summary(
        self, 
        title: str, 
        content: str,
        url: str
    ) -> list[str]:
        """LLMで要約を生成"""
        prompt = f"""以下のウェブページの内容を、最大3つの要点で簡潔に要約してください。

【重要な制約】
- 要点は3つ以内
- 各要点は1〜2文で簡潔に
- 「索引レベル」の要約に留める（詳しい解説は不要）
- 未来予測に関連する内容があれば優先的に含める
- 数字やデータは具体的に残す

タイトル: {title}
URL: {url}

本文:
{content[:8000]}

要点を以下のJSON形式で出力してください:
["要点1", "要点2", "要点3"]

要点が3つ未満でも問題ありません。"""

        response = await self.llm.generate_response(prompt)
        
        # JSON部分を抽出
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if json_match:
            import json
            try:
                points = json.loads(json_match.group())
                return points[:self.MAX_SUMMARY_POINTS]
            except json.JSONDecodeError:
                pass
        
        # JSONパースに失敗した場合、行で分割
        lines = [
            line.strip().lstrip("•-・").strip()
            for line in response.split("\n")
            if line.strip() and not line.startswith("[")
        ]
        return lines[:self.MAX_SUMMARY_POINTS]
    
    async def _find_related_predictions(
        self, 
        title: str, 
        content: str
    ) -> list[int]:
        """関連する予測を検索"""
        from predictions import get_prediction_ledger
        
        ledger = get_prediction_ledger()
        
        # 年号を抽出
        years = re.findall(r'20[2-9]\d', title + content)
        years = [int(y) for y in set(years)]
        
        related_ids = []
        
        # 各年号で検索
        for year in years[:3]:  # 最大3年分
            predictions = ledger.search(year=year, limit=5)
            for p in predictions:
                if p.id not in related_ids:
                    related_ids.append(p.id)
                    if len(related_ids) >= 5:
                        return related_ids
        
        return related_ids
    
    def _extract_domain(self, url: str) -> str:
        """URLからドメインを抽出"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return "unknown"
    
    def _is_valid_url(self, url: str) -> bool:
        """URLが有効か検証"""
        try:
            result = urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False
    
    def format_summary(self, summary: LinkSummary) -> str:
        """要約結果をDiscord投稿用にフォーマット"""
        if not summary.success:
            return summary.error_message or "要約に失敗しました"
        
        lines = [
            "📎 リンク要約",
            f"出典: [{summary.title or '無題'}] ({summary.domain})",
            ""
        ]
        
        # 要点
        if summary.summary_points:
            lines.append("要点:")
            for i, point in enumerate(summary.summary_points, 1):
                lines.append(f"  {i}. {point}")
        
        # 関連予測
        if summary.related_prediction_ids:
            lines.append("")
            ids_str = ", ".join(
                f"#{pid}" for pid in summary.related_prediction_ids[:3]
            )
            lines.append(f"予測台帳との関連: {ids_str}")
        
        return "\n".join(lines)


# シングルトンインスタンス
_summarizer: Optional[Summarizer] = None


def get_summarizer() -> Summarizer:
    """Summarizerインスタンスを取得"""
    global _summarizer
    if _summarizer is None:
        _summarizer = Summarizer()
    return _summarizer
