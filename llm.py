"""
llm.py - Anthropic Claude API インターフェース

栞（Shiori）Bot用のLLM呼び出しモジュール
Claude Haiku 4.5のみを使用（Q10: B案）
"""

import os
import asyncio
from typing import Optional
from anthropic import AsyncAnthropic

# モデル設定（Haiku 4.5のみ使用）
MODEL_ID = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048


class ShioriLLM:
    """栞のLLMインターフェース"""
    
    def __init__(self):
        self.client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self._system_prompt: Optional[str] = None
    
    @property
    def system_prompt(self) -> str:
        """システムプロンプトを遅延読み込み"""
        if self._system_prompt is None:
            prompt_path = os.path.join(
                os.path.dirname(__file__), 
                "system_prompt.txt"
            )
            with open(prompt_path, "r", encoding="utf-8") as f:
                self._system_prompt = f.read()
        return self._system_prompt
    
    async def generate_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        member_info: Optional[dict] = None,
        prediction_context: Optional[str] = None
    ) -> str:
        """
        栞としての応答を生成
        
        Args:
            user_message: ユーザーからのメッセージ
            context: 直前のチャンネルメッセージ（最大20件）
            member_info: メンバー情報（信頼度、専門分野など）
            prediction_context: 関連する予測記録
        
        Returns:
            生成された応答文
        """
        # 動的コンテキストの構築
        dynamic_context = self._build_dynamic_context(
            context, member_info, prediction_context
        )
        
        # システムプロンプト + 動的コンテキスト
        full_system = f"{self.system_prompt}\n\n{dynamic_context}"
        
        try:
            response = await self.client.messages.create(
                model=MODEL_ID,
                max_tokens=MAX_TOKENS,
                system=full_system,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text
        
        except Exception as e:
            # エラー時はキャラクター口調で返す（Q23: B案）
            return self._generate_error_message(e)
    
    def _build_dynamic_context(
        self,
        context: Optional[str],
        member_info: Optional[dict],
        prediction_context: Optional[str]
    ) -> str:
        """動的コンテキストを構築"""
        parts = []
        
        if context:
            parts.append(f"<recent_messages>\n{context}\n</recent_messages>")
        
        if member_info:
            trust_level = member_info.get("trust_level", 1)
            trust_score = member_info.get("trust_score", 0)
            specialties = member_info.get("specialties", [])
            
            parts.append(f"""<member_context>
発言者の信頼度: Lv{trust_level}（スコア: {trust_score}）
専門分野: {', '.join(specialties) if specialties else '未記録'}
</member_context>""")
        
        if prediction_context:
            parts.append(f"<related_predictions>\n{prediction_context}\n</related_predictions>")
        
        return "\n\n".join(parts)
    
    def _generate_error_message(self, error: Exception) -> str:
        """キャラクター口調のエラーメッセージ（Q23: B案）"""
        error_str = str(error).lower()
        
        if "rate" in error_str or "limit" in error_str:
            return "ごめんなさい、今ちょっと処理が混み合っていて……少し時間を置いてから呼んでください🙏"
        elif "timeout" in error_str:
            return "あっ、すみません……応答に時間がかかりすぎちゃいました📎💦 もう一度試してもらえますか？"
        else:
            return "あれ、なにか問題が起きたみたいです……ごめんなさい、もう一度試してもらえますか？📎"
    
    async def analyze_prediction(self, message: str) -> Optional[dict]:
        """
        メッセージが予測を含むか分析
        
        Returns:
            予測情報の辞書、または予測でない場合はNone
        """
        analysis_prompt = """以下のメッセージが未来予測を含むか分析してください。

メッセージ:
{message}

以下の形式でJSON形式で回答してください（予測を含まない場合は null）:
{{
  "is_prediction": true/false,
  "content": "予測内容の要約",
  "timeline_start": "開始年（不明なら null）",
  "timeline_end": "終了年（不明なら null）",
  "category_suggestion": "カテゴリ提案"
}}

予測の判定基準:
- 年号（2027、2030等）を含む
- 未来の出来事についての主張（〜になる、〜が実現、〜までに等）
- 単なる希望や願望ではなく、予測・予想として述べられている

JSON以外の文章は出力しないでください。"""

        try:
            response = await self.client.messages.create(
                model=MODEL_ID,
                max_tokens=512,
                messages=[
                    {"role": "user", "content": analysis_prompt.format(message=message)}
                ]
            )
            
            import json
            result_text = response.content[0].text.strip()
            
            if result_text.lower() == "null":
                return None
            
            return json.loads(result_text)
        
        except Exception:
            return None
    
    async def summarize_link(self, url: str, content: str) -> str:
        """
        リンク内容を要約（3点以内、索引レベル）
        Rom🧄の深い解説との差別化
        """
        summary_prompt = f"""以下のウェブページ内容を、栞（記録係の大学生）として要約してください。

URL: {url}

内容:
{content[:8000]}  # トークン制限のため切り詰め

要約ルール:
1. 要点は3つ以内
2. 索引レベルの簡潔さ（深い解説はしない）
3. 栞の口調で（「〜ですね」「〜みたいです」）
4. 予測に関連する内容があれば特に注目

出力形式:
📎 リンク要約
出典: [タイトル] (ドメイン)
要点:
①...
②...
③...
"""
        
        try:
            response = await self.client.messages.create(
                model=MODEL_ID,
                max_tokens=512,
                messages=[
                    {"role": "user", "content": summary_prompt}
                ]
            )
            return response.content[0].text
        
        except Exception as e:
            return self._generate_error_message(e)
    
    async def generate_discussion_summary(
        self, 
        messages: list[dict],
        topic: Optional[str] = None
    ) -> str:
        """
        議論要約を生成
        各メンバーの立場を整理して提示
        """
        # メッセージを整形
        formatted = "\n".join([
            f"[{m['author']}] {m['content']}"
            for m in messages
        ])
        
        summary_prompt = f"""以下の議論を、栞（記録係の大学生）として要約してください。

{"論題: " + topic if topic else ""}

議論内容:
{formatted}

要約ルール:
1. 各発言者の立場を整理
2. 合意点と未決着点を明確に
3. 栞の口調で
4. 中立的な立場を維持

出力形式:
📓 議論まとめ
論題: ...

[発言者A]説: ...
[発言者B]説: ...

未決着: ...
"""
        
        try:
            response = await self.client.messages.create(
                model=MODEL_ID,
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": summary_prompt}
                ]
            )
            return response.content[0].text
        
        except Exception as e:
            return self._generate_error_message(e)


# シングルトンインスタンス
_llm_instance: Optional[ShioriLLM] = None


def get_llm() -> ShioriLLM:
    """LLMインスタンスを取得"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ShioriLLM()
    return _llm_instance
