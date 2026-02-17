#!/usr/bin/env python3
"""apply_phase6.py — Shiori v5.3 Phase 6 bot.py 自動パッチスクリプト

shiori-bot リポジトリのルートディレクトリで実行:
  python apply_phase6.py

前提:
  - bot.py (v4.1+v5.2+v5.3-Phase3 以降) が存在
  - trust.py (V-01修正済み) が存在
  - config.py (v5.3) が存在
  - trust_level_up.py (Phase 4 で作成済み) が存在
  - prediction_highlighter.py (Phase 4 で作成済み) が存在

適用パッチ:
  A: import 追加 (trust_level_up, prediction_highlighter)
  B: __init__ に level_up_detector, prediction_highlighter, level_up_pending 追加
  C: on_trust_score_change() メソッド追加
  D: record_interaction 後に昇格チェックフック追加
  E: _handle_mention 内で昇格フラグ消費 (pop, N-03/N-04)
  F: リアクション処理を3引数 should_heart_react + get_heart_emoji に更新
  G: delayed_add_reaction を create_task 経由に変更 (N-01)
  H: generate_response に level_up_hint 渡し
  I: BOT_VERSION 更新
"""

import os
import re
import sys
import ast
import shutil
from datetime import datetime


def backup(filepath: str) -> str:
    """バックアップを作成して戻り値でバックアップパスを返す。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.bak_{ts}"
    shutil.copy2(filepath, backup_path)
    print(f"  [OK] バックアップ: {backup_path}")
    return backup_path


def patch_trust(filepath: str) -> None:
    """trust.py V-01修正: ローカル定数を config.py インポートに統一。"""
    print(f"\n--- trust.py パッチ ---")

    content = open(filepath, "r", encoding="utf-8").read()

    # 既に修正済みか確認
    if "from config import HEART_THRESHOLDS" in content:
        print("  [SKIP] 既に config.py からインポート済み")
        return

    backup(filepath)

    # 1. import 追加（logging の後に挿入）
    if "from config import" not in content:
        content = content.replace(
            "import logging",
            "import logging\n\n# V-01修正: config.py を単一参照元とする\nfrom config import HEART_THRESHOLDS, TRUST_GAIN_MULTIPLIER",
        )
        print("  [OK] from config import 追加")

    # 2. ローカル TRUST_GAIN_MULTIPLIER 定義を削除
    pattern = r"# 好感度2倍化.*?\nTRUST_GAIN_MULTIPLIER.*?\n(#.*?\n)*"
    if re.search(r"^TRUST_GAIN_MULTIPLIER\s*[:=]", content, re.MULTILINE):
        content = re.sub(
            r"^TRUST_GAIN_MULTIPLIER\s*[:=].*$",
            "# TRUST_GAIN_MULTIPLIER は config.py からインポート済み",
            content,
            flags=re.MULTILINE,
        )
        print("  [OK] ローカル TRUST_GAIN_MULTIPLIER 定義をコメントに置換")

    # 3. ローカル HEART_THRESHOLDS 定義を削除
    if re.search(r"^HEART_THRESHOLDS\s*[:=]", content, re.MULTILINE):
        # 辞書リテラル全体を置換（複数行に渡る場合）
        content = re.sub(
            r"^HEART_THRESHOLDS\s*[:=]\s*\{[^}]+\}",
            "# HEART_THRESHOLDS は config.py からインポート済み",
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        print("  [OK] ローカル HEART_THRESHOLDS 定義をコメントに置換")

    open(filepath, "w", encoding="utf-8").write(content)
    print(f"  [OK] {filepath} 保存完了")


def patch_bot(filepath: str) -> None:
    """bot.py Phase 6 パッチ適用。"""
    print(f"\n--- bot.py パッチ ---")

    content = open(filepath, "r", encoding="utf-8").read()
    backup(filepath)
    applied = []

    # === A: import 追加 ===
    if "from trust_level_up import" not in content:
        # 最後の from ... import の後に追加
        last_import_match = None
        for m in re.finditer(r"^(?:from|import)\s+.+$", content, re.MULTILINE):
            last_import_match = m
        if last_import_match:
            pos = last_import_match.end()
            insert = (
                "\n\n# Phase 4/6: 昇格検出・予測ハイライト\n"
                "from trust_level_up import TrustLevelUpDetector, LEVEL_UP_HINT_PROMPTS, get_heart_emoji\n"
                "from prediction_highlighter import PredictionHighlighter\n"
            )
            content = content[:pos] + insert + content[pos:]
            applied.append("A: import追加")
    else:
        print("  [SKIP] A: import 既存")

    # === B: __init__ に Phase 4/6 属性追加 ===
    if "self.level_up_detector" not in content:
        # self.reaction_handler の後、または __init__ 末尾に挿入
        init_insert = (
            "\n        # ===== Phase 4/6: 昇格検出・予測ハイライト =====\n"
            "        self.level_up_detector = TrustLevelUpDetector()\n"
            "        self.prediction_highlighter = PredictionHighlighter()\n"
            "        # 昇格保留フラグ辞書（§9.5 — 取得時は必ず pop() N-03）\n"
            "        self.level_up_pending: dict[str, dict] = {}\n"
        )
        # reaction_handler 初期化行の後に挿入を試みる
        rh_match = re.search(
            r"(self\.reaction_handler\s*=.*\n)", content
        )
        if rh_match:
            pos = rh_match.end()
            content = content[:pos] + init_insert + content[pos:]
            applied.append("B: __init__属性追加")
        else:
            print("  [WARN] B: self.reaction_handler が見つかりません。手動で追加してください:")
            print(init_insert)
    else:
        print("  [SKIP] B: level_up_detector 既存")

    # === C: on_trust_score_change() メソッド追加 ===
    if "def on_trust_score_change" not in content:
        method_code = '''
    def on_trust_score_change(
        self, user_id: str, old_score: int, new_score: int
    ) -> None:
        """好感度スコア変更時の昇格チェック（§9.4, §12.11 [5]）

        ⚠️ N-05: 呼び出し側で try/except で囲むこと。
        ⚠️ §13: sync メソッド。
        """
        level_up_info = self.level_up_detector.check_level_up(
            user_id, old_score, new_score
        )
        if level_up_info is not None:
            self.level_up_pending[user_id] = level_up_info
            logger.info(
                f"[LevelUp] Flag set for {user_id}: "
                f"Lv{level_up_info['old_level']} -> Lv{level_up_info['new_level']}"
            )

'''
        # on_message の前に挿入
        on_msg_match = re.search(r"(\n    async def on_message\b)", content)
        if on_msg_match:
            content = content[:on_msg_match.start()] + method_code + content[on_msg_match.start():]
            applied.append("C: on_trust_score_change追加")
        else:
            print("  [WARN] C: on_message が見つかりません。手動で追加してください")
    else:
        print("  [SKIP] C: on_trust_score_change 既存")

    # === D: record_interaction 後の昇格チェックフック ===
    if "on_trust_score_change" in content and "# Phase 4/6: 昇格チェック" not in content:
        # record_interaction の呼び出し箇所を検索
        ri_pattern = r"(result\s*=\s*await\s+self\.trust(?:_manager)?\.record_interaction\([^)]+\))"
        for m in re.finditer(ri_pattern, content):
            pos = m.end()
            hook = '''
            # Phase 4/6: 昇格チェック（N-05: エラー隔離必須）
            try:
                self.on_trust_score_change(
                    str(user_id),
                    result["old_score"],
                    result["new_score"],
                )
            except Exception as e:
                logger.error(f"[LevelUp] on_trust_score_change failed: {e}")
'''
            content = content[:pos] + hook + content[pos:]
            applied.append("D: 昇格チェックフック追加")
            break  # 最初の箇所のみ（他はパターンが異なる可能性）
    else:
        if "# Phase 4/6: 昇格チェック" in content:
            print("  [SKIP] D: 昇格チェックフック既存")

    # === E: 昇格フラグ消費（_handle_mention 内） ===
    if "level_up_pending.pop(" not in content:
        # response_mode 判定の後に挿入を試みる
        rm_match = re.search(
            r"(response_mode\s*=\s*.*determine_response_mode.*\n)", content
        )
        if rm_match:
            pos = rm_match.end()
            flag_code = '''
            # ===== Phase 4/6: 昇格フラグ消費（§9.5, N-03, N-04） =====
            # ⚠️ CRITICAL: pop() 必須。get() 禁止（無限ループ防止）。
            level_up_info = self.level_up_pending.pop(str(user_id), None)
            level_up_hint = ""
            if level_up_info is not None:
                if response_mode == "free":
                    level_up_hint = LEVEL_UP_HINT_PROMPTS.get(
                        level_up_info["new_level"], ""
                    )
                    logger.info(
                        f"[LevelUp] Consuming flag for {user_id}: "
                        f"Lv{level_up_info['new_level']} hint applied"
                    )
                elif response_mode == "record":
                    # N-04: 記録モードでは演出せず再登録
                    self.level_up_pending[str(user_id)] = level_up_info
                    logger.info(
                        f"[LevelUp] Re-registered for {user_id}: "
                        f"record mode, deferring"
                    )

'''
            content = content[:pos] + flag_code + content[pos:]
            applied.append("E: 昇格フラグ消費追加")
        else:
            print("  [WARN] E: determine_response_mode が見つかりません。手動で追加してください")
    else:
        print("  [SKIP] E: level_up_pending.pop 既存")

    # === I: BOT_VERSION 更新 ===
    content = re.sub(
        r'BOT_VERSION\s*=\s*"[^"]*"',
        'BOT_VERSION = "v4.1+v5.2+v5.3-Phase6"',
        content,
    )
    applied.append("I: BOT_VERSION更新")

    # 保存
    open(filepath, "w", encoding="utf-8").write(content)
    print(f"  適用済みパッチ: {', '.join(applied)}")
    print(f"  [OK] {filepath} 保存完了")

    # 手動確認必要な項目を表示
    print("""
  ⚠️ 以下は自動適用が困難なため手動確認が必要です:

  [F] リアクション処理: on_message 内の should_heart_react() 呼び出しが
      3引数（content, is_reply, is_mention）であること確認

  [G] delayed_add_reaction が asyncio.create_task() 経由であること確認
      → grep -n "delayed_add_reaction" bot.py

  [H] generate_response() 呼び出しに level_up_hint を渡す:
      extra_context に level_up_hint を連結

  [J] daily_maintenance に prediction_highlighter を渡す（該当する場合）
""")


def verify(cwd: str) -> None:
    """構文検証 + grep チェック。"""
    print("\n--- 検証 ---")

    # AST 構文検証
    for f in ["bot.py", "trust.py", "config.py", "reaction_handler.py"]:
        path = os.path.join(cwd, f)
        if not os.path.exists(path):
            print(f"  [SKIP] {f} — ファイルなし")
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                ast.parse(fh.read())
            print(f"  [OK] {f} — 構文OK")
        except SyntaxError as e:
            print(f"  [FAIL] {f} — 構文エラー: {e}")

    # grep チェック
    print("\n  --- grep チェック ---")
    py_files = [f for f in os.listdir(cwd) if f.endswith(".py")]

    # N-03: level_up_pending の取得が pop() であること
    for f in py_files:
        path = os.path.join(cwd, f)
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if "level_up_pending" in line and ".get(" in line:
                    print(f"  [FAIL] N-03違反: {f}:{i} — .get() 使用 → .pop() に修正必要")

    # N-01: delayed_add_reaction が await 直接呼び出しされていないこと
    for f in py_files:
        path = os.path.join(cwd, f)
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if "await" in line and "delayed_add_reaction" in line and "asyncio.sleep" not in line:
                    if "create_task" not in line:
                        print(f"  [FAIL] N-01違反: {f}:{i} — await 直接呼び出し")

    # HEART_THRESHOLDS が config.py のみに定義
    ht_defs = []
    for f in py_files:
        path = os.path.join(cwd, f)
        with open(path, "r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if re.match(r"^HEART_THRESHOLDS\s*[:=]", line):
                    ht_defs.append(f"{f}:{i}")
    if len(ht_defs) == 1 and ht_defs[0].startswith("config.py"):
        print("  [OK] N-04: HEART_THRESHOLDS は config.py のみに定義")
    elif len(ht_defs) == 0:
        print("  [WARN] N-04: HEART_THRESHOLDS の定義が見つかりません")
    else:
        print(f"  [FAIL] N-04: HEART_THRESHOLDS が複数箇所に定義: {ht_defs}")

    print("\n  検証完了")


def main():
    print("=" * 60)
    print("Shiori v5.3 Phase 6 自動適用スクリプト")
    print("=" * 60)

    cwd = os.getcwd()
    print(f"\n作業ディレクトリ: {cwd}")

    required = ["bot.py", "trust.py", "config.py"]
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        print(f"\n[ERROR] 必須ファイルが見つかりません: {', '.join(missing)}")
        print("        shiori-bot のルートディレクトリで実行してください")
        sys.exit(1)

    # trust.py パッチ
    patch_trust("trust.py")

    # bot.py パッチ
    patch_bot("bot.py")

    # 検証
    verify(cwd)

    print("\n" + "=" * 60)
    print("Phase 6 適用完了")
    print("=" * 60)
    print("""
次のステップ:
  1. 上記の [WARN] や [FAIL] がある場合、手動で修正してください
  2. 特に手動確認が必要な箇所:
     a) bot.py の generate_response() に level_up_hint を渡す（変更点 H）
     b) bot.py の should_heart_react() が3引数か（変更点 F）
     c) delayed_add_reaction が create_task 経由か（変更点 G）
  3. git diff で変更内容を確認
  4. python -c "import ast; ast.parse(open('bot.py').read())" で構文確認
  5. Railway にデプロイ

grep確認コマンド:
  grep -n "level_up_pending" *.py          # .pop() のみ (N-03)
  grep -rn "delayed_add_reaction" *.py     # create_task経由のみ (N-01)
  grep -n "HEART_THRESHOLDS" *.py          # config.pyのみに定義 (N-04)
  grep -rn "from anthropic import Anthropic$" *.py  # 0件 (§13)
""")


if __name__ == "__main__":
    main()