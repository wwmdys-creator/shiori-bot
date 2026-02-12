"""
Summarizer module for Shiori bot.
Handles link extraction, web page fetching, and summary prompt building.
"""
import re
import aiohttp
from typing import List, Optional
from bs4 import BeautifulSoup


async def fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch web page content.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Page text content or None if fetch fails
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text
                text = soup.get_text()
                
                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                return text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text.
    
    Args:
        text: Text to extract URLs from
        
    Returns:
        List of extracted URLs
    """
    # URL pattern
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    urls = url_pattern.findall(text)
    return urls


def build_summary_prompt(url: str, content: str, max_length: int = 3000) -> str:
    """
    Build prompt for summarizing web page content.
    
    Args:
        url: Source URL
        content: Page content
        max_length: Maximum content length to include in prompt
        
    Returns:
        Formatted prompt for LLM
    """
    # Truncate content if too long
    if len(content) > max_length:
        content = content[:max_length] + "...\n(内容は省略されました)"
    
    prompt = f"""以下のウェブページを要約してください。

URL: {url}

内容:
{content}

以下の形式で要約してください：

📎 リンク要約
出典: [タイトル] ({url})
要点: ①... ②... ③...

要点は3つ以内で、簡潔に記述してください。
"""
    
    return prompt
