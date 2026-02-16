"""weekly_monologue.py — 週次フィールドノート投稿タスク

§8 準拠。毎週日曜21:00 JSTに Shiori_ch へ独り言を投稿する。
2045年から来たフィールドワーカー「栞」のメモ書き風テキストを
Sonnetモデルで生成し、サーバーの実際の議論を反映した内容にする。

インターフェース契約: §12.7.4
依存: bot, config.py, Sonnet API
呼び出し元: bot.py (discord.ext.tasks.loop)

COMMON_MISTAKES対応:
  N-05: チャンネルNoneチェック必須 (§18 Railway Volume)
  §15: 全メソッドにエラー隔離 — コンテキスト収集失敗でも生成は続行
"""

import calendar
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("shiori.weekly_monologue")

JST = timezone(timedelta(hours=9))


# ===== プロンプト定義（§8.4.1, §8.4.2） =====

MONOLOGUE_SYSTEM_PROMPT = """\
あなたは2045年からフィールドワークで2025年に来ている研究者「栞」です。
今週のサーバーの活動を踏まえて、フィールドノートの走り書き風の独り言を書いてください。

ルール:
- 80〜150字で書くこと（短く簡潔に）
- 「話しかけて」「返信してね」等の呼びかけは絶対に含まない
- あくまで独り言・メモ書きの体裁を維持する
- 以下のいずれかのトーンで書くこと:
  (A) 今週のサーバー議論への観察コメント
  (B) 未来の知識を匂わせるが寸止めする（タイムパラドックス回避）
  (C) この時代へのフィールドワーカーとしての素朴な感慨
- 絵文字は最大1個（📎推奨）
- 改行なしの1段落で書くこと"""

MONOLOGUE_USER_PROMPT = """\
今週のサーバー活動サマリー:
- アクティブメンバー数: {active_count}名
- 主な話題: {topics}
- 注目の予測: {notable_predictions}

上記を踏まえて、フィールドノートの走り書きを1つ書いてください。"""

# フォールバック: LLM生成失敗時の汎用テキスト（§8.4.4）
FALLBACK_MONOLOGUE = (
    "今週もフィールドノートを整理中です。"
    "この時代の議論は、毎週新しい発見があって飽きないですね📎"
)


def validate_monologue(content: str) -> str:
    """独り言の投稿前バリデーション（§8.5.1）

    Args:
        content: 生成された独り言テキスト

    Returns:
        バリデーション済みテキスト（メンション除去済み）

    処理:
    - <@!?数字> 形式のメンション記法を除去
    - @everyone / @here を除去
    - 除去があった場合は警告ログを出力
    """
    # @メンション記法の除去
    cleaned = re.sub(r"<@!?\d+>", "", content)

    # @everyone / @here の除去
    cleaned = cleaned.replace("@everyone", "").replace("@here", "")

    if cleaned != content:
        logger.warning(
            "[WeeklyMonologue] Removed mentions from generated content"
        )

    return cleaned.strip()


class WeeklyMonologueTask:
    """週次フィールドノート投稿タスク（§8, §12.7.4）

    日曜21:00 JST に discord.ext.tasks.loop で実行。
    日曜以外の日はループ起動後に早期リターンする。

    ⚠️ 独り言の生成にはSonnetを使用する（品質重視）。
       Haiku（バックグラウンドタスク用）ではない点に注意。
    """

    # §12.3 config.py のフォールバック値
    MONOLOGUE_DAY = calendar.SUNDAY  # 6

    def __init__(self, bot) -> None:
        """
        Args:
            bot: [必須] discord.ext.commands.Bot インスタンス。
                 以下の属性を持つことを前提とする:
                   - bot.guilds: サーバー一覧
                   - bot.llm_client: Anthropic APIクライアント
                   - bot.member_profile: MemberProfileManager
                   - bot.predictions: PredictionManager
                   - bot.config: 設定オブジェクト
        """
        self.bot = bot
        self.shiori_channel_id: int | None = None

    # ========== 公開メソッド ==========

    async def weekly_monologue_loop(self) -> None:
        """週次ループのエントリポイント

        毎日21:00 JSTにループが起動し、日曜日のみ実際に投稿する。
        日曜以外の日は早期リターンする。

        ⚠️ 現在の曜日が MONOLOGUE_DAY でなければスキップ
        ⚠️ 全体をtry/exceptで囲み、例外でbotを止めない（§15）
        """
        now = datetime.now(tz=JST)

        # config から曜日設定を取得（フォールバック: SUNDAY）
        monologue_day = getattr(
            getattr(self.bot, "config", None),
            "MONOLOGUE_DAY",
            self.MONOLOGUE_DAY,
        )

        if now.weekday() != monologue_day:
            return

        try:
            monologue = await self._generate_monologue()
            await self._post_to_shiori_ch(monologue)
            logger.info(
                f"[WeeklyMonologue] Posted at {now.isoformat()}"
            )
        except Exception as e:
            logger.error(
                f"[WeeklyMonologue] Failed: {e}", exc_info=True
            )

    # ========== 内部メソッド ==========

    async def _generate_monologue(self) -> str:
        """独り言を生成する（§8.4.4）

        Returns:
            str — 80〜150字の独り言テキスト

        ⚠️ Sonnetを使用する（Haikuではない）— 品質重視
        ⚠️ 生成失敗時は FALLBACK_MONOLOGUE を返す
        """
        context = await self._gather_weekly_context()

        user_prompt = MONOLOGUE_USER_PROMPT.format(
            active_count=context["active_count"],
            topics="、".join(context["topics"]),
            notable_predictions=context["notable_predictions"],
        )

        try:
            response = await self.bot.llm_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                temperature=0.8,  # 創造性を高めに設定
                system=MONOLOGUE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            monologue = response.content[0].text.strip()

            # メンション除去（§8.5.1）
            monologue = validate_monologue(monologue)

            # 文字数バリデーション
            min_chars = getattr(
                getattr(self.bot, "config", None),
                "MONOLOGUE_MIN_CHARS",
                80,
            )
            max_chars = getattr(
                getattr(self.bot, "config", None),
                "MONOLOGUE_MAX_CHARS",
                150,
            )

            if len(monologue) < (min_chars // 2) or len(monologue) > (max_chars * 2):
                logger.warning(
                    f"[WeeklyMonologue] Length extreme: {len(monologue)} "
                    f"(expected {min_chars}-{max_chars}), using fallback"
                )
                return FALLBACK_MONOLOGUE

            if len(monologue) < min_chars or len(monologue) > max_chars:
                logger.warning(
                    f"[WeeklyMonologue] Length out of range: "
                    f"{len(monologue)} (expected {min_chars}-{max_chars})"
                )

            return monologue

        except Exception as e:
            logger.error(f"[WeeklyMonologue] Generation failed: {e}")
            return FALLBACK_MONOLOGUE

    async def _post_to_shiori_ch(self, content: str) -> None:
        """Shiori_chに独り言を投稿する（§8.2）

        Args:
            content: [必須] 投稿テキスト

        ⚠️ N-05: bot.get_channel() の戻り値がNoneになりうる
        ⚠️ Forbidden例外のハンドリング必須
        """
        if self.shiori_channel_id is None:
            self.shiori_channel_id = await self._find_shiori_channel()

        if self.shiori_channel_id is None:
            logger.error(
                "[WeeklyMonologue] Shiori channel not found, "
                "skipping monologue"
            )
            return

        channel = self.bot.get_channel(self.shiori_channel_id)
        if channel is None:
            logger.error(
                f"[WeeklyMonologue] Channel {self.shiori_channel_id} "
                f"not found in cache"
            )
            return

        try:
            await channel.send(content)
        except Exception as e:
            logger.error(f"[WeeklyMonologue] Post failed: {e}")

    async def _find_shiori_channel(self) -> int | None:
        """Shiori_chのチャンネルIDを検索する

        Returns:
            チャンネルID。見つからない場合はNone。
        """
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                name_lower = channel.name.lower()
                if "shiori" in name_lower or "\u681e" in channel.name:
                    return channel.id
        return None

    async def _gather_weekly_context(self) -> dict:
        """直近1週間のサーバー活動サマリーを収集する（§8.4.3）

        Returns:
            {
                "active_count": int,
                "topics": list[str],
                "notable_predictions": str,
            }

        ⚠️ 収集失敗時はデフォルト値を返す（独り言生成は続行）
        """
        now = datetime.now(tz=JST)
        week_ago = now - timedelta(days=7)

        result = {
            "active_count": 0,
            "topics": ["（活動情報の取得に失敗）"],
            "notable_predictions": "（なし）",
        }

        # Step 1: MAINカテゴリからメッセージ収集
        messages = []
        try:
            channels = self._get_monitored_channels()
            for channel in channels:
                try:
                    async for msg in channel.history(
                        after=week_ago, limit=500
                    ):
                        if not msg.author.bot:
                            messages.append(msg)
                except Exception as e:
                    logger.warning(
                        f"[WeeklyMonologue] Channel scan error "
                        f"in {channel.name}: {e}"
                    )
                    continue
        except Exception as e:
            logger.warning(f"[WeeklyMonologue] Channel list error: {e}")

        # Step 2: アクティブメンバー数
        if messages:
            active_members = set(msg.author.id for msg in messages)
            result["active_count"] = len(active_members)

        # Step 3: 話題抽出（Haikuで軽量処理）
        try:
            if messages:
                result["topics"] = await self._extract_topics_with_haiku(
                    messages
                )
        except Exception as e:
            logger.warning(f"[WeeklyMonologue] Topic extraction failed: {e}")

        # Step 4: 注目予測
        try:
            predictions_text = await self._get_recent_predictions(week_ago)
            if predictions_text:
                result["notable_predictions"] = predictions_text
        except Exception as e:
            logger.warning(f"[WeeklyMonologue] Prediction fetch failed: {e}")

        return result

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

    async def _extract_topics_with_haiku(self, messages: list) -> list[str]:
        """Haikuを使ってメッセージ群から主要話題を抽出する

        Args:
            messages: 直近1週間のメッセージリスト

        Returns:
            話題キーワードのリスト（最大5個）
        """
        if not messages:
            return ["（発言なし）"]

        sample = messages[-50:]
        text_sample = "\n".join(
            f"{msg.author.display_name}: {msg.content[:100]}"
            for msg in sample
            if msg.content
        )

        if not text_sample:
            return ["（テキスト発言なし）"]

        try:
            response = await self.bot.llm_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": (
                        "以下のDiscordチャット発言から主要な話題キーワードを"
                        "最大5個、カンマ区切りで列挙してください。"
                        "キーワードのみを出力してください。\n\n"
                        f"{text_sample}"
                    ),
                }],
            )
            raw = response.content[0].text.strip()
            topics = [t.strip() for t in raw.split("\u3001") if t.strip()]
            if not topics:
                topics = [t.strip() for t in raw.split(",") if t.strip()]
            return topics[:5] if topics else ["（抽出失敗）"]

        except Exception as e:
            logger.warning(
                f"[WeeklyMonologue] Haiku topic extraction failed: {e}"
            )
            return ["（抽出失敗）"]

    async def _get_recent_predictions(self, since: datetime) -> str:
        """直近の予測投稿から注目予測をテキストで返す

        Args:
            since: この日時以降の予測を対象とする

        Returns:
            注目予測のテキスト要約。なければ空文字列。
        """
        try:
            all_predictions = self.bot.predictions.get_all_active()

            recent = []
            for pred in all_predictions:
                recorded = pred.get("recorded_at", "")
                if recorded and recorded >= since.isoformat():
                    recent.append(pred)

            if not recent:
                return ""

            summaries = []
            for p in recent[:3]:
                author = p.get("author_display_name", "不明")
                content = p.get("content", "")[:80]
                summaries.append(f"{author}: {content}")

            return " / ".join(summaries)

        except Exception as e:
            logger.warning(
                f"[WeeklyMonologue] Prediction summary error: {e}"
            )
            return ""
