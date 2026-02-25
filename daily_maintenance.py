"""daily_maintenance.py — 日次データ整理タスク

§5 準拠。毎日18:00 JSTに実行される自動メンテナンス。
チャンネル走査、予測検出、プロファイル更新、好感度減衰、報告投稿を行う。

インターフェース契約: §12.7.2
依存: prediction_highlighter.py, config.py, shiori_posting.py
呼び出し元: bot.py (discord.ext.tasks.loop)

COMMON_MISTAKES対応:
  N-05: チャンネルNoneチェック必須 (§18 Railway Volume)
  §15: 全メソッドにエラー隔離 — 1ステップ失敗で全体を止めない
  §12.4.4: 戻り値フォーマット厳守
  §38: Forum Thread と TextChannel を混同しない
       → 投稿は shiori_posting.post_to_shiori_thread() に委譲

変更履歴:
  2026-02-23: Step 6「動的メモ統合」追加（memos_consolidated を常に0件返す不具合修正）
              _consolidate_dynamic_memos() を実装。
              config.MEMO_CONSOLIDATION_THRESHOLD (デフォルト10) 件超で Haiku 統合。
"""

import logging
from datetime import datetime, timedelta, timezone

import config as shiori_config
from shiori_posting import post_to_shiori_thread

logger = logging.getLogger("shiori.daily_maintenance")

JST = timezone(timedelta(hours=9))

# 動的メモ統合の閾値（この件数を超えたメンバーが統合対象）
# config に MEMO_CONSOLIDATION_THRESHOLD が定義されていればそちらを優先
_MEMO_CONSOLIDATION_THRESHOLD_DEFAULT = 5

# Haiku への統合依頼プロンプト（call_haiku ではなく _client.messages.create を直接使用）
_MEMO_CONSOLIDATION_SYSTEM = (
    "あなたはメモ整理アシスタントです。"
    "渡されたメモ群を重複排除し、情報を失わずに簡潔に統合してください。"
    "出力フォーマット: 各メモを改行区切りで出力。1件あたり最大80文字。"
    "先頭の日付タグ [YYYY-MM-DD] は最新日付に統一してください。"
)


class DailyMaintenanceTask:
    """日次データ整理タスク（§5詳細参照）

    毎日18:00 JSTに discord.ext.tasks.loop で実行。
    コンストラクタでbotインスタンスを受け取る。
    """

    def __init__(self, bot) -> None:
        """
        Args:
            bot: [必須] discord.ext.commands.Bot インスタンス。
                 以下の属性を持つことを前提とする:
                   - bot.guilds: サーバー一覧
                   - bot.member_profile: MemberProfileManager
                   - bot.predictions: PredictionManager
                   - bot.llm: LLMClient（._client で AsyncAnthropic にアクセス）
                   - bot.trust: TrustManager
                   - bot.config: 設定オブジェクト（BOT_VERSION, DEPLOY_DATE等）
        """
        self.bot = bot
        # Shiori_ch への投稿は shiori_posting.post_to_shiori_thread() に委譲
        self._highlighter = None  # 遅延初期化

    @property
    def highlighter(self):
        """PredictionHighlighter を遅延初期化する"""
        if self._highlighter is None:
            from prediction_highlighter import PredictionHighlighter
            self._highlighter = PredictionHighlighter()
        return self._highlighter

    # ========== 公開メソッド ==========

    async def run_daily_maintenance(self) -> dict:
        """日次メンテナンスの全ステップを実行する

        処理フロー（各ステップが独立try/except — COMMON_MISTAKES N-05）:
            1. MAINカテゴリの全チャンネルから直近24hメッセージをスキャン
            2. 予測候補の検出と記録
            3. メンバープロファイルの更新
            4. 好感度の日次減衰適用
            5. 未解決予測ハイライトの選定
            6. 動的メモの統合・重複排除（新規追加）

        Returns:
            dict — §12.4.4 形式の統計情報:
                total_messages_scanned: スキャン件数
                new_predictions: 新規予測数
                profiles_updated: 更新メンバー数
                memos_consolidated: 統合メモ処理を行ったメンバー数
                highlights: list[dict] (§12.4.3 形式)
                trust_decays_applied: 減衰適用数

        ⚠️ 1ステップの失敗が他ステップをブロックしない（エラー隔離原則）
        ⚠️ 日次減衰には TRUST_GAIN_MULTIPLIER を適用しない（§2規定）
        """
        stats = {
            "total_messages_scanned": 0,
            "new_predictions": 0,
            "profiles_updated": 0,
            "memos_consolidated": 0,
            "highlights": [],
            "trust_decays_applied": 0,
        }

        now = datetime.now(tz=JST)
        since = now - timedelta(hours=24)
        updated_member_ids: set[str] = set()

        # ===== Step 1-3: チャンネル走査・予測検出・プロファイル更新 =====
        channels = self._get_monitored_channels()
        for channel in channels:
            try:
                async for msg in channel.history(after=since, limit=500):
                    if msg.author.bot:
                        continue

                    stats["total_messages_scanned"] += 1

                    # Step 2: 予測検出
                    try:
                        if self._is_prediction_candidate(msg.content):
                            if not self._is_already_recorded(msg.id):
                                await self._record_prediction(msg)
                                stats["new_predictions"] += 1
                    except Exception as e:
                        logger.error(
                            f"[DailyMaintenance] Prediction detection error "
                            f"in {channel.name}: {e}"
                        )

                    # Step 3: プロファイル更新
                    try:
                        author_id = str(msg.author.id)
                        if author_id not in updated_member_ids:
                            self._update_member_profile(msg)
                            updated_member_ids.add(author_id)
                    except Exception as e:
                        logger.error(
                            f"[DailyMaintenance] Profile update error "
                            f"for {msg.author}: {e}"
                        )

            except Exception as e:
                logger.error(
                    f"[DailyMaintenance] Channel scan error in "
                    f"{channel.name}: {e}"
                )
                continue  # 1チャンネル失敗で全体を止めない

        stats["profiles_updated"] = len(updated_member_ids)

        # ===== Step 4: 好感度の日次減衰 =====
        try:
            stats["trust_decays_applied"] = await self._apply_trust_decay()
        except Exception as e:
            logger.error(f"[DailyMaintenance] Trust decay failed: {e}")

        # ===== Step 5: 予測ハイライト選定 =====
        try:
            stats["highlights"] = self._select_highlights(now)
        except Exception as e:
            logger.error(
                f"[DailyMaintenance] Highlight selection failed: {e}"
            )

        # ===== Step 6: 動的メモ統合（新規追加） =====
        try:
            stats["memos_consolidated"] = await self._consolidate_dynamic_memos()
        except Exception as e:
            logger.error(
                f"[DailyMaintenance] Memo consolidation failed: {e}"
            )

        # ===== データ保存 =====
        try:
            await self._save_data()
        except Exception as e:
            logger.error(f"[DailyMaintenance] Data save failed: {e}")

        logger.info(f"[DailyMaintenance] Completed: {stats}")
        return stats

    async def post_daily_report(self, stats: dict) -> None:
        """日次報告をShiori_chに投稿する

        Args:
            stats: [必須] run_daily_maintenance() の戻り値（§12.4.4形式）

        ⚠️ 報告に含めてはいけない情報: Tier, スコア, 信頼度レベル（§5.4参照）
        ⚠️ BOT_VERSION と DEPLOY_DATE を報告ヘッダに含める（§5.3参照）
        ⚠️ §38: Forum Thread への投稿は shiori_posting に委譲
        """
        today = datetime.now(tz=JST).strftime("%Y-%m-%d")

        # 設定値取得（configモジュールから直接）
        version_str = getattr(shiori_config, "BOT_VERSION", "5.3")
        deploy_str = getattr(shiori_config, "DEPLOY_DATE", "unknown")

        # 所感を生成（Haiku使用 — バックグラウンドタスク用）
        observation = await self._generate_observation(stats)

        # ハイライトテキスト構築
        highlight_text = self._format_highlights(stats.get("highlights", []))

        # §5.3 報告フォーマット
        report = (
            f"📔 本日のフィールドノート整理（{today} 18:00）\n"
            f"Shiori v{version_str} ({deploy_str} deployed)\n\n"
            f"今日のサーバー活動: "
            f"{stats.get('total_messages_scanned', 0)}件の投稿を確認しました。\n"
            f"新規予測記録: {stats.get('new_predictions', 0)}件追加\n"
            f"プロファイル更新: {stats.get('profiles_updated', 0)}名分\n"
            f"動的メモ整理: {stats.get('memos_consolidated', 0)}件を統合・更新\n"
        )

        if highlight_text:
            report += f"\n📌 気になる予測メモ:\n{highlight_text}\n"

        report += f"\n所感: {observation}\n\n次回整理: 明日 18:00"

        # §38: Forum Thread への投稿は共通ヘルパーに委譲
        success = await post_to_shiori_thread(
            self.bot, report, caller="DailyMaintenance"
        )
        if success:
            logger.info("[DailyMaintenance] Daily report posted")
        else:
            logger.error("[DailyMaintenance] Daily report post failed")

    # ========== 内部メソッド ==========

    def _get_monitored_channels(self) -> list:
        """MAINカテゴリ内のテキストチャンネル一覧を返す"""
        channels = []
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if (
                    channel.category
                    and "MAIN" in (channel.category.name or "").upper()
                ):
                    channels.append(channel)
        return channels

    def _is_prediction_candidate(self, content: str) -> bool:
        """予測投稿の候補か簡易判定する

        §5で定義された予測チャンネルのメッセージを対象とする。
        詳細な予測パースは別モジュール（prediction_parser）が担当。
        ここでは最低限のフィルタのみ行う。
        """
        if not content or len(content) < 10:
            return False
        # 予測チャンネルのメッセージは基本的にすべて予測候補
        # 詳細判定はrecord_prediction内でparser経由で行う
        return True

    def _is_already_recorded(self, message_id: int) -> bool:
        """メッセージIDが既に予測として記録済みか確認する

        P1 hotfix: predictions.is_recorded() は未実装。
        predictions.predictions リスト内の message_id フィールドで簡易チェック。
        """
        try:
            for pred in self.bot.predictions.predictions:
                if pred.get("message_id") == message_id:
                    return True
            return False
        except Exception:
            return False

    async def _record_prediction(self, msg) -> None:
        """予測を記録する（delegateパターン）

        P1 hotfix: record_from_message() は未実装。
        既存の record_prediction() に msg_dict を渡す。
        """
        msg_dict = {
            "user_id": msg.author.id,
            "display_name": msg.author.display_name,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
            "channel": msg.channel.name,
            "channel_category_id": getattr(
                msg.channel.category, "id", None
            ),
        }
        await self.bot.predictions.record_prediction(
            message=msg_dict,
            prediction_text=msg.content[:200],
            detection_method="daily_scan",
        )

    def _update_member_profile(self, msg) -> None:
        """メッセージからプロファイルを更新する

        P1 hotfix: update_activity() は未実装。
        プロファイル辞書に直接 last_active を書き込む簡易処理。

        P1-1修正: タイムスタンプ形式を JST YYYY-MM-DD に統一。
        trust.py の strptime("%Y-%m-%d") と整合させる。
        """
        profile = self.bot.member_profile.get_profile(user_id=msg.author.id)
        if profile is not None:
            # P1-1: UTC→JST変換し、trust.py と同じ YYYY-MM-DD 形式で記録
            jst_dt = msg.created_at.replace(tzinfo=timezone.utc).astimezone(JST)
            profile["last_active"] = jst_dt.strftime("%Y-%m-%d")
        # profile が None（未登録メンバー）の場合はスキップ

    async def _apply_trust_decay(self) -> int:
        """全メンバーに日次好感度減衰を適用する

        §2規定: 日次減衰にはTRUST_GAIN_MULTIPLIERを適用しない

        P1 hotfix: get_all_profiles()/update_trust_score() は未実装。
        trust.members を直接操作する。

        Returns:
            減衰を適用したメンバー数
        """
        count = 0
        try:
            decay = getattr(shiori_config, "DAILY_TRUST_DECAY", -1)
            for user_id, member_data in list(self.bot.trust.members.items()):
                old_score = member_data.get("score", 0)
                if old_score > 0:
                    new_score = max(0, old_score + decay)
                    if new_score != old_score:
                        member_data["score"] = new_score
                        count += 1
        except Exception as e:
            logger.error(f"[DailyMaintenance] Trust decay error: {e}")
        return count

    def _select_highlights(self, current_date: datetime) -> list[dict]:
        """PredictionHighlighterを呼び出してハイライトを選定する

        P1 hotfix: get_all_active()/get_all_profiles() は未実装。
        predictions.predictions と member_profile.profiles を直接使用。

        Returns:
            list[dict] — §12.4.3 形式
        """
        try:
            predictions = self.bot.predictions.predictions
            member_profiles = self.bot.member_profile.profiles

            return self.highlighter.select_highlights(
                predictions=predictions,
                member_profiles=member_profiles,
                current_date=current_date,
            )
        except Exception as e:
            logger.error(f"[DailyMaintenance] Highlight selection: {e}")
            return []

    async def _consolidate_dynamic_memos(self) -> int:
        """動的メモが閾値を超えたメンバーのメモをHaikuで統合する（Step 6）

        閾値は config.MEMO_CONSOLIDATION_THRESHOLD（デフォルト10）。
        超過メンバーのメモ全件をHaikuに渡し、重複排除・要約した
        結果（最大5件）で上書きする。

        エラー隔離: 1メンバーの失敗は他メンバーの処理に影響しない（N-05）。
        LLM失敗時はそのメンバーをスキップし、元のメモを保持する。

        Returns:
            統合処理を実行したメンバー数（LLM失敗でスキップしたメンバーは含まない）
        """
        threshold = getattr(
            shiori_config,
            "MEMO_CONSOLIDATION_THRESHOLD",
            _MEMO_CONSOLIDATION_THRESHOLD_DEFAULT,
        )
        tier1_model = getattr(
            shiori_config, "TIER1_MODEL", "claude-haiku-4-5-20251001"
        )

        consolidated_count = 0
        today_str = datetime.now(tz=JST).strftime("%Y-%m-%d")

        profiles: dict = self.bot.member_profile.profiles

        for uid, profile in profiles.items():
            memos: list[str] = profile.get("dynamic_memos", [])
            if len(memos) <= threshold:
                continue

            display_name = profile.get("display_name", uid)
            logger.info(
                "[DailyMaintenance] Consolidating memos for %s (%d memos > threshold %d)",
                display_name,
                len(memos),
                threshold,
            )

            try:
                consolidated = await self._call_haiku_consolidate(
                    memos=memos,
                    display_name=display_name,
                    today_str=today_str,
                    model=tier1_model,
                )
                if consolidated:
                    profile["dynamic_memos"] = consolidated
                    consolidated_count += 1
                    logger.info(
                        "[DailyMaintenance] Memos consolidated for %s: %d → %d",
                        display_name,
                        len(memos),
                        len(consolidated),
                    )
            except Exception as e:
                # 1メンバーの失敗は全体に影響させない（N-05）
                logger.error(
                    "[DailyMaintenance] Memo consolidation failed for %s: %s",
                    display_name,
                    e,
                )
                continue

        return consolidated_count

    async def _call_haiku_consolidate(
        self,
        memos: list[str],
        display_name: str,
        today_str: str,
        model: str,
    ) -> list[str]:
        """Haikuを呼び出してメモ群を統合する

        Args:
            memos: 統合対象の動的メモリスト（日付タグ付き）
            display_name: ログ用のメンバー表示名
            today_str: 統合後メモの日付タグに使う YYYY-MM-DD 文字列
            model: 使用するHaikuモデルID

        Returns:
            統合後のメモリスト（最大5件）。空リストの場合は呼び出し元でスキップ。

        Raises:
            Exception: LLM呼び出し失敗時（呼び出し元でキャッチ）
        """
        memo_text = "\n".join(memos)
        user_prompt = (
            f"以下は「{display_name}」さんの動的メモです。\n"
            f"重複・類似内容を統合し、最大5件の簡潔なメモに整理してください。\n"
            f"各メモの先頭は [{today_str}] とし、改行区切りで出力してください。\n\n"
            f"【メモ一覧】\n{memo_text}"
        )

        response = await self.bot.llm._client.messages.create(
            model=model,
            max_tokens=512,
            system=_MEMO_CONSOLIDATION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_output = response.content[0].text.strip()
        if not raw_output:
            return []

        # 改行で分割し、空行・前後空白を除去して最大5件に絞る
        lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
        return lines[:5]

    def _format_highlights(self, highlights: list[dict]) -> str:
        """ハイライトリストを報告用テキストに整形する

        Args:
            highlights: §12.4.3 形式のリスト

        Returns:
            報告に挿入するテキスト。空文字列＝ハイライトなし
        """
        if not highlights:
            return ""

        lines = []
        for i, h in enumerate(highlights, 1):
            narrative = h.get("narrative", "")
            if narrative:
                lines.append(f"  {i}. {narrative}")

        return "\n".join(lines)

    async def _generate_observation(self, stats: dict) -> str:
        """所感テキストを生成する（Haiku使用）

        バックグラウンドタスクなのでHaikuモデルを使用。
        生成失敗時はフォールバックテキストを返す。

        v5.3.1: 所感を3〜4文に拡充（従来は1〜2文）。
        """
        try:
            prompt = (
                f"以下の日次整理結果を踏まえて、"
                f"2045年から来た研究者「栞」としてフィールドノートの所感を書いてください。\n"
                f"投稿確認数: {stats.get('total_messages_scanned', 0)}件\n"
                f"新規予測: {stats.get('new_predictions', 0)}件\n"
                f"プロファイル更新: {stats.get('profiles_updated', 0)}名\n"
                f"メモ統合: {stats.get('memos_consolidated', 0)}名分\n\n"
                f"条件:\n"
                f"- 3〜4文で書くこと（短すぎず長すぎず）\n"
                f"- 1文目は今日のデータの全体的な印象\n"
                f"- 2〜3文目は観測から感じた傾向や気づき、"
                f"2045年の視点からの比較や感慨\n"
                f"- 最後の文は明日への期待や次に注目したいテーマ\n"
                f"- フィールドノートの走り書き風\n"
                f"- 「# 栞の日誌より」の見出しは不要\n"
                f"- メンバー名やスコアに言及しない\n"
            )

            response = await self.bot.llm._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.warning(
                f"[DailyMaintenance] Observation generation failed: {e}"
            )
            return (
                "今日も観測データの整理を完了しました。"
                "2045年の私たちの時代から振り返ると、"
                "この時期の予測活動の活発さには改めて驚かされます📎"
            )

    async def _save_data(self) -> None:
        """データファイルを保存する"""
        try:
            await self.bot.member_profile.save()
        except Exception as e:
            logger.error(f"[DailyMaintenance] Profile save failed: {e}")

        try:
            await self.bot.predictions.save()
        except Exception as e:
            logger.error(f"[DailyMaintenance] Predictions save failed: {e}")

    # ========== 手動メモ整理（チャットコマンド用） ==========

    async def run_manual_consolidation(self) -> str:
        """手動でメモ統合を実行し、結果レポートを返す

        bot.py からメンション経由で呼ばれる。
        統合対象があればHaikuで統合し、結果を文字列で返す。
        統合後にデータを保存する。

        Returns:
            チャットに投稿する結果レポート文字列

        COMMON_MISTAKES N-05: メンバーごとにエラー隔離
        """
        logger.info("[ManualConsolidation] Starting manual memo consolidation")

        threshold = getattr(
            shiori_config,
            "MEMO_CONSOLIDATION_THRESHOLD",
            _MEMO_CONSOLIDATION_THRESHOLD_DEFAULT,
        )
        profiles: dict = self.bot.member_profile.profiles

        # 統合対象の事前チェック
        candidates = []
        for uid, profile in profiles.items():
            memos = profile.get("dynamic_memos", [])
            if len(memos) > threshold:
                display_name = profile.get("display_name", uid)
                candidates.append((uid, display_name, len(memos)))

        if not candidates:
            total_memos = sum(
                len(p.get("dynamic_memos", [])) for p in profiles.values()
            )
            members_with_memos = sum(
                1 for p in profiles.values()
                if len(p.get("dynamic_memos", [])) > 0
            )
            return (
                f"📎 動的メモ整理（手動実行）\n\n"
                f"統合対象メンバー: 0名\n"
                f"（閾値: {threshold}件超で統合）\n\n"
                f"現在のメモ状況:\n"
                f"  メモ保有メンバー: {members_with_memos}名\n"
                f"  全メモ合計: {total_memos}件\n\n"
                f"閾値を超えるメンバーがいないため、統合処理はスキップしました。"
            )

        # 統合実行
        consolidated_count = 0
        details = []

        try:
            consolidated_count = await self._consolidate_dynamic_memos()
        except Exception as e:
            logger.error(f"[ManualConsolidation] Failed: {e}")
            return (
                f"📎 動的メモ整理（手動実行）\n\n"
                f"⚠️ 統合処理中にエラーが発生しました: {str(e)[:100]}\n"
                f"統合対象: {len(candidates)}名"
            )

        # 統合後のメモ件数を収集
        for uid, display_name, original_count in candidates:
            profile = profiles.get(uid)
            if profile:
                new_count = len(profile.get("dynamic_memos", []))
                details.append(
                    f"  {display_name}: {original_count}件 → {new_count}件"
                )

        # データ保存
        try:
            await self.bot.member_profile.save()
            logger.info("[ManualConsolidation] Profile data saved")
        except Exception as e:
            logger.error(f"[ManualConsolidation] Save failed: {e}")

        # レポート生成
        detail_text = "\n".join(details) if details else "  （詳細なし）"
        total_memos_after = sum(
            len(p.get("dynamic_memos", [])) for p in profiles.values()
        )

        return (
            f"📎 動的メモ整理（手動実行）\n\n"
            f"統合対象: {len(candidates)}名"
            f"（閾値: {threshold}件超）\n"
            f"統合完了: {consolidated_count}名\n\n"
            f"統合結果:\n{detail_text}\n\n"
            f"全メモ合計（統合後）: {total_memos_after}件\n"
            f"データ保存: 完了"
        )

