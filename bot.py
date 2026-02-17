"""bot.py — 栞（Shiori）統合版 v4.1 + v5.2

Discordイベント処理の統合ハンドラ。
v4.1: T1-T8パイプライン、予測記録、ナッジ、リンク要約、議論要約
v5.2: CFR、ハートリアクション、動的学習、Haiku最適化

COMMON_MISTAKES §13: llm.py は AsyncAnthropic（非同期クライアント）を使用。
COMMON_MISTAKES §10: NudgeManager(llm, member_profile) — 2引数必須。
COMMON_MISTAKES §15: 全参照メソッドが実装済みであること。
COMMON_MISTAKES §17: 変数スコープの検証済み。

v5.2 Anti-patterns:
F-01: CFRTracker.is_active() で期限/回数/発動済みを一括チェック
F-02: mark_cfr_triggered() は送信直後に呼ぶ
F-03: CFR応答では register_response() しない（直接応答のみ）
F-12: ハートリアクションは asyncio.create_task で応答と独立
F-13: remaining_checks は Haiku分析前に同期デクリメント
F-14: クールダウンは CFR のみ、メンション/返信には影響しない

v5.2-fix1: _handle_passive 例外が _handle_cfr をブロックしないよう分離
v5.2-fix1: CFR登録ログを DEBUG→INFO に昇格（Railway診断用）

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

# ── 既存モジュール（v4.1） ──
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

# ── v5.2 新モジュール ──
import config as shiori_config
from cfr import CFRAnalyzer, CFRTracker
from haiku_context import HaikuContextManager
from haiku_prompts import parse_with_default
from learning_detector import LearningDetector
from member_query import MemberQueryDetector
from reaction_handler import ReactionHandler
from response_generator import ResponseConfig, ResponseGenerator

# Phase 4/6: 昇格検出・予測ハイライト
from trust_level_up import TrustLevelUpDetector, LEVEL_UP_HINT_PROMPTS, get_heart_emoji
from prediction_highlighter import PredictionHighlighter

# Phase P1: v5.3 新モジュール統合
from response_mode import determine_response_mode, has_prediction_content, _silent_record_prediction
from discussion_summary import detect_summary_request as detect_member_summary, handle_member_summary
from daily_maintenance import DailyMaintenanceTask
from weekly_monologue import WeeklyMonologueTask


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

    discord.Client を継承。v4.1 + v5.2 統合。
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)

        # ═══ v4.1 既存モジュール ═══

        # 1. 依存なしモジュール
        self.channel_config = ChannelConfig()
        self.rate_limiter = RateLimiter(cooldown_seconds=5)
        self.member_profile = MemberProfileManager()
        self.trust = TrustManager()
        self.reactions = ReactionManager()

        # 2. LLMクライアント（AsyncAnthropic）
        #    v5.2: call_haiku() / call_sonnet() メソッドが追加済みであること
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

        # ═══ v5.2 新モジュール ═══

        # CFR（Contextual Follow-up Response）
        self.cfr_tracker = CFRTracker()
        self.cfr_analyzer = CFRAnalyzer(self.llm)

        # ハートリアクション（既存 self.reactions とは独立）
        self.heart_reactions = ReactionHandler()

        # 動的学習
        self.learning_detector = LearningDetector(self.llm)

        # メンバー質問検出
        self.member_query_detector = MemberQueryDetector()

        # 応答生成（CFR応答で使用）
        self.response_generator = ResponseGenerator(self.llm)

        # Haikuコンテキスト管理
        self.haiku_ctx = HaikuContextManager()

        # ═══ v5.3 Phase 4/6: 昇格検出・予測ハイライト ═══
        self.level_up_detector = TrustLevelUpDetector()
        self.prediction_highlighter = PredictionHighlighter()
        self.level_up_pending: dict[str, dict] = {}

        # ═══ P1: v5.3 定期タスク（§5, §8） ═══
        self.daily_maintenance_task = DailyMaintenanceTask(self)
        self.weekly_monologue_task = WeeklyMonologueTask(self)

    # ─── Discordイベントハンドラ ────────────────────────────

    async def on_ready(self) -> None:
        """Bot起動時処理。データファイルロード＋直近100件取得（Q24: B案）"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

        # v5.2: BOT_USER_IDをconfig.pyに設定
        shiori_config.BOT_USER_ID = self.user.id

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
            f"Shiori bot ready (v4.1+v5.2+v5.3-P0P1-hotfix). "
            f"Loaded {member_count} members, {prediction_count} predictions. "
            f"CFR={'ON' if shiori_config.CFR_ENABLED else 'OFF'}"
        )

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

        # ── v5.2 F-12: ハートリアクション（応答とは独立して実行） ──
        # v5.3 §1: is_mention も渡す（should_heart_react 3引数化対応）
        asyncio.create_task(
            self._handle_heart_reaction(message, is_reply, is_mention)
        )

        # ── v5.2: 動的学習（バックグラウンド） ──
        asyncio.create_task(self._handle_learning(message))

        if is_mention or is_reply:
            # GATE 4: レート制限チェック
            # F-14: レート制限はメンション/返信にのみ適用（CFRには別のクールダウン）
            if not self.rate_limiter.can_respond(message.channel.id):
                logger.debug(f"Rate limited in channel {message.channel.id}")
                return
            await self._handle_mention(message, is_reply=is_reply)
        else:
            # ── v5.2-fix1: _handle_passive の例外が _handle_cfr をブロックしないよう分離 ──
            try:
                await self._handle_passive(message)
            except Exception as e:
                logger.warning(f"Passive monitor failed (non-fatal): {e}")

            # v5.2: CFR処理（F-14: CFR専用クールダウン、レート制限とは別）
            if shiori_config.CFR_ENABLED:
                try:
                    await self._handle_cfr(message)
                except Exception as e:
                    logger.warning(f"CFR handling failed (non-fatal): {e}")

    async def on_member_remove(self, member: discord.Member) -> None:
        """メンバー離脱時の匿名化処理（Q26: B案）"""
        anon_name = await self.trust.anonymize_member(member.id)
        logger.info(f"Member {member.id} left. Anonymized as {anon_name}.")

    # ═══════════════════════════════════════════════════
    #  メンション/返信トリガー時の応答フロー（v4.1 既存 + v5.2 拡張）
    # ═══════════════════════════════════════════════════

    async def _handle_mention(
        self,
        message: discord.Message,
        is_reply: bool = False,
    ) -> None:
        """メンション/返信トリガー時の応答フロー。"""
        user_id = message.author.id
        display_name = message.author.display_name

        # STEP 1: 信頼度記録
        interaction_result = await self.trust.record_interaction(user_id, "mention")

        # Phase 4/6: 昇格チェック（N-05: 例外隔離）
        try:
            self.on_trust_score_change(
                str(user_id),
                interaction_result["old_score"],
                interaction_result["new_score"],
            )
        except Exception as e:
            logger.error(f"[LevelUp] on_trust_score_change failed: {e}")

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

        # P1-5: v5.3 §7 メンバー指定要約の検出（legacy T7より先にチェック）
        # メンション部分を除去してから判定
        clean_content = re.sub(r'<@!?\d+>', '', message.content).strip()
        member_summary_req = detect_member_summary(clean_content)

        # 議論要約リクエスト？（legacy: 一般要約キーワード検出）
        is_summary_request = (
            (member_summary_req is not None)
            or any(kw in content_lower for kw in SUMMARY_KEYWORDS)
        )

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

        # ─── 議論要約フロー（v5.3 §7 + legacy T7）
        if is_summary_request:
            # P1-5: メンバー指定要約が検出された場合は §7 フローを優先
            if member_summary_req and member_summary_req.get("type") == "member":
                try:
                    summary_text = await handle_member_summary(
                        message=message,
                        summary_request=member_summary_req,
                        guild_members=message.guild.members if message.guild else None,
                        profile_data=self.member_profile.profiles,
                    )
                    await message.channel.send(summary_text)
                    await self.reactions.add_reaction(message, "discussion")
                    sum_result = await self.trust.record_interaction(user_id, "summary_request")
                    try:
                        self.on_trust_score_change(
                            str(user_id), sum_result["old_score"], sum_result["new_score"],
                        )
                    except Exception as e:
                        logger.error(f"[LevelUp] on_trust_score_change failed: {e}")
                except Exception as e:
                    logger.error(f"[MemberSummary] Failed: {e}")
                    error_msg = format_error_message("unknown")
                    await message.channel.send(error_msg)
                self.rate_limiter.record_response(message.channel.id)
                return

            # legacy T7: 一般要約フロー
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
                sum_result = await self.trust.record_interaction(user_id, "summary_request")
                try:
                    self.on_trust_score_change(
                        str(user_id), sum_result["old_score"], sum_result["new_score"],
                    )
                except Exception as e:
                    logger.error(f"[LevelUp] on_trust_score_change failed: {e}")
            else:
                error_msg = format_error_message("unknown")
                await message.channel.send(error_msg)
            self.rate_limiter.record_response(message.channel.id)
            return

        # ─── コミュニティ知識の追加コンテキスト
        community_knowledge = self.member_profile.get_community_knowledge_text(
            compact=True
        )
        if community_knowledge:
            extra_context["community_knowledge"] = community_knowledge

        # ─── P1-4: v5.3 §3 応答モード判定 ───
        # メンション部分を除去してからモード判定
        clean_for_mode = re.sub(r'<@!?\d+>', '', message.content).strip()
        response_mode = determine_response_mode(clean_for_mode)
        logger.info(f"[ResponseMode] user={display_name}, mode={response_mode}")

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
                pred_result = await self.trust.record_interaction(user_id, "prediction")
                try:
                    self.on_trust_score_change(
                        str(user_id), pred_result["old_score"], pred_result["new_score"],
                    )
                except Exception as e:
                    logger.error(f"[LevelUp] on_trust_score_change failed: {e}")
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

        # §6.6 コミュニティ知識応答のため、全メンバー情報を取得
        community_knowledge_text = self.member_profile.get_community_knowledge_text(
            compact=False  # 全情報を含める
        )

        # STEP 9.5: メンバー質問の検出とハイライト
        # ユーザーのメッセージからメンバー名を抽出し、該当プロファイルをハイライト
        queried_member_highlight = self._extract_and_highlight_queried_member(
            message.content, community_knowledge_text
        )

        # DEBUG: ハイライトされたメンバー情報をログ出力
        if queried_member_highlight:
            logger.info(f"[DEBUG] Queried member highlight: {queried_member_highlight[:100]}...")

        system_prompt = self.llm.build_system_prompt(
            trust_level=trust_level,
            member_profile=profile,
            channel_overrides=overrides,
            community_knowledge_text=community_knowledge_text,
        )

        # ハイライトされたメンバー情報をシステムプロンプトの先頭に追加
        if queried_member_highlight:
            system_prompt = queried_member_highlight + "\n\n" + system_prompt

        # DEBUG: システムプロンプトの長さをログ出力
        logger.info(f"[DEBUG] Final system_prompt length: {len(system_prompt)}")

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

        # Phase 4/6: 昇格フラグ消費（§9.4, N-03/N-04）
        # C-01修正: ResponseGeneratorに渡して応答モードに応じた処理を委譲
        level_up_hint_text = None
        level_up_info = self.level_up_pending.pop(str(user_id), None)
        if level_up_info:
            new_level = level_up_info["new_level"]
            heart = level_up_info["new_heart"]
            hint_prompts = LEVEL_UP_HINT_PROMPTS.get(new_level, "")
            level_up_hint_text = (
                f"[昇格通知ヒント]\n"
                f"このメンバーがLv{level_up_info['old_level']}→Lv{new_level}に昇格しました。\n"
                f"ハート色: {heart}\n"
                f"ヒント: {hint_prompts}\n"
                f"→ お祝いの言葉を応答に自然に織り込んでください"
            )
            logger.info(
                f"[LevelUp] Consumed pending for {user_id}: "
                f"Lv{level_up_info['old_level']} -> Lv{new_level}"
            )

        # STEP 10: コンテキスト変換
        api_messages = self.llm.convert_context_to_api_format(
            context_messages=context_messages,
            bot_user_id=self.user.id,
        )

        # STEP 11: メイン応答生成 — ResponseGenerator経由（C-01修正）
        # ResponseGeneratorが応答モード指示(§3.3)、昇格モード保護(§9.5.2)、
        # 後処理(F-07文字数/F-10箇条書き除去)を適用する。
        response_config = ResponseConfig(
            response_type="prediction" if response_mode == "record" else "casual",
            use_sonnet=True,
            trust_level=trust_level,
        )
        response_text = await self.response_generator.generate(
            message=message,
            config=response_config,
            level_up_hint=level_up_hint_text,
            response_mode=response_mode,
            system_prompt=system_prompt,
            api_messages=api_messages,
        )

        # STEP 11.5: 名前プレフィックスの除去
        # LLMが「Shiori: 」「栞: 」などを付けてしまう場合がある
        response_text = re.sub(r'^(Shiori:\s*)+', '', response_text, flags=re.IGNORECASE)
        response_text = re.sub(r'^(栞:\s*)+', '', response_text)
        response_text = response_text.strip()

        # STEP 12: 応答送信
        sent_message = await message.channel.send(response_text)

        # ═══ v5.2: CFRコンテキスト登録 ═══
        # F-03: 直接応答のみ登録。CFR応答では register_response() しない。
        if shiori_config.CFR_ENABLED and response_text:
            try:
                summary = self.haiku_ctx.summarize_shiori_response(response_text)
                self.cfr_tracker.register_response(
                    sent_message.id, message.channel.id, summary
                )
                # v5.2-fix1: DEBUG→INFO に昇格（Railway診断用）
                logger.info(
                    "CFR context registered: channel=%d, msg=%d, summary='%s'",
                    message.channel.id,
                    sent_message.id,
                    summary[:60] if summary else "(empty)",
                )
            except Exception as e:
                logger.warning(f"CFR registration failed: {e}")

        # STEP 13: リアクション付与（既存: 予測/プレモーテム/高信頼度リアクション）
        if prediction_context:
            await self.reactions.add_reaction(message, "prediction")
        if premortem_hint:
            await self.reactions.add_reaction(message, "premortem")
        if trust_level >= 4:
            await self.reactions.add_reaction(message, "high_trust")

        # STEP 14: レート制限記録
        self.rate_limiter.record_response(message.channel.id)

        # P1-4: v5.3 §3 自由モード時の予測サイレント記録
        # 自由モードで応答したが、予測的内容が含まれる場合は内部記録のみ行う
        if response_mode == "free" and has_prediction_content(message.content):
            asyncio.create_task(
                _silent_record_prediction(
                    message,
                    record_callback=self._record_prediction_from_message,
                )
            )

    # ═══════════════════════════════════════════════════
    #  v5.2: CFR（Contextual Follow-up Response）処理
    # ═══════════════════════════════════════════════════

    async def _handle_cfr(self, message: discord.Message) -> None:
        """CFR判定・応答。栞の直前発言へのフォローアップを検出して短く返す。

        F-01: check_followup() 内で is_active() チェック＆同期デクリメント
        F-02: 送信後すぐに mark_cfr_triggered() を呼ぶ
        F-03: CFR応答は新たな CFR コンテキストを生成しない
        F-14: クールダウンは CFR のみに適用
        """
        channel_id = message.channel.id

        # F-14: CFR専用クールダウンチェック
        if self.cfr_tracker.is_channel_on_cooldown(channel_id):
            return

        # F-01 + F-13: check_followup でアクティブ判定＆残回数デクリメント
        context = self.cfr_tracker.check_followup(channel_id)
        if context is None:
            return

        # v5.2-fix1: CFR候補検出をINFOでログ（診断用）
        logger.info(
            "CFR candidate detected: channel=%d, user=%s, content='%s'",
            channel_id,
            message.author.display_name,
            (message.content or "")[:80],
        )

        # CFR関連性判定（Haiku）
        try:
            result = await self.cfr_analyzer.analyze(
                context.shiori_response_summary, message.content or ""
            )
        except Exception as e:
            logger.warning(f"CFR analysis failed: {e}")
            return

        if not result.should_respond:
            logger.info(
                "CFR not triggered: channel=%d, confidence=%.2f",
                channel_id,
                result.confidence,
            )
            return

        # CFR応答生成
        cfr_config = ResponseConfig(
            response_type="cfr",
            max_chars=100,
            allow_question=False,
            question_style="none",
        )
        try:
            cfr_response = await self.response_generator.generate(
                message, cfr_config, context=context.shiori_response_summary
            )
        except Exception as e:
            logger.warning(f"CFR response generation failed: {e}")
            return

        if not cfr_response:
            return

        # F-02: 送信と mark_cfr_triggered をセットで実行
        await message.channel.send(cfr_response)
        self.cfr_tracker.mark_cfr_triggered(channel_id)

        logger.info(
            "CFR triggered: channel=%d, confidence=%.2f, type=%s",
            channel_id,
            result.confidence,
            result.relevance_type,
        )

    # ═══════════════════════════════════════════════════
    #  v5.2: ハートリアクション処理
    # ═══════════════════════════════════════════════════

    async def _handle_heart_reaction(
        self,
        message: discord.Message,
        is_reply_to_shiori: bool,
        is_mention_to_shiori: bool,
    ) -> None:
        """F-12: ハートリアクション判定・付与。応答とは独立して実行される。

        v5.3 §1: should_heart_react 3引数化に対応（is_mention_to_shiori 追加）。
        v5.3 §4: handle_reaction() 統合フロー — 好感度レベル別ハートカラー。
        v5.3 §10: delayed_add_reaction() 20秒遅延（handle_reaction内部で実行）。
        asyncio.create_task() で呼び出されるため、例外を内部で処理する。

        P0-A1 hotfix: add_heart_reaction() → handle_reaction() に修正。
        """
        try:
            # trust_score を取得（§4: ハートカラー判定に必要）
            trust_score = self.trust.get_trust_score(message.author.id)

            # handle_reaction() が should_heart_react + emoji選択 + 遅延付与を一括処理
            await self.heart_reactions.handle_reaction(
                message=message,
                trust_score=trust_score,
                is_reply_to_shiori=is_reply_to_shiori,
                is_mention_to_shiori=is_mention_to_shiori,
            )
        except Exception:
            logger.exception("Heart reaction handling error")

    # ═══════════════════════════════════════════════════
    #  P1-4: 予測サイレント記録ヘルパー
    # ═══════════════════════════════════════════════════

    async def _record_prediction_from_message(
        self, message: discord.Message
    ) -> None:
        """自由モード時の予測サイレント記録コールバック（§3.3）。

        _silent_record_prediction() の record_callback として渡される。
        既存の predictions.record_prediction() に委譲する。
        """
        msg_dict = {
            "user_id": message.author.id,
            "display_name": message.author.display_name,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "channel": message.channel.name,
            "channel_category_id": getattr(
                message.channel.category, "id", None
            ),
        }
        t1_result = await self.passive_monitor.check_message(msg_dict)
        if (
            t1_result
            and t1_result.get("is_prediction")
            and t1_result.get("confidence", 0) >= 0.6
        ):
            await self.predictions.record_prediction(
                message=msg_dict,
                prediction_text=t1_result["prediction_text"],
                detection_method="silent",
            )
            logger.info(
                f"[SilentRecord] Prediction recorded for "
                f"{message.author.display_name} (msg:{message.id})"
            )

    # ═══════════════════════════════════════════════════
    #  v5.2: 動的学習処理
    # ═══════════════════════════════════════════════════

    async def _handle_learning(self, message: discord.Message) -> None:
        """バックグラウンドでの動的学習。メンバーの新情報を自動検出・記録する。

        F-15: LearningDetector内で正規表現プレチェック → Haiku判定の2段階。
        asyncio.create_task() で呼び出されるため、例外を内部で処理する。
        """
        try:
            content = message.content or ""
            if not content or len(content) < 10:
                return

            # 正規表現プレフィルタ → Haiku判定
            result = await self.learning_detector.detect(
                content, message.author.display_name
            )
            if result.has_learnable_info and result.extracted_info:
                user_id = str(message.author.id)
                await self.member_profile.add_dynamic_memo(
                    user_id, result.extracted_info
                )
                logger.info(
                    "Dynamic learning: user=%s, info='%s'",
                    message.author.display_name,
                    result.extracted_info[:50],
                )
        except Exception:
            logger.exception("Learning detection error")

    # ═══════════════════════════════════════════════════
    #  受動監視（v4.1 既存）
    # ═══════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════
    #  起動時処理
    # ═══════════════════════════════════════════════════

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
            "data/members_seed.md",
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

    def _extract_and_highlight_queried_member(
        self,
        message_content: str,
        community_knowledge_text: str,
    ) -> str | None:
        """メッセージからメンバー名を抽出し、該当プロファイルをハイライトする。

        「〇〇さんについて」「〇〇って誰」等のパターンを検出し、
        該当メンバーの情報をシステムプロンプトの先頭に配置するためのテキストを生成。

        Args:
            message_content: ユーザーのメッセージ
            community_knowledge_text: コミュニティ知識テキスト（未使用、互換性のため残す）

        Returns:
            str | None: ハイライトテキスト。該当なしの場合はNone。
        """
        # メンション記法を除去してからパターンマッチ
        clean_content = re.sub(r'<@!?\d+>\s*', '', message_content).strip()
        logger.info(f"[DEBUG] Clean message content: '{clean_content}'")

        # v5.2: MemberQueryDetector を使ったクリーンな検出
        queried_name = self.member_query_detector.detect_queried_member(clean_content)

        if not queried_name:
            logger.info("[DEBUG] No member name pattern detected")
            return None

        logger.info(f"[DEBUG] Detected queried member name: '{queried_name}'")

        # member_profile.py のメソッドを使って検索
        member_summary = self.member_profile.get_member_summary_for_highlight(queried_name)

        if not member_summary:
            logger.info(f"[DEBUG] Member '{queried_name}' not found in profiles")
            return None

        logger.info(f"[DEBUG] Found member summary for '{queried_name}'")

        # ハイライトテキストを生成
        highlight = f"""
================================================================
【質問されたメンバー情報 - 必ずこの情報を使って回答すること】
================================================================

{member_summary}

【応答ルール - 厳守】
✅ 上記の情報を「フィールドノートによると……」として紹介する
✅ 「わたしの印象では……」として紹介してもよい
❌ 「記録が薄い」「把握できていない」は絶対禁止
❌ 「教えていただけますか？」と聞き返すのは絶対禁止

================================================================
"""
        return highlight

    # ─── バックグラウンドタスク ────────────────────────────

    def _start_background_tasks(self) -> None:
        """定期タスクを開始する。"""
        self._check_trust_decay.start()
        self._auto_save.start()
        # v5.2: CFRクリーンアップループ
        if shiori_config.CFR_ENABLED:
            self._cfr_cleanup.start()
        # P1: v5.3 日次メンテナンス（§5）— 毎日18:00 JST
        self._daily_maintenance_loop.start()
        # P1: v5.3 週次モノローグ（§8）— 毎日21:00 JST（日曜のみ投稿）
        self._weekly_monologue_loop.start()

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
        # v5.2: メンバープロファイル（動的メモ含む）の定期保存
        try:
            await self.member_profile.save()
        except Exception:
            logger.exception("member_profile auto-save failed")
        logger.debug("Auto-save completed")

    @tasks.loop(minutes=1)
    async def _cfr_cleanup(self) -> None:
        """v5.2: 期限切れCFRコンテキストの定期クリーンアップ。"""
        self.cfr_tracker.cleanup_expired()

    @_check_trust_decay.before_loop
    async def _before_trust_decay(self) -> None:
        await self.wait_until_ready()

    @_auto_save.before_loop
    async def _before_auto_save(self) -> None:
        await self.wait_until_ready()

    @_cfr_cleanup.before_loop
    async def _before_cfr_cleanup(self) -> None:
        await self.wait_until_ready()

    # ═══ P1: v5.3 日次メンテナンスタスク（§5） ═══

    @tasks.loop(hours=24)
    async def _daily_maintenance_loop(self) -> None:
        """§5: 毎日18:00 JSTに日次メンテナンスを実行する。

        P1 hotfix: DailyMaintenanceTask を起動し、結果を報告する。
        例外は内部で隔離（N-05）。
        """
        try:
            now = datetime.now(JST)
            target_hour = shiori_config.DAILY_MAINTENANCE_HOUR
            if now.hour != target_hour:
                return
            stats = await self.daily_maintenance_task.run_daily_maintenance()
            await self.daily_maintenance_task.post_daily_report(stats)
        except Exception:
            logger.exception("[DailyMaintenance] Loop error (isolated)")

    @_daily_maintenance_loop.before_loop
    async def _before_daily_maintenance(self) -> None:
        await self.wait_until_ready()

    # ═══ P1: v5.3 週次モノローグタスク（§8） ═══

    @tasks.loop(hours=24)
    async def _weekly_monologue_loop(self) -> None:
        """§8: 毎日21:00 JST起動、日曜日のみ投稿。

        P1 hotfix: WeeklyMonologueTask を起動。
        例外は内部で隔離（N-05）。
        """
        try:
            now = datetime.now(JST)
            target_hour = getattr(shiori_config, "MONOLOGUE_HOUR", 21)
            if now.hour != target_hour:
                return
            await self.weekly_monologue_task.weekly_monologue_loop()
        except Exception:
            logger.exception("[WeeklyMonologue] Loop error (isolated)")

    @_weekly_monologue_loop.before_loop
    async def _before_weekly_monologue(self) -> None:
        await self.wait_until_ready()


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
