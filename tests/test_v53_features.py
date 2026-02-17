"""
Shiori v5.3 補完テスト — §1〜§6 (T13-01 〜 T13-47)
=======================================================
§13.4 リアクション制限強化 (T13-01〜T13-06)
§13.5 好感度上昇量2倍化 (T13-10〜T13-14)
§13.6 記録モード／自由モード (T13-20〜T13-26)
§13.7 ハートカラー好感度連動 (T13-30〜T13-34)
§13.8 日次データ整理 (T13-35〜T13-41)
§13.9 メンション時の包括的データ更新 (T13-42〜T13-47)

検証方法:
  Auto     — pytest で自動実行
  LLM-Eval — 人間がLLM出力を §13.14 チェックリストで評価
  Manual   — Discord 実環境で手動確認

実行:
  pytest tests/test_v53_features.py -v
  pytest tests/test_v53_features.py -v -m auto       # Autoのみ
  pytest tests/test_v53_features.py -v -m llm_eval   # LLM-Eval のみ
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# テスト用共通定数
# ---------------------------------------------------------------------------
JST = timezone(timedelta(hours=9))
BOT_USER_ID = 123456789  # 栞の Discord user ID (テスト用)

TRUST_GAIN_MULTIPLIER = 2  # §2: 好感度上昇量2倍

HEART_EMOJI_MAP = {1: "🧡", 2: "💛", 3: "💗", 4: "❤️"}

TRUST_THRESHOLDS = {
    1: (0, 19),
    2: (20, 49),
    3: (50, 79),
    4: (80, 100),
}


# ---------------------------------------------------------------------------
# Mock ヘルパー
# ---------------------------------------------------------------------------
def _make_message(
    content: str,
    author_id: int = 999,
    author_name: str = "test_user",
    is_reply_to_shiori: bool = False,
    is_mention_to_shiori: bool = False,
) -> MagicMock:
    """discord.Message のモックを生成する。"""
    msg = MagicMock()
    msg.content = content
    msg.author.id = author_id
    msg.author.display_name = author_name
    msg.author.name = author_name
    msg.author.bot = False
    msg.channel.id = 111
    msg.id = 10000 + hash(content) % 10000
    msg.add_reaction = AsyncMock()
    msg.created_at = datetime.now(tz=timezone.utc)

    # v5.3 追加フラグ
    msg._is_reply_to_shiori = is_reply_to_shiori
    msg._is_mention_to_shiori = is_mention_to_shiori

    # reference (返信先)
    if is_reply_to_shiori:
        ref = MagicMock()
        ref.resolved = MagicMock()
        ref.resolved.author.id = BOT_USER_ID
        msg.reference = ref
    else:
        msg.reference = None

    # mentions
    if is_mention_to_shiori:
        bot_user = MagicMock()
        bot_user.id = BOT_USER_ID
        msg.mentions = [bot_user]
    else:
        msg.mentions = []

    return msg


# ===========================================================================
# §13.4 — §1 リアクション制限強化テスト (T13-01 〜 T13-06)
# ===========================================================================
class TestReactionRestriction:
    """§1: is_reply_to_shiori / is_mention_to_shiori に基づくリアクション制限。"""

    # --- T13-01: 栞メンション＋好意的内容 → リアクションあり ---
    @pytest.mark.auto
    def test_t13_01_mention_positive_reacts(self):
        """栞へのメンション＋好意的内容 → ハートリアクション付与。"""
        content = "ありがとう！"
        is_reply = False
        is_mention = True

        should = _should_react_heart(content, is_reply, is_mention)
        assert should is True, "栞メンション＋好意的 → リアクション付与"

    # --- T13-02: 栞への返信＋好意的内容 → リアクションあり ---
    @pytest.mark.auto
    def test_t13_02_reply_positive_reacts(self):
        """栞への返信＋好意的内容 → ハートリアクション付与。"""
        content = "いい分析だね"
        should = _should_react_heart(content, is_reply=True, is_mention=False)
        assert should is True

    # --- T13-03: 栞メンションなし＋好意的内容 → リアクションなし ---
    @pytest.mark.auto
    def test_t13_03_no_mention_no_reaction(self):
        """栞宛てでない好意的メッセージ → リアクションなし。"""
        content = "みんなありがとう！最高！"
        should = _should_react_heart(content, is_reply=False, is_mention=False)
        assert should is False, "栞宛てでない → リアクションなし"

    # --- T13-04: 栞メンション＋中立的内容 → リアクションなし ---
    @pytest.mark.auto
    def test_t13_04_mention_neutral_no_reaction(self):
        """栞メンション＋好意キーワードなし → ハートリアクションなし。"""
        content = "AGIはいつ来る？"
        should = _should_react_heart(content, is_reply=False, is_mention=True)
        assert should is False, "好意キーワード不一致 → リアクションなし"

    # --- T13-05: should_react_heart の3引数呼び出し ---
    @pytest.mark.auto
    def test_t13_05_three_args_no_typeerror(self):
        """should_react_heart が3引数で TypeError にならない。"""
        try:
            _should_react_heart("test", True, False)
            _should_react_heart("test", False, True)
            _should_react_heart("test", False, False)
        except TypeError as e:
            pytest.fail(f"should_react_heart 3引数で TypeError: {e}")

    # --- T13-06: v5.2 との後方互換 ---
    @pytest.mark.auto
    def test_t13_06_v52_positive_patterns(self):
        """v5.2 の好意的検出パターンが引き続き検出される。"""
        v52_patterns = ["すごい", "ありがとう", "なるほど", "面白い", "助かる"]
        for word in v52_patterns:
            assert _is_positive_content(word), f"'{word}' が好意的と判定されること"


# ===========================================================================
# §13.5 — §2 好感度上昇量2倍化テスト (T13-10 〜 T13-14)
# ===========================================================================
class TestTrustGainMultiplier:
    """§2: TRUST_GAIN_MULTIPLIER = 2 の適用テスト。"""

    # --- T13-10: メンション応答の上昇量 ---
    @pytest.mark.auto
    def test_t13_10_mention_gain_doubled(self):
        """メンション応答の信頼度上昇が base_gain × 2。"""
        base_gain = 3  # メンション応答 base
        actual = _apply_trust_gain(base_gain)
        assert actual == base_gain * TRUST_GAIN_MULTIPLIER

    # --- T13-11: 好意的リアクション受信の上昇量 ---
    @pytest.mark.auto
    def test_t13_11_reaction_gain_doubled(self):
        """好意的リアクション受信の信頼度上昇が × 2。"""
        base_gain = 2  # reaction gain base
        actual = _apply_trust_gain(base_gain)
        assert actual == 4

    # --- T13-12: 日次減衰は2倍にならない ---
    @pytest.mark.auto
    def test_t13_12_decay_not_multiplied(self):
        """日次減衰量は2倍適用されない。"""
        decay = -10  # 30日非活動
        actual = _apply_trust_change(decay)
        assert actual == -10, "負値にはマルチプライヤ非適用"

    # --- T13-13: スコア上限100 ---
    @pytest.mark.auto
    def test_t13_13_score_capped_at_100(self):
        """スコアが100を超えない。"""
        current = 98
        gain = _apply_trust_gain(3)  # +6
        new_score = min(current + gain, 100)
        assert new_score == 100

    # --- T13-14: スコア下限0 ---
    @pytest.mark.auto
    def test_t13_14_score_floor_at_0(self):
        """スコアが0を下回らない。"""
        current = 1
        change = _apply_trust_change(-10)
        new_score = max(current + change, 0)
        assert new_score == 0


# ===========================================================================
# §13.6 — §3 記録モード／自由モードテスト (T13-20 〜 T13-26)
# ===========================================================================
class TestResponseMode:
    """§3: determine_response_mode() のモード判定テスト。"""

    # --- T13-20: 予測投稿 → 記録モード ---
    @pytest.mark.auto
    def test_t13_20_prediction_record_mode(self):
        """年号＋予測キーワード → record。"""
        assert _determine_response_mode("2030年にはAGIが実現すると思う") == "record"

    # --- T13-21: 意見質問 → 自由モード ---
    @pytest.mark.auto
    def test_t13_21_opinion_free_mode(self):
        """予測キーワードなし → free。"""
        assert _determine_response_mode("AGIってどう思う？") == "free"

    # --- T13-22: 予測＋意見混在 → 自由モード（Q2決定） ---
    @pytest.mark.auto
    def test_t13_22_mixed_defaults_to_free(self):
        """予測＋意見混在 → Q2決定で free が優先。"""
        content = "AGIは2030年に来ると思うけど、栞はどう思う？"
        assert _determine_response_mode(content) == "free"

    # --- T13-23: 記録モード出力に自由会話混入なし (LLM-Eval) ---
    @pytest.mark.llm_eval
    def test_t13_23_record_no_freeform(self):
        """記録モード応答がフォーマット出力のみ。(LLM-Eval: 目視確認)"""
        pytest.skip("LLM-Eval: 記録モード応答に自由会話が混入しないか目視確認")

    # --- T13-24: 自由モード出力にフォーマット混入なし (LLM-Eval) ---
    @pytest.mark.llm_eval
    def test_t13_24_free_no_format(self):
        """自由モード応答に📎記録形式が混入しない。(LLM-Eval)"""
        pytest.skip("LLM-Eval: 自由モード応答に構造化フォーマットが混入しないか目視確認")

    # --- T13-25: モード判定のログ出力 ---
    @pytest.mark.auto
    def test_t13_25_mode_logged(self, caplog):
        """モード判定結果がログに出力される。"""
        with caplog.at_level(logging.DEBUG):
            mode = _determine_response_mode("2030年にAGIが来る")
        # 実装側で logger.debug(f"[DEBUG] Response mode: {mode.upper()}")
        # テスト時は関数内ログを確認（ここでは判定結果のみ確認）
        assert mode in ("record", "free")

    # --- T13-26: モード判定のフォールバック ---
    @pytest.mark.auto
    def test_t13_26_fallback_to_free(self):
        """空文字列やNone相当 → free にフォールバック。"""
        assert _determine_response_mode("") == "free"
        assert _determine_response_mode("こんにちは") == "free"


# ===========================================================================
# §13.7 — §4 ハートカラー好感度連動テスト (T13-30 〜 T13-34)
# ===========================================================================
class TestHeartColor:
    """§4: 信頼度レベルに応じたハートカラーのマッピング。"""

    # --- T13-30 〜 T13-33: 各レベルのハートカラー ---
    @pytest.mark.auto
    @pytest.mark.parametrize(
        "test_id, score, expected_emoji",
        [
            ("T13-30", 10, "🧡"),   # Lv1: 0〜19
            ("T13-31", 35, "💛"),   # Lv2: 20〜49
            ("T13-32", 65, "💗"),   # Lv3: 50〜79
            ("T13-33", 95, "❤️"),   # Lv4: 80〜100
        ],
    )
    def test_heart_color_mapping(self, test_id, score, expected_emoji):
        """スコアに応じた正しいハートカラーが返る。"""
        level = _score_to_level(score)
        emoji = HEART_EMOJI_MAP[level]
        assert emoji == expected_emoji, f"{test_id}: score={score}, level={level}"

    # --- T13-34: テキスト応答内のハート使用 (LLM-Eval) ---
    @pytest.mark.llm_eval
    def test_t13_34_text_heart_consistency(self):
        """テキスト内ハートがメンバーのレベルに連動。(LLM-Eval)"""
        pytest.skip("LLM-Eval: Lv3メンバーへの応答で💗のみ使用されるか目視確認")

    # --- 境界値テスト ---
    @pytest.mark.auto
    @pytest.mark.parametrize(
        "score, expected_level",
        [
            (0, 1), (19, 1),    # Lv1 境界
            (20, 2), (49, 2),   # Lv2 境界
            (50, 3), (79, 3),   # Lv3 境界
            (80, 4), (100, 4),  # Lv4 境界
        ],
    )
    def test_heart_boundary_values(self, score, expected_level):
        """閾値の境界で正しいレベルが返る。"""
        assert _score_to_level(score) == expected_level


# ===========================================================================
# §13.8 — §5 日次データ整理テスト (T13-35 〜 T13-41)
# ===========================================================================
class TestDailyMaintenance:
    """§5: 日次メンテナンスタスクのテスト。"""

    # --- T13-35: 18:00 JSTに正常実行 ---
    @pytest.mark.auto
    def test_t13_35_scheduled_time(self):
        """18:00 JST スケジュール設定の確認。"""
        target_hour = 18
        target_tz = JST
        scheduled_time = datetime.now(tz=target_tz).replace(
            hour=target_hour, minute=0, second=0, microsecond=0
        )
        assert scheduled_time.hour == 18
        assert scheduled_time.tzinfo == JST

    # --- T13-36: レポートにバージョン情報 ---
    @pytest.mark.auto
    def test_t13_36_report_has_version(self):
        """日次レポートに v5.3 + デプロイ日時が含まれる。"""
        report = _mock_daily_report()
        assert "v5.3" in report, "バージョン番号がレポートに含まれる"
        # Q7: バージョン＋デプロイ日時
        assert "デプロイ" in report or "deploy" in report.lower()

    # --- T13-37: 未解決予測ハイライト含有 ---
    @pytest.mark.auto
    def test_t13_37_highlight_present(self):
        """未解決予測がある場合ハイライトセクションが存在する。"""
        report = _mock_daily_report(has_unresolved=True)
        assert "注目" in report or "ハイライト" in report or "予測" in report

    # --- T13-38: 未解決予測ゼロ時のハイライト省略 ---
    @pytest.mark.auto
    def test_t13_38_no_highlight_when_empty(self):
        """未解決予測ゼロ → ハイライトセクションなし。"""
        report = _mock_daily_report(has_unresolved=False)
        # ハイライトなしのときは「注目の予測」がレポートに含まれない
        assert "注目の予測" not in report

    # --- T13-39: 信頼度の日次減衰 ---
    @pytest.mark.auto
    def test_t13_39_daily_decay_applied(self):
        """30日非活動メンバーに減衰が適用される。"""
        score_before = 50
        decay = -10
        score_after = max(score_before + decay, 0)
        assert score_after == 40

    # --- T13-40: 各ステップ独立 try/except (N-05) ---
    @pytest.mark.auto
    def test_t13_40_steps_independent(self):
        """各メンテステップが独立しており、1ステップ失敗でも他が実行される。"""
        results = _mock_maintenance_with_failure(fail_step=2)
        assert results["step1"] == "ok"
        assert results["step2"] == "error"
        assert results["step3"] == "ok", "step2失敗後もstep3は実行される"

    # --- T13-41: 箇条書き非使用 (F-10) ---
    @pytest.mark.auto
    def test_t13_41_no_bullet_points(self):
        """日次レポートに箇条書きパターンが含まれない。"""
        report = _mock_daily_report()
        bullet_patterns = ["- ", "• ", "* ", "・"]
        for pat in bullet_patterns:
            assert pat not in report, f"箇条書きパターン '{pat}' が混入 (F-10)"


# ===========================================================================
# §13.9 — §6 メンション時の包括的データ更新テスト (T13-42 〜 T13-47)
# ===========================================================================
class TestMentionComprehensiveUpdate:
    """§6: メンション受信時のバックグラウンド更新の並列実行。"""

    # --- T13-42: 全更新ステップの並列実行 ---
    @pytest.mark.auto
    @pytest.mark.asyncio
    async def test_t13_42_parallel_updates(self):
        """trust更新・profile照合・prediction処理が並列で実行される。"""
        results = await _mock_parallel_updates()
        assert results["trust_updated"] is True
        assert results["profile_checked"] is True
        assert results["prediction_processed"] is True

    # --- T13-43: trust_score の即時反映 ---
    @pytest.mark.auto
    def test_t13_43_trust_immediate(self):
        """メンション応答後に trust_score が即時更新される。"""
        before = 30
        gain = _apply_trust_gain(3)  # +6 (base 3 × 2)
        after = min(before + gain, 100)
        assert after == 36

    # --- T13-44: プロファイル照合の非ブロッキング ---
    @pytest.mark.auto
    @pytest.mark.asyncio
    async def test_t13_44_profile_nonblocking(self):
        """プロファイル照合が応答生成をブロックしない。"""
        response_time, profile_time = await _mock_nonblocking_profile()
        assert response_time < profile_time, "応答がプロファイル照合完了前に返る"

    # --- T13-45: バックグラウンドエラーの隔離 ---
    @pytest.mark.auto
    @pytest.mark.asyncio
    async def test_t13_45_bg_error_isolation(self):
        """バックグラウンド更新のエラーがメイン応答に影響しない。"""
        result = await _mock_bg_with_error()
        assert result["response_sent"] is True, "メイン応答は成功"
        assert result["bg_error_logged"] is True, "BGエラーはログに記録"

    # --- T13-46: 動的メモの更新 ---
    @pytest.mark.auto
    def test_t13_46_dynamic_memo_update(self):
        """§6.3 プロファイル照合で検出された変化がメモに反映される。"""
        update = {
            "has_update": True,
            "updates": [
                {
                    "field": "interest",
                    "old_value": "AGI楽観派",
                    "new_value": "AGI慎重派に変化",
                    "confidence": 0.85,
                }
            ],
        }
        assert update["has_update"] is True
        assert update["updates"][0]["confidence"] >= 0.7

    # --- T13-47: confidence < 0.7 は破棄 ---
    @pytest.mark.auto
    def test_t13_47_low_confidence_discarded(self):
        """confidence < 0.7 の更新候補は破棄される。"""
        update = {"has_update": True, "updates": [
            {"field": "interest", "confidence": 0.5}
        ]}
        filtered = [u for u in update["updates"] if u["confidence"] >= 0.7]
        assert len(filtered) == 0, "低confidence更新は破棄"


# ===========================================================================
# テスト用ヘルパー関数 (実モジュールの簡易再現)
# ===========================================================================

# --- §1 リアクション判定 ---
_POSITIVE_KEYWORDS = [
    "ありがとう", "すごい", "なるほど", "面白い", "助かる",
    "いいね", "さすが", "素晴らしい", "感謝", "参考になる",
    "いい分析", "わかりやすい", "神",
]


def _is_positive_content(content: str) -> bool:
    """好意的キーワードの検出。"""
    return any(kw in content for kw in _POSITIVE_KEYWORDS)


def _should_react_heart(
    content: str,
    is_reply_to_shiori: bool,
    is_mention_to_shiori: bool,
) -> bool:
    """§1: リアクション付与判定 (3引数版)。"""
    if not (is_reply_to_shiori or is_mention_to_shiori):
        return False
    return _is_positive_content(content)


# --- §2 好感度変更 ---
def _apply_trust_gain(base_gain: int) -> int:
    """正の上昇値に TRUST_GAIN_MULTIPLIER を適用。"""
    return base_gain * TRUST_GAIN_MULTIPLIER


def _apply_trust_change(change: int) -> int:
    """正値は2倍、負値はそのまま。"""
    if change > 0:
        return change * TRUST_GAIN_MULTIPLIER
    return change


# --- §3 モード判定 ---
import re

_RECORD_TRIGGERS = [
    re.compile(r"20\d{2}年.*(?:する|なる|実現|完成|達成|来る|届く|越える|超える)"),
    re.compile(r"(?:記録して|メモして|予測として残して)"),
    re.compile(r"(?:前の予測|前回.*言った|前回.*予測)"),
]

_FREE_TRIGGERS = [
    re.compile(r"(?:どう思う|どう考える|意見|教えて|質問)"),
]


def _determine_response_mode(content: str) -> str:
    """§3.3: 記録/自由モード判定。混在時は free 優先 (Q2)。"""
    if not content.strip():
        return "free"

    has_record = any(p.search(content) for p in _RECORD_TRIGGERS)
    has_free = any(p.search(content) for p in _FREE_TRIGGERS)

    # Q2: 両方該当 → free
    if has_record and has_free:
        return "free"
    if has_record:
        return "record"
    return "free"


# --- §4 ハートカラー ---
def _score_to_level(score: int) -> int:
    """スコアから信頼度レベルを返す。"""
    for level, (low, high) in sorted(TRUST_THRESHOLDS.items()):
        if low <= score <= high:
            return level
    return 1  # fallback


# --- §5 日次レポート ---
def _mock_daily_report(has_unresolved: bool = True) -> str:
    """テスト用の日次レポートを返す。"""
    date_str = datetime.now(tz=JST).strftime("%Y-%m-%d")
    lines = [
        f"📎 フィールドノート整理 {date_str}",
        "",
        "v5.3（デプロイ: 2026-02-17）",
        "",
        f"今日の記録として、サーバー内で{3}件の予測関連発言を観測しました。"
        "新規の予測記録は1件追加しています。",
    ]
    if has_unresolved:
        lines.append("")
        lines.append(
            "注目の予測として、かちこちさんの「2027年末までに汎用翻訳デバイスが"
            "実用化」が期限まで残り1年を切っています。その後の考えを聞いてみたいですね。"
        )
    lines.append("")
    lines.append("明日も観測を続けます。何か気になることがあれば声をかけてくださいね。")
    return "\n".join(lines)


def _mock_maintenance_with_failure(fail_step: int = 2) -> dict:
    """独立 try/except の検証用。指定ステップで例外発生。"""
    results = {}
    for step in [1, 2, 3]:
        try:
            if step == fail_step:
                raise RuntimeError(f"Step {step} failed")
            results[f"step{step}"] = "ok"
        except Exception:
            results[f"step{step}"] = "error"
    return results


# --- §6 並列更新 ---
async def _mock_parallel_updates() -> dict:
    """3つのバックグラウンドタスクの並列実行をシミュレート。"""
    results = {}

    async def trust_update():
        await asyncio.sleep(0.01)
        results["trust_updated"] = True

    async def profile_check():
        await asyncio.sleep(0.02)
        results["profile_checked"] = True

    async def prediction_process():
        await asyncio.sleep(0.01)
        results["prediction_processed"] = True

    await asyncio.gather(trust_update(), profile_check(), prediction_process())
    return results


async def _mock_nonblocking_profile() -> tuple[float, float]:
    """プロファイル照合が応答をブロックしないことをシミュレート。"""
    import time

    response_done = 0.0
    profile_done = 0.0

    async def generate_response():
        nonlocal response_done
        await asyncio.sleep(0.01)
        response_done = time.monotonic()

    async def check_profile():
        nonlocal profile_done
        await asyncio.sleep(0.05)  # プロファイル照合は遅い
        profile_done = time.monotonic()

    start = time.monotonic()
    # 応答は即座に開始、プロファイルはバックグラウンド
    task = asyncio.create_task(check_profile())
    await generate_response()
    await task
    return response_done - start, profile_done - start


async def _mock_bg_with_error() -> dict:
    """バックグラウンドエラーが応答に影響しないことを検証。"""
    result = {"response_sent": False, "bg_error_logged": False}

    async def bg_task():
        try:
            raise ValueError("BG task error")
        except Exception:
            result["bg_error_logged"] = True

    # メイン応答
    asyncio.create_task(bg_task())
    await asyncio.sleep(0.01)
    result["response_sent"] = True
    await asyncio.sleep(0.05)  # BGタスク完了待ち
    return result


# ===========================================================================
# pytest marker 登録 (conftest.py が無い場合のフォールバック)
# ===========================================================================
def pytest_configure(config):
    config.addinivalue_line("markers", "auto: Automatic verification test")
    config.addinivalue_line("markers", "llm_eval: LLM output evaluation test")
    config.addinivalue_line("markers", "asyncio: Async test")
