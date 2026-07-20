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

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
PRIVATE_CHANNEL_ID = int(os.environ.get("PRIVATE_CHANNEL_ID", "0"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# Custom Premium Emoji IDs (Fallbacks)
EMOJI_STAR = "5438341604928232974"       # Star icon
EMOJI_CHECK = "5438341604928232975"      # Green check
EMOJI_ALERT = "5438341604928232976"      # Warning/Danger
EMOJI_REWARD = "5438341604928232977"     # Gift box
EMOJI_LEADER = "5438341604928232978"     # Trophy
EMOJI_WALLET = "5438341604928232979"     # Wallet

# --- FSM States ---
class Form(StatesGroup):
    waiting_for_wallet = State()
    waiting_for_withdrawal = State()
    # Admin States
    waiting_for_channel_id = State()
    waiting_for_channel_title = State()
    waiting_for_channel_link = State()
    waiting_for_broadcast = State()

# --- Keyboard Builders (App-Like Edit-in-Place UX) ---
async def get_subscription_keyboard(bot: Bot, user_id: int):
    channels = await db.get_active_channels()
    buttons = []
    
    # 1. Join buttons (Blue / Primary style for sponsorship actions)
    for idx, ch in enumerate(channels):
        title = ch.get("title", f"Kanal #{idx+1}")
        url = ch.get("invite_link", "")
        buttons.append([
            InlineKeyboardButton(
                text=f"➕ {title}",
                url=url,
                style="primary",
                icon_custom_emoji_id=EMOJI_STAR
            )
        ])
        
    # 2. Verify subscription button (Green / Success style)
    buttons.append([
        InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data="check_subs",
            style="success",
            icon_custom_emoji_id=EMOJI_CHECK
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_main_menu_keyboard(user_id: int):
    is_admin = user_id in ADMIN_IDS
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔗 Taklif Havolasi",
                callback_data="menu_referral",
                style="primary",
                icon_custom_emoji_id=EMOJI_STAR
            ),
            InlineKeyboardButton(
                text="🎁 Kunlik Bonus",
                callback_data="menu_bonus",
                style="success",
                icon_custom_emoji_id=EMOJI_REWARD
            )
        ],
        [
            InlineKeyboardButton(
                text="🏆 Reyting (Leaderboard)",
                callback_data="menu_leaderboard",
                icon_custom_emoji_id=EMOJI_LEADER
            ),
            InlineKeyboardButton(
                text="💼 Hamyon / Balans",
                callback_data="menu_wallet",
                icon_custom_emoji_id=EMOJI_WALLET
            )
        ]
    ]
    
    if is_admin:
        keyboard.append([
            InlineKeyboardButton(
                text="🛠 Admin Panel",
                callback_data="admin_menu",
                style="primary"
            )
        ])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_keyboard(callback_target="main_menu"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⬅️ Ortga",
                callback_data=callback_target,
                style="danger",
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

    # Check if they are verified. If not, show force subscription
    if not user["is_verified"] and not user["is_banned"]:
        kb = await get_subscription_keyboard(bot, user_id)
        await message.answer(
            f"Assalomu alaykum, {first_name}! Botdan to'liq foydalanish uchun quyidagi homiy kanallarga obuna bo'ling:",
            reply_markup=kb
        )
    elif user["is_banned"]:
        await message.answer("⚠️ Siz ushbu botdan foydalanishdan chetlatilgansiz.")
    else:
        # Show Main Menu
        kb = await get_main_menu_keyboard(user_id)
        await message.answer(
            f"Xush kelibsiz, {first_name}! Quyidagi menyulardan birini tanlang:",
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
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi. Qayta /start bosing.", show_alert=True)
        return
        
    if user["is_banned"]:
        await callback.answer("Siz bloklangansiz.", show_alert=True)
        return

    # Check subscriptions
    channels = await db.get_active_channels()
    unsubscribed = []
    
    for ch in channels:
        ch_tg_id = ch["tg_id"]
        try:
            member = await bot.get_chat_member(chat_id=ch_tg_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                unsubscribed.append(ch)
        except Exception as e:
            logger.warning(f"Could not check membership in {ch_tg_id}: {e}")
            unsubscribed.append(ch)
            
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
                await db.update_user(ref_id, points=new_points)
                
                # Notify referrer
                try:
                    await bot.send_message(
                        chat_id=ref_id,
                        text=f"🎉 Tabriklaymiz! Siz taklif qilgan {callback.from_user.first_name} obunalarni tasdiqladi.\nSizga +{pts_per_ref} ball taqdim etildi! Hozirgi balansingiz: {new_points} ball."
                    )
                except Exception as e:
                    logger.warning(f"Could not notify referrer {ref_id}: {e}")

    # Show main menu
    kb = await get_main_menu_keyboard(user_id)
    await callback.message.edit_text(
        text="A'zoligingiz muvaffaqiyatli tasdiqlandi. Botimizga xush kelibsiz!",
        reply_markup=kb
    )

@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    kb = await get_main_menu_keyboard(user_id)
    await callback.message.edit_text(
        text="Asosiy menyuga xush kelibsiz. Kerakli bo'limni tanlang:",
        reply_markup=kb
    )

@router.callback_query(F.data == "menu_referral")
async def callback_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    ref_count = await db.get_referrer_count(user_id)
    
    text = (
        f"🎯 <b>Sizning Referral Ma'lumotlaringiz:</b>\n\n"
        f"👥 Taklif etilgan faol do'stlaringiz: <b>{ref_count} ta</b>\n"
        f"💰 Balans: <b>{user['points']} ball</b>\n\n"
        f"🔗 Taklif havolangiz:\n<code>{ref_link}</code>\n\n"
        f"Havolani nusxalash uchun ustiga bosing. Do'stlaringizni taklif qiling va mukofot ballarini jamlang!"
    )
    
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "menu_bonus")
async def callback_bonus(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    now = datetime.now(timezone.utc)
    last_claim = user.get("last_bonus_claim")
    
    can_claim = True
    time_remaining_str = ""
    
    if last_claim:
        last_claim_dt = datetime.fromisoformat(last_claim.replace("Z", "+00:00"))
        time_passed = now - last_claim_dt
        if time_passed < timedelta(hours=24):
            can_claim = False
            remaining = timedelta(hours=24) - time_passed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_remaining_str = f"{hours}h {minutes}m"
            
    if not can_claim:
        await callback.answer(f"Kunlik bonusni olish uchun yana {time_remaining_str} kutishingiz kerak.", show_alert=True)
        return
        
    bonus_pts = int(await db.get_setting("daily_bonus_points", 1))
    new_points = user["points"] + bonus_pts
    
    await db.update_user(user_id, points=new_points, last_bonus_claim=now.isoformat())
    await callback.answer(f"Tabriklaymiz! Sizga +{bonus_pts} bonus ball berildi. 🎉", show_alert=True)
    
    kb = await get_main_menu_keyboard(user_id)
    await callback.message.edit_text(
        text=f"Bonus qabul qilindi. Sizning joriy balansingiz: {new_points} ball.",
        reply_markup=kb
    )

@router.callback_query(F.data == "menu_leaderboard")
async def callback_leaderboard(callback: CallbackQuery):
    leaderboard = await db.get_leaderboard(10)
    
    text = "🏆 <b>TOP 10 Konkurs Ishtirokchilari:</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    if not leaderboard:
        text += "Hozircha faol ishtirokchilar mavjud emas."
    else:
        for idx, row in enumerate(leaderboard):
            medal = medals[idx] if idx < len(medals) else f"•"
            name = row.get("first_name", "Ishtirokchi")
            username_str = f" (@{row['username']})" if row.get("username") else ""
            points = row.get("points", 0)
            text += f"{medal} <b>{name}</b>{username_str} — <b>{points} ball</b>\n"
            
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

@router.callback_query(F.data == "menu_wallet")
async def callback_wallet(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    wallet_str = user.get("wallet") or "Bog'lanmagan ⚠️"
    points = user.get("points", 0)
    min_points = int(await db.get_setting("min_withdrawal_points", 5))
    
    text = (
        f"💼 <b>Sizning Balansingiz:</b>\n\n"
        f"💰 Jamg'arilgan ballar: <b>{points} ball</b>\n"
        f"💳 Hamyon (USDT/TRX): <code>{wallet_str}</code>\n\n"
        f"• Minimal pul yechish summasi: <b>{min_points} ball</b>\n"
    )
    
    buttons = [
        [
            InlineKeyboardButton(text="💳 Hamyonni bog'lash", callback_data="wallet_setup", style="primary"),
            InlineKeyboardButton(text="💸 Pul yechish", callback_data="wallet_withdraw", style="success")
        ],
        [
            InlineKeyboardButton(text="⬅️ Ortga", callback_data="main_menu", style="danger")
        ]
    ]
    
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data == "wallet_setup")
async def callback_wallet_setup(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text="💳 USDT (TRC-20) yoki TRX hamyon manzilingizni yuboring:",
        reply_markup=get_back_keyboard("menu_wallet")
    )
    await state.set_state(Form.waiting_for_wallet)

@router.message(Form.waiting_for_wallet)
async def process_wallet_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    wallet_address = message.text.strip()
    
    if len(wallet_address) < 20 or not any(wallet_address.startswith(x) for x in ['T', 'U', '0x']):
        await message.answer("⚠️ Hamyon manzili noto'g'ri ko'rinadi. Iltimos, haqiqiy TRX/USDT (TRC20) manzilini kiriting:")
        return
        
    await db.update_user(user_id, wallet=wallet_address)
    await state.clear()
    
    kb = await get_main_menu_keyboard(user_id)
    await message.answer(
        f"✅ Hamyon manzilingiz muvaffaqiyatli bog'landi: <code>{wallet_address}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data == "wallet_withdraw")
async def callback_wallet_withdraw(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
        
    points = user.get("points", 0)
    wallet = user.get("wallet")
    min_points = int(await db.get_setting("min_withdrawal_points", 5))
    
    if not wallet:
        await callback.answer("⚠️ Iltimos, avval hamyon manzilingizni bog'lang.", show_alert=True)
        return
        
    if points < min_points:
        await callback.answer(f"⚠️ Ballar yetarli emas. Minimal pul yechish: {min_points} ball. Sizda: {points} ball.", show_alert=True)
        return
        
    await callback.message.edit_text(
        text=f"💸 Yechib olmoqchi bo'lgan ballaringiz miqdorini kiriting (maksimum: {points}):",
        reply_markup=get_back_keyboard("menu_wallet")
    )
    await state.set_state(Form.waiting_for_withdrawal)

@router.message(Form.waiting_for_withdrawal)
async def process_withdrawal_amount(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await state.clear()
        return
        
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat butun yoki o'nlik raqam kiriting:")
        return
        
    points = user.get("points", 0)
    min_points = int(await db.get_setting("min_withdrawal_points", 5))
    
    if amount < min_points:
        await message.answer(f"⚠️ Minimal yechib olish summasi {min_points} ball. Iltimos, kattaroq miqdor kiriting:")
        return
        
    if amount > points:
        await message.answer(f"⚠️ Balansingizda yetarli ball yo'q. Maksimal yechish: {points} ball. Qayta kiriting:")
        return
        
    await state.clear()
    
    new_points = points - amount
    await db.update_user(user_id, points=new_points)
    
    withdr = await db.create_withdrawal(user_id, user["wallet"], amount)
    w_id = withdr["id"]
    
    kb = await get_main_menu_keyboard(user_id)
    await message.answer(
        f"✅ Yechib olish so'rovi muvaffaqiyatli yuborildi!\n"
        f"Summa: {amount} ball\nHamyon: <code>{user['wallet']}</code>\n"
        f"So'rov adminlar tomonidan tekshiriladi.",
        parse_mode="HTML",
        reply_markup=kb
    )
    
    admin_group_text = (
        f"🔔 <b>YANGI YECHIB OLISH SO'ROVI (ID: #{w_id})</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.first_name} (@{message.from_user.username or 'yoq'})\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"💰 Miqdor: <b>{amount} ball</b>\n"
        f"💳 Hamyon: <code>{user['wallet']}</code>\n"
        f"🤖 Spam ehtimoli: <b>{user.get('cheat_score', 0.0)*100:.1f}%</b>"
    )
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Tasdiqlash (Pay)", callback_data=f"withdraw_approve:{w_id}", style="success"),
            InlineKeyboardButton(text="🔴 Rad etish", callback_data=f"withdraw_reject:{w_id}", style="danger")
        ]
    ])
    
    if PRIVATE_CHANNEL_ID:
        try:
            await bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=admin_group_text, parse_mode="HTML", reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Failed to send withdrawal request to Private Channel: {e}")
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(chat_id=admin_id, text=admin_group_text, parse_mode="HTML", reply_markup=admin_kb)
                except Exception:
                    pass
    else:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_group_text, parse_mode="HTML", reply_markup=admin_kb)
            except Exception:
                pass

# --- Admin Withdrawal Approvals ---
@router.callback_query(F.data.startswith("withdraw_approve:"))
async def callback_withdraw_approve(callback: CallbackQuery, bot: Bot):
    w_id = int(callback.data.split(":")[1])
    w = await db.get_withdrawal(w_id)
    
    if not w:
        await callback.answer("So'rov topilmadi.", show_alert=True)
        return
        
    if w["status"] != "pending":
        await callback.answer(f"Bu so'rov allaqachon '{w['status']}' holatida.", show_alert=True)
        return
        
    await db.update_withdrawal_status(w_id, "approved")
    await callback.answer("Yechib olish tasdiqlandi. To'lov amalga oshirildi! ✅", show_alert=True)
    
    await callback.message.edit_text(
        text=callback.message.text + f"\n\n✅ <b>TASDIQLANDI</b> (Admin: {callback.from_user.first_name})",
        parse_mode="HTML",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            chat_id=w["tg_id"],
            text=f"🎉 Tabriklaymiz! Sizning #{w_id}-raqamli {w['amount']} ballik pul yechish so'rovingiz tasdiqlandi va hamyoningizga o'tkazildi!"
        )
    except Exception:
        pass

@router.callback_query(F.data.startswith("withdraw_reject:"))
async def callback_withdraw_reject(callback: CallbackQuery, bot: Bot):
    w_id = int(callback.data.split(":")[1])
    w = await db.get_withdrawal(w_id)
    
    if not w:
        await callback.answer("So'rov topilmadi.", show_alert=True)
        return
        
    if w["status"] != "pending":
        await callback.answer(f"Bu so'rov allaqachon '{w['status']}' holatida.", show_alert=True)
        return
        
    await db.update_withdrawal_status(w_id, "rejected")
    
    user_id = w["tg_id"]
    user = await db.get_user(user_id)
    if user:
        refunded_pts = user["points"] + float(w["amount"])
        await db.update_user(user_id, points=refunded_pts)
        
    await callback.answer("Yechib olish rad etildi, ballar qaytarildi! ❌", show_alert=True)
    
    await callback.message.edit_text(
        text=callback.message.text + f"\n\n❌ <b>RAD ETILDI</b> (Admin: {callback.from_user.first_name})",
        parse_mode="HTML",
        reply_markup=None
    )
    
    try:
        await bot.send_message(
            chat_id=w["tg_id"],
            text=f"❌ Sizning #{w_id}-raqamli pul yechish so'rovingiz rad etildi. Ballar balansingizga qaytarildi."
        )
    except Exception:
        pass


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
    
    text = (
        f"📊 <b>BOTNING REAL-VAQT STATISTIKASI:</b>\n\n"
        f"👥 Ro'yxatdan o'tgan foydalanuvchilar: <b>{stats['total_users']} ta</b>\n"
        f"✅ Tasdiqlangan faol ishtirokchilar: <b>{stats['verified_users']} ta</b>\n"
        f"🚫 Cheat sababli bloklanganlar: <b>{stats['banned_users']} ta</b>\n"
        f"💸 Tasdiqlangan jami to'lovlar: <b>{stats['total_withdrawn']} ball</b>\n"
        f"⏳ Kutilayotgan pul yechish so'rovlari: <b>{stats['pending_withdrawals']} ta</b>"
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
