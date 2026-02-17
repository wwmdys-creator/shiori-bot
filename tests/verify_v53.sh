#!/usr/bin/env bash
# ============================================================================
# verify_v53.sh — Shiori v5.3 静的検証スクリプト
# ============================================================================
# 根拠: §12.14 grep確認コマンド (G12-1〜G12-7)
#        §11.7  統合チェックリスト
#        §11.5  N-01〜N-07 v5.3新規パターン
#        §11.4  F-01〜F-15 v5.2固有ミスパターン
#
# 使い方:
#   cd /path/to/shiori-bot-main
#   bash verify_v53.sh          # 通常実行
#   bash verify_v53.sh --verbose  # 詳細出力
#
# 終了コード: 0=全チェック通過  1=違反あり
# ============================================================================

set -euo pipefail

# --- 色定義 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

# --- カウンタ ---
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
SKIP_COUNT=0
VERBOSE=false

if [[ "${1:-}" == "--verbose" ]]; then
    VERBOSE=true
fi

# --- ヘルパー関数 ---
pass_check() {
    local id="$1"
    local desc="$2"
    echo -e "  ${GREEN}✓ PASS${NC}  ${id}: ${desc}"
    ((PASS_COUNT++))
}

fail_check() {
    local id="$1"
    local desc="$2"
    local detail="${3:-}"
    echo -e "  ${RED}✗ FAIL${NC}  ${id}: ${desc}"
    if [[ -n "$detail" ]]; then
        echo -e "         ${RED}→ ${detail}${NC}"
    fi
    ((FAIL_COUNT++))
}

warn_check() {
    local id="$1"
    local desc="$2"
    local detail="${3:-}"
    echo -e "  ${YELLOW}⚠ WARN${NC}  ${id}: ${desc}"
    if [[ -n "$detail" ]]; then
        echo -e "         ${YELLOW}→ ${detail}${NC}"
    fi
    ((WARN_COUNT++))
}

skip_check() {
    local id="$1"
    local desc="$2"
    echo -e "  ${CYAN}– SKIP${NC}  ${id}: ${desc} (ファイル未存在)"
    ((SKIP_COUNT++))
}

section_header() {
    echo ""
    echo -e "${BOLD}━━━ $1 ━━━${NC}"
}

# --- 実行ディレクトリ確認 ---
if [[ ! -f "bot.py" ]]; then
    echo -e "${RED}Error: bot.py が見つかりません。Shioriリポジトリのルートで実行してください。${NC}"
    exit 1
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Shiori v5.3 静的検証スクリプト (verify_v53.sh)     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "実行日時: $(date '+%Y-%m-%d %H:%M:%S')"
echo "作業ディレクトリ: $(pwd)"


# ============================================================================
# SECTION 1: §12.14 G12-1〜G12-7 インターフェース契約検証
# ============================================================================
section_header "§12.14 インターフェース契約 (G12-1〜G12-7)"

# --- G12-1: v5.3 新規モジュールの存在確認 ---
V53_MODULES=(
    "response_generator.py"
    "haiku_prompts.py"
)
# 注: daily_maintenance.py, weekly_monologue.py, discussion_summary.py,
#      prediction_highlighter.py, trust_level_up.py, response_mode.py は
#      後続フェーズで実装予定。存在しなければ SKIP とする。
V53_OPTIONAL_MODULES=(
    "response_mode.py"
    "daily_maintenance.py"
    "prediction_highlighter.py"
    "weekly_monologue.py"
    "discussion_summary.py"
    "trust_level_up.py"
)

for mod in "${V53_MODULES[@]}"; do
    if [[ -f "$mod" ]]; then
        pass_check "G12-1" "${mod} 存在確認"
    else
        fail_check "G12-1" "${mod} が見つかりません"
    fi
done

for mod in "${V53_OPTIONAL_MODULES[@]}"; do
    if [[ -f "$mod" ]]; then
        pass_check "G12-1" "${mod} 存在確認"
    else
        skip_check "G12-1" "${mod} (後続フェーズ)"
    fi
done

# system_prompt.txt の存在確認
if [[ -f "system_prompt.txt" ]]; then
    pass_check "G12-1" "system_prompt.txt 存在確認"
else
    fail_check "G12-1" "system_prompt.txt が見つかりません"
fi

# --- G12-2: should_react_heart の引数数（3引数） ---
HEART_DEF=$(grep -n "def should_react_heart\|def should_heart_react" ./*.py 2>/dev/null || true)
if [[ -n "$HEART_DEF" ]]; then
    # 引数が3つ（self除く）であることを確認
    ARG_COUNT=$(echo "$HEART_DEF" | grep -oP '\(.*?\)' | head -1 | tr ',' '\n' | wc -l)
    if [[ "$ARG_COUNT" -ge 3 ]]; then
        pass_check "G12-2" "should_react_heart: 3引数以上で定義"
    else
        fail_check "G12-2" "should_react_heart: 引数が不足 (${ARG_COUNT}個)" "期待: (message_content, is_reply_to_shiori, is_mention_to_shiori)"
    fi
    if $VERBOSE; then
        echo "         定義: $HEART_DEF"
    fi
else
    skip_check "G12-2" "should_react_heart 定義が未発見"
fi

# --- G12-3: delayed_add_reaction が create_task 経由のみ ---
AWAIT_DIRECT=$(grep -rn "await delayed_add_reaction\|await.*delayed_add_reaction" ./*.py 2>/dev/null | grep -v "await asyncio.sleep\|# " || true)
CREATE_TASK=$(grep -rn "create_task.*delayed_add_reaction\|create_task(delayed_add_reaction" ./*.py 2>/dev/null || true)

if [[ -z "$AWAIT_DIRECT" ]]; then
    pass_check "G12-3" "delayed_add_reaction: await直接呼び出し 0件"
else
    fail_check "G12-3" "delayed_add_reaction: await直接呼び出しが残留" "$(echo "$AWAIT_DIRECT" | head -3)"
fi

if [[ -n "$CREATE_TASK" ]]; then
    pass_check "G12-3" "delayed_add_reaction: create_task経由の呼び出しあり"
elif grep -rqn "delayed_add_reaction" ./*.py 2>/dev/null; then
    warn_check "G12-3" "delayed_add_reaction: create_task経由の呼び出しが見つかりません"
else
    skip_check "G12-3" "delayed_add_reaction 自体が未定義"
fi

# --- G12-4: level_up_pending の取得方法 (.pop() であること) ---
LEVEL_UP_REFS=$(grep -n "level_up_pending" ./*.py 2>/dev/null || true)
if [[ -n "$LEVEL_UP_REFS" ]]; then
    # .get( で取得している箇所がないか
    GET_USAGE=$(echo "$LEVEL_UP_REFS" | grep "\.get(" | grep -v "\.pop(\|def \|#" || true)
    if [[ -z "$GET_USAGE" ]]; then
        pass_check "G12-4" "level_up_pending: .get() による取得なし (.pop() のみ)"
    else
        fail_check "G12-4" "level_up_pending: .get() で取得している箇所あり" "$(echo "$GET_USAGE" | head -3)"
    fi
    if $VERBOSE; then
        echo "         参照箇所:"
        echo "$LEVEL_UP_REFS" | while read -r line; do echo "           $line"; done
    fi
else
    skip_check "G12-4" "level_up_pending 参照なし"
fi

# --- G12-5: sync Anthropic クライアント不使用 ---
SYNC_CLIENT=$(grep -rn "from anthropic import Anthropic$\|^from anthropic import Anthropic$" ./*.py 2>/dev/null || true)
SYNC_INIT=$(grep -rn "= Anthropic()" ./*.py 2>/dev/null | grep -v "AsyncAnthropic" || true)

if [[ -z "$SYNC_CLIENT" ]] && [[ -z "$SYNC_INIT" ]]; then
    pass_check "G12-5" "同期Anthropicクライアント: 0件 (AsyncAnthropicのみ)"
else
    fail_check "G12-5" "同期Anthropicクライアントが検出されました" "$(echo "${SYNC_CLIENT}${SYNC_INIT}" | head -3)"
fi

# --- G12-6: import妥当性チェック (Python構文チェック) ---
SYNTAX_ERRORS=""
for pyfile in ./*.py; do
    [[ -f "$pyfile" ]] || continue
    if ! python3 -c "import ast; ast.parse(open('${pyfile}').read())" 2>/dev/null; then
        SYNTAX_ERRORS="${SYNTAX_ERRORS}  ${pyfile}\n"
    fi
done

if [[ -z "$SYNTAX_ERRORS" ]]; then
    pass_check "G12-6" "全.pyファイル: Python構文エラー 0件"
else
    fail_check "G12-6" "Python構文エラーが検出されました" "$(echo -e "$SYNTAX_ERRORS")"
fi

# --- G12-7: HEART_THRESHOLDS / LEVEL_THRESHOLDS の同期確認 ---
HEART_DEFS=$(grep -n "HEART_THRESHOLDS\|LEVEL_THRESHOLDS\|HEART_EMOJI_MAP" ./*.py ./config.py 2>/dev/null || true)
if [[ -n "$HEART_DEFS" ]]; then
    # config.py で定義されていることを確認
    CONFIG_DEF=$(echo "$HEART_DEFS" | grep "config.py" || true)
    if [[ -n "$CONFIG_DEF" ]]; then
        pass_check "G12-7" "HEART_THRESHOLDS: config.py に定義あり"
    else
        warn_check "G12-7" "HEART_THRESHOLDS: config.py 外で定義" "$(echo "$HEART_DEFS" | head -3)"
    fi
    if $VERBOSE; then
        echo "         定義箇所:"
        echo "$HEART_DEFS" | while read -r line; do echo "           $line"; done
    fi
else
    skip_check "G12-7" "HEART_THRESHOLDS/LEVEL_THRESHOLDS 定義なし"
fi


# ============================================================================
# SECTION 2: §11.5 N-01〜N-07 v5.3新規パターン検証
# ============================================================================
section_header "§11.5 v5.3新規パターン (N-01〜N-07)"

# --- N-01: delayed_add_reaction は create_task 経由のみ (G12-3と重複するが明示的に再確認) ---
# (G12-3 で既にチェック済み — ここでは関数定義内の構造を確認)
DELAYED_DEF=$(grep -n "async def delayed_add_reaction" ./*.py 2>/dev/null || true)
if [[ -n "$DELAYED_DEF" ]]; then
    pass_check "N-01" "delayed_add_reaction: async def として定義あり"
else
    skip_check "N-01" "delayed_add_reaction 関数定義なし"
fi

# --- N-02: delayed_add_reaction 内の4種エラーハンドリング ---
if [[ -n "$DELAYED_DEF" ]]; then
    DELAYED_FILE=$(echo "$DELAYED_DEF" | head -1 | cut -d: -f1)
    NOTFOUND=$(grep -c "NotFound\|not_found" "$DELAYED_FILE" 2>/dev/null || echo 0)
    FORBIDDEN=$(grep -c "Forbidden" "$DELAYED_FILE" 2>/dev/null || echo 0)
    CANCELLED=$(grep -c "CancelledError\|asyncio.CancelledError" "$DELAYED_FILE" 2>/dev/null || echo 0)
    GENERAL_EX=$(grep -c "except Exception\|except BaseException" "$DELAYED_FILE" 2>/dev/null || echo 0)

    MISSING=""
    [[ "$NOTFOUND" -eq 0 ]] && MISSING="${MISSING}NotFound, "
    [[ "$FORBIDDEN" -eq 0 ]] && MISSING="${MISSING}Forbidden, "
    [[ "$CANCELLED" -eq 0 ]] && MISSING="${MISSING}CancelledError, "
    [[ "$GENERAL_EX" -eq 0 ]] && MISSING="${MISSING}Exception(汎用), "

    if [[ -z "$MISSING" ]]; then
        pass_check "N-02" "delayed_add_reaction: 4種エラーハンドリング完備"
    else
        warn_check "N-02" "delayed_add_reaction: 未検出のエラーハンドリング" "${MISSING%%, }"
    fi
else
    skip_check "N-02" "delayed_add_reaction 関数定義なし"
fi

# --- N-03: level_up_pending の pop() (G12-4で詳細チェック済み — サマリのみ) ---
# G12-4 結果を流用

# --- N-04: 記録モードでの昇格演出スキップ ---
RECORD_SKIP=$(grep -n "record.*level_up\|record.*hint\|mode.*record.*skip\|RECORD_MODE_INSTRUCTION" ./*.py 2>/dev/null || true)
if [[ -n "$RECORD_SKIP" ]]; then
    pass_check "N-04" "記録モード / 昇格演出: 関連コードあり (目視確認推奨)"
    if $VERBOSE; then
        echo "$RECORD_SKIP" | head -5 | while read -r line; do echo "           $line"; done
    fi
else
    skip_check "N-04" "記録モード昇格スキップの実装箇所が未発見 (手動確認必要)"
fi

# --- N-05: 日次メンテナンスの独立 try/except ---
if [[ -f "daily_maintenance.py" ]]; then
    TRY_COUNT=$(grep -c "^[[:space:]]*try:" daily_maintenance.py 2>/dev/null || echo 0)
    EXCEPT_COUNT=$(grep -c "^[[:space:]]*except" daily_maintenance.py 2>/dev/null || echo 0)
    if [[ "$TRY_COUNT" -ge 3 ]]; then
        pass_check "N-05" "daily_maintenance.py: 独立try/except ${TRY_COUNT}ブロック"
    else
        warn_check "N-05" "daily_maintenance.py: try/exceptブロックが少ない (${TRY_COUNT}個)" "各ステップに独立try/exceptが必要"
    fi
elif [[ -f "haiku_prompts.py" ]]; then
    # Phase 7では haiku_prompts.py に日次メンテナンスロジックが含まれる
    TRY_COUNT=$(grep -c "^[[:space:]]*try:" haiku_prompts.py 2>/dev/null || echo 0)
    if [[ "$TRY_COUNT" -ge 3 ]]; then
        pass_check "N-05" "haiku_prompts.py: 独立try/except ${TRY_COUNT}ブロック (日次メンテナンス含む)"
    else
        warn_check "N-05" "haiku_prompts.py: try/exceptブロック確認 (${TRY_COUNT}個)"
    fi
else
    skip_check "N-05" "daily_maintenance.py / haiku_prompts.py 未存在"
fi

# --- N-06: 週次独り言のNoneチェック ---
if [[ -f "weekly_monologue.py" ]]; then
    NONE_CHECK=$(grep -n "is None\|is not None\|if.*channel" weekly_monologue.py 2>/dev/null || true)
    FORBIDDEN_HANDLE=$(grep -n "Forbidden" weekly_monologue.py 2>/dev/null || true)
    if [[ -n "$NONE_CHECK" ]]; then
        pass_check "N-06" "weekly_monologue.py: チャンネルNoneチェックあり"
    else
        warn_check "N-06" "weekly_monologue.py: チャンネルNoneチェックが見つかりません"
    fi
    if [[ -n "$FORBIDDEN_HANDLE" ]]; then
        pass_check "N-06" "weekly_monologue.py: Forbiddenハンドリングあり"
    else
        warn_check "N-06" "weekly_monologue.py: Forbiddenハンドリングが見つかりません"
    fi
elif [[ -f "haiku_prompts.py" ]]; then
    # haiku_prompts.py に週次独り言ロジックが含まれる場合
    NONE_CHECK=$(grep -n "is None\|channel" haiku_prompts.py 2>/dev/null | grep -i "monologue\|週次\|weekly" || true)
    if [[ -n "$NONE_CHECK" ]]; then
        pass_check "N-06" "haiku_prompts.py: 週次独り言のチャンネルチェック関連コードあり"
    else
        skip_check "N-06" "週次独り言のチャンネルチェック (手動確認推奨)"
    fi
else
    skip_check "N-06" "weekly_monologue.py 未存在"
fi

# --- N-07: resolve_member_name の優先順位付き照合 ---
RESOLVE_FUNC=$(grep -rn "def resolve_member_name\|def _resolve_member" ./*.py 2>/dev/null || true)
if [[ -n "$RESOLVE_FUNC" ]]; then
    pass_check "N-07" "resolve_member_name: 関数定義あり (目視で優先順位確認推奨)"
    if $VERBOSE; then
        echo "         定義: $RESOLVE_FUNC"
    fi
else
    skip_check "N-07" "resolve_member_name 関数が未定義 (後続フェーズ)"
fi


# ============================================================================
# SECTION 3: §11.3 Part B (COMMON_MISTAKES §10〜§21) 検証
# ============================================================================
section_header "§11.3 Part B 汎用ミスパターン (§10〜§21)"

# --- §10: クロスモジュール整合性 (import/呼び出し突合) ---
IMPORT_ERRORS=""
for pyfile in ./*.py; do
    [[ -f "$pyfile" ]] || continue
    # from X import Y の X が .py として存在するかチェック
    IMPORTS=$(grep -oP "^from (\w+) import" "$pyfile" 2>/dev/null | grep -oP "from \K\w+" || true)
    for imp in $IMPORTS; do
        # 標準ライブラリ・サードパーティは除外
        case "$imp" in
            os|sys|re|json|time|datetime|asyncio|pathlib|logging|random|math|typing|collections|functools|copy|io|traceback|textwrap|dataclasses|enum|abc|hashlib|secrets|struct|base64|calendar|zoneinfo)
                continue ;;
            discord|anthropic|dotenv|aiohttp|httpx|pytest|unittest|pydantic)
                continue ;;
            config|pytz)
                continue ;;
        esac
        if [[ ! -f "./${imp}.py" ]]; then
            IMPORT_ERRORS="${IMPORT_ERRORS}  ${pyfile}: from ${imp} import ... → ${imp}.py が見つかりません\n"
        fi
    done
done

if [[ -z "$IMPORT_ERRORS" ]]; then
    pass_check "CM§10" "クロスモジュールimport: ローカルモジュール参照整合"
else
    warn_check "CM§10" "存在しないローカルモジュールへのimportあり" "$(echo -e "$IMPORT_ERRORS" | head -5)"
fi

# --- §12: ファイルリネーム残留 ---
OLD_NAMES=$(grep -rn "from reaction_handler import\|import reaction_handler" ./*.py 2>/dev/null || true)
if [[ -z "$OLD_NAMES" ]]; then
    pass_check "CM§12" "旧ファイル名 reaction_handler: import残留 0件"
else
    fail_check "CM§12" "reaction_handler への参照が残留" "$(echo "$OLD_NAMES" | head -3)"
fi

# --- §13: sync/async 一致 ---
# AsyncAnthropic の使用確認
ASYNC_CLIENT=$(grep -rn "AsyncAnthropic" ./*.py 2>/dev/null || true)
if [[ -n "$ASYNC_CLIENT" ]]; then
    pass_check "CM§13" "AsyncAnthropic: 使用あり"
else
    warn_check "CM§13" "AsyncAnthropic: 使用が見つかりません (LLM呼び出しモジュール要確認)"
fi

# --- §15: 未実装メソッド参照 (ライブコードパス上の TODO/NotImplemented) ---
LIVE_TODO=$(grep -rn "TODO\|FIXME\|NotImplementedError\|raise NotImplemented" ./*.py 2>/dev/null \
    | grep -v "test_\|tests/\|#.*TODO.*後続\|#.*FIXME.*将来" || true)
if [[ -z "$LIVE_TODO" ]]; then
    pass_check "CM§15" "ライブコードパス上の TODO/NotImplemented: 0件"
else
    warn_check "CM§15" "ライブコードパス上に TODO/NotImplemented あり" "$(echo "$LIVE_TODO" | head -5)"
fi

# --- §17: 変数スコープ (静的解析の限界があるため構文チェックのみ) ---
# G12-6 の構文チェックで代替

# --- §18: seed/ と data/ の分離確認 ---
if [[ -d "seed" ]]; then
    SEED_FILES=$(ls seed/*.md 2>/dev/null | wc -l)
    pass_check "CM§18" "seed/ ディレクトリ: 存在 (${SEED_FILES}ファイル)"
else
    warn_check "CM§18" "seed/ ディレクトリが未作成 (Railway Volume分離が必要)"
fi

# 旧パスのハードコード残留
OLD_SEED_PATHS=$(grep -rn '"data/members_seed.md"\|"data/community_lexicon.md"\|"data/consensus_tracker.md"' ./*.py 2>/dev/null \
    | grep -v "config.py\|#" || true)
if [[ -z "$OLD_SEED_PATHS" ]]; then
    pass_check "CM§18" "旧seedパス (data/members_seed.md等): ハードコード 0件"
else
    warn_check "CM§18" "旧seedパスのハードコードが残留" "$(echo "$OLD_SEED_PATHS" | head -3)"
fi


# ============================================================================
# SECTION 4: §11.4 Part F (v5.2固有ミスパターン F-01〜F-15) 検証
# ============================================================================
section_header "§11.4 Part F v5.2固有パターン (抜粋)"

# --- F-04: Haiku呼び出し前の切り詰め ---
HAIKU_TRUNCATE=$(grep -rn "HaikuContextManager\|truncate.*haiku\|haiku.*truncat" ./*.py 2>/dev/null || true)
if [[ -n "$HAIKU_TRUNCATE" ]]; then
    pass_check "F-04" "HaikuContextManager / truncate: 使用箇所あり"
else
    skip_check "F-04" "HaikuContextManager 未使用 (Haiku呼び出しモジュール要確認)"
fi

# --- F-06: safe_parse_json の使用 ---
SAFE_PARSE=$(grep -rn "safe_parse_json" ./*.py 2>/dev/null || true)
if [[ -n "$SAFE_PARSE" ]]; then
    # 定義が1箇所のみであることを確認 (重複定義防止)
    DEF_COUNT=$(echo "$SAFE_PARSE" | grep "def safe_parse_json" | wc -l)
    if [[ "$DEF_COUNT" -le 1 ]]; then
        pass_check "F-06" "safe_parse_json: 定義1箇所 + 呼び出しあり"
    else
        fail_check "F-06" "safe_parse_json: 定義が${DEF_COUNT}箇所 (重複)" "定義を1箇所に統合してimportで共有すること"
    fi
else
    skip_check "F-06" "safe_parse_json 未使用"
fi

# --- F-07: 応答文字数チェック ---
CHAR_CHECK=$(grep -rn "len(.*response\|文字数\|MAX_.*LENGTH\|max_length\|[:]\s*[0-9]*\]" ./*.py 2>/dev/null \
    | grep -iv "test\|#" | head -5 || true)
if [[ -n "$CHAR_CHECK" ]]; then
    pass_check "F-07" "応答文字数チェック: 関連コードあり"
else
    warn_check "F-07" "応答文字数チェック: 明示的なチェックが見つかりません"
fi

# --- F-10: 箇条書き禁止 (bullet point detection) ---
BULLET_CHECK=$(grep -rn "箇条書き\|bullet\|strip_bullets\|remove_bullets\|^- \|^・\|^・" ./*.py 2>/dev/null \
    | grep -v "test_\|tests/\|#.*箇条書き禁止" || true)
if [[ -n "$BULLET_CHECK" ]]; then
    pass_check "F-10" "箇条書き対策: 関連コードあり (変換/検出ロジック)"
else
    warn_check "F-10" "箇条書き禁止対策: 明示的な変換ロジックが見つかりません"
fi

# --- F-12: リアクションと応答の独立判定 ---
INDEPENDENT_REACT=$(grep -rn "create_task.*reaction\|asyncio.gather\|並列" ./*.py 2>/dev/null || true)
if [[ -n "$INDEPENDENT_REACT" ]]; then
    pass_check "F-12" "リアクション/応答 独立実行: create_task or gather 使用あり"
else
    skip_check "F-12" "リアクション/応答の並列実行パターン (手動確認推奨)"
fi


# ============================================================================
# SECTION 5: 追加整合性チェック
# ============================================================================
section_header "追加整合性チェック"

# --- config.py 必須定数の存在確認 ---
if [[ -f "config.py" ]]; then
    REQUIRED_CONSTS=(
        "HEART_THRESHOLDS"
        "TRUST_GAIN_MULTIPLIER"
    )
    OPTIONAL_CONSTS=(
        "SEED_DIR"
        "DATA_DIR"
        "DISCUSSIONS_FILE"
        "WEEKLY_NOTES_FILE"
    )

    for const in "${REQUIRED_CONSTS[@]}"; do
        if grep -q "$const" config.py 2>/dev/null; then
            pass_check "CFG" "config.py: ${const} 定義あり"
        else
            fail_check "CFG" "config.py: ${const} が未定義" "v5.3必須定数"
        fi
    done

    for const in "${OPTIONAL_CONSTS[@]}"; do
        if grep -q "$const" config.py 2>/dev/null; then
            pass_check "CFG" "config.py: ${const} 定義あり"
        else
            warn_check "CFG" "config.py: ${const} が未定義 (v5.3推奨)"
        fi
    done
else
    fail_check "CFG" "config.py が見つかりません"
fi

# --- tests/ ディレクトリの確認 ---
if [[ -d "tests" ]]; then
    TEST_COUNT=$(find tests/ -name "test_*.py" 2>/dev/null | wc -l)
    pass_check "TEST" "tests/ ディレクトリ: ${TEST_COUNT}個のテストファイル"
else
    warn_check "TEST" "tests/ ディレクトリが未作成"
fi

# --- .gitignore の data/ 除外確認 ---
if [[ -f ".gitignore" ]]; then
    if grep -q "data/" .gitignore 2>/dev/null; then
        pass_check "GIT" ".gitignore: data/ パターンあり"
    else
        warn_check "GIT" ".gitignore: data/ が除外されていません (Railway Volume分離時に必要)"
    fi
else
    warn_check "GIT" ".gitignore が見つかりません"
fi


# ============================================================================
# サマリ
# ============================================================================
echo ""
echo -e "${BOLD}━━━ 検証サマリ ━━━${NC}"
echo ""
TOTAL=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT + SKIP_COUNT))
echo -e "  ${GREEN}PASS${NC}: ${PASS_COUNT}"
echo -e "  ${RED}FAIL${NC}: ${FAIL_COUNT}"
echo -e "  ${YELLOW}WARN${NC}: ${WARN_COUNT}"
echo -e "  ${CYAN}SKIP${NC}: ${SKIP_COUNT}"
echo -e "  合計: ${TOTAL}チェック"
echo ""

if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}結果: 全チェック通過 (FAIL 0件)${NC}"
    if [[ "$WARN_COUNT" -gt 0 ]]; then
        echo -e "${YELLOW}  ※ ${WARN_COUNT}件の警告あり — 目視確認を推奨${NC}"
    fi
    echo ""
    exit 0
else
    echo -e "${RED}${BOLD}結果: ${FAIL_COUNT}件の違反が検出されました${NC}"
    echo -e "${RED}  修正後に再実行してください: bash verify_v53.sh${NC}"
    echo ""
    exit 1
fi
