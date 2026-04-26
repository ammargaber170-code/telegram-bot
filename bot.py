#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Professional Guard Bot (V13)
Powered by Design Lab

Features:
- Legacy behavior retained (lock, unlock, purge, replace, info, reset, allow/disallow, vip, admin, setcode, etc.)
- Role system: owner, admin, moderator, vip, user
- Custom per-user permissions
- /del command can delete without reply (using message id or previous message)
- Admin action logging
- Badge system
- Join-date tracking
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
import importlib.util
from collections import defaultdict, deque
from datetime import datetime
from html import escape
from typing import Optional

if importlib.util.find_spec("telegram") is None:
    print(
        "Missing dependency: python-telegram-bot.\n"
        "Install dependencies with:\n"
        "  pip install -r requirements.txt"
    )
    sys.exit(1)

from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

# ==============================================================================
# 1. STYLES
# ==============================================================================

ASCII_ART = """
\033[1;36m
██████╗  █████╗ ██╗   ██╗██████╗ ██████╗
██╔════╝ ██╔══██╗██║   ██║██╔══██╗██╔══██╗
██║  ███╗███████║██║   ██║██████╔╝██║  ██║
██║   ██║██╔══██║██║   ██║██╔══██╗██║  ██║
╚██████╔╝██║  ██║╚██████╔╝██║  ██║██████╔╝
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝
        V13 PROFESSIONAL EDITION
\033[0m
"""

STYLE = {
    "header": "<b>🛡 SYSTEM DASHBOARD</b>\n━━━━━━━━━━━━━━━━━━━━",
    "warn": "<b>⚠️ WARNING ISSUED</b>\n━━━━━━━━━━━━━━━━━━━━",
    "ban": "<b>⛔ USER BANNED</b>\n━━━━━━━━━━━━━━━━━━━━",
    "mute": "<b>🔇 USER MUTED</b>\n━━━━━━━━━━━━━━━━━━━━",
    "success": "<b>✅ SUCCESS</b>\n━━━━━━━━━━━━━━━━━━━━",
    "error": "<b>❌ ERROR</b>\n━━━━━━━━━━━━━━━━━━━━",
    "replace": "<b>📝 ADMIN NOTICE</b>\n━━━━━━━━━━━━━━━━━━━━",
    "info": "<b>👤 USER INTELLIGENCE</b>\n━━━━━━━━━━━━━━━━━━━━",
    "sig": "\n━━━━━━━━━━━━━━━━━━━━\n<i>Design Lab</i>",
}

# ==============================================================================
# 2. CONFIG
# ==============================================================================

TOKEN_FILE = ".bot_token"
DATA_FILE = "bot_state.json"
ACTION_LOG_FILE = "admin_actions.log"

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"
ROLE_VIP = "vip"
ROLE_USER = "user"

ROLE_LEVEL = {
    ROLE_OWNER: 100,
    ROLE_ADMIN: 70,
    ROLE_MODERATOR: 50,
    ROLE_VIP: 20,
    ROLE_USER: 0,
}

ROLE_DEFAULT_PERMISSIONS = {
    ROLE_OWNER: {
        "delete", "mute", "ban", "warn", "lock", "purge", "broadcast", "replace",
        "grant", "revoke", "setrole", "setbadge", "info", "reset",
    },
    ROLE_ADMIN: {
        "delete", "mute", "ban", "warn", "lock", "purge", "broadcast", "replace", "info", "reset",
    },
    ROLE_MODERATOR: {
        "delete", "mute", "warn", "broadcast", "replace", "info", "reset",
    },
    ROLE_VIP: set(),
    ROLE_USER: set(),
}

DEFAULT_BADGES = {
    ROLE_OWNER: "👑",
    ROLE_ADMIN: "🛡️",
    ROLE_MODERATOR: "🔧",
    ROLE_VIP: "💎",
    ROLE_USER: "👤",
}

URL_PATTERN = re.compile(r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.[^\s]{2,})")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
action_logger = logging.getLogger("admin_actions")
action_logger.setLevel(logging.INFO)
action_logger.addHandler(logging.FileHandler(ACTION_LOG_FILE, encoding="utf-8"))

# ==============================================================================
# 3. STATE
# ==============================================================================


class BotState:
    def __init__(self):
        self.data = {
            "owner_id": None,
            "super_admins": [],
            "moderators": [],
            "vips": [],
            "banned_words": [],
            "allowed_domains": [],
            "admin_codes": {},
            "username_map": {},
            "settings": {
                "welcome_msg": "Welcome {mention}!\nPlease respect the rules.",
                "warn_msg": "{header}\n👁 <b>Target:</b> {mention}\n🔘 <b>Count:</b> {current}/{limit}\n📑 <b>Reason:</b> {reason}{sig}",
                "mute_msg": "{header}\n👁 <b>Target:</b> {mention}\n🛠 <b>Action:</b> Muted\n📑 <b>Reason:</b> Excessive Violations{sig}",
                "ban_msg": "{header}\n👁 <b>Target:</b> {mention}\n🛠 <b>Action:</b> Banned\n📑 <b>Reason:</b> Security Threat{sig}",
            },
            "users": {},
            "custom_permissions": {},
            "badges": {},
            "role_overrides": {},
        }
        self.load()

    def load(self):
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception as exc:
            logger.warning("Failed to load state: %s", exc)

    def save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def cache_username(self, user):
        if user and user.username:
            self.data["username_map"][user.username.lower()] = user.id

    def get_user_data(self, user_id: int):
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {"warns": 0, "timestamps": [], "join_date": None}
        return self.data["users"][uid]


state = BotState()
admin_cache = {}
flood_cache = defaultdict(lambda: deque(maxlen=10))

# ==============================================================================
# 4. UTILITIES
# ==============================================================================


def get_token_and_owner():
    print(ASCII_ART)
    env_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if env_token:
        token = env_token
    elif os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()
    else:
        token = input("Enter Bot Token: ").strip()
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)

    env_owner = os.getenv("TELEGRAM_OWNER_ID", "").strip()
    if env_owner.isdigit():
        state.data["owner_id"] = int(env_owner)
        state.save()
    elif state.data["owner_id"] is None:
        try:
            state.data["owner_id"] = int(input("Enter Owner ID: ").strip())
            state.save()
        except ValueError:
            sys.exit(1)
    return token


def normalize_link(url: str) -> str:
    url = re.sub(r"^https?://", "", url.lower())
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def display_name(user) -> str:
    return user.full_name if user else "Unknown"


def resolve_user_badge(user_id: int, role: str) -> str:
    return state.data.get("badges", {}).get(str(user_id), DEFAULT_BADGES.get(role, "👤"))


async def log_admin_action(update: Update, action: str, target=None, details: str = ""):
    actor = update.effective_user
    chat = update.effective_chat
    target_txt = f" target={target.id}" if target else ""
    line = (
        f"chat={chat.id} actor={actor.id} action={action}{target_txt} details={details} "
        f"at={datetime.utcnow().isoformat()}"
    )
    action_logger.info(line)


async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if not context.args:
        return None

    raw = context.args[0]
    if raw.isdigit():
        try:
            m = await context.bot.get_chat_member(update.effective_chat.id, int(raw))
            return m.user
        except TelegramError:
            return None
    if raw.startswith("@"):
        uid = state.data["username_map"].get(raw[1:].lower())
        if not uid:
            return "unknown_username"
        try:
            m = await context.bot.get_chat_member(update.effective_chat.id, uid)
            return m.user
        except TelegramError:
            return None
    return None


async def get_user_role(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    if user_id == state.data["owner_id"]:
        return ROLE_OWNER
    role_override = state.data.get("role_overrides", {}).get(str(user_id))
    if role_override in [ROLE_ADMIN, ROLE_MODERATOR, ROLE_VIP, ROLE_USER]:
        return role_override
    if user_id in state.data.get("super_admins", []):
        return ROLE_ADMIN
    if user_id in state.data.get("moderators", []):
        return ROLE_MODERATOR

    now = time.time()
    admin_cache.setdefault(chat_id, {})
    if user_id in admin_cache[chat_id] and now < admin_cache[chat_id][user_id][1]:
        status = admin_cache[chat_id][user_id][0]
        if status in ["creator", "administrator"]:
            return ROLE_ADMIN
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        admin_cache[chat_id][user_id] = (m.status, now + 60)
        if m.status in ["creator", "administrator"]:
            return ROLE_ADMIN
    except TelegramError:
        pass

    if user_id in state.data.get("vips", []):
        return ROLE_VIP
    return ROLE_USER


async def has_permission(
    user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    min_role: str = ROLE_USER,
    permission_key: Optional[str] = None,
) -> bool:
    role = await get_user_role(user_id, chat_id, context)
    if ROLE_LEVEL[role] >= ROLE_LEVEL[min_role]:
        return True

    if permission_key:
        if permission_key in ROLE_DEFAULT_PERMISSIONS.get(role, set()):
            return True
        user_perms = state.data.get("custom_permissions", {}).get(str(user_id), [])
        if permission_key in user_perms:
            return True
    return False


async def apply_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, reason: str):
    chat_id = update.effective_chat.id
    ud = state.get_user_data(user_id)
    now = time.time()

    ud["timestamps"] = [t for t in ud["timestamps"] if now - t < 600]
    ud["warns"] += 1
    ud["timestamps"].append(now)

    action = "ban" if ud["warns"] >= 5 else "mute" if (len(ud["timestamps"]) >= 4 or ud["warns"] >= 3) else "warn"
    mention = f"@{escape(username)}" if username else f"<code>{user_id}</code>"

    if action == "warn":
        msg = state.data["settings"]["warn_msg"].format(
            header=STYLE["warn"], mention=mention, current=ud["warns"], limit=5, reason=escape(reason), sig=STYLE["sig"]
        )
    elif action == "mute":
        try:
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
            msg = state.data["settings"]["mute_msg"].format(header=STYLE["mute"], mention=mention, sig=STYLE["sig"])
            ud["timestamps"] = []
        except TelegramError:
            msg = f"{STYLE['error']}\nError muting user.{STYLE['sig']}"
    else:
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            msg = state.data["settings"]["ban_msg"].format(header=STYLE["ban"], mention=mention, sig=STYLE["sig"])
            ud["warns"] = 0
            ud["timestamps"] = []
        except TelegramError:
            msg = f"{STYLE['error']}\nError banning user.{STYLE['sig']}"

    state.save()
    await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML)


# ==============================================================================
# 5. COMMANDS
# ==============================================================================


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    text = (
        f"{STYLE['header']}\n"
        "👋 <b>Welcome Commander!</b>\n\n"
        "🛡 <b>Guard System:</b> <code>ONLINE</code>\n"
        "📦 <b>Smart Cache:</b> <code>ACTIVE</code>\n\n"
        f"{STYLE['sig']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = (
        f"{STYLE['header']}\n"
        "<b>CONTROL</b>\n"
        "/lock /unlock /purge /del\n"
        "/info /reset /replace\n\n"
        "<b>ADMIN</b>\n"
        "/admin /unadmin /mod /unmod\n"
        "/vip /unvip /allow /disallow\n"
        "/setcode /setrole /setbadge /grant /revoke\n"
        "/list /add /delword\n"
        f"{STYLE['sig']}"
    )
    await update.message.reply_text(menu, parse_mode=ParseMode.HTML)


async def config_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    cmd = update.message.text.split()[0][1:].lower()

    if cmd == "list":
        rev = {v: k for k, v in state.data["username_map"].items()}

        def names(ids):
            return ", ".join(f"@{rev[i]}" if i in rev else str(i) for i in ids) or "None"

        report = (
            f"{STYLE['header']}\n"
            f"Admins: <code>{escape(names(state.data['super_admins']))}</code>\n"
            f"Moderators: <code>{escape(names(state.data['moderators']))}</code>\n"
            f"VIPs: <code>{escape(names(state.data['vips']))}</code>\n"
            f"Allowed Domains: <code>{escape(', '.join(state.data['allowed_domains']) or 'None')}</code>\n"
            f"Banned Words: <code>{escape(', '.join(state.data['banned_words']) or 'None')}</code>\n"
            f"{STYLE['sig']}"
        )
        await update.message.reply_text(report, parse_mode=ParseMode.HTML)
        return

    arg = " ".join(context.args).strip().lower()
    if cmd == "add" and arg:
        if arg not in state.data["banned_words"]:
            state.data["banned_words"].append(arg)
            state.save()
        await update.message.reply_text(f"{STYLE['success']}\nAdded banned word: <b>{escape(arg)}</b>", parse_mode=ParseMode.HTML)
    elif cmd in ["delword", "del"] and arg:
        if arg in state.data["banned_words"]:
            state.data["banned_words"].remove(arg)
            state.save()
        await update.message.reply_text(f"{STYLE['success']}\nRemoved banned word: <b>{escape(arg)}</b>", parse_mode=ParseMode.HTML)


async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    target = await get_target_user(update, context)
    if target == "unknown_username":
        return await update.message.reply_text("Unknown username.")
    if not target:
        return await update.message.reply_text("Target required.")

    cmd = update.message.text.split()[0][1:].lower()
    if cmd == "admin":
        if target.id not in state.data["super_admins"]:
            state.data["super_admins"].append(target.id)
        msg = f"User <b>{escape(display_name(target))}</b> is now Admin."
    else:
        if target.id in state.data["super_admins"]:
            state.data["super_admins"].remove(target.id)
        msg = f"User <b>{escape(display_name(target))}</b> removed from Admins."

    state.save()
    await log_admin_action(update, cmd, target)
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode=ParseMode.HTML)


async def manage_mods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    target = await get_target_user(update, context)
    if target in (None, "unknown_username"):
        return await update.message.reply_text("Target required.")

    cmd = update.message.text.split()[0][1:].lower()
    if cmd == "mod":
        if target.id not in state.data["moderators"]:
            state.data["moderators"].append(target.id)
        msg = "Moderator granted."
    else:
        if target.id in state.data["moderators"]:
            state.data["moderators"].remove(target.id)
        msg = "Moderator removed."
    state.save()
    await log_admin_action(update, cmd, target)
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode=ParseMode.HTML)


async def manage_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    target = await get_target_user(update, context)
    if target in (None, "unknown_username"):
        return await update.message.reply_text("Target required.")

    cmd = update.message.text.split()[0][1:].lower()
    if cmd == "vip":
        if target.id not in state.data["vips"]:
            state.data["vips"].append(target.id)
        msg = "Added VIP."
    else:
        if target.id in state.data["vips"]:
            state.data["vips"].remove(target.id)
        msg = "Removed VIP."
    state.save()
    await log_admin_action(update, cmd, target)
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode=ParseMode.HTML)


async def config_domains(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    if not context.args:
        return await update.message.reply_text("Usage: /allow [domain]")

    link = normalize_link(context.args[0])
    cmd = update.message.text.split()[0][1:].lower()
    if cmd == "allow":
        if link not in state.data["allowed_domains"]:
            state.data["allowed_domains"].append(link)
        msg = f"Allowed: <b>{escape(link)}</b>"
    else:
        if link in state.data["allowed_domains"]:
            state.data["allowed_domains"].remove(link)
        msg = f"Removed: <b>{escape(link)}</b>"
    state.save()
    await log_admin_action(update, cmd, details=link)
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode=ParseMode.HTML)


async def set_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    target = await get_target_user(update, context)
    if target in (None, "unknown_username"):
        return await update.message.reply_text("Reply to user or provide id.")

    if update.message.reply_to_message:
        code = " ".join(context.args)
    else:
        code = " ".join(context.args[1:]) if context.args else ""

    if not code:
        return await update.message.reply_text("Usage: /setcode <user> <Code>")

    state.data["admin_codes"][str(target.id)] = code
    state.save()
    await log_admin_action(update, "setcode", target, code)
    await update.message.reply_text(f"{STYLE['success']}\nSignature set: <b>{escape(code)}</b>", parse_mode=ParseMode.HTML)


async def set_badge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update.effective_user.id, update.effective_chat.id, context, ROLE_OWNER):
        return
    target = await get_target_user(update, context)
    if target in (None, "unknown_username"):
        return await update.message.reply_text("Usage: reply /setbadge ⭐")

    badge = context.args[-1] if context.args else ""
    if not badge:
        return await update.message.reply_text("Usage: /setbadge <user> <badge>")

    state.data.setdefault("badges", {})[str(target.id)] = badge
    state.save()
    await log_admin_action(update, "setbadge", target, badge)
 
