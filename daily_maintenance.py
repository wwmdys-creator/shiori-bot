"""daily_maintenance.py — 日次データ整理タスク

§5 準拠。毎日18:00 JSTに実行される自動メンテナンス。
チャンネル走査、予測検出、プロファイル更新、好感度減衰、報告投稿を行う。

インターフェース契約: §12.7.2
依存: prediction_highlighter.py, config.py
呼び出し元: bot.py (discord.ext.tasks.loop)

COMMON_MISTAKES対応:
  N-05: チャンネルNoneチェック必須 (§18 Railway Volume)
  §15: 全メソッドにエラー隔離 — 1ステップ失敗で全体を止めない
  §12.4.4: 戻り値フォーマット厳守
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("shiori.daily_maintenance")

JST = timezone(timedelta(hours=9))


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
                   - bot.llm_client: Anthropic APIクライアント
                   - bot.config: 設定オブジェクト（BOT_VERSION, DEPLOY_DATE等）
        """
        self.bot = bot
        self.shiori_channel_id: int | None = None
        self._highlighter = None  # 遅延初期化

    @property
    def highlighter(self):
        """PredictionHighlighter を遅延初期化する"""
        if self._highlighter is None:
            from prediction_highlighter import PredictionHighlighter
            self._highlighter = PredictionHighlighter()
        return self._highlighter

    # ========== 公開メソッド ==========

    async def find_shiori_channel(self) -> int | None:
        """Shiori_chのチャンネルIDを検索する

        Returns:
            チャンネルID。見つからない場合はNone。

        検索基準:
            チャンネル名に "shiori"（大文字小文字不問）
            または "栞" を含むテキストチャンネル
        """
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                name_lower = channel.name.lower()
                if "shiori" in name_lower or "栞" in channel.name:
                    return channel.id
        return None

    async def run_daily_maintenance(self) -> dict:
        """日次メンテナンスの全ステップを実行する

        処理フロー（各ステップが独立try/except — COMMON_MISTAKES N-05）:
            1. MAINカテゴリの全チャンネルから直近24hメッセージをスキャン
            2. 予測候補の検出と記録
            3. メンバープロファイルの更新
            4. 好感度の日次減衰適用
            5. 未解決予測ハイライトの選定

        Returns:
            dict — §12.4.4 形式の統計情報:
                total_messages: スキャン件数
                new_predictions: 新規予測数
                updated_members: 更新メンバー数
                highlights: list[dict] (§12.4.3 形式)
                trust_decays_applied: 減衰適用数

        ⚠️ 1ステップの失敗が他ステップをブロックしない（エラー隔離原則）
        ⚠️ 日次減衰には TRUST_GAIN_MULTIPLIER を適用しない（§2規定）
        """
        stats = {
            "total_messages": 0,
            "new_predictions": 0,
            "updated_members": 0,
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

                    stats["total_messages"] += 1

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

        stats["updated_members"] = len(updated_member_ids)

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
        ⚠️ チャンネルNoneチェック必須（COMMON_MISTAKES N-05, §18）
        """
        # チャンネル検索
        if not self.shiori_channel_id:
            self.shiori_channel_id = await self.find_shiori_channel()

        if not self.shiori_channel_id:
            logger.warning(
                "[DailyMaintenance] Shiori channel not found, "
                "skipping daily report"
            )
            return

        # N-05: bot.get_channel() の戻り値がNoneになりうる
        channel = self.bot.get_channel(self.shiori_channel_id)
        if channel is None:
            logger.error(
                f"[DailyMaintenance] Channel {self.shiori_channel_id} "
                f"not found in cache"
            )
            return

        today = datetime.now(tz=JST).strftime("%Y-%m-%d")

        # 設定値取得（フォールバック付き）
        bot_version = getattr(self.bot, "config", None)
        version_str = getattr(bot_version, "BOT_VERSION", "5.3")
        deploy_str = getattr(bot_version, "DEPLOY_DATE", "unknown")

        # 所感を生成（Haiku使用 — バックグラウンドタスク用）
        observation = await self._generate_observation(stats)

        # ハイライトテキスト構築
        highlight_text = self._format_highlights(stats.get("highlights", []))

        # §5.3 報告フォーマット
        report = (
            f"📔 本日のフィールドノート整理（{today} 18:00）\n"
            f"Shiori v{version_str} ({deploy_str} deployed)\n\n"
            f"今日のサーバー活動: "
            f"{stats.get('total_messages', 0)}件の投稿を確認しました。\n"
            f"新規予測記録: {stats.get('new_predictions', 0)}件追加\n"
            f"プロファイル更新: {stats.get('updated_members', 0)}名分\n"
        )

        if highlight_text:
            report += f"\n📌 気になる予測メモ:\n{highlight_text}\n"

        report += f"\n所感: {observation}\n\n次回整理: 明日 18:00"

        try:
            await channel.send(report)
            logger.info("[DailyMaintenance] Daily report posted")
        except Exception as e:
            logger.error(f"[DailyMaintenance] Report post failed: {e}")

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
        """メッセージIDが既に予測として記録済みか確認する"""
        try:
            return self.bot.predictions.is_recorded(message_id)
        except Exception:
            return False

    async def _record_prediction(self, msg) -> None:
        """予測を記録する（delegateパターン）"""
        await self.bot.predictions.record_from_message(msg)

    def _update_member_profile(self, msg) -> None:
        """メッセージからプロファイルを更新する

        更新対象:
            - last_active: メッセージのタイムスタンプ
            - total_messages: インクリメント
        """
        self.bot.member_profile.update_activity(
            user_id=str(msg.author.id),
            username=msg.author.name,
            display_name=getattr(msg.author, "global_name", None)
            or msg.author.display_name,
            timestamp=msg.created_at,
        )

    async def _apply_trust_decay(self) -> int:
        """全メンバーに日次好感度減衰を適用する

        §2規定: 日次減衰にはTRUST_GAIN_MULTIPLIERを適用しない

        Returns:
            減衰を適用したメンバー数
        """
        count = 0
        try:
            profiles = self.bot.member_profile.get_all_profiles()
            for user_id, profile in profiles.items():
                old_score = profile.get("trust_score", 0)
                if old_score > 0:
                    # 減衰値はconfig定数から取得（デフォルト: -1）
                    decay = getattr(
                        getattr(self.bot, "config", None),
                        "DAILY_TRUST_DECAY",
                        -1,
                    )
                    new_score = max(0, old_score + decay)
                    if new_score != old_score:
                        self.bot.member_profile.update_trust_score(
                            user_id, new_score
                        )
                        count += 1
        except Exception as e:
            logger.error(f"[DailyMaintenance] Trust decay error: {e}")
        return count

    def _select_highlights(self, current_date: datetime) -> list[dict]:
        """PredictionHighlighterを呼び出してハイライトを選定する

        Returns:
            list[dict] — §12.4.3 形式
        """
        try:
            predictions = self.bot.predictions.get_all_active()
            member_profiles = self.bot.member_profile.get_all_profiles()

            return self.highlighter.select_highlights(
                predictions=predictions,
                member_profiles=member_profiles,
                current_date=current_date,
            )
        except Exception as e:
            logger.error(f"[DailyMaintenance] Highlight selection: {e}")
            return []

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
        """
        try:
            prompt = (
                f"以下の日次整理結果を踏まえて、"
                f"2045年から来た研究者「栞」として1〜2文の短い所感を書いてください。\n"
                f"投稿確認数: {stats.get('total_messages', 0)}件\n"
                f"新規予測: {stats.get('new_predictions', 0)}件\n"
                f"プロファイル更新: {stats.get('updated_members', 0)}名\n\n"
                f"条件:\n"
                f"- 1〜2文で簡潔に\n"
                f"- フィールドノートの走り書き風\n"
                f"- メンバー名やスコアに言及しない\n"
            )

            response = await self.bot.llm_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.warning(
                f"[DailyMaintenance] Observation generation failed: {e}"
            )
            return "今日も観測データの整理を完了しました📎"

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
