import sys
import os
import math

# Add bot folder to path
sys.path.append(os.path.dirname(__file__))

import cheat_detector as cd

def test_entropy():
    print("--- Testing Shannon Entropy Math ---")
    
    # Real looking usernames
    usernames_good = ["abdu_khamid", "dilshod_99", "nodir_bek", "sardor1995"]
    # Spam looking usernames (random chars)
    usernames_bad = ["asdfgh123jh", "qwer1234tyui", "zxcvbnm123as", "a1b2c3d4e5f6"]
    
    for u in usernames_good:
        ent = cd.calculate_entropy(u)
        print(f"Good Username: '{u:<15}' -> Entropy: {ent:.2f} (Normalized Score: {min(1.0, ent/4.0):.2f})")
        
    for u in usernames_bad:
        ent = cd.calculate_entropy(u)
        print(f"Bad Username:  '{u:<15}' -> Entropy: {ent:.2f} (Normalized Score: {min(1.0, ent/4.0):.2f})")

def test_spam_sigmoid():
    print("\n--- Testing Spam Probability Sigmoid Math ---")
    
    # Simulating users
    # z = -3.0 + 2.5 * x_age + 2.0 * x_avatar + 1.5 * x_entropy
    # where x_age is calculated from Telegram ID (0.0 to 1.0)
    
    users = [
        {
            "name": "Old Real User (Old ID, has avatar, real username)",
            "tg_id": 350000000,
            "username": "dilshod_99",
            "has_avatar": True
        },
        {
            "name": "New Real User (New ID, has avatar, real username)",
            "tg_id": 8500000000,
            "username": "nodir_bek",
            "has_avatar": True
        },
        {
            "name": "Spambot (New ID, no avatar, random username)",
            "tg_id": 8600000000,
            "username": "asdfgh123jh",
            "has_avatar": False
        },
        {
            "name": "Suspicious User (New ID, no avatar, real username)",
            "tg_id": 8500000000,
            "username": "sardor1995",
            "has_avatar": False
        }
    ]
    
    for user in users:
        # Calculate features manually as in cheat_detector.py
        tg_id = user["tg_id"]
        username = user["username"]
        has_avatar = user["has_avatar"]
        
        # 1. Age
        x_age = min(1.0, max(0.0, (float(tg_id) - 1000000000.0) / 6000000000.0))
        # 2. Avatar
        x_avatar = 0.0 if has_avatar else 1.0
        # 3. Entropy
        ent = cd.calculate_entropy(username)
        x_entropy = min(1.0, ent / 4.0)
        
        # Sigmoid
        z = -3.0 + (2.5 * x_age) + (2.0 * x_avatar) + (1.5 * x_entropy)
        prob = 1.0 / (1.0 + math.exp(-z))
        
        print(f"User: {user['name']}")
        print(f"  ID Age Score: {x_age:.2f}, No Avatar Score: {x_avatar:.1f}, Entropy Score: {x_entropy:.2f}")
        print(f"  Calculated Logit Z: {z:.2f} -> Spam Probability: {prob*100:.1f}%")
        print(f"  Flagged as Spambot? {'🔴 YES (BANNED)' if prob > 0.70 else '🟢 NO (CLEAN)'}\n")

if __name__ == "__main__":
    test_entropy()
    test_spam_sigmoid()
