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
    
    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 1.0
    ) -> str:
        """
        Generate simple response (1-turn conversation).
        
        Args:
            system_prompt: System instruction (character definition)
            user_message: User's message
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
