"""categories.py — 栞（Shiori）カテゴリ管理モジュール

予測のカテゴリ分類を行う。T2テンプレートを使用。

参照: interface_contract.md §2.5, prompt_templates.md T2
"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm import LLMClient

logger = logging.getLogger("shiori.categories")

# T2テンプレート（カテゴリ分類）
T2_SYSTEM = """あなたは予測記録システムの分類エンジンです。
与えられた予測テキストを適切なカテゴリに分類してください。

出力形式は必ずJSON形式で:
{
  "categories": ["大分類 / 小分類", ...],
  "is_new_category": true/false,
  "suggested_new_category": "新規カテゴリ案（is_new_category=trueの場合のみ）"
}

カテゴリは1〜3個を選択してください。"""

T2_USER_TEMPLATE = """既存カテゴリ一覧:
{existing_categories}

予測テキスト:
「{prediction_text}」

投稿者: {author_display_name}

この予測を適切なカテゴリに分類してください。
既存カテゴリに該当するものがあればそれを選択し、なければ新規カテゴリを提案してください。"""


def normalize_category(category: str) -> str:
    """カテゴリ名を正規化する。

    - 全角スペースを半角に統一
    - 前後の空白を除去
    - スラッシュ周りのスペースを統一

    Args:
        category: 元のカテゴリ名

    Returns:
        str: 正規化されたカテゴリ名
    """
    # 全角スペースを半角に
    category = category.replace("　", " ")

    # 前後の空白を除去
    category = category.strip()

    # スラッシュ周りを " / " に統一
    category = re.sub(r"\s*/\s*", " / ", category)

    return category


class CategoryManager:
    """カテゴリ管理クラス。

    Attributes:
        llm: LLMクライアント
        categories: カテゴリリスト（"大分類 / 小分類" 形式）
        filepath: データファイルパス
    """

    def __init__(self, llm: "LLMClient"):
        self.llm = llm
        self.categories: list[str] = []
        self.filepath = "data/categories.md"

    async def load(self, filepath: str = "data/categories.md") -> None:
        """起動時にカテゴリマスタを読み込む。

        Args:
            filepath: カテゴリマスタファイルパス
        """
        self.filepath = filepath
        path = Path(filepath)

        if not path.exists():
            logger.info(f"Categories file not found: {filepath}, using seed")
            self.categories = self._get_seed_categories()
            return

        try:
            content = path.read_text(encoding="utf-8")
            self.categories = self._parse_categories_md(content)
            logger.info(f"Loaded {len(self.categories)} categories from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load categories: {e}")
            self.categories = self._get_seed_categories()

    def _parse_categories_md(self, content: str) -> list[str]:
        """categories.mdをパースしてカテゴリリストを返す。"""
        categories = []

        for line in content.split("\n"):
            line = line.strip()
            # "- カテゴリ名" 形式
            if line.startswith("- "):
                category = normalize_category(line[2:])
                if category:
                    categories.append(category)

        return categories

    def _get_seed_categories(self) -> list[str]:
        """初期カテゴリ一覧を返す（categories_seed.md相当）。"""
        return [
            "AI / 汎用AI（AGI）",
            "AI / 特化型AI",
            "AI / AI規制・倫理",
            "テクノロジー / ロボティクス",
            "テクノロジー / 量子コンピュータ",
            "テクノロジー / 宇宙開発",
            "テクノロジー / エネルギー",
            "テクノロジー / バイオテクノロジー",
            "テクノロジー / ナノテクノロジー",
            "社会 / 経済",
            "社会 / 政治",
            "社会 / 労働・雇用",
            "社会 / 教育",
            "社会 / 医療・健康",
            "文化 / エンターテインメント",
            "文化 / コミュニケーション",
            "環境 / 気候変動",
            "環境 / 資源",
        ]

    async def classify(
        self,
        prediction_text: str,
        author_display_name: str,
    ) -> dict:
        """T2テンプレートでカテゴリを判定する。

        Args:
            prediction_text: 予測テキスト
            author_display_name: 投稿者の表示名

        Returns:
            dict: {"categories": list[str], "is_new_category": bool,
                   "suggested_new_category": str | None}
        """
        user_prompt = T2_USER_TEMPLATE.format(
            existing_categories=self.get_existing_categories_list(),
            prediction_text=prediction_text,
            author_display_name=author_display_name,
        )

        result = await self.llm.call_template(
            template_name="T2",
            system=T2_SYSTEM,
            user=user_prompt,
            max_tokens=300,
            temperature=0.3,
        )

        if not result:
            logger.warning("[classify] T2 template failed, using default category")
            return {
                "categories": ["その他 / 未分類"],
                "is_new_category": False,
                "suggested_new_category": None,
            }

        # カテゴリの正規化
        categories = result.get("categories", [])
        normalized = [normalize_category(c) for c in categories if c]

        return {
            "categories": normalized if normalized else ["その他 / 未分類"],
            "is_new_category": result.get("is_new_category", False),
            "suggested_new_category": result.get("suggested_new_category"),
        }

    def get_existing_categories_list(self) -> str:
        """既存カテゴリの一覧テキストを返す（T2プロンプトに注入用）。

        同期メソッド。

        Returns:
            str: カテゴリ一覧（改行区切り）
        """
        if not self.categories:
            return "（カテゴリなし）"

        return "\n".join(f"- {c}" for c in self.categories)

    async def register_new_category(self, category: str) -> None:
        """新規カテゴリをマスタに追加する。

        Args:
            category: 新規カテゴリ名（"大分類 / 小分類" 形式）
        """
        normalized = normalize_category(category)

        if normalized and normalized not in self.categories:
            self.categories.append(normalized)
            logger.info(f"[register_new_category] Added: {normalized}")

    async def save(self) -> None:
        """categories.md に書き出す。"""
        path = Path(self.filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ["# カテゴリマスタ\n"]
        lines.extend(f"- {c}" for c in sorted(self.categories))

        content = "\n".join(lines)
        path.write_text(content, encoding="utf-8")
        logger.info(f"Saved {len(self.categories)} categories to {self.filepath}")

    def find_category(self, query: str) -> list[str]:
        """クエリに部分一致するカテゴリを検索する。

        Args:
            query: 検索クエリ

        Returns:
            list[str]: 一致するカテゴリのリスト
        """
        query_lower = query.lower()
        return [c for c in self.categories if query_lower in c.lower()]
