"""
リアクションハンドラモジュール — reaction_handler.py
v5.3-P0P1-v2

変更履歴:
  v5.3:        should_heart_react() 3引数化、遅延リアクション
  v5.3-P0:     HEART_EMOJIS を config.py に集約
  v5.3-P0P1-v2: キーワード+確率判定 → Haiku好意判定に完全移行
                 - LLMClient 依存を追加（コンストラクタ引数）
                 - should_heart_react() → check_favorability() に置換
                 - 確率30% → 好意的なら100%付与
                 - CFR向け handle_cfr_reaction() 追加

依存: config.py (REACTION_DELAY_SECONDS, get_heart_emoji)
      llm.py (LLMClient.call_haiku)
      haiku_prompts.py (heart_favorability_check プロンプト)

COMMON_MISTAKES §13: LLMClient は AsyncAnthropic ベース。全呼び出しに await 必須。
"""

import asyncio
import logging

import discord

from config import REACTION_DELAY_SECONDS, get_heart_emoji
from haiku_prompts import parse_with_default

logger = logging.getLogger(__name__)

# Haiku好意判定のデフォルト値（F-06対策: 失敗時はリアクションしない）
_FAVORABILITY_DEFAULT = {"is_favorable": False}


class ReactionHandler:
    """ハートリアクション管理（Haiku好意判定ベース）

    v5.3-P0P1-v2 変更点:
      - キーワードマッチ + 30%確率 → Haiku LLM で好意判定
      - 好意的と判定されたら100%ハート付与（確率廃止）
      - LLMClient をコンストラクタで受け取る
      - handle_cfr_reaction() 追加（CFRトリガーメッセージ用）
    """

    def __init__(self, llm) -> None:
        """
        Args:
            llm: LLMClient インスタンス（call_haiku メソッドを持つ）

        ⚠️ bot.py 側で ReactionHandler(self.llm) に更新のこと
        """
        self.llm = llm

    async def check_favorability(self, message_content: str) -> bool:
        """Haikuで発言が栞に好意的かを判定する

        キーワードマッチを廃止し、LLM で文脈を理解した判定を行う。
        API失敗時は安全側（False）に倒す。

        Args:
            message_content: メッセージ内容

        Returns:
            True: 好意的（ハートリアクション対象）
            False: 好意的でない or 判定失敗
        """
        content = (message_content or "").strip()
        if not content:
            return False

        # 入力を300文字に切り詰め（F-04対策）
        trimmed = content[:300]

        try:
            raw_text = await self.llm.call_haiku(
                prompt_id="heart_favorability_check",
                template_vars={"message_content": trimmed},
            )
            result = parse_with_default(raw_text, _FAVORABILITY_DEFAULT)
            is_favorable = result.get("is_favorable", False)

            logger.debug(
                "好意判定: content='%s', favorable=%s",
                trimmed[:50], is_favorable,
            )
            return bool(is_favorable)

        except Exception as e:
            logger.warning("好意判定失敗(安全側=False): %s", e)
            return False

    async def handle_reaction(
        self,
        message: discord.Message,
        trust_score: int,
        is_reply_to_shiori: bool,
        is_mention_to_shiori: bool,
    ) -> None:
        """メンション/返信時のハートリアクション統合フロー

        v5.3-P0P1-v2:
          - キーワード判定 → Haiku好意判定に変更
          - 好意的と判定されたら100%ハート付与（確率廃止）

        Args:
            message:               対象メッセージ
            trust_score:           メッセージ投稿者の好感度スコア
            is_reply_to_shiori:    栞への返信か
            is_mention_to_shiori:  栞へのメンションか
        """
        # 栞宛てでなければリアクションしない
        if not is_reply_to_shiori and not is_mention_to_shiori:
            return

        # Haiku好意判定（好意的なら100%付与）
        if not await self.check_favorability(message.content):
            return

        emoji = get_heart_emoji(trust_score)

        schedule_delayed_reaction(message, emoji)
        logger.info(
            "ハートリアクション予約(メンション): msg=%s, emoji=%s, user=%s",
            message.id, emoji, message.author.display_name,
        )

    async def handle_cfr_reaction(
        self,
        message: discord.Message,
        trust_score: int,
    ) -> None:
        """CFRトリガーメッセージへのハートリアクション

        CFRが発動した（= 栞の発言へのフォローアップが検出された）
        メッセージについて、好意判定→ハート付与を行う。

        Args:
            message:     CFRトリガーとなったメッセージ
            trust_score: メッセージ投稿者の好感度スコア
        """
        if not await self.check_favorability(message.content):
            return

        emoji = get_heart_emoji(trust_score)

        schedule_delayed_reaction(message, emoji)
        logger.info(
            "ハートリアクション予約(CFR): msg=%s, emoji=%s, user=%s",
            message.id, emoji, message.author.display_name,
        )


# =====================================================================
#  遅延リアクション（§10, §12.5.2）
# =====================================================================

async def delayed_add_reaction(
    message: discord.Message,
    emoji: str,
    delay: int = REACTION_DELAY_SECONDS,
) -> bool:
    """遅延付きリアクション付与

    ⚠️ 本関数は asyncio.create_task() で呼び出すこと
       await 直接呼出しは応答を delay 秒ブロックする（COMMON_MISTAKES N-01）

    ⚠️ COMMON_MISTAKES N-02:
       4種のエラーを個別にキャッチする

    Args:
        message: リアクション対象メッセージ
        emoji:   リアクション絵文字
        delay:   遅延秒数（デフォルト: REACTION_DELAY_SECONDS）

    Returns:
        True:  リアクション成功
        False: 失敗
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return False

    try:
        await message.add_reaction(emoji)
        logger.info(
            "リアクション付与完了: msg=%s, emoji=%s", message.id, emoji,
        )
        return True

    except discord.NotFound:
        logger.warning(
            "リアクション失敗(NotFound): msg=%s — メッセージ削除済み",
            message.id,
        )
        return False

    except discord.Forbidden:
        logger.warning(
            "リアクション失敗(Forbidden): msg=%s — 権限不足",
            message.id,
        )
        return False

    except asyncio.CancelledError:
        return False

    except Exception as exc:
        logger.error(
            "リアクション失敗(予期せぬエラー): msg=%s, error=%s",
            message.id, exc,
        )
        return False


# =====================================================================
#  安全ラッパー（§10.10.2）
# =====================================================================

def schedule_delayed_reaction(
    message: discord.Message,
    emoji: str,
) -> None:
    """遅延リアクションのスケジュール

    create_task() の呼び出しを try/except で囲み、
    スケジューリング自体の失敗が他の処理に影響しないことを保証する。

    Args:
        message: リアクション対象メッセージ
        emoji:   リアクション絵文字
    """
    try:
        asyncio.create_task(delayed_add_reaction(message, emoji))
    except Exception as e:
        logger.error(
            "[Reaction] Failed to schedule delayed reaction "
            "for message %s: %s",
            message.id, e,
        )
