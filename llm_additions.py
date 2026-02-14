"""llm.py への追加メソッド — v5.2 モジュール対応

以下の2メソッドを既存の LLMClient クラスに追加してください。
v5.2 モジュール（cfr.py, learning_detector.py, response_generator.py）が
これらのメソッドを呼び出します。

追加場所: LLMClient クラスの末尾（既存メソッドの後）
追加 import: from haiku_prompts import HaikuPrompt, HaikuPromptRegistry
追加 import: import config as shiori_config  （TIER1_MODEL / MAIN_MODEL の参照）

COMMON_MISTAKES §13: AsyncAnthropic を使用した async def であること。
"""


# ═══ 以下を LLMClient クラスに追加 ═══

async def call_haiku(
    self,
    prompt_id: str,
    *,
    template_vars: dict[str, str],
) -> str:
    """Haiku（Tier-1）プロンプトを実行する。

    v5.2 の CFR判定・学習検出・応答タイプ分類で使用。
    HaikuPromptRegistry に登録されたプロンプトテンプレートを参照する。

    Args:
        prompt_id: HaikuPromptRegistry に登録済みのプロンプトID
        template_vars: user_template に渡す変数辞書

    Returns:
        Haikuモデルの出力テキスト
    """
    from haiku_prompts import HaikuPromptRegistry
    import config as shiori_config

    prompt = HaikuPromptRegistry.get(prompt_id)
    user_content = prompt.user_template.format(**template_vars)

    logger.debug(
        "Haiku call [%s]: system=%d chars, user=%d chars",
        prompt_id,
        len(prompt.system),
        len(user_content),
    )

    response = await self.client.messages.create(
        model=shiori_config.TIER1_MODEL,
        max_tokens=prompt.max_tokens,
        system=prompt.system,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


async def call_sonnet(
    self,
    *,
    system: str,
    user_content: str,
    max_tokens: int = 1024,
) -> str:
    """Sonnet（メインモデル）を直接呼び出す。

    v5.2 の ResponseGenerator で CFR以外の応答生成に使用。

    Args:
        system: システムプロンプト
        user_content: ユーザーメッセージ
        max_tokens: 最大出力トークン数

    Returns:
        Sonnetモデルの出力テキスト
    """
    import config as shiori_config

    logger.debug(
        "Sonnet call: system=%d chars, user=%d chars",
        len(system),
        len(user_content),
    )

    response = await self.client.messages.create(
        model=shiori_config.MAIN_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text
