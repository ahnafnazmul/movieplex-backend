import os
import json
import time
import requests
from bs4 import BeautifulSoup
import cloudscraper
import re

# গিটহাব ভ্যারিয়েবল ও সিক্রেটস থেকে ডেটা নেওয়া
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
TMDB_API_KEY = d7e75f78343840e48bf11200be3d7ec9'

# ডাইনামিক সোর্স ইউআরএল (গিটহাব ভ্যারিয়েবল থেকে আসবে, না থাকলে ডিফল্ট)
URL_MOVIEBOX = os.getenv("URL_MOVIEBOX", "https://themoviebox.xyz/")
URL_MLBD = os.getenv("URL_MLBD", "https://jy5g4w.movielinkbd.li/")
URL_BANGLAPLEX = os.getenv("URL_BANGLAPLEX", "https://banglaplex.lat/")
URL_RTALLY = os.getenv("URL_RTALLY", "https://www.rtally.site/home")

DB_FILE = 'movie_master_db.json'
BANNED_WORDS = ['fifa', 'world cup', 'ipl', 'live tv', 'sports', 'japan', 'japanese', '18+', 'adult', 'ullu']

report_log = {"added": 0, "merged": 0, "errors": []}

def send_telegram_report():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    msg = f"🤖 *Movieplex BD Daily Sync*\n\n"
    msg += f"✅ New Content Added: {report_log['added']}\n"
    msg += f"🔄 Existing Merged: {report_log['merged']}\n\n"
    if report_log['errors']:
        msg += "⚠️ *Errors/Alerts:*\n" + "\n".join(report_log['errors'])
    else:
        msg += "🌟 All Sources Scanned Successfully!"
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

def is_banned(title):
    return any(w in title.lower() for w in BANNED_WORDS)

# [এখানে TMDB গেটকিপার ফাংশনটি আগের মতোই থাকবে, তবে 'media_type' অনুযায়ী 'type': 'series' বা 'movie' রিটার্ন করবে]
# ... (Get TMDB Info Logic) ...

def scrape_homepage_moviebox(scraper, db_dict):
    print("-> Scanning Moviebox Homepage...")
    try:
        res = scraper.get(URL_MOVIEBOX, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        # শুধু হোমপেজের লেটেস্ট মুভি লিঙ্ক
        links = set(re.findall(r'href=["\'](.*?/detail/.*?)["\']', res.text))
        
        for l in list(links)[:30]: # প্রথম ৩০টি লেটেস্ট
            full_url = l if l.startswith('http') else URL_MOVIEBOX.rstrip('/') + '/' + l.lstrip('/')
            # ... (লিঙ্কে ঢুকে .mp4 বের করা এবং TMDB চেক করে db_dict এ অ্যাড বা মার্জ করা) ...
            # সফল হলে report_log['added'] বা report_log['merged'] আপডেট করা
    except Exception as e:
        report_log['errors'].append(f"Moviebox Failed: {str(e)}")

def scrape_homepage_mlbd(scraper, db_dict):
    print("-> Scanning MLBD Homepage...")
    try:
        res = scraper.get(URL_MLBD, timeout=15)
        # হোমপেজ লজিক...
    except Exception as e:
        report_log['errors'].append(f"MLBD Failed: {str(e)}")

# Banglaplex & Rtally logic inside try-except...

if __name__ == '__main__':
    print("🚀 Initiating Daily Lightweight Scanner...")
    existing_db = load_db()
    db_dict = {item['id']: item for item in existing_db}
    
    scraper = cloudscraper.create_scraper()
    
    # Isolated Execution (একটার ভুলের জন্য অন্যটা থামবে না)
    scrape_homepage_moviebox(scraper, db_dict)
    scrape_homepage_mlbd(scraper, db_dict)
    # scrape_homepage_banglaplex(scraper, db_dict)
    # scrape_homepage_rtally(scraper, db_dict)
    
    save_db(list(db_dict.values()))
    send_telegram_report()
    print("✅ Sync Complete & Report Sent!")
