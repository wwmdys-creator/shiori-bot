"""
categories.py - LLM自動カテゴリ生成モジュール

Q20: B案 - LLM自動生成（既存カテゴリ優先使用）
新規予測のカテゴリをLLMが自動判定し、既存カテゴリがあれば優先的に使用
"""

import json
import os
from typing import Optional
from pathlib import Path

# デフォルトカテゴリ（初期シードとして使用）
DEFAULT_CATEGORIES = [
    "AI技術 / AGI",
    "AI技術 / ASI",
    "AI技術 / LLM",
    "ロボティクス / ヒューマノイド",
    "ロボティクス / ドローン",
    "宇宙開発 / 軌道エレベーター",
    "宇宙開発 / 火星移住",
    "宇宙開発 / 宇宙太陽光発電",
    "医療技術 / LEV（寿命脱出速度）",
    "医療技術 / 遺伝子治療",
    "医療技術 / BMI（脳機械インターフェース）",
    "社会制度 / UBI（ユニバーサル・ベーシック・インカム）",
    "社会制度 / 労働の未来",
    "エネルギー / 核融合",
    "エネルギー / 太陽光発電",
    "エネルギー / 電力問題",
    "デバイス / 翻訳技術",
    "デバイス / AR/VR",
    "経済 / 投資",
    "経済 / 市場予測",
    "その他",
]


class CategoryManager:
    """
    予測カテゴリの管理
    
    - 既存カテゴリの一覧管理
    - LLMによる自動カテゴリ判定
    - 新規カテゴリの追加
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.categories_file = self.data_dir / "categories.json"
        self.categories: list[str] = []
        self._load()
    
    def _load(self) -> None:
        """カテゴリ一覧をファイルから読み込み"""
        if self.categories_file.exists():
            try:
                with open(self.categories_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.categories = data.get("categories", DEFAULT_CATEGORIES.copy())
            except (json.JSONDecodeError, IOError):
                self.categories = DEFAULT_CATEGORIES.copy()
        else:
            self.categories = DEFAULT_CATEGORIES.copy()
            self._save()
    
    def _save(self) -> None:
        """カテゴリ一覧をファイルに保存"""
        with open(self.categories_file, "w", encoding="utf-8") as f:
            json.dump({
                "categories": self.categories,
                "count": len(self.categories)
            }, f, ensure_ascii=False, indent=2)
    
    def get_all_categories(self) -> list[str]:
        """全カテゴリ一覧を取得"""
        return self.categories.copy()
    
    def get_categories_for_prompt(self) -> str:
        """LLMプロンプト用のカテゴリ一覧文字列を生成"""
        return "\n".join(f"- {cat}" for cat in self.categories)
    
    def add_category(self, category: str) -> bool:
        """
        新規カテゴリを追加
        
        Returns:
            bool: 追加成功したらTrue、既存ならFalse
        """
        # 正規化（前後の空白削除）
        category = category.strip()
        
        if not category:
            return False
        
        # 重複チェック（大文字小文字を区別しない）
        normalized = category.lower()
        for existing in self.categories:
            if existing.lower() == normalized:
                return False
        
        self.categories.append(category)
        self._save()
        return True
    
    def find_similar_category(self, category: str) -> Optional[str]:
        """
        類似するカテゴリを検索
        
        部分一致や正規化後の一致を探す
        """
        category_lower = category.lower().strip()
        
        # 完全一致
        for existing in self.categories:
            if existing.lower() == category_lower:
                return existing
        
        # 部分一致（既存カテゴリに含まれるか）
        for existing in self.categories:
            if category_lower in existing.lower():
                return existing
            if existing.lower() in category_lower:
                return existing
        
        return None
    
    def normalize_category(self, category: str) -> str:
        """
        カテゴリを正規化
        
        類似カテゴリがあればそれを返し、なければ新規追加して返す
        """
        similar = self.find_similar_category(category)
        if similar:
            return similar
        
        # 新規カテゴリを追加
        self.add_category(category)
        return category
    
    def get_category_stats(self) -> dict:
        """カテゴリの統計情報を取得"""
        # 親カテゴリでグループ化
        parent_counts: dict[str, int] = {}
        for cat in self.categories:
            if " / " in cat:
                parent = cat.split(" / ")[0]
            else:
                parent = cat
            parent_counts[parent] = parent_counts.get(parent, 0) + 1
        
        return {
            "total_categories": len(self.categories),
            "parent_categories": parent_counts
        }


# シングルトンインスタンス
_category_manager: Optional[CategoryManager] = None


def get_category_manager(data_dir: str = "data") -> CategoryManager:
    """CategoryManagerのシングルトンインスタンスを取得"""
    global _category_manager
    if _category_manager is None:
        _category_manager = CategoryManager(data_dir)
    return _category_manager


def build_categorization_prompt(prediction_content: str, existing_categories: str) -> str:
    """
    予測内容からカテゴリを判定するためのLLMプロンプトを構築
    
    Args:
        prediction_content: 予測の内容
        existing_categories: 既存カテゴリの一覧（改行区切り）
    
    Returns:
        LLMに送るプロンプト
    """
    return f"""以下の予測内容に最も適切なカテゴリを判定してください。

【予測内容】
{prediction_content}

【既存カテゴリ一覧】
{existing_categories}

【指示】
1. 既存カテゴリの中から最も適切なものを選んでください
2. 適切なカテゴリがない場合のみ、「親カテゴリ / サブカテゴリ」の形式で新規カテゴリを提案してください
3. カテゴリ名のみを出力してください（説明は不要）

【出力形式】
カテゴリ名のみ（1行）"""
