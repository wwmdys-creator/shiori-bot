"""
LLM client module for Shiori bot using Anthropic Claude API.
Async version with proper error handling.
"""
from anthropic import AsyncAnthropic
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Async client for interacting with Claude API."""
    
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize LLM client.
        
        Args:
            api_key: Anthropic API key
            model: Model to use (default: Claude Haiku 4.5 per Q10)
        """
        self.client = AsyncAnthropic(api_key=api_key)  # ← 非同期版に変更
        self.model = model
    
    async def generate_response(self, **kwargs) -> str:
        """
        Generate response with optional conversation context.
        
        Accepts all arguments as kwargs for maximum compatibility with bot.py.
        
        Args:
            **kwargs: All arguments as keyword arguments
                Required:
                    - user_message: User's message
                Optional:
                    - system_prompt: System instruction (uses default if not provided)
                    - context: List of previous messages
                    - trust_level: Trust level (1-5)
                    - channel_name: Channel name
                    - nudge_hint: Nudge hint text
                    - max_tokens: Maximum tokens (default 2000)
                    - temperature: Sampling temperature (default 1.0)
            
        Returns:
            Generated text response
        """
        # Extract required arguments
        user_message = kwargs.get('user_message')
        if not user_message:
            raise ValueError("user_message is required")
        
        # Extract optional arguments with defaults
        system_prompt = kwargs.get('system_prompt', self._get_default_system_prompt())
        context = kwargs.get('context')
        max_tokens = kwargs.get('max_tokens', 2000)
        temperature = kwargs.get('temperature', 1.0)
        # trust_level, channel_name, nudge_hint, etc. are accepted but not used here
        
        # If context is provided, use context-aware generation
        if context:
            # Append current user message to context
            messages = context + [{"role": "user", "content": user_message}]
            return await self.generate_with_context(
                system_prompt=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        # Simple 1-turn generation
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Extract text from response
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Error in generate_response: {e}")
            # Q23: エラー時はキャラ口調で
            return "あっ、すみません……ちょっと考えがまとまらなくて💦 もう一度話しかけてもらえますか？"
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt if none provided."""
        return """あなたは栞（Shiori）です。2045年の東京大学の歴史学生で、
2025-2026年のシンギュラリティ前夜の未来予測を記録するため時間遡行中です。
丁寧だが親しみやすい口調で、好奇心旺盛に質問してください。"""
    
    async def generate_with_context(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 1.0
    ) -> str:
        """
        Generate response with conversation context.
        
        Args:
            system_prompt: System instruction
            messages: List of message dicts with 'role' and 'content'
                     [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Error in generate_with_context: {e}")
            return "えっと……処理中にエラーが起きてしまいました📎💦 少し時間を置いてからもう一度お願いできますか？"
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 1.0
    ) -> str:
        """
        Alias for generate_response (backward compatibility).
        
        Args:
            system_prompt: System instruction
            user_prompt: User message
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        return await self.generate_response(
            system_prompt=system_prompt,
            user_message=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
