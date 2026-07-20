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
    Evaluates a user profile to calculate a cheat/bot score using Logistic Regression.
    
    Features:
    1. Account Age (approximated from sequential TG ID ranges)
    2. Profile Photo (avatar existence)
    3. Username Character Entropy (gibberish detector)
    
    Returns:
    dict: {
        "avatar_exists": bool,
        "username_entropy": float,
        "cheat_score": float,
        "is_cheat": bool
    }
    """
    # 1. Feature: Account Age from ID
    # Old IDs (e.g. < 1B) are safe (x_age = 0.0)
    # New IDs (e.g. > 7B) are risky (x_age = 1.0)
    # Between 1B and 7B scales linearly
    id_val = float(tg_id)
    x_age = min(1.0, max(0.0, (id_val - 1000000000.0) / 6000000000.0))
    
    # 2. Feature: Profile Photo existence
    avatar_exists = False
    x_avatar = 1.0  # Default: No avatar is a risk indicator
    try:
        photos = await bot.get_user_profile_photos(user_id=tg_id, limit=1)
        if photos and photos.total_count > 0:
            avatar_exists = True
            x_avatar = 0.0
    except Exception as e:
        logger.warning(f"Failed to check profile photos for {tg_id}: {e}")
        # If API check fails, we assume no avatar or keep neutral (0.5)
        x_avatar = 0.5

    # 3. Feature: Username Entropy
    entropy = 0.0
    if username:
        entropy = calculate_entropy(username)
        # Max entropy for a typical 15-char string is ~3.9
        # Normalize to 0.0 - 1.0 range
        x_entropy = min(1.0, entropy / 4.0)
    else:
        # No username: moderately risky for spam bots (but normal for some users)
        x_entropy = 0.7
        
    # Logistic Regression Formula
    # Weights:
    # beta_0 (bias): -3.0
    # beta_1 (new ID age): 2.5
    # beta_2 (no avatar): 2.0
    # beta_3 (entropy): 1.5
    beta_0 = -3.0
    beta_1 = 2.5
    beta_2 = 2.0
    beta_3 = 1.5
    
    z = beta_0 + (beta_1 * x_age) + (beta_2 * x_avatar) + (beta_3 * x_entropy)
    
    # Sigmoid function
    try:
        cheat_score = 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        cheat_score = 0.0 if z < 0 else 1.0
        
    # If the probability is greater than 0.70, flag as a cheat
    is_cheat = cheat_score > 0.70
    
    return {
        "avatar_exists": avatar_exists,
        "username_entropy": round(entropy, 2),
        "cheat_score": round(cheat_score, 4),
        "is_cheat": is_cheat
    }
