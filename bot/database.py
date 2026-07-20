import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

# Initialize client
client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Helper to run synchronous supabase functions in a threadpool
async def _run_async(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

# --- Settings Operations ---
def _get_settings_sync():
    res = client.table("settings").select("*").execute()
    return {row["key"]: row["value"] for row in res.data} if res.data else {}

async def get_settings():
    return await _run_async(_get_settings_sync)

def _get_setting_sync(key, default=None):
    res = client.table("settings").select("value").eq("key", key).execute()
    return res.data[0]["value"] if res.data else default

async def get_setting(key, default=None):
    return await _run_async(_get_setting_sync, key, default)

def _update_setting_sync(key, value):
    res = client.table("settings").upsert({"key": key, "value": str(value)}).execute()
    return res.data

async def update_setting(key, value):
    return await _run_async(_update_setting_sync, key, value)

# --- User Operations ---
def _get_user_sync(tg_id):
    res = client.table("users").select("*").eq("telegram_id", tg_id).execute()
    return res.data[0] if res.data else None

async def get_user(tg_id):
    return await _run_async(_get_user_sync, tg_id)

def _create_user_sync(tg_id, username, first_name, referrer_id=None, avatar_exists=False, username_entropy=0.0, cheat_score=0.0, is_verified=False):
    # Ensure referrer exists in DB
    ref_id = None
    if referrer_id:
        ref_exists = client.table("users").select("telegram_id").eq("telegram_id", referrer_id).execute()
        if ref_exists.data:
            ref_id = referrer_id

    data = {
        "telegram_id": tg_id,
        "username": username,
        "first_name": first_name,
        "referred_by": ref_id,
        "avatar_exists": avatar_exists,
        "username_entropy": username_entropy,
        "cheat_score": cheat_score,
        "is_verified": is_verified,
        "points": 0,
        "is_banned": False
    }
    res = client.table("users").insert(data).execute()
    return res.data[0] if res.data else None

async def create_user(tg_id, username, first_name, referrer_id=None, avatar_exists=False, username_entropy=0.0, cheat_score=0.0, is_verified=False):
    return await _run_async(_create_user_sync, tg_id, username, first_name, referrer_id, avatar_exists, username_entropy, cheat_score, is_verified)

def _update_user_sync(tg_id, **kwargs):
    # Map FSM status to database column
    if "status" in kwargs:
        status = kwargs.pop("status")
        kwargs["is_banned"] = (status == "banned")
    if "referrer_id" in kwargs:
        kwargs["referred_by"] = kwargs.pop("referrer_id")
        
    res = client.table("users").update(kwargs).eq("telegram_id", tg_id).execute()
    return res.data[0] if res.data else None

async def update_user(tg_id, **kwargs):
    return await _run_async(_update_user_sync, tg_id, **kwargs)

def _get_leaderboard_sync(limit=10):
    res = client.table("users").select("username, first_name, points").eq("is_banned", False).order("points", desc=True).limit(limit).execute()
    return res.data or []

async def get_leaderboard(limit=10):
    return await _run_async(_get_leaderboard_sync, limit)

def _get_referrer_count_sync(tg_id):
    # Count verified referrals
    res = client.table("users").select("telegram_id", count="exact").eq("referred_by", tg_id).eq("is_verified", True).execute()
    return res.count if hasattr(res, 'count') else len(res.data)

async def get_referrer_count(tg_id):
    return await _run_async(_get_referrer_count_sync, tg_id)

# --- Channel Operations (Force Subscribe) ---
def _get_active_channels_sync():
    res = client.table("channels").select("*").execute()
    return res.data or []

async def get_active_channels():
    return await _run_async(_get_active_channels_sync)

def _add_channel_sync(tg_id, title, invite_link, creates_join_request=True):
    data = {
        "tg_id": tg_id,
        "title": title,
        "invite_link": invite_link,
        "creates_join_request": creates_join_request
    }
    res = client.table("channels").insert(data).execute()
    return res.data[0] if res.data else None

async def add_channel(tg_id, title, invite_link, creates_join_request=True):
    return await _run_async(_add_channel_sync, tg_id, title, invite_link, creates_join_request)

def _delete_channel_sync(channel_id):
    res = client.table("channels").delete().eq("id", channel_id).execute()
    return res.data

async def delete_channel(channel_id):
    return await _run_async(_delete_channel_sync, channel_id)

def _delete_channel_by_tg_id_sync(tg_id):
    res = client.table("channels").delete().eq("tg_id", tg_id).execute()
    return res.data

async def delete_channel_by_tg_id(tg_id):
    return await _run_async(_delete_channel_by_tg_id_sync, tg_id)

# --- Withdrawal Operations ---
def _create_withdrawal_sync(tg_id, wallet, amount):
    data = {
        "tg_id": tg_id,
        "wallet": wallet,
        "amount": amount,
        "status": "pending"
    }
    res = client.table("withdrawals").insert(data).execute()
    return res.data[0] if res.data else None

async def create_withdrawal(tg_id, wallet, amount):
    return await _run_async(_create_withdrawal_sync, tg_id, wallet, amount)

def _get_withdrawal_sync(withdrawal_id):
    res = client.table("withdrawals").select("*").eq("id", withdrawal_id).execute()
    return res.data[0] if res.data else None

async def get_withdrawal(withdrawal_id):
    return await _run_async(_get_withdrawal_sync, withdrawal_id)

def _update_withdrawal_status_sync(withdrawal_id, status):
    res = client.table("withdrawals").update({"status": status}).eq("id", withdrawal_id).execute()
    return res.data[0] if res.data else None

async def update_withdrawal_status(withdrawal_id, status):
    return await _run_async(_update_withdrawal_status_sync, withdrawal_id, status)

# --- Admin Operations (Stats, Reset, Export) ---
def _get_statistics_sync():
    users_res = client.table("users").select("is_banned, is_verified, referral_count, points").execute()
    
    total_users = len(users_res.data) if users_res.data else 0
    verified_users = sum(1 for u in users_res.data if u["is_verified"]) if users_res.data else 0
    banned_users = sum(1 for u in users_res.data if u["is_banned"]) if users_res.data else 0
    
    # Fetch threshold
    th_res = client.table("settings").select("value").eq("key", "referral_threshold").execute()
    threshold = int(th_res.data[0]["value"]) if th_res.data else 5
    
    course_unlocked = 0
    if users_res.data:
        for u in users_res.data:
            ref_c = u.get("referral_count") or 0
            pts = u.get("points") or 0
            if ref_c >= threshold or pts >= threshold:
                course_unlocked += 1
                
    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "banned_users": banned_users,
        "course_unlocked_users": course_unlocked
    }

async def get_statistics():
    return await _run_async(_get_statistics_sync)

def _get_all_users_sync():
    res = client.table("users").select("*").execute()
    return res.data or []

async def get_all_users():
    return await _run_async(_get_all_users_sync)

def _reset_contest_sync():
    # Set points = 0, remove referrer relationships, remove withdrawals, unverify users
    client.table("withdrawals").delete().neq("id", 0).execute()
    client.table("users").update({"points": 0, "referred_by": None, "is_verified": False}).neq("telegram_id", 0).execute()
    return True

async def reset_contest():
    return await _run_async(_reset_contest_sync)
