import math
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)

def calculate_entropy(text: str) -> float:
    """
    Calculates the Shannon Entropy of a string to detect random character sequences.
    """
    if not text:
        return 0.0
    
    # Calculate frequency of each character
    frequencies = {}
    for char in text:
        frequencies[char] = frequencies.get(char, 0) + 1
        
    # Calculate Shannon Entropy
    entropy = 0.0
    length = len(text)
    for count in frequencies.values():
        p = count / length
        entropy -= p * math.log2(p)
        
    return entropy

async def evaluate_user_cheat_score(bot: Bot, tg_id: int, username: str) -> dict:
    """
    Evaluates a user profile. Disabled/bypassed as requested by the user.
    """
    return {
        "avatar_exists": True,
        "username_entropy": 0.0,
        "cheat_score": 0.0,
        "is_cheat": False
    }
