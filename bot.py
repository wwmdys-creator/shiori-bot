"""
bot.py - 栞（Shiori）Discord Bot メインエントリーポイント

Discord「シンギュラリティ・サーバー」常駐の記録係Bot
全モジュールを統合し、Discordイベントを処理する

反応条件（Q2決定）:
- @メンション
- 栞への返信
※ 上記以外のメッセージには反応しない
"""

import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 栞モジュール群
from llm import ShioriLLM
from trust import TrustManager, TrustLevel
from predictions import PredictionManager
from categories import CategoryManager
from judgments import JudgmentManager, DueDateChecker, JudgmentResult, format_judgment_response
from summarizer import LinkSummarizer
from passive_monitor import PassiveMonitor
from channel_config import ChannelConfigManager, ChannelType
from rate_limiter import RateLimiter
from profiles import ProfileManager
from errors import (
    ShioriErrorHandler, 
    handle_errors, 
    RateLimitError, 
    ExternalServiceError
)
from reactions import ReactionManager, ReactionType

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('shiori')

# 環境変数読み込み
load_dotenv()

# 設定値
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
MAIN_CHANNEL_CATEGORY_ID = os.getenv('MAIN_CHANNEL_CATEGORY_ID')
RATE_LIMIT_SECONDS = int(os.getenv('RATE_LIMIT_SECONDS', '30'))
CONTEXT_MESSAGE_COUNT = int(os.getenv('CONTEXT_MESSAGE_COUNT', '20'))
STARTUP_MESSAGE_COUNT = int(os.getenv('STARTUP_MESSAGE_COUNT', '100'))


class ShioriBot(commands.Bot):
    """
    栞（Shiori）Discord Bot
    
    Q1: 自発的投稿なし（依頼ベースのみ）
    Q2: メンション + 返信のみに反応
    """
    
    def __init__(self):
        # Discord.py インテント設定
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.reactions = True
        
        super().__init__(
            command_prefix='!',  # 使用しないがcommands.Botに必要
            intents=intents,
            help_command=None
        )
        
        # モジュール初期化
        self.llm = ShioriLLM(api_key=ANTHROPIC_API_KEY)
        self.trust_manager = TrustManager(data_dir="data")
        self.prediction_manager = PredictionManager(data_dir="data")
        self.category_manager = CategoryManager(data_dir="data")
        self.judgment_manager = JudgmentManager(data_dir="data")
        self.summarizer = LinkSummarizer(llm=self.llm)
        self.passive_monitor = PassiveMonitor(
            prediction_manager=self.prediction_manager,
            category_manager=self.category_manager,
            main_category_id=int(MAIN_CHANNEL_CATEGORY_ID) if MAIN_CHANNEL_CATEGORY_ID else None
        )
        self.channel_config = ChannelConfigManager(data_dir="data")
        self.rate_limiter = RateLimiter(default_cooldown=RATE_LIMIT_SECONDS)
        self.profile_manager = ProfileManager(data_dir="data")
        self.error_handler = ShioriErrorHandler()
        self.reaction_manager = ReactionManager(self)
        self.due_checker = DueDateChecker(
            predictions_manager=self.prediction_manager,
            judgment_manager=self.judgment_manager
        )
        
        # 初期化完了フラグ
        self._initialized = False
    
    async def setup_hook(self):
        """Bot起動時の初期化処理"""
        logger.info("📎 栞を初期化中...")
        
        # プロファイルデータの読み込み（Q11: 初日フルロード）
        await self._load_initial_profiles()
        
        logger.info("📎 栞の初期化完了")
    
    async def _load_initial_profiles(self):
        """既存プロファイルの読み込み"""
        # プロジェクトファイルからの初期プロファイル読み込み
        # (実際のデプロイ時にはプロファイルデータを適宜設定)
        pass
    
    async def on_ready(self):
        """Bot接続完了時"""
        logger.info(f"📎 栞がログインしました: {self.user}")
        logger.info(f"   接続サーバー数: {len(self.guilds)}")
        
        # ステータス設定
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="フィールドノート記録中..."
        )
        await self.change_presence(activity=activity)
        
        # Q24: 起動時処理 - 直近メッセージ取得
        if not self._initialized:
            await self._process_startup_messages()
            self._initialized = True
    
    async def _process_startup_messages(self):
        """起動時の直近メッセージ処理（Q24: B案）"""
        logger.info(f"📎 起動時処理: 直近{STARTUP_MESSAGE_COUNT}件のメッセージを取得中...")
        
        for guild in self.guilds:
            for channel in guild.text_channels:
                # MAIN_CHANNELカテゴリのみ処理（Q4）
                if self.passive_monitor.should_monitor_channel(channel):
                    try:
                        async for message in channel.history(limit=STARTUP_MESSAGE_COUNT):
                            if message.author.bot:
                                continue
                            # 受動監視で予測検出
                            await self.passive_monitor.process_message(message)
                    except discord.Forbidden:
                        logger.warning(f"チャンネルアクセス権限なし: {channel.name}")
                    except Exception as e:
                        logger.error(f"起動時処理エラー ({channel.name}): {e}")
        
        logger.info("📎 起動時処理完了")
    
    async def on_message(self, message: discord.Message):
        """メッセージ受信時の処理"""
        # 自分自身のメッセージは無視
        if message.author == self.user:
            return
        
        # Bot のメッセージは無視
        if message.author.bot:
            return
        
        # DM対応（Q19: B案）
        if isinstance(message.channel, discord.DMChannel):
            await self._handle_dm(message)
            return
        
        # 反応すべきかチェック（Q2: メンション + 返信のみ）
        should_respond = self._should_respond(message)
        
        if should_respond:
            # レート制限チェック（Q17）
            if not await self._check_rate_limit(message):
                return
            
            # メンション/返信への応答
            await self._handle_mention(message)
        else:
            # 受動監視（Q3: メンションなしでも内部記録）
            if self.passive_monitor.should_monitor_channel(message.channel):
                await self.passive_monitor.process_message(message)
    
    def _should_respond(self, message: discord.Message) -> bool:
        """
        応答すべきかどうか判定（Q2決定）
        
        トリガー:
        - @メンション
        - 栞への返信
        """
        # メンションされている場合
        if self.user in message.mentions:
            return True
        
        # 栞の投稿への返信の場合
        if message.reference:
            try:
                # 参照メッセージを取得（キャッシュから）
                ref_msg = message.reference.resolved
                if ref_msg and ref_msg.author == self.user:
                    return True
            except:
                pass
        
        return False
    
    async def _check_rate_limit(self, message: discord.Message) -> bool:
        """
        レート制限チェック（Q17: チャンネルごと30秒）
        
        Returns:
            True: 応答可能
            False: レート制限中
        """
        channel_id = message.channel.id
        
        if not self.rate_limiter.can_respond(channel_id):
            remaining = self.rate_limiter.get_remaining_cooldown(channel_id)
            logger.info(f"レート制限中: {message.channel.name} (残り{remaining:.1f}秒)")
            # レート制限中はサイレントに無視（ユーザーには通知しない）
            return False
        
        # クールダウン開始
        self.rate_limiter.record_response(channel_id)
        return True
    
    async def _handle_dm(self, message: discord.Message):
        """
        DM対応（Q19: B案）
        「サーバーで話しかけてください」と返答
        """
        response = (
            "あ、DMですね……すみません、わたしはサーバーのフィールドワーク中なので、"
            "#未来予測を投稿するch で話しかけてもらえると嬉しいです📎"
        )
        await message.channel.send(response)
    
    async def _handle_mention(self, message: discord.Message):
        """メンション/返信への応答処理"""
        try:
            # チャンネル設定取得
            channel_type = self.channel_config.get_channel_type(message.channel.id)
            
            # コンテキスト取得（Q16: 直前20件）
            context_messages = await self._get_context_messages(
                message.channel, 
                limit=CONTEXT_MESSAGE_COUNT
            )
            
            # ユーザープロファイル取得
            user_profile = self.profile_manager.get_profile(message.author.id)
            
            # 信頼度取得
            trust_level = self.trust_manager.get_trust_level(message.author.id)
            
            # 信頼度上昇: 栞に話しかける (+3)
            await self.trust_manager.add_score(
                message.author.id, 
                3, 
                "shiori_mention"
            )
            
            # LLM応答生成
            response = await self._generate_response(
                message=message,
                context=context_messages,
                user_profile=user_profile,
                trust_level=trust_level,
                channel_type=channel_type
            )
            
            # 応答送信
            await self._send_response(message, response)
            
            # リアクション付与（Q25）
            await self._add_appropriate_reaction(message, response)
            
        except Exception as e:
            # エラーハンドリング（Q23: キャラ口調）
            error_response = self.error_handler.format_error(e)
            await message.channel.send(error_response)
            logger.error(f"応答生成エラー: {e}", exc_info=True)
    
    async def _get_context_messages(
        self, 
        channel: discord.TextChannel, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        コンテキストメッセージを取得（Q16: 直前20件）
        """
        context = []
        
        try:
            async for msg in channel.history(limit=limit):
                context.append({
                    'author': msg.author.display_name,
                    'author_id': msg.author.id,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat(),
                    'is_bot': msg.author.bot
                })
        except discord.Forbidden:
            logger.warning(f"履歴取得権限なし: {channel.name}")
        
        # 時系列順に並び替え（古い順）
        context.reverse()
        return context
    
    async def _generate_response(
        self,
        message: discord.Message,
        context: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]],
        trust_level: TrustLevel,
        channel_type: ChannelType
    ) -> str:
        """LLM応答を生成"""
        
        # メッセージ内容の解析
        content = message.content
        
        # メンションを除去
        content = re.sub(r'<@!?\d+>', '', content).strip()
        
        # リンク抽出
        urls = self._extract_urls(content)
        
        # 予測パターン検出
        prediction_info = self.passive_monitor._extract_prediction_info(content)
        
        # 期限到来予測チェック（Q27）
        due_prediction = self.due_checker.get_oldest_due_prediction(message.author.id)
        
        # LLMコンテキスト構築
        llm_context = {
            'user_message': content,
            'user_name': message.author.display_name,
            'user_id': message.author.id,
            'channel_name': message.channel.name,
            'channel_type': channel_type.value,
            'trust_level': trust_level.value,
            'trust_name': trust_level.name,
            'context_messages': context[-10:],  # 直近10件をLLMに
            'has_urls': len(urls) > 0,
            'urls': urls,
            'is_prediction': prediction_info is not None,
            'prediction_info': prediction_info,
            'due_prediction': due_prediction,
            'user_profile': user_profile
        }
        
        # LLM呼び出し
        response = await self.llm.generate_response(llm_context)
        
        # 予測が検出された場合は記録
        if prediction_info:
            await self._record_prediction(message, prediction_info)
        
        # リンク要約リクエストの処理
        if self._is_summary_request(content) and urls:
            summary = await self.summarizer.summarize_url(urls[0])
            if summary:
                response = f"{response}\n\n{summary}"
        
        # 期限到来予測のリマインダー追加（Q27）
        if due_prediction and len(response) < 1500:  # 長すぎなければ追加
            reminder = self.due_checker.format_due_reminder(due_prediction)
            response = f"{response}\n\n{reminder}"
        
        return response
    
    def _extract_urls(self, text: str) -> List[str]:
        """テキストからURLを抽出"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)
    
    def _is_summary_request(self, text: str) -> bool:
        """要約リクエストかどうか判定"""
        summary_keywords = [
            '要約', 'まとめ', 'サマリ', 'summary',
            '読んで', '教えて', '何が書いてある'
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in summary_keywords)
    
    async def _record_prediction(
        self, 
        message: discord.Message, 
        prediction_info: Dict[str, Any]
    ):
        """予測を記録"""
        try:
            prediction = await self.prediction_manager.create_prediction(
                user_id=message.author.id,
                user_name=message.author.display_name,
                content=prediction_info.get('content', message.content),
                category=prediction_info.get('category'),
                timeline=prediction_info.get('timeline'),
                source_message_id=message.id,
                source_channel_id=message.channel.id
            )
            
            # 信頼度上昇: 予測投稿 (+2)
            await self.trust_manager.add_score(
                message.author.id,
                2,
                "prediction_post"
            )
            
            logger.info(f"予測記録: {prediction.prediction_id} by {message.author.display_name}")
            
        except Exception as e:
            logger.error(f"予測記録エラー: {e}")
    
    async def _send_response(self, message: discord.Message, response: str):
        """応答を送信（Q13: 通常1メッセージ、長い場合は分割）"""
        # Discord の文字数制限（2000文字）
        MAX_LENGTH = 2000
        
        if len(response) <= MAX_LENGTH:
            await message.reply(response, mention_author=False)
        else:
            # 長い応答は分割
            chunks = self._split_response(response, MAX_LENGTH)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.reply(chunk, mention_author=False)
                else:
                    await message.channel.send(chunk)
    
    def _split_response(self, text: str, max_length: int) -> List[str]:
        """応答を分割"""
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += '\n' + line if current_chunk else line
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _add_appropriate_reaction(self, message: discord.Message, response: str):
        """適切なリアクションを付与（Q25）"""
        # 応答内容に基づいてリアクションタイプを判定
        if '予測記録' in response or '📎' in response:
            reaction_type = ReactionType.BOOKMARK
        elif '議論まとめ' in response or '📓' in response:
            reaction_type = ReactionType.FIELD_NOTES
        elif 'リスク' in response or '❓' in response:
            reaction_type = ReactionType.QUESTION
        elif '的中' in response or '外れ' in response:
            reaction_type = ReactionType.CONFIRMED
        else:
            # デフォルトは📎
            reaction_type = ReactionType.BOOKMARK
        
        await self.reaction_manager.add_reaction(message, reaction_type)
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """リアクション追加時の処理"""
        # 自分自身のリアクションは無視
        if user == self.user:
            return
        
        # Bot のリアクションは無視
        if user.bot:
            return
        
        # 📎リアクションは廃止（Q2: B案）
        # 他のリアクション処理があれば here
        pass
    
    async def on_member_remove(self, member: discord.Member):
        """メンバー離脱時の処理（Q26: 匿名化して保持）"""
        logger.info(f"メンバー離脱: {member.display_name} ({member.id})")
        
        # プロファイルの匿名化
        await self.profile_manager.anonymize_member(member.id)
        
        # 信頼度データの削除
        self.trust_manager.remove_member(member.id)


async def main():
    """メイン関数"""
    # 環境変数チェック
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN が設定されていません")
        return
    
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY が設定されていません")
        return
    
    # Bot 起動
    bot = ShioriBot()
    
    try:
        logger.info("📎 栞を起動します...")
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("📎 栞を終了します...")
        await bot.close()
    except Exception as e:
        logger.error(f"Bot エラー: {e}", exc_info=True)
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
