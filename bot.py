description: "bot.py修正版 - 環境変数エラーメッセージとget_profile_summary()呼び出しを修正"
path: "/mnt/user-data/outputs/bot_fixed.py"
file_text: """
bot.py — Shiori Discord Bot メインモジュール

修正内容:
- 54-56行目: エラーメッセージから「in .env」を削除（Railway対応）
- 211-213行目: get_profile_summary()の引数を修正
  - message.author.id → message.author.name
  - 不要な第2引数（self._member_profiles）を削除
"""

import os
import re
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

import discord

from llm import LLMClient
from trust import TrustManager
from predictions import PredictionLedger
# from passive_monitor import PassiveMonitor  # TODO: Implement PassiveMonitor
from nudge import NudgeManager
from member_profile import load_member_profiles, get_profile_summary
from summarizer import build_summary_prompt, extract_urls, fetch_page

# ──────────────────────────────────────────────
# ログ設定
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("shiori.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("shiori.bot")

# discord.pyの冗長なログを抑制
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("discord.http").setLevel(logging.WARNING)

# ──────────────────────────────────────────────
# 設定
# ──────────────────────────────────────────────

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY is not set")

# レート制限: チャンネルごとに30秒クールダウン
COOLDOWN_SECONDS = 30

# 会話コンテキスト: 直前20件
CONTEXT_MESSAGE_COUNT = 20

# ──────────────────────────────────────────────
# Intents設定
# ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True  # Message Content Intent（受動監視に必須)
intents.guilds = True
intents.members = True


# ──────────────────────────────────────────────
# Bot本体
# ──────────────────────────────────────────────

class ShioriBot(discord.Client):
    """栞（Shiori）Discord Bot"""

    def __init__(self) -> None:
        super().__init__(intents=intents)

        # モジュール初期化
        self.llm = LLMClient(api_key=ANTHROPIC_API_KEY)
        self.trust = TrustManager()
        self.predictions = PredictionLedger()
        self.nudge = NudgeManager()
        # self.monitor = PassiveMonitor()  # TODO: Implement PassiveMonitor

        # レート制限: channel_id -> last_response_timestamp
        self._cooldowns: dict[int, float] = defaultdict(float)

        # 応答キュー: channel_id -> asyncio.Queue
        self._queues: dict[int, asyncio.Queue] = {}

        # メンバープロファイル（起動時にロード）
        self._member_profiles = {}
        
    async def setup_hook(self) -> None:
        """Bot初期化時の非同期処理"""
        # メンバープロファイルのロード
        self._member_profiles = load_member_profiles()
        logger.info(f"Loaded {len(self._member_profiles)} member profiles")

    # ── イベントハンドラ ──

    async def on_ready(self) -> None:
        """Bot起動完了"""
        logger.info("Shiori is online: %s (ID: %s)", self.user, self.user.id)
        # logger.info("Predictions in ledger: %d", self.predictions.count)  # TODO: Implement count property
        logger.info("Connected to %d guilds", len(self.guilds))

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信イベント"""
        # 自分自身・他のbotは無視
        if message.author.bot:
            return

        # 全メッセージで受動監視（活動記録）
        # TODO: Implement PassiveMonitor.record_activity
        # self.monitor.record_activity(
        #     user_id=message.author.id,
        #     username=message.author.name,
        #     channel_id=message.channel.id
        # )
        
        # 活動記録をnudgeにも反映
        self.nudge.update_activity(
            user_id=message.author.name  # NudgeManagerは内部でusernameをキーに使用
        )

        # 応答すべきか判定
        if not self._should_respond(message):
            return

        # レート制限チェック
        if not self._check_cooldown(message.channel.id):
            logger.info("Cooldown active for channel %s", message.channel.id)
            return

        # キューに追加
        await self._enqueue_message(message)

    # ── 内部メソッド ──

    def _should_respond(self, message: discord.Message) -> bool:
        """応答すべきメッセージか判定"""
        # メンションされた場合
        if self.user in message.mentions:
            return True

        # 返信先が自分の場合
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and ref.author == self.user:
                return True

        return False

    def _check_cooldown(self, channel_id: int) -> bool:
        """レート制限チェック（True: OK, False: NG）"""
        now = datetime.now().timestamp()
        last = self._cooldowns.get(channel_id, 0)
        
        if now - last < COOLDOWN_SECONDS:
            return False
        
        self._cooldowns[channel_id] = now
        return True

    async def _enqueue_message(self, message: discord.Message) -> None:
        """メッセージをキューに追加"""
        channel_id = message.channel.id
        
        if channel_id not in self._queues:
            self._queues[channel_id] = asyncio.Queue()
            asyncio.create_task(self._process_queue(channel_id))
        
        await self._queues[channel_id].put(message)

    async def _process_queue(self, channel_id: int) -> None:
        """キューを処理"""
        queue = self._queues[channel_id]
        
        while True:
            message = await queue.get()
            
            try:
                await self._handle_mention(message)
            except Exception as e:
                logger.error("Error handling message: %s", e, exc_info=True)
                try:
                    await message.channel.send(
                        "すみません、エラーが発生しました……🙏\n"
                        f"エラー内容: {type(e).__name__}"
                    )
                except:
                    pass
            finally:
                queue.task_done()

    async def _handle_mention(self, message: discord.Message) -> None:
        """メンション・返信への応答処理"""
        # Typing indicator表示
        async with message.channel.typing():
            # コンテキスト取得
            context = await self._get_context(message)
            
            # プロファイル取得
            profile_summary = get_profile_summary(message.author.name)
            
            # Nudgeヒント取得
            nudge_hint = self.nudge.build_nudge_hint()
            
            # LLM応答生成
            response = await self.llm.generate_response(
                user_message=self._clean_message(message.content),
                context=context,
                trust_level=self.trust.get_level(message.author.id),
                channel_name=message.channel.name,
                profile_context=profile_summary,
                nudge_hint=nudge_hint
            )
            
            # 応答送信
            await message.channel.send(response)
            
            # 信頼度更新
            self.trust.record_interaction(message.author.id, "mention")
            
            # 予測抽出・記録
            # （省略: predictions.extract_and_recordを呼ぶ）

    async def _get_context(self, message: discord.Message) -> list[dict]:
        """会話コンテキストを取得"""
        context = []
        
        try:
            # 直前のメッセージを取得
            async for msg in message.channel.history(limit=CONTEXT_MESSAGE_COUNT + 1):
                if msg.id == message.id:
                    continue
                    
                context.append({
                    "author": msg.author.name,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                })
        except Exception as e:
            logger.warning("Failed to get context: %s", e)
        
        return list(reversed(context))

    def _clean_message(self, content: str) -> str:
        """メンション記法を除去"""
        # <@123456789> 形式を除去
        content = re.sub(r'<@!?\d+>', '', content)
        return content.strip()


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    """エントリーポイント"""
    bot = ShioriBot()
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)

if __name__ == "__main__":
    main()
"""
