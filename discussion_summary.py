"""discussion_summary.py — 議論まとめ機能（メンバー名指定対応）

§7 準拠。v5.2の一般要約に加え、v5.3ではメンバー名指定での
会話取得・要約を追加する。

インターフェース契約: §12.7.6
依存: discord.py, Sonnet API
呼び出し元: bot.py (on_message ハンドラ)

COMMON_MISTAKES対応:
  N-07: メンバー名照合は完全一致→部分一致の順（§12.7.6）
  F-10: 要約出力は箇条書き禁止、文章形式（§7.6.2, §27）
  §15: 各ステップにエラー隔離
"""

import logging
import re

logger = logging.getLogger("shiori.discussion_summary")


# ===== 要約依頼パターン（§7.2.1） =====

# 一般要約依頼パターン（v5.2から継続）
SUMMARY_REQUEST_PATTERNS = [
    r"(まとめ|要約|整理).*(?:して|お願い|欲しい|ほしい|くれ|ください)",
    r"(?:して|お願い|欲しい|ほしい|くれ|ください).*(まとめ|要約|整理)",
]

# メンバー名指定パターン（v5.3追加）
# ⚠️ より具体的なパターン（複数名）を先にチェックする
MEMBER_SUMMARY_PATTERNS = [
    # 「〇〇さんと△△さんの会話まとめて」（複数名・敬称付き）
    r"(.+?)(?:さん|くん|ちゃん)?と(.+?)(?:さん|くん|ちゃん)?の"
    r"(?:会話|議論|やりとり|やり取り).*(?:まとめ|要約|整理)",
    # 「〇〇と△△の会話まとめて」（複数名・敬称なし）
    r"(.+?)と(.+?)の(?:会話|議論|やりとり|やり取り|発言)"
    r".*(?:まとめ|要約|整理)",
    # 「〇〇さんの発言まとめて」（単独名）
    r"(.+?)(?:さん|くん|ちゃん)?の(?:発言|投稿|意見|コメント)"
    r".*(?:まとめ|要約|整理)",
]


# ===== LLMプロンプト（§7.6.3） =====

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


# ===== 公開関数（§12.7.6） =====


def detect_summary_request(message_content: str) -> dict | None:
    """メッセージが要約依頼かを判定する（§7.2.1, §12.7.6）

    Args:
        message_content: [必須] メンション除去済みのメッセージ内容

    Returns:
        None: 要約依頼ではない
        {"type": "general"}: 一般要約
        {"type": "member", "members": ["名前1"]}: メンバー指定（単独）
        {"type": "member", "members": ["名前1", "名前2"]}: メンバー指定（複数）

    ⚠️ メンバー名指定パターンを先にチェックする（より具体的なパターン優先）
    ⚠️ §12.4.2 形式に準拠
    """
    content = message_content

    # メンバー名指定パターンを先にチェック（より具体的なパターン優先）
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

    # 一般要約依頼チェック
    for pattern in SUMMARY_REQUEST_PATTERNS:
        if re.search(pattern, content):
            return {"type": "general"}

    return None


def resolve_member_name(
    query: str,
    guild_members: list,
    profile_data: dict | None = None,
) -> list:
    """クエリ文字列からDiscordメンバーを照合する（§7.3, §12.7.6）

    Args:
        query: [必須] 検索クエリ（敬称除去済み）
        guild_members: [必須] guild.members（サーバーのメンバーリスト）
        profile_data: [任意] members_extended.md から読み込んだプロファイル辞書

    Returns:
        マッチしたメンバーのリスト（空リスト＝該当なし）

    照合優先順位（§12.7.6 準拠）:
        1. global_name（表示名）完全一致
        2. username（ユーザー名）完全一致
        3. members_extended.md のエイリアス完全一致
        4. global_name（表示名）部分一致（contains）
        5. username（ユーザー名）部分一致（contains）
        6. nick（サーバーニックネーム）部分一致
        7. profile_data 内の display_name / notes / aliases 部分一致

    ⚠️ Bot自身は検索対象から除外する
    ⚠️ 大文字小文字を区別しない（case-insensitive）
    ⚠️ COMMON_MISTAKES N-07: 完全一致を部分一致より優先し、
       「ろーる」で「ぴろーるん」がヒットする問題を軽減
    """
    query_lower = query.lower()
    if not query_lower:
        return []

    # ===== Phase 1: 完全一致（exact match） =====

    # 1. global_name 完全一致
    for member in guild_members:
        if member.bot:
            continue
        if (
            member.global_name
            and query_lower == member.global_name.lower()
        ):
            return [member]

    # 2. username 完全一致
    for member in guild_members:
        if member.bot:
            continue
        if query_lower == member.name.lower():
            return [member]

    # 3. aliases 完全一致（profile_data から）
    if profile_data:
        for _key, profile in profile_data.items():
            aliases = [a.lower() for a in profile.get("aliases", [])]
            if query_lower in aliases:
                uid = profile.get("user_id")
                if uid:
                    for member in guild_members:
                        if str(member.id) == str(uid) and not member.bot:
                            return [member]

    # ===== Phase 2: 部分一致（partial / contains match） =====

    matches = []

    # 4. global_name 部分一致
    for member in guild_members:
        if member.bot:
            continue
        if (
            member.global_name
            and query_lower in member.global_name.lower()
            and member not in matches
        ):
            matches.append(member)

    if matches:
        return matches

    # 5. username 部分一致
    for member in guild_members:
        if member.bot:
            continue
        if (
            query_lower in member.name.lower()
            and member not in matches
        ):
            matches.append(member)

    if matches:
        return matches

    # 6. nick（サーバーニックネーム）部分一致
    for member in guild_members:
        if member.bot:
            continue
        if (
            member.nick
            and query_lower in member.nick.lower()
            and member not in matches
        ):
            matches.append(member)

    if matches:
        return matches

    # 7. profile_data 内の display_name / notes / aliases 部分一致
    if profile_data:
        for _key, profile in profile_data.items():
            display = profile.get("display_name", "").lower()
            notes = profile.get("notes", "").lower()
            aliases = [a.lower() for a in profile.get("aliases", [])]

            matched = (
                query_lower in display
                or query_lower in notes
                or any(query_lower in alias for alias in aliases)
            )

            if matched:
                uid = profile.get("user_id")
                if uid:
                    for member in guild_members:
                        if (
                            str(member.id) == str(uid)
                            and not member.bot
                            and member not in matches
                        ):
                            matches.append(member)
                            break

    return matches


async def fetch_member_conversation(
    channel,
    member_ids: list[int],
    limit: int = 100,
) -> list:
    """指定メンバーの会話を直近メッセージから抽出する（§7.4, §12.7.6）

    Args:
        channel: [必須] 検索対象チャンネル（discord.TextChannel）
        member_ids: [必須] 対象メンバーのDiscord ID（1〜2名）
        limit: [任意] 取得件数上限（デフォルト100 — Q9決定）

    Returns:
        対象メンバーのメッセージリスト（時系列順: 古い→新しい）

    ⚠️ channel.history() は新しい順に返すため、最後にソートが必要
    ⚠️ Q8決定: 依頼があったチャンネルのみ検索（クロスチャンネル不可）
    """
    messages = []

    async for msg in channel.history(limit=limit):
        if msg.author.id in member_ids:
            messages.append(msg)

    # 時系列順にソート（古い→新しい）
    messages.sort(key=lambda m: m.created_at)

    return messages


async def handle_member_summary(
    message,
    summary_request: dict,
    member_profile_data: dict | None = None,
    llm_client=None,
) -> str:
    """メンバー名指定の会話要約を処理する（§7.5, §12.7.6）

    Args:
        message: [必須] トリガーとなったdiscord.Message
        summary_request: [必須] detect_summary_request() の戻り値
                         {"type": "member", "members": [...]}
        member_profile_data: [任意] members_extended.md のプロファイル辞書
        llm_client: [任意] Anthropic APIクライアント

    Returns:
        str — 要約テキスト（失敗時はフォールバックメッセージ）

    処理フロー:
        1. resolve_member_name() でメンバー特定
        2. fetch_member_conversation() で会話取得
        3. Sonnet で要約生成
        4. 失敗時は Q1決定（Option B）に基づくフォールバック

    ⚠️ 要約出力は箇条書き禁止（COMMON_MISTAKES F-10, §27）
    ⚠️ フォールバックは§7.5.2テンプレートの「意味」に沿いつつ
       LLMがキャラクターに合わせて自然に生成する
    """
    member_names = summary_request.get("members", [])
    resolved_members = []
    unresolved_names = []

    # Step 1: メンバー名を照合
    for name in member_names:
        try:
            matches = resolve_member_name(
                name,
                message.guild.members,
                member_profile_data,
            )
            if matches:
                resolved_members.append(matches[0])  # 最初のマッチを採用
            else:
                unresolved_names.append(name)
        except Exception as e:
            logger.error(
                f"[DiscussionSummary] Member resolve error "
                f"for '{name}': {e}"
            )
            unresolved_names.append(name)

    # 照合失敗があった場合（§7.5.2）
    if unresolved_names:
        names_str = "」「".join(unresolved_names)
        return (
            f"「{names_str}」さんが特定できませんでした。"
            f"表示名かユーザー名で教えてもらえますか？"
        )

    # Step 2: 会話を取得
    member_ids = [m.id for m in resolved_members]
    try:
        conversations = await fetch_member_conversation(
            message.channel,
            member_ids,
            limit=100,
        )
    except Exception as e:
        logger.error(
            f"[DiscussionSummary] Conversation fetch error: {e}"
        )
        return (
            "メッセージの取得中にエラーが発生しました。"
            "少し経ってから再度お願いします。"
        )

    # Step 3: 件数に応じた処理（§7.5.1）
    count = len(conversations)

    if count == 0:
        # 0件: 正直に不在を伝える（§7.5.2）
        names_str = "さんと".join(
            m.display_name for m in resolved_members
        )
        return (
            f"直近100件のメッセージの中で{names_str}さんの発言が"
            f"見つかりませんでした。もう少し前の会話でしたか？"
        )

    # 1件以上: 要約を生成（LLMに渡す）
    context_text = _format_conversation_for_summary(conversations)
    member_display_names = [
        f"{m.display_name}さん" for m in resolved_members
    ]
    names_joined = "と".join(member_display_names)

    summary = await _generate_summary_with_llm(
        channel_name=message.channel.name,
        member_names=names_joined,
        conversation_text=context_text,
        llm_client=llm_client,
    )

    if count <= 2:
        # 少数: 注記を付加（§7.5.1）
        prefix = (
            f"直近100件では{count}件しか見つかりませんでしたが、"
            f"見つかった分をまとめますね。\n\n"
        )
        return prefix + summary

    # §7.6.1 出力フォーマット
    footer = f"\n\n対象: 直近100件中、{count}件の発言を元に作成"
    return f"📋 会話まとめ（{names_joined}）\n\n{summary}{footer}"


# ===== 内部ヘルパー関数 =====


def _format_conversation_for_summary(messages: list) -> str:
    """メッセージリストをLLMに渡すテキスト形式に変換する

    Args:
        messages: discord.Message のリスト（時系列順）

    Returns:
        フォーマット済みテキスト
    """
    lines = []
    for msg in messages:
        timestamp = msg.created_at.strftime("%H:%M")
        author = msg.author.display_name
        content = msg.content
        if content:
            lines.append(f"[{timestamp}] {author}: {content}")

    return "\n".join(lines)


async def _generate_summary_with_llm(
    channel_name: str,
    member_names: str,
    conversation_text: str,
    llm_client=None,
) -> str:
    """LLMを使って会話の要約を生成する（§7.6.3）

    Args:
        channel_name: チャンネル名
        member_names: メンバー名の文字列（「〇〇さんと△△さん」形式）
        conversation_text: フォーマット済み会話テキスト
        llm_client: Anthropic APIクライアント

    Returns:
        要約テキスト

    ⚠️ Sonnet使用（品質重視）
    ⚠️ 箇条書き禁止（COMMON_MISTAKES F-10）
    ⚠️ 生成失敗時はフォールバックテキストを返す
    """
    if llm_client is None:
        logger.warning(
            "[DiscussionSummary] LLM client not provided, "
            "returning raw text"
        )
        return conversation_text[:300] + "..."

    prompt = MEMBER_SUMMARY_USER_PROMPT.format(
        channel_name=channel_name,
        member_names=member_names,
        conversation_text=conversation_text,
    )

    try:
        response = await llm_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            temperature=0.3,  # 要約は低温度で正確に
            messages=[{"role": "user", "content": prompt}],
        )
        summary = response.content[0].text.strip()
        return summary

    except Exception as e:
        logger.error(
            f"[DiscussionSummary] LLM summary generation failed: {e}"
        )
        # フォールバック: LLM生成失敗時は会話の先頭部分を返す
        return (
            "要約の生成中にエラーが発生しました。"
            "対象の会話は見つかっていますので、"
            "少し経ってから再度お願いします。"
        )
