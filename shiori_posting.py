"""shiori_posting.py — Shiori_ch (Forum Thread) への投稿ヘルパー

Shiori_ch は singularity_forum (ForumChannel) 内の Thread であり、
通常の TextChannel ではない。このモジュールは Forum Thread 固有の
取得・投稿ロジックを一箇所に集約し、日次メンテナンス（§4）と
週次独り言（§7）の両方から共通利用する。

COMMON_MISTAKES対応:
  §38: Forum Thread と TextChannel を混同しない
  N-06: Thread ID は環境変数で管理 + None チェック
  N-05: get_channel() の戻り値が None になりうる → fetch_channel() フォールバック

依存: discord.py, config.py
呼び出し元: daily_maintenance.py, weekly_monologue.py
"""

import logging

import discord

import config as shiori_config

logger = logging.getLogger("shiori.posting")


def _get_shiori_thread_id() -> int:
    """SHIORI_THREAD_ID を config から取得する。

    config.py に SHIORI_THREAD_ID が定義されていない場合は 0 を返す。
    """
    return getattr(shiori_config, "SHIORI_THREAD_ID", 0)


async def get_shiori_thread(bot: discord.Client) -> discord.Thread | None:
    """Shiori_ch の Forum Thread を取得する

    取得戦略:
        1. bot.get_channel() でキャッシュから取得を試みる
        2. キャッシュになければ bot.fetch_channel() で API から取得
        3. 取得した対象が Thread でなければ None を返す

    アーカイブ解除:
        取得した Thread が archived=True の場合、自動的に
        archived=False に変更してから返す。

    Returns:
        discord.Thread | None — 取得失敗時は None
    """
    thread_id = _get_shiori_thread_id()

    if thread_id == 0:
        logger.error("[ShioriPosting] SHIORI_THREAD_ID is not set (0)")
        return None

    # Step 1: キャッシュから取得
    thread = bot.get_channel(thread_id)

    # Step 2: キャッシュになければ API から取得
    if thread is None:
        try:
            thread = await bot.fetch_channel(thread_id)
        except discord.NotFound:
            logger.error(
                f"[ShioriPosting] Thread {thread_id} not found. "
                f"The thread may have been deleted."
            )
            return None
        except discord.Forbidden:
            logger.error(
                f"[ShioriPosting] No permission to access thread {thread_id}"
            )
            return None
        except Exception as e:
            logger.error(f"[ShioriPosting] Failed to fetch thread: {e}")
            return None

    # Step 3: Thread 型チェック
    if not isinstance(thread, discord.Thread):
        logger.error(
            f"[ShioriPosting] ID {thread_id} is {type(thread).__name__}, "
            f"not Thread. Check SHIORI_THREAD_ID."
        )
        return None

    # Step 4: アーカイブ解除（クローズされている場合）
    if thread.archived:
        try:
            await thread.edit(archived=False)
            logger.info(
                f"[ShioriPosting] Unarchived thread {thread.name} "
                f"(was closed/archived)"
            )
        except discord.Forbidden:
            logger.error(
                "[ShioriPosting] No permission to unarchive thread. "
                "Bot needs 'Manage Threads' permission."
            )
            return None
        except Exception as e:
            logger.error(f"[ShioriPosting] Failed to unarchive: {e}")
            return None

    return thread


async def post_to_shiori_thread(
    bot: discord.Client,
    content: str,
    caller: str = "Unknown",
) -> bool:
    """Shiori_ch (Forum Thread) にメッセージを投稿する

    Args:
        bot: Discord Bot インスタンス
        content: 投稿内容
        caller: 呼び出し元の識別名（ログ用）

    Returns:
        True: 投稿成功 / False: 投稿失敗

    ⚠️ N-06 準拠: Thread ID は環境変数管理 + None チェック
    ⚠️ アーカイブ済み Thread は自動解除後に投稿
    ⚠️ Forbidden 例外のハンドリング必須
    """
    thread = await get_shiori_thread(bot)
    if thread is None:
        return False

    try:
        await thread.send(content)
        logger.info(f"[{caller}] Posted to Shiori_ch (thread: {thread.name})")
        return True
    except discord.Forbidden:
        logger.error(
            f"[{caller}] No 'Send Messages in Threads' permission "
            f"for thread {_get_shiori_thread_id()}"
        )
        return False
    except discord.HTTPException as e:
        logger.error(f"[{caller}] HTTP error posting to thread: {e}")
        return False
    except Exception as e:
        logger.error(f"[{caller}] Unexpected error: {e}")
        return False
