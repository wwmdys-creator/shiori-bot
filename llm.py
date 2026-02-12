"""
LLM client module for Shiori bot using Anthropic Claude API.
"""
import os
from anthropic import Anthropic


class LLMClient:
    """Client for interacting with Claude API."""
    
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize LLM client.
        
        Args:
            api_key: Anthropic API key
            model: Model to use (default: Claude Haiku 4.5)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        temperature: float = 1.0
    ) -> str:
        """
        Generate response from Claude.
        
        Args:
            system_prompt: System instruction
            user_prompt: User message
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Extract text from response
            return message.content[0].text
            
        except Exception as e:
            print(f"Error generating response: {e}")
            raise
    
    def generate_with_context(
        self,
        system_prompt: str,
        messages: list,
        max_tokens: int = 2000,
        temperature: float = 1.0
    ) -> str:
        """
        Generate response with conversation context.
        
        Args:
            system_prompt: System instruction
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"Error generating response with context: {e}")
            raise
