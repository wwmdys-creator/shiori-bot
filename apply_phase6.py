"""
apply_phase6.py — ★アーカイブ対象（v5.3-P0P1-v3）

Phase 6 統合時の自動パッチスクリプト（366行）。
本番環境に残存しているが、統合作業は完了済みのため不要。

対応方法（いずれか）:
  1. _archive/ ディレクトリに移動: mv apply_phase6.py _archive/
  2. .gitignore に追加: echo "apply_phase6.py" >> .gitignore
  3. リポジトリから削除: git rm apply_phase6.py

本ファイルで上書きすることで本番実行を防止する。
"""

raise RuntimeError(
    "apply_phase6.py は Phase 6 統合完了済みのため実行不要です。"
    " _archive/ への移動を推奨します。"
)
