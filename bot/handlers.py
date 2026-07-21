import os
import csv
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, CallbackQuery, ChatJoinRequest,
    InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import cheat_detector as cd
from rate_limiter import rate_limiter

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
PRIVATE_CHANNEL_ID = int(os.environ.get("PRIVATE_CHANNEL_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# Custom Premium Emoji IDs (User provided)
EMOJI_REYTING = "5226431245918942763"
EMOJI_KURSGA_KIRISH = "5278573677900752088"
EMOJI_DOSTLARNI_TAKLIF_QILISH = "5332724926216428039"
EMOJI_TAKLIF_HAVOLASI = "5118489535130371328"

# Custom Premium Emoji IDs (Fallbacks)
EMOJI_STAR = "5438341604928232974"       # Star icon
EMOJI_CHECK = "5438341604928232975"      # Green check
EMOJI_ALERT = "5438341604928232976"      # Warning/Danger
EMOJI_REWARD = "5438341604928232977"     # Gift box
EMOJI_LEADER = "5438341604928232978"     # Trophy
EMOJI_WALLET = "5438341604928232979"     # Wallet

# --- FSM States ---
class Form(StatesGroup):
    # Admin States
    waiting_for_channel_id = State()
    waiting_for_channel_title = State()
    waiting_for_channel_link = State()
    waiting_for_broadcast = State()

# --- Keyboard Builders (App-Like Edit-in-Place UX) ---
async def check_user_subscriptions(bot: Bot, user_id: int) -> list:
    channels = await db.get_active_channels()
    unsubscribed = []
    
    for ch in channels:
        ch_tg_id = ch["tg_id"]
        try:
            member = await bot.get_chat_member(chat_id=ch_tg_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                unsubscribed.append(ch)
        except Exception as e:
            logger.warning(f"Could not check membership in {ch_tg_id} for user {user_id}: {e}")
            unsubscribed.append(ch)
            
    return unsubscribed

async def enforce_subscription(callback: CallbackQuery, bot: Bot) -> bool:
    """
    Checks subscription and edits the message if user is unsubscribed.
    Returns True if unsubscribed (and handled), False if fully subscribed.
    """
    user_id = callback.from_user.id
    unsubscribed = await check_user_subscriptions(bot, user_id)
    if unsubscribed:
        await db.update_user(user_id, is_verified=False)
        kb = await get_subscription_keyboard(bot, user_id)
        await callback.message.edit_text(
            text=(
                "⚠️ <b>Botdan foydalanish uchun homiy kanallarga obuna bo'lishingiz lozim:</b>\n\n"
                "Siz a'zo bo'lmagan kanallar 🔴 rangda, a'zo bo'lganlaringiz esa 🟢 rangda ko'rsatilgan. "
                "Barcha kanallarga a'zo bo'lib, keyin <b>Obunani tekshirish</b> tugmasini bosing. 👇"
            ),
            parse_mode="HTML",
            reply_markup=kb
        )
        return True
    return False

async def get_subscription_keyboard(bot: Bot, user_id: int):
    channels = await db.get_active_channels()
    buttons = []
    
    unsubscribed = await check_user_subscriptions(bot, user_id)
    unsubscribed_ids = {ch["tg_id"] for ch in unsubscribed}
    
    # 1. Join buttons (style="danger" if unsubscribed, style="success" if subscribed)
    for idx, ch in enumerate(channels):
        title = ch.get("title", f"Kanal #{idx+1}")
        url = ch.get("invite_link", "")
        ch_tg_id = ch["tg_id"]
        
        if ch_tg_id in unsubscribed_ids:
            btn_style = "danger"
        else:
            btn_style = "success"
            
        buttons.append([
            InlineKeyboardButton(
                text=title,
                url=url,
                style=btn_style
            )
        ])
        
    # 2. Verify subscription button (Blue style)
    buttons.append([
        InlineKeyboardButton(
            text="Obunani tekshirish",
            callback_data="check_subs",
            style="primary",
            icon_custom_emoji_id=EMOJI_CHECK
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_main_menu_keyboard(user_id: int):
    is_admin = user_id in ADMIN_IDS
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="Do'stlarni taklif qilish",
                callback_data="menu_referral",
                style="primary",
                icon_custom_emoji_id=EMOJI_DOSTLARNI_TAKLIF_QILISH
            )
        ],
        [
            InlineKeyboardButton(
                text="Reyting",
                callback_data="menu_leaderboard",
                style="danger",
                icon_custom_emoji_id=EMOJI_REYTING
            ),
            InlineKeyboardButton(
                text="Kursga kirish",
                callback_data="menu_course",
                style="success",
                icon_custom_emoji_id=EMOJI_KURSGA_KIRISH
            )
        ]
    ]
    
    if is_admin:
        keyboard.append([
            InlineKeyboardButton(
                text="Admin Panel",
                callback_data="admin_menu",
                style="primary",
                icon_custom_emoji_id=EMOJI_STAR
            )
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_keyboard(callback_target="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Ortga",
                callback_data=callback_target,
                style="primary",
                icon_custom_emoji_id=EMOJI_ALERT
            )
        ]
    ])

# --- Start Handler ---
@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(user_id, action="start")
    if not rl["allowed"]:
        if rl["temp_banned"]:
            await message.answer(rl["reason"])
        else:
            # Silent ignore for normal cooldown (don't spam back)
            logger.info(f"Rate limited /start from user {user_id} (retry in {rl['retry_after']:.1f}s)")
        return
    
    referrer_id = None
    if command.args:
        try:
            arg_ref = int(command.args)
            if arg_ref != user_id:
                referrer_id = arg_ref
        except ValueError:
            pass

    user = await db.get_user(user_id)
    
    if not user:
        # Calculate cheat scoring properties
        cd_info = await cd.evaluate_user_cheat_score(bot, user_id, username)
        
        # Save to database
        user = await db.create_user(
            tg_id=user_id,
            username=username,
            first_name=first_name,
            referrer_id=referrer_id,
            avatar_exists=cd_info["avatar_exists"],
            username_entropy=cd_info["username_entropy"],
            cheat_score=cd_info["cheat_score"],
            is_verified=False
        )
        
        if cd_info["is_cheat"]:
            # Auto-ban
            await db.update_user(user_id, status="banned")
            logger.warning(f"User {user_id} automatically banned due to high spam probability: {cd_info['cheat_score']}")
            await message.answer("⚠️ Tizim xavfsizlik filtri tomonidan shubhali faollik aniqlandi. Ruxsat berilmadi.")
            return

    # Check if they are banned
    if user["is_banned"]:
        await message.answer("⚠️ Siz ushbu botdan foydalanishdan chetlatilgansiz.")
        return

    # Check current subscription status
    unsubscribed = await check_user_subscriptions(bot, user_id)
    
    if unsubscribed:
        # If they were verified before but left the channels, reset their verification status
        if user["is_verified"]:
            await db.update_user(user_id, is_verified=False)
            
        kb = await get_subscription_keyboard(bot, user_id)
        await message.answer(
            text=(
                f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
                f"⚠️ <b>Botdan to'liq foydalanish uchun homiy kanallarga obuna bo'lishingiz lozim:</b>\n\n"
                f"Siz a'zo bo'lmagan kanallar 🔴 rangda, a'zo bo'lganlaringiz esa 🟢 rangda ko'rsatilgan. "
                f"Barcha kanallarga a'zo bo'lib, keyin <b>Obunani tekshirish</b> tugmasini bosing. 👇"
            ),
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        # User is subscribed to all channels. If not verified in DB, verify them now.
        if not user["is_verified"]:
            await db.update_user(user_id, is_verified=True)
            
            # Award referrer if any
            if user["referred_by"]:
                ref_id = user["referred_by"]
                referrer = await db.get_user(ref_id)
                if referrer and not referrer["is_banned"]:
                    pts_per_ref = int(await db.get_setting("points_per_referral", 1))
                    new_points = referrer["points"] + pts_per_ref
                    new_ref_count = (referrer.get("referral_count") or 0) + 1
                    await db.update_user(ref_id, points=new_points, referral_count=new_ref_count)
                    
                    # Notify referrer
                    try:
                        await bot.send_message(
                            chat_id=ref_id,
                            text=f"🎉 Tabriklaymiz! Siz taklif qilgan {first_name} obunalarni tasdiqladi.\nSizning takliflaringiz soni +1 ga oshdi! Hozirgi takliflaringiz soni: {new_ref_count} ta."
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify referrer {ref_id}: {e}")

        # Show Main Menu with referral link directly
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        kb = await get_main_menu_keyboard(user_id)
        await message.answer(
            text=(
                f"👋 <b>Assalomu alaykum, {first_name}!</b>\n\n"
                f"Bizning botga xush kelibsiz! Bu yerda do'stlaringizni taklif qilib, yopiq kursimizga mutlaqo <b>bepul</b> kirish huquqini qo'lga kiritishingiz mumkin. ✨\n\n"
                f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
                f"<i>💡 Havolani do'stlaringizga yuboring. Ular botga kirib, homiy kanallarga obuna bo'lishsa, sizga ball yoziladi.</i>\n\n"
                f"👇 Quyidagi menyudan kerakli bo'limni tanlang:"
            ),
            parse_mode="HTML",
            reply_markup=kb
        )

# --- ChatJoinRequest Handler (Bot API 10.1) ---
@router.chat_join_request()
async def handle_join_request(request: ChatJoinRequest, bot: Bot):
    user_id = request.from_user.id
    username = request.from_user.username
    chat_id = request.chat.id
    
    logger.info(f"Received Join Request from {user_id} (@{username}) for chat {chat_id}")
    
    cd_info = await cd.evaluate_user_cheat_score(bot, user_id, username)
    
    if cd_info["is_cheat"]:
        try:
            await bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
            logger.info(f"Declined join request from cheat/bot user {user_id} for channel {chat_id}")
        except Exception as e:
            logger.error(f"Error declining join request: {e}")
    else:
        # Load private channel ID from settings
        db_chan_id = await db.get_setting("private_channel_id")
        target_channel_id = None
        if db_chan_id:
            try:
                target_channel_id = int(db_chan_id.strip())
            except ValueError:
                pass
        
        # Check if this join request is for the private course channel
        if target_channel_id and chat_id == target_channel_id:
            user = await db.get_user(user_id)
            threshold = int(await db.get_setting("referral_threshold", 5))
            
            effective_count = 0
            if user:
                referral_count = user.get("referral_count") or 0
                points = user.get("points", 0)
                effective_count = max(referral_count, points)
                
            if user and not user["is_banned"] and effective_count >= threshold:
                try:
                    await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                    logger.info(f"Approved private course channel join request for user {user_id} ({effective_count}/{threshold} referrals)")
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🎉 <b>Arizangiz tasdiqlandi!</b>\n\n"
                            f"Siz yopiq kurs kanaliga muvaffaqiyatli qo'shildingiz. "
                            f"Taklif qilgan do'stlaringiz soni: <b>{effective_count} ta</b>."
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error approving course join request: {e}")
            else:
                try:
                    await bot.decline_chat_join_request(chat_id=chat_id, user_id=user_id)
                    logger.info(f"Declined private course channel join request for user {user_id} ({effective_count}/{threshold} referrals)")
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"❌ <b>Arizangiz rad etildi!</b>\n\n"
                            f"Yopiq kurs kanaliga kirish uchun sizda yetarli takliflar mavjud emas.\n"
                            f"Sizda: <b>{effective_count} ta</b> (Talab etiladi: {threshold} ta).\n\n"
                            f"Iltimos, do'stlaringizni taklif qiling va havolani bajargach qayta urinib ko'ring!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error declining course join request: {e}")
        else:
            # Regular Force Subscribe sponsor channel auto-approval
            try:
                await bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
                logger.info(f"Approved join request from verified user {user_id} for channel {chat_id}")
                
                user = await db.get_user(user_id)
                if not user:
                    await db.create_user(
                        tg_id=user_id,
                        username=username,
                        first_name=request.from_user.first_name,
                        avatar_exists=cd_info["avatar_exists"],
                        username_entropy=cd_info["username_entropy"],
                        cheat_score=cd_info["cheat_score"],
                        is_verified=False
                    )
            except Exception as e:
                logger.error(f"Error approving join request: {e}")

# --- Callback Queries ---

@router.callback_query(F.data == "check_subs")
async def callback_check_subs(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(user_id, action="callback")
    if not rl["allowed"]:
        if rl["temp_banned"]:
            await callback.answer(rl["reason"], show_alert=True)
        else:
            await callback.answer(rl["reason"], show_alert=False)
        return
    
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi. Qayta /start bosing.", show_alert=True)
        return
        
    if user["is_banned"]:
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return

    # Check subscriptions
    unsubscribed = await check_user_subscriptions(bot, user_id)
            
    if unsubscribed:
        unsub_names = ", ".join([c["title"] for c in unsubscribed])
        await callback.answer(f"Siz hali barcha kanallarga a'zo bo'lmadingiz: {unsub_names}", show_alert=True)
        kb = await get_subscription_keyboard(bot, user_id)
        await callback.message.edit_reply_markup(reply_markup=kb)
        return

    await callback.answer("Obunalar tasdiqlandi! 🎉", show_alert=False)
    
    if not user["is_verified"]:
        await db.update_user(user_id, is_verified=True)
        
        # Award referrer if any
        if user["referred_by"]:
            ref_id = user["referred_by"]
            referrer = await db.get_user(ref_id)
            if referrer and not referrer["is_banned"]:
                pts_per_ref = int(await db.get_setting("points_per_referral", 1))
                new_points = referrer["points"] + pts_per_ref
                new_ref_count = (referrer.get("referral_count") or 0) + 1
                await db.update_user(ref_id, points=new_points, referral_count=new_ref_count)
                
                # Notify referrer
                try:
                    await bot.send_message(
                        chat_id=ref_id,
                        text=f"🎉 Tabriklaymiz! Siz taklif qilgan {callback.from_user.first_name} obunalarni tasdiqladi.\nSizning takliflaringiz soni +1 ga oshdi! Hozirgi takliflaringiz soni: {new_ref_count} ta."
                    )
                except Exception as e:
                    logger.warning(f"Could not notify referrer {ref_id}: {e}")

    # Show main menu along with their referral link directly in the message!
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    kb = await get_main_menu_keyboard(user_id)
    await callback.message.edit_text(
        text=(
            f"🎉 <b>A'zoligingiz muvaffaqiyatli tasdiqlandi!</b> Botimizga xush kelibsiz.\n\n"
            f"🔗 <b>Sizning taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
            f"Ushbu havolani do'stlaringizga ulashing. Havolani nusxalash uchun ustiga bosing!"
        ),
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(user_id, action="callback")
    if not rl["allowed"]:
        if rl["temp_banned"]:
            await callback.answer(rl["reason"], show_alert=True)
        else:
            await callback.answer(rl["reason"], show_alert=False)
        return
    
    await state.clear()
    if await enforce_subscription(callback, bot):
        return
        
    user_id = callback.from_user.id
    kb = await get_main_menu_keyboard(user_id)
    await callback.message.edit_text(
        text="Asosiy menyuga xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=kb
    )

@router.callback_query(F.data == "menu_referral")
async def callback_referral(callback: CallbackQuery, bot: Bot):
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(callback.from_user.id, action="callback")
    if not rl["allowed"]:
        await callback.answer(rl["reason"], show_alert=rl["temp_banned"])
        return
    
    if await enforce_subscription(callback, bot):
        return
        
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    ref_count = await db.get_referrer_count(user_id)
    
    from urllib.parse import quote
    sharing_text = await db.get_setting("sharing_text", "Zuhra Olimova • Har bir qiz o‘z multfilmini yarata oladi! Bot orqali ro'yxatdan o'ting va yopiq darslarga bepul kiring:")
    share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote(sharing_text)}"
    
    text = (
        f"👥 <b>Do'stlarni Taklif Qilish Tizimi</b>\n\n"
        f"Do'stlaringizni botimizga taklif qiling va yopiq darslarga bepul kirish imkoniyatini qo'lga kiriting!\n\n"
        f"📊 <b>Sizning ko'rsatkichlaringiz:</b>\n"
        f"└ Taklif etilgan faol do'stlaringiz: <b>{ref_count} ta</b>\n\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<i>💡 Ustiga bossangiz havolani nusxalaydi. Do'stlaringizga yoki guruhlarga pastdagi ko'k tugma orqali osongina yuborishingiz mumkin.</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Do'stlarni taklif qilish",
                url=share_url,
                style="primary",
                icon_custom_emoji_id=EMOJI_TAKLIF_HAVOLASI
            )
        ],
        [
            InlineKeyboardButton(
                text="Ortga",
                callback_data="main_menu",
                style="primary"
            )
        ]
    ])
    
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

def mask_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if not text:
        return ""
    parts = text.split()
    masked_parts = []
    for part in parts:
        length = len(part)
        if length <= 2:
            masked_parts.append(part[0] + "*" if length > 0 else "")
        elif length == 3:
            masked_parts.append(part[0] + "*" + part[2])
        elif length == 4:
            masked_parts.append(part[0] + "**" + part[3])
        else:
            masked_parts.append(part[:2] + "***" + part[-1])
    return " ".join(masked_parts)

@router.callback_query(F.data == "menu_leaderboard")
async def callback_leaderboard(callback: CallbackQuery, bot: Bot):
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(callback.from_user.id, action="callback")
    if not rl["allowed"]:
        await callback.answer(rl["reason"], show_alert=rl["temp_banned"])
        return
    
    if await enforce_subscription(callback, bot):
        return
        
    leaderboard = await db.get_leaderboard(10)
    
    text = (
        f"🏆 <b>Reyting Jadvali (TOP 10)</b>\n"
        f"Eng ko'p do'st taklif qilgan faol ishtirokchilar ro'yxati:\n\n"
    )
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    if not leaderboard:
        text += "<i>Hozircha faol ishtirokchilar mavjud emas. Birinchilardan bo'ling!</i>"
    else:
        for idx, row in enumerate(leaderboard):
            medal = medals[idx] if idx < len(medals) else f"•"
            name = row.get("first_name", "Ishtirokchi")
            masked_name = mask_text(name)
            masked_name = masked_name.replace("<", "&lt;").replace(">", "&gt;")
            
            raw_username = row.get("username")
            username_str = f" (@{mask_text(raw_username)})" if raw_username else ""
            points = row.get("points", 0)
            text += f"{medal} <b>{masked_name}</b>{username_str} — <b>{points}</b> ta taklif\n"
            
    text += f"\n\n👥 <i>Siz ham do'stlaringizni taklif qilib, reyting tepasiga ko'tariling!</i>"
            
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "menu_course")
async def callback_course(callback: CallbackQuery, bot: Bot):
    # --- Rate Limit Check ---
    rl = rate_limiter.check_rate_limit(callback.from_user.id, action="callback")
    if not rl["allowed"]:
        await callback.answer(rl["reason"], show_alert=rl["temp_banned"])
        return
    
    if await enforce_subscription(callback, bot):
        return
        
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    referral_count = user.get("referral_count") or 0
    points = user.get("points", 0)
    effective_count = max(referral_count, points)
    threshold = int(await db.get_setting("referral_threshold", 5))
    
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    if effective_count >= threshold:
        # Load the direct invite link configured in settings
        fallback_link = await db.get_setting("private_channel_link")
        if fallback_link:
            text = (
                f"🎉 <b>Tabriklaymiz! Kursga bepul kirish imkoniyatingiz ochildi!</b>\n\n"
                f"Siz muvaffaqiyatli taklif qildingiz: <b>{effective_count} / {threshold}</b> ta do'st.\n\n"
                f"👇 Kursni boshlash uchun pastdagi yashil tugmani bosing va kanalga a'zo bo'lish so'rovini yuboring (Request to join):"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Kursga kirish",
                        url=fallback_link,
                        style="success",
                        icon_custom_emoji_id=EMOJI_KURSGA_KIRISH
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Ortga",
                        callback_data="main_menu",
                        style="primary"
                    )
                ]
            ])
        else:
            text = (
                f"🎉 <b>Tabriklaymiz! Siz yopiq kanalga kirish huquqini qo'lga kiritdingiz!</b>\n\n"
                f"Siz taklif qildingiz: <b>{effective_count} / {threshold}</b> ta do'st.\n\n"
                f"⚠️ Hozircha yopiq kanal havolasi sozlanmagan. Iltimos, administratorga xabar bering."
            )
            keyboard = get_back_keyboard()
    else:
        from urllib.parse import quote
        sharing_text = await db.get_setting("sharing_text", "Zuhra Olimova • Har bir qiz o‘z multfilmini yarata oladi! Bot orqali ro'yxatdan o'ting va yopiq darslarga bepul kiring:")
        share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote(sharing_text)}"
        
        text = (
            f"🔒 <b>Kurs yopiq kanalda joylashgan!</b>\n\n"
            f"Kursga kirish uchun siz kamida <b>{threshold} ta</b> do'stingizni taklif qilishingiz zarur.\n\n"
            f"📊 <b>Sizning ko'rsatkichlaringiz:</b>\n"
            f"├ Taklif etilgan faol a'zolar: <b>{effective_count} ta</b>\n"
            f"└ Kursni ochish uchun yana: <b>{threshold - effective_count} ta</b> taklif kerak\n\n"
            f"🔗 <b>Sizning taklif havolangiz:</b>\n<code>{ref_link}</code>\n\n"
            f"Do'stlaringizni taklif qiling va kursga bepul kirish huquqini qo'lga kiriting!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Do'stlarni taklif qilish",
                    url=share_url,
                    style="primary",
                    icon_custom_emoji_id=EMOJI_TAKLIF_HAVOLASI
                )
            ],
            [
                InlineKeyboardButton(
                    text="Ortga",
                    callback_data="main_menu",
                    style="primary"
                )
            ]
        ])
        
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# --- Admin Panel Handlers ---

@router.callback_query(F.data == "admin_menu")
async def callback_admin_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("Sizga bu bo'lim taqiqlangan.", show_alert=True)
        return
        
    text = "🛠 <b>ADMINISTRATOR BOSHQARUV PANELI:</b>"
    
    buttons = [
        [
            InlineKeyboardButton(text="📊 Real-Vaqt Tahlili (Stats)", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Xabar yuborish (Broadcast)", callback_data="admin_broadcast_prompt")
        ],
        [
            InlineKeyboardButton(text="📢 Kanallarni Boshqarish", callback_data="admin_channels"),
            InlineKeyboardButton(text="📥 CSV Yuklab olish (Export)", callback_data="admin_export_csv")
        ],
        [
            InlineKeyboardButton(text="🔄 Konkursni nolga tushirish (Reset)", callback_data="admin_reset_prompt", style="danger")
        ],
        [
            InlineKeyboardButton(text="⬅️ Asosiy Menyu", callback_data="main_menu")
        ]
    ]
    
    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    stats = await db.get_statistics()
    rl_stats = rate_limiter.get_stats()
    
    text = (
        f"📊 <b>BOTNING REAL-VAQT STATISTIKASI:</b>\n\n"
        f"👥 Ro'yxatdan o'tgan foydalanuvchilar: <b>{stats['total_users']} ta</b>\n"
        f"✅ Tasdiqlangan faol ishtirokchilar: <b>{stats['verified_users']} ta</b>\n"
        f"🚫 Cheat sababli bloklanganlar: <b>{stats['banned_users']} ta</b>\n"
        f"🔑 Kursga kirish huquqini ochganlar: <b>{stats['course_unlocked_users']} ta</b>\n\n"
        f"🛡 <b>Anti-Spam Himoyasi:</b>\n"
        f"👁 Kuzatilayotgan foydalanuvchilar: <b>{rl_stats['tracked_users']}</b>\n"
        f"⚠️ Faol qoidabuzarliklar: <b>{rl_stats['active_violations']}</b>\n"
        f"⛔ Vaqtincha bloklangan: <b>{rl_stats['temp_banned_users']} ta</b>"
    )
    
    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=get_back_keyboard("admin_menu"))

@router.callback_query(F.data == "admin_channels")
async def callback_admin_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    channels = await db.get_active_channels()
    
    text = "📢 <b>Majburiy A'zolik Kanallari Ro'yxati:</b>\n\n"
    buttons = []
    
    if not channels:
        text += "Hozircha hech qanday kanal majburiy qilib belgilanmagan."
    else:
        for ch in channels:
            req_type = "Join Request" if ch.get("creates_join_request") else "Normal"
            text += f"• <b>{ch['title']}</b> (ID: {ch['tg_id']}, link: {ch['invite_link']}, tur: {req_type})\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ O'chirish: {ch['title']}",
                    callback_data=f"admin_del_channel:{ch['id']}",
                    style="danger"
                )
            ])
            
    buttons.append([
        InlineKeyboardButton(text="➕ Yangi Kanal Qo'shish", callback_data="admin_add_channel_prompt", style="success")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Admin Panelga", callback_data="admin_menu")
    ])
    
    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("admin_del_channel:"))
async def callback_admin_del_channel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    ch_id = int(callback.data.split(":")[1])
    await db.delete_channel(ch_id)
    
    await callback.answer("Kanal muvaffaqiyatli o'chirildi.", show_alert=True)
    await callback_admin_channels(callback)

@router.callback_query(F.data == "admin_add_channel_prompt")
async def callback_add_channel_prompt(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    await callback.message.edit_text(
        text="➕ <b>Yangi kanal qo'shish</b>\n\nIltimah, kanalning Telegram ID raqamini kiriting (masalan, <code>-100123456789</code>):",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_channels")
    )
    await state.set_state(Form.waiting_for_channel_id)

@router.message(Form.waiting_for_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    try:
        ch_id = int(message.text.strip())
        await state.update_data(tg_id=ch_id)
        await message.answer("Endi kanalning nomini (Title) kiriting (masalan, <i>Kanal Nomi</i>):", parse_mode="HTML")
        await state.set_state(Form.waiting_for_channel_title)
    except ValueError:
        await message.answer("⚠️ Noto'g'ri format. Iltimos, faqat ID kiriting:")

@router.message(Form.waiting_for_channel_title)
async def process_channel_title(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    title = message.text.strip()
    await state.update_data(title=title)
    await message.answer("Endi kanalning taklif havolasini (Invite Link) kiriting:", parse_mode="HTML")
    await state.set_state(Form.waiting_for_channel_link)

@router.message(Form.waiting_for_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("⚠️ Noto'g'ri havola. Iltimos, to'liq havolani yuboring:")
        return
        
    data = await state.get_data()
    creates_join_request = True
    
    await db.add_channel(
        tg_id=data["tg_id"],
        title=data["title"],
        invite_link=link,
        creates_join_request=creates_join_request
    )
    
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Kanallarni ko'rish", callback_data="admin_channels")]])
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!", reply_markup=kb)

# --- Admin Broadcast Handlers ---
@router.callback_query(F.data == "admin_broadcast_prompt")
async def callback_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
        
    await callback.message.edit_text(
        text="📢 <b>Broadcast (Reklama)</b>\n\nBarcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting:",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_menu")
    )
    await state.set_state(Form.waiting_for_broadcast)

@router.message(Form.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    await state.clear()
    
    users = await db.get_all_users()
    if not users:
        await message.answer("Foydalanuvchilar topilmadi.")
        return
        
    sent_count = 0
    fail_count = 0
    
    status_msg = await message.answer(f"⏳ Xabar tarqatilmoqda... (Jami: {len(users)} ta)")
    
    for u in users:
        if u["is_banned"]:
            continue
            
        tg_id = u["telegram_id"]
        try:
            await message.send_copy(chat_id=tg_id)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1
            
    await status_msg.edit_text(
        f"📢 <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"✅ Yuborilganlar: <b>{sent_count} ta</b>\n"
        f"❌ Muammolar: <b>{fail_count} ta</b>",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_menu")
    )

# --- Admin Export CSV ---
@router.callback_query(F.data == "admin_export_csv")
async def callback_export_csv(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
        
    await callback.answer("Ma'lumotlar eksport qilinmoqda...", show_alert=False)
    
    users = await db.get_all_users()
    
    os.makedirs("bot/exports", exist_ok=True)
    file_path = "bot/exports/users_export.csv"
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Telegram ID", "Username", "First Name", "Referred By", "Points", "Wallet", "Is Banned", "Cheat Score", "Is Verified", "Created At"])
        for u in users:
            writer.writerow([
                u["telegram_id"],
                u.get("username", ""),
                u.get("first_name", ""),
                u.get("referred_by", ""),
                u.get("points", 0),
                u.get("wallet", ""),
                u.get("is_banned", False),
                u.get("cheat_score", 0.0),
                u.get("is_verified", False),
                u.get("created_at", "")
            ])
            
    try:
        csv_file = FSInputFile(file_path, filename="Referral_Contest_Users.csv")
        await bot.send_document(
            chat_id=user_id,
            document=csv_file,
            caption="📂 Konkurs ishtirokchilarining to'liq ma'lumotlar bazasi CSV formati."
        )
    except Exception as e:
        logger.error(f"Failed to send CSV: {e}")
        await callback.message.answer(f"⚠️ CSV fayl yuborishda xatolik: {e}")

# --- Admin Reset Contest ---
@router.callback_query(F.data == "admin_reset_prompt")
async def callback_reset_prompt(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
        
    text = (
        "⚠️ <b>DIQQAT! KONKURS BALLARINI NOLLASHTIRISH</b>\n\n"
        "Ushbu amal barcha ishtirokchilar ballarini, referral bog'lanishlarini va yechib olish so'rovlarini mutlaqo tozalaydi.\n"
        "Haqiqatan ham buni amalga oshirmoqchimisiz?"
    )
    
    buttons = [
        [
            InlineKeyboardButton(text="💥 Ha, nollashtirilsin!", callback_data="admin_reset_confirm", style="danger"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_menu")
        ]
    ]
    
    await callback.message.edit_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "admin_reset_confirm")
async def callback_reset_confirm(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
        
    await db.reset_contest()
    await callback.answer("Konkurs ballari va so'rovlari muvaffaqiyatli nollashtirildi! 💥", show_alert=True)
    await callback_admin_menu(callback)

# --- Helper: Get Channel ID by forwarding a message ---
@router.message(F.forward_from_chat)
async def handle_forwarded_channel_msg(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    chat = message.forward_from_chat
    if chat.type == "channel":
        await message.answer(
            f"🔑 <b>Kanalingiz haqida ma'lumotlar:</b>\n\n"
            f"📌 <b>Kanal nomi:</b> {chat.title or 'Noma\'lum kanal'}\n"
            f"🆔 <b>Kanal ID raqami:</b> <code>{chat.id}</code>\n\n"
            f"Ushbu 🆔 raqamni nusxalab, admin paneldagi <b>\"Yopiq kanal ID-si\"</b> maydoniga kiriting.",
            parse_mode="HTML"
        )
