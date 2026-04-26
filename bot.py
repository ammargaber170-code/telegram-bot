#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
馃洝锔� Professional Guard Bot (V12 - Join Date Tracker)
POWERED BY: @Desiign_lab
Updates:
- New: /info shows Join Date (for new members).
- Logic: Bot records timestamp when users join via Welcome handler.
- Includes: All V11 features (Lock, Purge, Replace, etc).
"""

import os
import json
import time
import logging
import re
import sys
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest
from telegram.error import TelegramError, TimedOut, NetworkError, BadRequest

# ==============================================================================
# 1. VISUAL STYLES
# ==============================================================================

ASCII_ART = """
\033[1;36m
鈻堚枅鈺�   鈻堚枅鈺� 鈻堚枅鈺椻枅鈻堚枅鈻堚枅鈻堚晽 
鈻堚枅鈺�   鈻堚枅鈺戔枅鈻堚枅鈺戔暁鈺愨晲鈺愨晲鈻堚枅鈺�
鈻堚枅鈺�   鈻堚枅鈺戔暁鈻堚枅鈺� 鈻堚枅鈻堚枅鈻堚晹鈺�
鈺氣枅鈻堚晽 鈻堚枅鈺斺暆 鈻堚枅鈺戔枅鈻堚晹鈺愨晲鈺愨暆 
 鈺氣枅鈻堚枅鈻堚晹鈺�  鈻堚枅鈺戔枅鈻堚枅鈻堚枅鈻堚枅鈺�
  鈺氣晲鈺愨晲鈺�   鈺氣晲鈺濃暁鈺愨晲鈺愨晲鈺愨晲鈺�
 馃洝锔� V12: DATE TRACKER 馃洝锔�
\033[0m
"""

STYLE = {
    "header": "<b>馃敯 SYSTEM DASHBOARD 馃敯</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "warn": "<b>鈿狅笍 WARNING ISSUED</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "ban": "<b>鉀� USER BANNED</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "mute": "<b>馃攪 USER MUTED</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "success": "<b>鉁� SUCCESS</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "error": "<b>鉂� ERROR</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "replace": "<b>馃敂 ADMIN NOTICE</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "info": "<b>馃懁 USER INTELLIGENCE</b>\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣",
    "sig": "\n鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣鈹佲攣\n<i>馃敀 Protected by GuardBot</i>"
}

# ==============================================================================
# 2. CONFIGURATION
# ==============================================================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TOKEN_FILE = ".bot_token"
DATA_FILE = "bot_state.json"

PERM_OWNER = 100
PERM_SUPER_ADMIN = 80
PERM_ADMIN = 50
PERM_VIP = 20
PERM_USER = 0

URL_PATTERN = re.compile(r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.[^\s]{2,})')

# ==============================================================================
# 3. STATE MANAGEMENT
# ==============================================================================

class BotState:
    def __init__(self):
        self.data = {
            "owner_id": None, 
            "super_admins": [], 
            "vips": [], 
            "banned_words": [], 
            "allowed_domains": [], 
            "admin_codes": {},
            "username_map": {},
            "settings": {
                "welcome_msg": "Welcome {mention}!\nPlease respect the rules.",
                "warn_msg": "{header}\n馃懁 <b>Target:</b> {mention}\n馃敘 <b>Count:</b> {current}/{limit}\n馃摑 <b>Reason:</b> {reason}{sig}",
                "mute_msg": "{header}\n馃懁 <b>Target:</b> {mention}\n馃洃 <b>Action:</b> Muted\n馃摑 <b>Reason:</b> Excessive Violations{sig}",
                "ban_msg": "{header}\n馃懁 <b>Target:</b> {mention}\n馃洃 <b>Action:</b> Banned\n馃摑 <b>Reason:</b> Security Threat{sig}"
            },
            "users": {}
        }
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f: 
                    loaded = json.load(f)
                    self.data.update(loaded)
            except: pass

    def save(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(self.data, f, indent=2, ensure_ascii=False)
        except: pass

    def get_user_data(self, user_id):
        uid = str(user_id)
        # Structure: {"warns": 0, "timestamps": [], "join_date": timestamp}
        if uid not in self.data["users"]: 
            self.data["users"][uid] = {"warns": 0, "timestamps": [], "join_date": None}
        return self.data["users"][uid]

    def update_user_data(self, user_id, data):
        self.data["users"][str(user_id)] = data
        self.save()

    def cache_username(self, user):
        if user.username:
            u_lower = user.username.lower()
            if u_lower not in self.data["username_map"] or self.data["username_map"][u_lower] != user.id:
                self.data["username_map"][u_lower] = user.id

state = BotState()
admin_cache = {}
flood_cache = defaultdict(lambda: deque(maxlen=10))

# ==============================================================================
# 4. UTILITIES
# ==============================================================================

def get_token_and_owner():
    print(ASCII_ART)
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f: token = f.read().strip()
    else:
        token = input("馃攽 Enter Bot Token: ").strip()
        with open(TOKEN_FILE, 'w') as f: f.write(token)
    
    if state.data["owner_id"] is None:
        try:
            owner_id = int(input("馃憫 Enter Owner ID: ").strip())
            state.data["owner_id"] = owner_id
            state.save()
        except: sys.exit(1)
    return token

async def get_target_user(update, context):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        raw_arg = context.args[0]
        if raw_arg.isdigit():
            try:
                member = await context.bot.get_chat_member(update.effective_chat.id, int(raw_arg))
                return member.user
            except: pass
        elif raw_arg.startswith("@"):
            username = raw_arg[1:].lower()
            user_id = state.data["username_map"].get(username)
            if user_id:
                try:
                    member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                    return member.user
                except: pass
            else:
                return "unknown_username"
    return None

async def check_permissions(user_id, chat_id, context):
    if user_id == state.data["owner_id"]: return PERM_OWNER
    if user_id in state.data["super_admins"]: return PERM_SUPER_ADMIN
    
    now = time.time()
    if chat_id not in admin_cache: admin_cache[chat_id] = {}
    if user_id in admin_cache[chat_id]:
        s, t = admin_cache[chat_id][user_id]
        if now < t: 
            return PERM_ADMIN if s in ['creator', 'administrator'] else PERM_VIP if user_id in state.data["vips"] else PERM_USER

    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        admin_cache[chat_id][user_id] = (m.status, now + 60)
        if m.status in ['creator', 'administrator']: return PERM_ADMIN
    except: pass
    
    if user_id in state.data["vips"]: return PERM_VIP
    return PERM_USER

def normalize_link(url):
    url = re.sub(r'^https?://', '', url.lower())
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

async def apply_punishment(update, context, user_id, user_name, reason):
    chat_id = update.effective_chat.id
    ud = state.get_user_data(user_id)
    now = time.time()
    
    ud["timestamps"] = [t for t in ud["timestamps"] if now - t < 600]
    ud["warns"] += 1; ud["timestamps"].append(now)
    
    act = "ban" if ud["warns"] >=5 else "mute" if (len(ud["timestamps"])>=4 or ud["warns"]>=3) else "warn"
    
    if act == "warn":
        msg = state.data["settings"]["warn_msg"].format(header=STYLE["warn"], mention=f"@{user_name}", current=ud["warns"], limit=5, reason=reason, sig=STYLE["sig"])
    elif act == "mute":
        try:
            await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(False))
            msg = state.data["settings"]["mute_msg"].format(header=STYLE["mute"], mention=f"@{user_name}", sig=STYLE["sig"])
            ud["timestamps"] = []
        except: msg = "鉂� Error muting."
    elif act == "ban":
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            msg = state.data["settings"]["ban_msg"].format(header=STYLE["ban"], mention=f"@{user_name}", sig=STYLE["sig"])
            ud["warns"] = 0; ud["timestamps"] = []
        except: msg = "鉂� Error banning."

    await context.bot.send_message(chat_id, msg, parse_mode="HTML")
    state.update_user_data(user_id, ud)

# ==============================================================================
# 5. COMMANDS
# ==============================================================================

async def cmd_start(update, context):
    if update.effective_chat.type == "private":
        dash = (
            f"{STYLE['header']}\n"
            "馃憢 <b>Welcome Commander!</b>\n\n"
            "馃洝锔� <b>Guard System:</b> <code>ONLINE</code>\n"
            "馃 <b>Smart Cache:</b> <code>ACTIVE</code>\n\n"
            "<i>Bot recognized: @Desiign_lab</i>\n"
            f"{STYLE['sig']}"
        )
        await update.message.reply_text(dash, parse_mode="HTML")

async def cmd_help(update, context):
    menu = (
        f"{STYLE['header']}\n"
        "<b>馃懏鈥嶁檪锔� CONTROL:</b>\n"
        "/lock, /unlock, /purge\n"
        "/info, /reset, /replace\n\n"
        "<b>鈿欙笍 ADMIN:</b>\n"
        "/admin, /allow, /setcode\n"
        "/ban, /mute, /vip\n"
        f"{STYLE['sig']}"
    )
    await update.message.reply_text(menu, parse_mode="HTML")

async def config_general(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    cmd = update.message.text.split()[0][1:]
    
    if cmd == "list":
        d = state.data
        def fmt(lst): return ', '.join(map(str, lst)) if lst else "None"
        def resolve_names(ids):
            names = []
            rev_map = {v: k for k, v in d["username_map"].items()}
            for i in ids: names.append(f"@{rev_map[i]}" if i in rev_map else str(i))
            return ', '.join(names) if names else "None"

        report = (
            f"{STYLE['header']}\n"
            f"馃懏 <b>Super Admins:</b>\n<code>{resolve_names(d['super_admins'])}</code>\n\n"
            f"馃専 <b>VIP Members:</b>\n<code>{resolve_names(d['vips'])}</code>\n\n"
            f"馃寪 <b>Allowed Links:</b>\n<code>{fmt(d['allowed_domains'])}</code>\n\n"
            f"馃毇 <b>Banned Words:</b>\n<code>{fmt(d['banned_words'])}</code>\n"
            f"{STYLE['sig']}"
        )
        if len(report) > 4000:
            await update.message.reply_text(report[:4000], parse_mode="HTML")
            await update.message.reply_text(report[4000:], parse_mode="HTML")
        else:
            await update.message.reply_text(report, parse_mode="HTML")
        return

    arg = " ".join(context.args).lower()
    if cmd == "add" and arg:
        state.data["banned_words"].append(arg); state.save()
        await update.message.reply_text(f"{STYLE['success']}\nAdded: <b>{arg}</b>", parse_mode="HTML")
    elif cmd == "del" and arg:
        if arg in state.data["banned_words"]: state.data["banned_words"].remove(arg); state.save()
        await update.message.reply_text(f"{STYLE['success']}\nRemoved: <b>{arg}</b>", parse_mode="HTML")

async def manage_admins(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    target = await get_target_user(update, context)
    
    if target == "unknown_username": return await update.message.reply_text(f"{STYLE['error']}\nUnknown username.", parse_mode="HTML")
    if not target: return await update.message.reply_text("Target required.")
    
    cmd = update.message.text.split()[0][1:]
    if cmd == "admin":
        if target.id not in state.data["super_admins"]: state.data["super_admins"].append(target.id)
        msg = f"User <b>{target.first_name}</b> is now Super Admin."
    elif cmd == "unadmin":
        if target.id in state.data["super_admins"]: state.data["super_admins"].remove(target.id)
        msg = f"User <b>{target.first_name}</b> removed from Admins."
    state.save()
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode="HTML")

async def config_domains(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    if not context.args: return await update.message.reply_text("Usage: /allow [link]")
    
    link = normalize_link(context.args[0])
    cmd = update.message.text.split()[0][1:]
    
    if cmd == "allow":
        if link not in state.data["allowed_domains"]: state.data["allowed_domains"].append(link)
        msg = f"Allowed: <b>{link}</b>"
    else:
        if link in state.data["allowed_domains"]: state.data["allowed_domains"].remove(link)
        msg = f"Removed: <b>{link}</b>"
    state.save()
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode="HTML")

async def manage_vip(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    target = await get_target_user(update, context)
    if not target or target == "unknown_username": return await update.message.reply_text("Target required.")
    
    cmd = update.message.text.split()[0][1:]
    if cmd == "vip":
        if target.id not in state.data["vips"]: state.data["vips"].append(target.id)
        msg = "Added VIP."
    else:
        if target.id in state.data["vips"]: state.data["vips"].remove(target.id)
        msg = "Removed VIP."
    state.save()
    await update.message.reply_text(f"{STYLE['success']}\n{msg}", parse_mode="HTML")

async def set_code(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    target = await get_target_user(update, context)
    if not target or target == "unknown_username": return await update.message.reply_text("Reply to user.")
    if not context.args: return await update.message.reply_text("Usage: /setcode [Code]")
    
    if update.message.reply_to_message: code = " ".join(context.args)
    else: code = " ".join(context.args[1:]) if (context.args[0].isdigit() or context.args[0].startswith("@")) else " ".join(context.args)

    state.data["admin_codes"][str(target.id)] = code
    state.save()
    await update.message.reply_text(f"{STYLE['success']}\nSignature set: <b>{code}</b>", parse_mode="HTML")

async def set_messages(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_OWNER: return
    cmd = update.message.text.split()[0][1:]
    if not context.args: return await update.message.reply_text("Usage: /set... [New Message]")
    text = update.message.text.split(None, 1)[1]
    
    key_map = {"setwelcome": "welcome_msg", "setwarnmsg": "warn_msg", "setmutemsg": "mute_msg", "setbanmsg": "ban_msg"}
    if key_map.get(cmd):
        state.data["settings"][key_map[cmd]] = text
        state.save()
        await update.message.reply_text(f"{STYLE['success']}\nMessage Updated.", parse_mode="HTML")

# --- CONTROL ACTIONS ---

async def cmd_lockdown(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_SUPER_ADMIN: return
    chat = update.effective_chat
    cmd = update.message.text.split()[0][1:]
    
    if cmd == "lock":
        await context.bot.set_chat_permissions(chat.id, ChatPermissions(can_send_messages=False))
        await update.message.reply_text(f"{STYLE['header']}\n馃敀 <b>GROUP LOCKED</b>\nOnly admins can speak.{STYLE['sig']}", parse_mode="HTML")
    elif cmd == "unlock":
        await context.bot.set_chat_permissions(chat.id, ChatPermissions(
            can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True
        ))
        await update.message.reply_text(f"{STYLE['header']}\n馃敁 <b>GROUP UNLOCKED</b>\nEveryone can speak.{STYLE['sig']}", parse_mode="HTML")

async def cmd_purge(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_SUPER_ADMIN: return
    if not update.message.reply_to_message: return await update.message.reply_text("Reply to start purging.")
    
    msg_id = update.message.reply_to_message.message_id
    current_id = update.message.message_id
    
    await update.message.delete() 
    ids_to_delete = list(range(msg_id, current_id + 1))
    if len(ids_to_delete) > 50: ids_to_delete = ids_to_delete[-50:]
    
    deleted = 0
    for mid in ids_to_delete:
        try: await context.bot.delete_message(update.effective_chat.id, mid); deleted += 1
        except: pass
        
    msg = await context.bot.send_message(update.effective_chat.id, f"馃棏锔� Purged {deleted} messages.")
    time.sleep(3)
    try: await msg.delete()
    except: pass

async def cmd_info(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_ADMIN: return
    target = await get_target_user(update, context)
    if not target or target == "unknown_username": return await update.message.reply_text("Target required.")
    
    ud = state.get_user_data(target.id)
    perm_lvl = await check_permissions(target.id, update.effective_chat.id, context)
    
    role = "User"
    if perm_lvl == PERM_OWNER: role = "OWNER"
    elif perm_lvl == PERM_SUPER_ADMIN: role = "Super Admin"
    elif perm_lvl == PERM_ADMIN: role = "Admin"
    elif perm_lvl == PERM_VIP: role = "VIP"
    
    # FORMAT JOIN DATE
    join_ts = ud.get("join_date")
    join_str = datetime.fromtimestamp(join_ts).strftime("%Y-%m-%d %H:%M") if join_ts else "Unknown (Joined before V12)"

    text = (
        f"{STYLE['info']}\n"
        f"馃懁 <b>Name:</b> {target.full_name}\n"
        f"馃啍 <b>ID:</b> <code>{target.id}</code>\n"
        f"馃洝锔� <b>Role:</b> {role}\n"
        f"馃搮 <b>Joined:</b> {join_str}\n"
        f"鈿狅笍 <b>Warns:</b> {ud['warns']}/5\n"
        f"{STYLE['sig']}"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_reset_warns(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_ADMIN: return
    target = await get_target_user(update, context)
    if not target or target == "unknown_username": return await update.message.reply_text("Target required.")
    
    ud = state.get_user_data(target.id)
    ud["warns"] = 0
    ud["timestamps"] = []
    state.update_user_data(target.id, ud)
    await update.message.reply_text(f"{STYLE['success']}\nWarnings reset for {target.first_name}.", parse_mode="HTML")

async def admin_broadcast(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_ADMIN: return
    if not context.args: return
    code = state.data["admin_codes"].get(str(update.effective_user.id), f"A-{str(update.effective_user.id)[-4:]}")
    text = f"{' '.join(context.args)}\n\nSigned: <b>{code}</b>"
    await update.message.delete()
    if "reply" in update.message.text and update.message.reply_to_message:
        await context.bot.send_message(update.effective_chat.id, text, reply_to_message_id=update.message.reply_to_message.message_id, parse_mode="HTML")
    else:
        await context.bot.send_message(update.effective_chat.id, text, parse_mode="HTML")

async def admin_replace(update, context):
    if await check_permissions(update.effective_user.id, update.effective_chat.id, context) < PERM_ADMIN: return
    if not update.message.reply_to_message: return await update.message.reply_text("Reply to a message.")
    if not context.args: return

    target_msg = update.message.reply_to_message
    target_user = target_msg.from_user
    admin_i
