"""
discussion_summary.py - 議論まとめ機能強化

Shiori v5.3 - §7 議論まとめ機能の強化
Interface Contract: §12.7.6
Error Pattern: N-05（例外隔離）, N-07（メンバー名照合4段階フォールバック）

v5.2では「まとめて」「要約して」等のトリガーで議論要約を生成していたが、
v5.3ではメンバー名指定での会話取得、柔軟な名前照合、
件数に応じたフォールバック対応を追加する。
"""

import logging
import re

import discord
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

# ============================================================
# 定数定義
# ============================================================

# LLMモデル（デュアルモデルアーキテクチャ: Sonnet for creative tasks）
MAIN_MODEL = "claude-sonnet-4-20250514"
SUMMARY_MAX_TOKENS = 1000

# フェッチ制限（Q8/Q9決定: チャンネルのみ、直近100件）
FETCH_LIMIT = 100

# 部分一致の最小クエリ長（Q10決定: 3文字以上）
PARTIAL_MATCH_MIN_LENGTH = 3

# 照合結果の上限（N-07: 上限3名まで返す）
MAX_RESOLVE_RESULTS = 3


# ============================================================
# トリガー検出パターン（§7.2.1）
# ============================================================

# メンバー名指定パターン（v5.3追加）— より具体的なので先にチェック
MEMBER_SUMMARY_PATTERNS = [
    # 「〇〇さんの発言まとめて」
    r"(.+?)(?:さん|くん|ちゃん)?の(?:発言|投稿|意見|コメント).*(?:まとめ|要約|整理)",
    # 「〇〇さんと△△さんの会話まとめて」
    r"(.+?)(?:さん|くん|ちゃん)?と(.+?)(?:さん|くん|ちゃん)?の(?:会話|議論|やりとり|やり取り).*(?:まとめ|要約|整理)",
    # 「〇〇と△△の会話まとめて」（敬称なし）
    r"(.+?)と(.+?)の(?:会話|議論|やりとり|やり取り|発言).*(?:まとめ|要約|整理)",
]

# 一般要約依頼パターン（v5.2から継続）
SUMMARY_REQUEST_PATTERNS = [
    r"(まとめ|要約|整理).*(?:して|て|お願い|欲しい|ほしい|くれ|ください)",
    r"(?:して|お願い|欲しい|ほしい|くれ|ください).*(まとめ|要約|整理)",
]


# ============================================================
# LLMプロンプト（§7.6.3）
# ============================================================

MEMBER_SUMMARY_SYSTEM_PROMPT = (
    "あなたは会話の要約を行うアシスタントです。"
    "以下のルールに従ってください。"
    "箇条書きは使わず、自然な文章でまとめること。"
    "各メンバーの主な主張や意見を公平に扱うこと。"
    "150〜300字程度でまとめること。"
)

MEMBER_SUMMARY_USER_PROMPT = """
以下は{channel_name}での{member_names}の発言です。
この会話の要点を文章形式でまとめてください。

ルール:
- 箇条書きは使わず、自然な文章でまとめる
- 各メンバーの主な主張や意見を公平に扱う
- 時系列の流れがわかるようにする
- 150〜300字程度でまとめる

--- 対象発言 ---
{conversation_text}
"""


# ============================================================
# 公開API（§12.7.6 インターフェース契約）
# ============================================================


def detect_summary_request(message_content: str) -> dict | None:
    """要約依頼を検出し、対象メンバー名を抽出する

    Args:
        message_content: メッセージ本文

    Returns:
        None: 要約依頼ではない
        {"type": "general"}: 一般要約
        {"type": "member", "members": ["名前1"]}: メンバー指定（単独）
        {"type": "member", "members": ["名前1", "名前2"]}: メンバー指定（複数）

    ⚠️ メンバー名指定パターンを先にチェックする（より具体的なパターン優先）
    ⚠️ sync関数（§13: 正規表現マッチのみ、I/Oなし）
    """
    content = message_content

    # Phase 1: メンバー名指定パターンを先にチェック（より具体的なパターン優先）
    for pattern in MEMBER_SUMMARY_PATTERNS:
        match = re.search(pattern, content)
        if match:
            members = [g for g in match.groups() if g]
            # 敬称を除去
            members = [
                re.sub(r"(さん|くん|ちゃん)$", "", m.strip())
                for m in members
            ]
            # 空文字列を除外
            members = [m for m in members if m]
            if members:
                return {"type": "member", "members": members}

    # Phase 2: 一般要約依頼チェック
    for pattern in SUMMARY_REQUEST_PATTERNS:
        if re.search(pattern, content):
            return {"type": "general"}

    return None


def resolve_member_name(
    query: str,
    guild_members: list[discord.Member],
    profile_data: dict | None = None,
) -> list[discord.Member]:
    """メンバー名を照合し、一致するメンバーを返す

    N-07パターン: 4段階フォールバック照合
    Q10決定（Option C）: 部分一致 + global_name/username両方検索

    照合順序:
        Phase 1: global_name 完全一致
        Phase 2: username 完全一致
        Phase 3: profile_data aliases 完全一致
        Phase 4: global_name / username 部分一致（3文字以上のクエリのみ）

    Args:
        query: 検索クエリ（ユーザーが入力した名前）
        guild_members: サーバーメンバーリスト（discord.Member のリスト）
        profile_data: メンバープロファイル辞書（任意）
            形式: {
                "username": {
                    "display_name": str,
                    "notes": str,  # 旧表示名等が含まれる場合がある
                },
                ...
            }

    Returns:
        list[discord.Member]: 一致したメンバーリスト（上限3名: MAX_RESOLVE_RESULTS）

    ⚠️ sync関数（§13: リスト走査のみ、I/Oなし）
    ⚠️ Bot ユーザーは除外する
    ⚠️ 部分一致は3文字以上のクエリのみ（誤マッチ防止: §20）
    """
    query_lower = query.lower()
    matches = []
    seen_ids = set()

    def _add_if_new(member: discord.Member) -> bool:
        """重複を防いで追加"""
        if member.id not in seen_ids:
            seen_ids.add(member.id)
            matches.append(member)
            return True
        return False

    # Bot ユーザーを除外したリストを作成
    human_members = [m for m in guild_members if not m.bot]

    # Phase 1: global_name 完全一致
    for member in human_members:
        if member.global_name and member.global_name.lower() == query_lower:
            _add_if_new(member)
    if matches:
        return matches[:MAX_RESOLVE_RESULTS]

    # Phase 2: username 完全一致
    for member in human_members:
        if member.name.lower() == query_lower:
            _add_if_new(member)
    if matches:
        return matches[:MAX_RESOLVE_RESULTS]

    # Phase 3: profile_data aliases / notes 完全一致（§20: エイリアス対応）
    if profile_data:
        for username, profile in profile_data.items():
            display_name = profile.get("display_name", "")
            notes = profile.get("notes", "")
            # display_name 完全一致
            if display_name.lower() == query_lower:
                for member in human_members:
                    if member.name.lower() == username.lower():
                        _add_if_new(member)
            # notes に旧表示名が含まれている場合の完全一致チェック
            if notes and query_lower in notes.lower():
                for member in human_members:
                    if member.name.lower() == username.lower():
                        _add_if_new(member)
        if matches:
            return matches[:MAX_RESOLVE_RESULTS]

    # Phase 4: 部分一致（3文字以上のクエリのみ — 誤マッチ防止）
    if len(query) >= PARTIAL_MATCH_MIN_LENGTH:
        for member in human_members:
            # global_name 部分一致
            if member.global_name and query_lower in member.global_name.lower():
                _add_if_new(member)
                continue
            # username 部分一致
            if query_lower in member.name.lower():
                _add_if_new(member)
                continue
            # nick（サーバーニックネーム）部分一致
            if member.nick and query_lower in member.nick.lower():
                _add_if_new(member)
                continue

    return matches[:MAX_RESOLVE_RESULTS]


async def fetch_member_conversation(
    channel: discord.TextChannel,
    member_ids: list[int],
    limit: int = FETCH_LIMIT,
) -> list[discord.Message]:
    """指定メンバーの発言を取得する

    Q8決定: 依頼があったチャンネルのみ
    Q9決定: 直近100件

    Args:
        channel: 検索対象チャンネル
        member_ids: 対象メンバーのID リスト
        limit: 検索範囲のメッセージ数上限（デフォルト100）

    Returns:
        list[discord.Message]: 対象メンバーの発言リスト（時系列順）

    ⚠️ async関数（§13: channel.history() は async iterator）
    """
    member_id_set = set(member_ids)
    conversations = []

    try:
        async for msg in channel.history(limit=limit):
            if msg.author.id in member_id_set and not msg.author.bot:
                conversations.append(msg)
    except discord.Forbidden:
        logger.error(
            f"[DiscussionSummary] No permission to read history "
            f"in {channel.name}"
        )
        return []
    except Exception as e:
        logger.error(
            f"[DiscussionSummary] Failed to fetch history "
            f"in {channel.name}: {e}"
        )
        return []

    # 時系列順にソート（古い順）
    conversations.reverse()
    return conversations


async def handle_member_summary(
    message: discord.Message,
    summary_request: dict,
    guild_members: list[discord.Member] | None = None,
    profile_data: dict | None = None,
) -> str:
    """メンバー指定の要約を生成する

    処理フロー:
        1. メンバー名照合（resolve_member_name）
        2. 発言取得（fetch_member_conversation）
        3. 件数に応じたフォールバック（Q1決定: Option B）
        4. LLM要約生成（Sonnet）
        5. 📋フォーマットで返却

    Args:
        message: 要約依頼メッセージ
        summary_request: detect_summary_request() の戻り値
            形式: {"type": "member", "members": ["名前1", "名前2"]}
        guild_members: サーバーメンバーリスト（None時はguild.membersから取得）
        profile_data: メンバープロファイル辞書（任意、resolve_member_nameに渡す）

    Returns:
        str: 要約テキスト（📋形式）またはエラーメッセージ

    ⚠️ async関数（§13: channel.history + Sonnet API呼び出し）
    ⚠️ N-05: 例外隔離 — 要約生成失敗は全体を止めない
    """
    member_names_raw = summary_request.get("members", [])

    # ---- Phase 1: メンバー名照合 ----
    if guild_members is None:
        guild_members = message.guild.members if message.guild else []

    all_resolved = []
    unresolved_names = []

    for name in member_names_raw:
        resolved = resolve_member_name(name, guild_members, profile_data)
        if resolved:
            all_resolved.extend(resolved)
        else:
            unresolved_names.append(name)

    # 全員特定不可
    if not all_resolved:
        names_str = "、".join(member_names_raw)
        return (
            f"「{names_str}」さんを特定できませんでした。"
            f"表示名やユーザー名で指定してみてください。"
        )

    # 一部特定不可の場合は注記付きで続行
    partial_note = ""
    if unresolved_names:
        unresolved_str = "、".join(unresolved_names)
        partial_note = f"（※「{unresolved_str}」さんは特定できませんでした）\n\n"

    # ---- Phase 2: 発言取得 ----
    member_ids = [m.id for m in all_resolved]
    conversations = await fetch_member_conversation(
        message.channel, member_ids
    )

    count = len(conversations)

    # 表示用メンバー名（敬称付き: §7.6.2）
    display_names = []
    for m in all_resolved:
        name = m.global_name or m.name
        display_names.append(f"{name}さん")
    names_display = "と".join(display_names)

    # ---- Phase 3: 件数に応じたフォールバック（Q1決定: Option B） ----

    # 0件: 発言が見つからない
    if count == 0:
        return (
            partial_note
            + f"{names_display}の発言が"
            f"見つかりませんでした。もう少し前の会話でしたか？"
        )

    # ---- Phase 4: LLM要約生成 ----
    try:
        summary_text = await _generate_summary_with_llm(
            conversations, message.channel.name, names_display
        )
    except Exception as e:
        # N-05: 要約生成失敗は独立して処理
        logger.error(
            f"[DiscussionSummary] LLM summary generation failed: {e}"
        )
        return (
            partial_note
            + f"{names_display}の発言が{count}件見つかりましたが、"
            f"要約の生成中にエラーが発生しました。"
            f"しばらくしてからもう一度お試しください。"
        )

    # ---- Phase 5: 出力フォーマット（§7.6.1） ----

    # 1-2件: 注記付き部分要約
    if count <= 2:
        prefix = (
            f"直近{FETCH_LIMIT}件では{count}件しか見つかりませんでしたが、"
            f"見つかった分をまとめますね。\n\n"
        )
        formatted = _format_summary_output(
            summary_text, names_display, FETCH_LIMIT, count
        )
        return partial_note + prefix + formatted

    # 3件以上: 通常の要約
    formatted = _format_summary_output(
        summary_text, names_display, FETCH_LIMIT, count
    )
    return partial_note + formatted


# ============================================================
# 内部ヘルパー関数
# ============================================================


def _format_conversation_for_summary(
    conversations: list[discord.Message],
) -> str:
    """会話メッセージをLLMに渡すテキスト形式に変換する

    Args:
        conversations: メッセージリスト（時系列順）

    Returns:
        str: フォーマット済み会話テキスト

    ⚠️ §14: データフォーマット変換層 — 内部表現→API形式
    """
    lines = []
    for msg in conversations:
        # 表示名を取得（global_name > name）
        author_name = msg.author.global_name or msg.author.name
        # メッセージ内容が空の場合（添付ファイルのみ等）はスキップ
        content = msg.content.strip()
        if not content:
            continue
        timestamp = msg.created_at.strftime("%m/%d %H:%M")
        lines.append(f"[{timestamp}] {author_name}: {content}")

    return "\n".join(lines)


def _format_summary_output(
    summary_text: str,
    names_display: str,
    search_range: int,
    hit_count: int,
) -> str:
    """要約出力を📋フォーマットで整形する（§7.6.1）

    Args:
        summary_text: LLMが生成した要約テキスト
        names_display: 表示用メンバー名（敬称付き）
        search_range: 検索範囲のメッセージ数
        hit_count: 該当メッセージ数

    Returns:
        str: 📋フォーマットの要約テキスト
    """
    return (
        f"📋 会話まとめ（{names_display}）\n\n"
        f"{summary_text}\n\n"
        f"対象: 直近{search_range}件中、{hit_count}件の発言を元に作成"
    )


async def _generate_summary_with_llm(
    conversations: list[discord.Message],
    channel_name: str,
    member_names: str,
) -> str:
    """LLM（Sonnet）を使って要約を生成する

    Args:
        conversations: 要約対象のメッセージリスト
        channel_name: チャンネル名
        member_names: 表示用メンバー名

    Returns:
        str: LLMが生成した要約テキスト

    Raises:
        Exception: API呼び出し失敗時（呼び出し元でN-05パターンで捕捉）

    ⚠️ async関数（§13: AsyncAnthropic 使用必須）
    ⚠️ COMMON_MISTAKES F-10: 箇条書き禁止をプロンプトで指示
    """
    conversation_text = _format_conversation_for_summary(conversations)

    # 会話テキストが空の場合（content が空のメッセージのみだった場合）
    if not conversation_text.strip():
        return "テキストの発言が見つかりませんでした（画像やファイルのみの可能性があります）。"

    user_prompt = MEMBER_SUMMARY_USER_PROMPT.format(
        channel_name=channel_name,
        member_names=member_names,
        conversation_text=conversation_text,
    )

    client = AsyncAnthropic()

    response = await client.messages.create(
        model=MAIN_MODEL,
        max_tokens=SUMMARY_MAX_TOKENS,
        system=MEMBER_SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text
