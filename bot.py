"""bot.py — 栞（Shiori）メインDiscordボット

Discordイベント処理の統合ハンドラ。
on_ready(), on_message(), on_member_remove() を実装する。

COMMON_MISTAKES §13: llm.py は AsyncAnthropic（非同期クライアント）を使用。
COMMON_MISTAKES §10: NudgeManager(llm, member_profile) — 2引数必須。
COMMON_MISTAKES §15: build_nudge_hint() は4引数。

依存: 全モジュール
参照: interface_contract.md §2.1, event_flow.md 全体
"""

import os
import re
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import tasks

from llm import LLMClient
from trust import TrustManager
from predictions import PredictionLedger
from nudge import NudgeManager
from summarizer import LinkSummarizer
from passive_monitor import PassiveMonitor
from channel_config import ChannelConfig
from rate_limiter import RateLimiter
from member_profile import MemberProfileManager
from reactions import ReactionManager
from errors import format_error_message

logger = logging.getLogger("shiori.bot")

JST = timezone(timedelta(hours=9))

# URL抽出用正規表現
URL_PATTERN = re.compile(r'https?://[^\s<>\"\']+')

# 要約リクエストキーワード
SUMMARY_KEYWORDS = ["まとめて", "要約して", "議論をまとめて", "整理して"]
LINK_SUMMARY_KEYWORDS = ["要約", "何これ", "読んで", "これ何"]

# T6 プレモーテム
T6_SYSTEM_PROMPT = (
    "あなたは栞（Shiori）の思考補助です。\n"
    "楽観的な未来予測に対し、記録の網羅性のためにリスク要因を聞く質問を生成します。\n"
    "敵対的にならず、好奇心ベースの質問にしてください。\n"
    "JSONのみを出力してください。"
)

T6_USER_TEMPLATE = """以下の予測に対して、「事前リスク検証（プレモーテム）」の質問を1つ生成してください。

予測内容: {prediction_text}
投稿者: {author_display_name}
カテゴリ: {category}

ルール:
1. 栞のキャラクターで質問する（19歳の大学生、記録係）
2. 「フィールドノートのリスク要因欄を埋めたい」という動機
3. 攻撃的でなく、純粋な好奇心として聞く
4. 40字以内の1文

以下のJSON形式で回答してください:
{{"premortem_question": "質問文", "risk_angle": "技術的障壁|規制|コスト|社会受容|その他"}}"""

# T7 議論要約
T7_SYSTEM_PROMPT = (
    "あなたは議論要約アシスタントです。\n"
    "Discord上の議論を公平に整理し、各メンバーの立場を正確に要約します。\n"
    "特定の立場に偏らず、中立的にまとめてください。\n"
    "JSONのみを出力してください。"
)

T7_USER_TEMPLATE = """以下のDiscord議論を要約してください。

議論メッセージ（時系列順）:
{formatted_messages}

ルール:
1. 論題を1文で要約
2. 各発言者の立場を「〇〇説:」形式で整理（主要発言者のみ、最大5名）
3. 未決着の論点を列挙
4. 合計150〜300字以内

以下のJSON形式で回答してください:
{{"topic": "論題", "positions": [{{"member": "表示名", "position": "立場の要約"}}], "unresolved": ["未決着の論点1", "未決着の論点2"]}}"""


class ShioriBot(discord.Client):
    """栞（Shiori）メインBotクラス。

    discord.Client を継承。
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)

        # 1. 依存なしモジュール
        self.channel_config = ChannelConfig()
        self.rate_limiter = RateLimiter(cooldown_seconds=30)
        self.member_profile = MemberProfileManager()
        self.trust = TrustManager()
        self.reactions = ReactionManager()

        # 2. LLMクライアント（AsyncAnthropic）
        self.llm = LLMClient()

        # 3. LLMに依存するモジュール
        self.predictions = PredictionLedger(llm=self.llm)
        self.nudge = NudgeManager(llm=self.llm, member_profile=self.member_profile)
        self.summarizer = LinkSummarizer(llm=self.llm)
        self.passive_monitor = PassiveMonitor(
            llm=self.llm,
            predictions=self.predictions,
            channel_config=self.channel_config,
        )

    # ─── Discordイベントハンドラ ────────────────────────────

    async def on_ready(self) -> None:
        """Bot起動時処理。データファイルロード＋直近100件取得（Q24: B案）"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

        # 1. データファイルのロード（依存順）
        await self.member_profile.load()
        await self.trust.load()
        await self.predictions.load()
        # categories.md は predictions.load() 内部でロード済み

        # 2. データ整合性検証
        errors = await self.validate_data_integrity()
        if errors:
            for err in errors:
                logger.warning(f"Data integrity issue: {err}")

        # 3. 起動時メッセージ取得
        await self._startup_fetch()

        # 4. 定期タスク開始
        self._start_background_tasks()

        member_count = len(self.member_profile.profiles)
        prediction_count = len(self.predictions.predictions)
        logger.info(
            f"Shiori bot ready. "
            f"Loaded {member_count} members, {prediction_count} predictions."
        )

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信時の統合ハンドラ。"""
        # GATE 1: Bot自身のメッセージ
        if message.author.id == self.user.id:
            return

        # GATE 2: DM
        if self.channel_config.is_dm(message):
            await message.channel.send(
                "あ、DMですね……すみません、わたしはサーバーの"
                "フィールドワーク中なので、#未来予測を投稿するch "
                "で話しかけてもらえると嬉しいです📎"
            )
            return

        # GATE 3: メンション or 返信
        is_mention = (
            self.user.mentioned_in(message)
            and not message.mention_everyone
        )
        is_reply = (
            message.reference is not None
            and message.reference.resolved is not None
            and hasattr(message.reference.resolved, "author")
            and message.reference.resolved.author.id == self.user.id
        )

        if is_mention or is_reply:
            # GATE 4: レート制限チェック
            if not self.rate_limiter.can_respond(message.channel.id):
                logger.debug(f"Rate limited in channel {message.channel.id}")
                return
            await self._handle_mention(message, is_reply=is_reply)
        else:
            await self._handle_passive(message)

    async def on_member_remove(self, member: discord.Member) -> None:
        """メンバー離脱時の匿名化処理（Q26: B案）"""
        anon_name = await self.trust.anonymize_member(member.id)
        logger.info(f"Member {member.id} left. Anonymized as {anon_name}.")

    # ─── 内部処理 ─────────────────────────────────────────

    async def _handle_mention(
        self,
        message: discord.Message,
        is_reply: bool = False,
    ) -> None:
        """メンション/返信トリガー時の応答フロー。"""
        user_id = message.author.id
        display_name = message.author.display_name

        # STEP 1: 信頼度記録
        await self.trust.record_interaction(user_id, "mention")

        # STEP 2: チャンネル設定取得
        overrides = self.channel_config.get_overrides(message.channel.name)

        # STEP 3: 対話相手のプロファイル取得
        profile = self.member_profile.get_profile(user_id=user_id)

        # STEP 4: 会話コンテキスト収集（直前20件）
        context_messages = await self._collect_context(message.channel)

        # 追加コンテキスト用の辞書
        extra_context = {}

        # STEP 4.5: 特殊リクエスト判定
        content_lower = message.content.lower()

        # 議論要約リクエスト？
        is_summary_request = any(kw in content_lower for kw in SUMMARY_KEYWORDS)

        # リンク要約リクエスト？
        urls = URL_PATTERN.findall(message.content)
        is_link_request = bool(urls) and any(
            kw in content_lower for kw in LINK_SUMMARY_KEYWORDS
        )

        # ─── リンク要約フロー（T5）
        if is_link_request and urls:
            result = await self.summarizer.summarize_url(
                url=urls[0],
                related_keywords=self._extract_prediction_keywords(),
            )
            if result:
                summary_text = self.summarizer.format_summary(result)
                await message.channel.send(summary_text)
            else:
                error_msg = format_error_message("link_fetch_failed")
                await message.channel.send(error_msg)
            self.rate_limiter.record_response(message.channel.id)
            return

        # ─── 議論要約フロー（T7）
        if is_summary_request:
            formatted_messages = "\n".join(
                f"{m['author_display_name']}: {m['content']}"
                for m in context_messages
            )
            t7_result = await self.llm.call_template(
                template_name="T7",
                system=T7_SYSTEM_PROMPT,
                user=T7_USER_TEMPLATE.format(
                    formatted_messages=formatted_messages
                ),
                max_tokens=500,
                temperature=0.5,
            )
            if t7_result:
                summary_text = self.llm.format_discussion_summary(t7_result)
                await message.channel.send(summary_text)
                await self.reactions.add_reaction(message, "discussion")
                await self.trust.record_interaction(user_id, "summary_request")
            else:
                error_msg = format_error_message("unknown")
                await message.channel.send(error_msg)
            self.rate_limiter.record_response(message.channel.id)
            return

        # ─── コミュニティ知識の追加コンテキスト
        community_knowledge = self.member_profile.get_community_knowledge_text(
            compact=True
        )
        # デバッグログ
        logger.info(f"Community knowledge length: {len(community_knowledge) if community_knowledge else 0}")
        if community_knowledge:
            preview = community_knowledge[:500].replace('\n', ' ')
            logger.info(f"Community knowledge preview: {preview}...")
            extra_context["community_knowledge"] = community_knowledge

        # ─── STEP 5: 予測検出（T1）
        msg_dict = {
            "user_id": user_id,
            "display_name": display_name,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "channel": message.channel.name,
            "channel_category_id": getattr(
                message.channel.category, "id", None
            ),
        }
        t1_result = await self.passive_monitor.check_message(msg_dict)

        prediction_context = None
        premortem_hint = None

        # STEP 6: 予測記録（T2 + T3 + T4）
        if (
            t1_result
            and t1_result.get("is_prediction")
            and t1_result.get("confidence", 0) >= 0.6
        ):
            prediction_record = await self.predictions.record_prediction(
                message=msg_dict,
                prediction_text=t1_result["prediction_text"],
                detection_method="reply" if is_reply else "mention",
            )
            if prediction_record:
                await self.trust.record_interaction(user_id, "prediction")
                prediction_context = prediction_record

                # STEP 7: プレモーテム生成（T6）
                if not overrides or overrides.get("premortem", True):
                    premortem = await self.llm.call_template(
                        template_name="T6",
                        system=T6_SYSTEM_PROMPT,
                        user=T6_USER_TEMPLATE.format(
                            prediction_text=t1_result["prediction_text"],
                            author_display_name=display_name,
                            category=prediction_record.get("category", ""),
                        ),
                        max_tokens=150,
                        temperature=0.7,
                    )
                    if premortem:
                        premortem_hint = premortem

        # STEP 8: ナッジ候補選定（T8）
        nudge_hint = None
        if not overrides or overrides.get("nudge", True):
            target = await self.nudge.select_nudge_target(
                current_topic=message.content
            )
            if target:
                nudge_hint = await self.nudge.build_nudge_hint(
                    current_topic=message.content,
                    target_display_name=target["member"]["display_name"],
                    past_relevant_message=target["past_message"],
                    last_active_date=target["member"].get("last_active", ""),
                )

        # STEP 9: システムプロンプト構築
        trust_level = self.trust.get_trust_level(user_id)
        
        # メンバーに関する質問かどうか判定し、該当メンバー情報を抽出
        member_query_info = self._extract_member_query_info(message.content)
        if member_query_info:
            logger.info(f"Member query detected: {member_query_info}")
        
        system_prompt = self.llm.build_system_prompt(
            trust_level=trust_level,
            member_profile=profile,
            channel_overrides=overrides,
            community_knowledge=community_knowledge,
            member_query_info=member_query_info,  # 追加
        )
        
        # デバッグ: システムプロンプトに橋が含まれているか確認
        if "橋" in system_prompt:
            logger.info("System prompt contains 橋 ✓")
        else:
            logger.warning("System prompt does NOT contain 橋 ✗")
        logger.info(f"System prompt length: {len(system_prompt)}")
        
        # デバッグ: §11の新しい説明が含まれているか確認
        if "メンバーについて質問されたら" in system_prompt:
            logger.info("System prompt has new §11 instructions ✓")
        else:
            logger.warning("System prompt is MISSING new §11 instructions ✗")

        # 動的コンテキスト注入
        if prediction_context:
            system_prompt += (
                f"\n\n[今回検出した予測]\n"
                f"予測番号: {prediction_context.get('id', '')}\n"
                f"内容: {prediction_context.get('content', '')}\n"
                f"カテゴリ: {prediction_context.get('category', '')}\n"
                f"時間軸: {prediction_context.get('timeline', '')}\n"
            )
        if premortem_hint:
            system_prompt += (
                f"\n\n[プレモーテムヒント]\n"
                f"質問案: {premortem_hint.get('premortem_question', '')}\n"
                f"リスク観点: {premortem_hint.get('risk_angle', '')}\n"
                f"→ 応答に自然に組み込んでください"
            )
        if nudge_hint:
            system_prompt += (
                f"\n\n[ナッジヒント]\n"
                f"言及文: {nudge_hint.get('nudge_text', '')}\n"
                f"→ 応答の末尾あたりにさりげなく織り込んでください"
            )

        # STEP 10: コンテキスト変換
        api_messages = self.llm.convert_context_to_api_format(
            context_messages=context_messages,
            bot_user_id=self.user.id,
        )

        # STEP 11: メイン応答生成
        response_text = await self.llm.generate_response(
            system_prompt=system_prompt,
            messages=api_messages,
            max_tokens=500,
            temperature=0.7,
        )

        # STEP 12: 応答送信
        await message.channel.send(response_text)

        # STEP 13: リアクション付与
        if prediction_context:
            await self.reactions.add_reaction(message, "prediction")
        if premortem_hint:
            await self.reactions.add_reaction(message, "premortem")
        if trust_level >= 4:
            await self.reactions.add_reaction(message, "high_trust")

        # STEP 14: レート制限記録
        self.rate_limiter.record_response(message.channel.id)

    async def _handle_passive(self, message: discord.Message) -> None:
        """受動監視フロー。応答は生成しない。"""
        # GATE: MAIN CHANNELカテゴリか？
        category_id = getattr(message.channel.category, "id", None)
        if not self.channel_config.is_main_channel_category(category_id):
            return

        msg_dict = {
            "user_id": message.author.id,
            "display_name": message.author.display_name,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "channel": message.channel.name,
            "channel_category_id": category_id,
        }

        # T1 予測検出
        t1_result = await self.passive_monitor.check_message(msg_dict)

        # 予測記録
        if (
            t1_result
            and t1_result.get("is_prediction")
            and t1_result.get("confidence", 0) >= 0.6
        ):
            await self.passive_monitor.process_prediction(msg_dict, t1_result)

    async def _startup_fetch(self) -> None:
        """起動時の直近100件メッセージ取得と予測スキャン（Q24: B案）"""
        main_cat_id = self.channel_config.main_channel_category_id
        if not main_cat_id:
            logger.warning("MAIN_CHANNEL_CATEGORY_ID not set, skipping startup fetch")
            return

        for guild in self.guilds:
            for channel in guild.text_channels:
                if not hasattr(channel, "category") or channel.category is None:
                    continue
                if channel.category.id != main_cat_id:
                    continue

                logger.info(f"Startup fetch: #{channel.name}")
                try:
                    async for msg in channel.history(limit=100):
                        if msg.author.id == self.user.id:
                            continue

                        msg_dict = {
                            "user_id": msg.author.id,
                            "display_name": msg.author.display_name,
                            "content": msg.content,
                            "timestamp": msg.created_at.isoformat(),
                            "channel": channel.name,
                            "channel_category_id": main_cat_id,
                        }

                        t1_result = await self.passive_monitor.check_message(
                            msg_dict
                        )
                        if (
                            t1_result
                            and t1_result.get("is_prediction")
                            and t1_result.get("confidence", 0) >= 0.6
                        ):
                            await self.passive_monitor.process_prediction(
                                msg_dict, t1_result
                            )

                        # レート制限考慮: 0.5秒間隔
                        await asyncio.sleep(0.5)

                except discord.Forbidden:
                    logger.warning(f"No permission to read #{channel.name}")
                except discord.HTTPException as e:
                    logger.warning(f"Failed to fetch #{channel.name}: {e}")

    async def validate_data_integrity(self) -> list[str]:
        """起動時のデータファイル間整合性検証。"""
        from pathlib import Path

        errors_list: list[str] = []

        # 必須ファイル存在確認
        required_files = [
            "data/members.md",
            "data/predictions.md",
            "data/categories.md",
        ]
        for filepath in required_files:
            if not Path(filepath).exists():
                errors_list.append(f"Missing required file: {filepath}")

        # judgments.md が存在しないことを確認（v4.1: Q27凍結）
        if Path("data/judgments.md").exists():
            errors_list.append(
                "data/judgments.md exists but Q27 is frozen in v4.1"
            )

        # predictions.md のカテゴリ ⊆ categories.md を検証
        existing_cats = self.predictions.categories.get_existing_categories_list()
        for pred in self.predictions.predictions:
            cat = pred.get("category", "")
            if cat and cat not in existing_cats and cat != "未分類 / その他":
                errors_list.append(
                    f"Prediction {pred.get('id', '?')}: "
                    f"category '{cat}' not in categories.md"
                )

        return errors_list

    # ─── ヘルパーメソッド ──────────────────────────────────

    async def _collect_context(
        self,
        channel: discord.TextChannel,
        limit: int = 20,
    ) -> list[dict]:
        """チャンネルから直前N件のメッセージを内部形式で収集する。"""
        context = []
        try:
            async for msg in channel.history(limit=limit):
                context.append({
                    "author_id": msg.author.id,
                    "author_display_name": msg.author.display_name,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "is_bot": msg.author.bot,
                })
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(f"Failed to collect context: {e}")

        # 時系列順にソート（history は新→旧なので逆転）
        context.reverse()
        return context

    def _extract_prediction_keywords(self) -> list[str]:
        """予測台帳から関連キーワードを抽出する。"""
        keywords = set()
        for pred in self.predictions.predictions[-20:]:
            cat = pred.get("category", "")
            if cat:
                keywords.add(cat)
        return list(keywords)[:10]

    def _extract_member_query_info(self, content: str) -> str | None:
        """メンバーに関する質問から該当メンバー情報を抽出する。
        
        Args:
            content: ユーザーのメッセージ
            
        Returns:
            str | None: 該当メンバーの情報テキスト、または None
        """
        import re
        
        # @Shiori等のメンションを除去
        content_clean = re.sub(r"@\S+\s*", "", content).strip()
        
        # メンバー質問パターン
        patterns = [
            r"(.+?)さん(?:って|は|の|について)",  # 〇〇さんって/は/の/について
            r"(.+?)(?:って|は)(?:どんな人|誰|だれ)",  # 〇〇ってどんな人
            r"(.+?)(?:の情報|について教えて|知ってる)",  # 〇〇の情報
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content_clean)
            if match:
                query_name = match.group(1).strip()
                
                # メンバー検索
                results = self.member_profile.search_member(query_name)
                if results:
                    # 最初のマッチを返す
                    member = results[0]
                    info_lines = [f"【質問されているメンバー: {member.get('display_name', query_name)}】"]
                    
                    if member.get("tier"):
                        info_lines.append(f"Tier: {member['tier']}")
                    if member.get("ポジション"):
                        info_lines.append(f"役割: {member['ポジション']}")
                    if member.get("関心領域"):
                        info_lines.append(f"関心領域: {member['関心領域']}")
                    if member.get("思想的特徴"):
                        info_lines.append(f"思想的特徴: {member['思想的特徴']}")
                    if member.get("発言スタイル"):
                        info_lines.append(f"発言スタイル: {member['発言スタイル']}")
                    
                    info = "\n".join(info_lines)
                    logger.info(f"Found member info for '{query_name}': {info[:100]}...")
                    return info
                else:
                    logger.info(f"No member found for query: '{query_name}'")
        
        return None

    # ─── バックグラウンドタスク ────────────────────────────

    def _start_background_tasks(self) -> None:
        """定期タスクを開始する。"""
        self._check_trust_decay.start()
        self._auto_save.start()

    @tasks.loop(hours=24)
    async def _check_trust_decay(self) -> None:
        """毎日1回、30日以上非活動のメンバーに減衰を適用する。"""
        now = datetime.now(JST)
        for user_id in list(self.trust.members.keys()):
            member_data = self.trust.members.get(user_id, {})
            last_active_str = member_data.get("last_active", "")
            if not last_active_str:
                continue
            try:
                last_active = datetime.fromisoformat(last_active_str)
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=JST)
                days_inactive = (now - last_active).days
                if days_inactive >= 30 and days_inactive % 30 == 0:
                    await self.trust.apply_decay(user_id)
            except (ValueError, TypeError):
                continue

    @tasks.loop(minutes=30)
    async def _auto_save(self) -> None:
        """30分ごとにデータファイルを書き出す。"""
        await self.trust.save()
        await self.predictions.save()
        logger.debug("Auto-save completed")


def main():
    """エントリポイント。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set")
        return

    bot = ShioriBot()
    bot.run(token)


if __name__ == "__main__":
    main()
