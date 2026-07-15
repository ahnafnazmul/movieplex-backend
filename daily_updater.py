import os
import json
import time
import requests
from bs4 import BeautifulSoup
import cloudscraper
import re
from playwright.sync_api import sync_playwright

# ================= Configurations =================
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
TMDB_API_KEY = 'd7e75f78343840e48bf11200be3d7ec9'

URL_MOVIEBOX = os.getenv("URL_MOVIEBOX", "https://themoviebox.xyz/")
URL_BANGLAPLEX = os.getenv("URL_BANGLAPLEX", "https://banglaplex.lat/")
URL_MLBD = os.getenv("URL_MLBD", "https://jy5g4w.movielinkbd.li/")
URL_RTALLY = os.getenv("URL_RTALLY", "https://www.rtally.site/home")

DB_FILE = 'movie_master_db.json'
BANNED_WORDS = ['fifa', 'world cup', 'ipl', 'wwe', 'live tv', 'sports', 'camrip', 'hdcam', 'japan', 'japanese', 'jav', '18+', 'adult']

# রিপোর্ট ট্র্যাকিং ডিকশনারি
report_log = {
    "site_status": {
        "Moviebox": "❌",
        "Banglaplex": "❌",
        "Movielink BD": "❌",
        "Rtally": "❌"
    },
    "added_count": 0,
    "merged_count": 0,
    "content_names": [],
    "total_db": 0
}

def send_telegram_report():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing. Skipping report.")
        return
    
    total_added = report_log['added_count'] + report_log['merged_count']
    
    # তোমার দেওয়া ফর্ম্যাট অনুযায়ী মেসেজ তৈরি
    msg = f"Hello Boss, This Is Your Admin,\nReporting Scheduled Update:\n\n"
    msg += f"Moviebox {report_log['site_status']['Moviebox']}\n"
    msg += f"Banglaplex {report_log['site_status']['Banglaplex']}\n"
    msg += f"Movielink BD {report_log['site_status']['Movielink BD']}\n"
    msg += f"Rtally {report_log['site_status']['Rtally']}\n\n"
    
    msg += f"Content Added: {total_added} Totals after Merging.\n"
    
    if report_log['content_names']:
        msg += "Contents Name:\n"
        # নামের লিস্ট (সর্বোচ্চ ৪০টি নাম দেখাবে যাতে মেসেজ সাইজ লিমিট ক্রস না করে)
        for idx, name in enumerate(report_log['content_names'][:40], 1):
            msg += f"{idx}. {name}\n"
            
    msg += f"\nTotal Contents In Database is: {report_log['total_db']} Now."
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        print("✅ Telegram report sent!")
    except Exception as e:
        print(f"❌ Failed to send telegram: {e}")

def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return []

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_banned(title):
    return any(w in title.lower() for w in BANNED_WORDS)

def get_tmdb_max_info(title):
    if not TMDB_API_KEY: return None
    clean_title = re.sub(r'\(.*?\)|\[.*?\]|hindi|bengali|s01|s02|season|episode|complete', '', title, flags=re.IGNORECASE).strip()
    try:
        search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={clean_title}&language=en-US"
        res = requests.get(search_url, timeout=10).json()
        if res.get('results'):
            top = res['results'][0]
            media_type = top.get('media_type', 'movie')
            tmdb_id = top.get('id')
            if top.get('adult') == True: return "ADULT_REJECT"
            
            detail_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
            detail = requests.get(detail_url, timeout=10).json()
            if detail.get('adult') == True: return "ADULT_REJECT"
            
            genres = [g['name'] for g in detail.get('genres', [])]
            if any('animation' in g.lower() or 'anime' in g.lower() for g in genres): return "ANIME_REJECT"
                
            cast = [{"name": c['name'], "image": f"https://image.tmdb.org/t/p/w185{c['profile_path']}" if c.get('profile_path') else ""} for c in detail.get('credits', {}).get('cast', [])[:5]]
            runtime = detail.get('runtime') or (detail.get('episode_run_time', [0])[0] if detail.get('episode_run_time') else "N/A")
            
            type_formatted = "series" if media_type == "tv" else "movie"
            
            return {
                "id": f"{media_type}_{tmdb_id}", "type": type_formatted, "title": top.get('title') or top.get('name'),
                "poster": f"https://image.tmdb.org/t/p/w500{detail.get('poster_path')}" if detail.get('poster_path') else "",
                "backdrop": f"https://image.tmdb.org/t/p/w1280{detail.get('backdrop_path')}" if detail.get('backdrop_path') else "",
                "rating": round(detail.get('vote_average', 7.0), 1), "release_date": detail.get('release_date') or detail.get('first_air_date', '2026'),
                "runtime": f"{runtime} min", "categories": genres, "cast": cast, "details": detail.get('overview', 'Premium OTT content.'), "players": []
            }
    except: pass
    return None

# ================= Source 1: Moviebox =================
def scrape_moviebox(db_dict):
    print("-> 🌐 Scanning Moviebox Homepage...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(URL_MOVIEBOX, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
            html_content = page.content()
            links = set(re.findall(r'href=["\'](.*?/detail/.*?)["\']', html_content))
            browser.close()
        
        scraper = cloudscraper.create_scraper()
        for l in list(links)[:20]:
            full_url = l if l.startswith('http') else URL_MOVIEBOX.rstrip('/') + '/' + l.lstrip('/')
            try:
                res = scraper.get(full_url, timeout=10)
                if res.status_code != 200: continue
                soup = BeautifulSoup(res.text, 'html.parser')
                raw_title = soup.find('h1') or soup.find('h2')
                title = raw_title.text.strip() if raw_title else full_url.split('/')[-1]
                if is_banned(title): continue
                
                stream_urls = []
                for script in soup.find_all('script'):
                    if script.string:
                        cdn_links = re.findall(r'(https?://[^\s"\']+\.(?:mp4|m3u8)[^\s"\']*)', script.string)
                        for link in cdn_links:
                            if link not in [s['player_url'] for s in stream_urls]:
                                stream_urls.append({"server_name": "MovieBox Premium", "player_url": link})
                
                if not stream_urls: continue
                tmdb_data = get_tmdb_max_info(title)
                if not tmdb_data or tmdb_data in ["ADULT_REJECT", "ANIME_REJECT"]: continue
                
                m_id = tmdb_data['id']
                if m_id not in db_dict:
                    tmdb_data['players'] = stream_urls
                    tmdb_data['_source_site'] = "themoviebox"
                    db_dict[m_id] = tmdb_data
                    report_log['added_count'] += 1
                    if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
            except: pass
        report_log['site_status']['Moviebox'] = "✅"
    except Exception as e: print(f"Moviebox Error: {e}")

# ================= Source 2: Banglaplex =================
def scrape_banglaplex(db_dict):
    print("-> 🌐 Scanning Banglaplex...")
    scraper = cloudscraper.create_scraper()
    try:
        r = requests.get(URL_BANGLAPLEX, timeout=15)
        links = [a['href'] for a in BeautifulSoup(r.text, 'html.parser').find_all('a', href=True) if len(a['href']) > 5 and 'login' not in a['href']]
        for h in links[:15]:
            f = h if h.startswith('http') else URL_BANGLAPLEX.rstrip('/') + h
            if 'banglaplex.lat' not in f: continue
            try:
                res = scraper.get(f, timeout=10)
                if res.status_code != 200: continue
                soup = BeautifulSoup(res.text, 'html.parser')
                title = soup.title.text.split('|')[0].split('-')[0].strip() if soup.title else f.split('/')[-1]
                if is_banned(title): continue
                
                players = [{"server_name": "Banglaplex Stream", "player_url": iframe.get('src')} for iframe in soup.find_all('iframe') if iframe.get('src') and ('plextream' in iframe.get('src') or 'embed' in iframe.get('src'))]
                if not players: continue
                
                tmdb_data = get_tmdb_max_info(title)
                if not tmdb_data or tmdb_data in ["ADULT_REJECT", "ANIME_REJECT"]: continue
                
                m_id = tmdb_data['id']
                if m_id in db_dict:
                    existing_urls = [p['player_url'] for p in db_dict[m_id]['players']]
                    added = False
                    for p in players:
                        if p['player_url'] not in existing_urls: 
                            db_dict[m_id]['players'].append(p)
                            added = True
                    if added: 
                        report_log['merged_count'] += 1
                        if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
                else:
                    tmdb_data['players'] = players
                    tmdb_data['_source_site'] = "banglaplex"
                    db_dict[m_id] = tmdb_data
                    report_log['added_count'] += 1
                    if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
            except: pass
        report_log['site_status']['Banglaplex'] = "✅"
    except Exception as e: print(f"Banglaplex Error: {e}")

# ================= Source 3: Movielink BD =================
def scrape_mlbd(db_dict):
    print("-> 🌐 Scanning Movielink BD...")
    scraper = cloudscraper.create_scraper()
    try:
        r = scraper.get(URL_MLBD, timeout=15)
        links = set(re.findall(r'href=["\'](.*?/watch/.*?|.*?/series/.*?|.*?/movie/.*?)["\']', r.text))
        for l in list(links)[:15]:
            full_url = l if l.startswith('http') else URL_MLBD.rstrip('/') + '/' + l.lstrip('/')
            try:
                res = scraper.get(full_url, timeout=10)
                if res.status_code != 200: continue
                soup = BeautifulSoup(res.text, 'html.parser')
                title = soup.title.text.split('|')[0].split('-')[0].strip() if soup.title else full_url.split('/')[-1]
                if is_banned(title): continue
                
                players = []
                for a in soup.find_all('a', href=True):
                    if 'download' in a.text.lower():
                        href = a['href'] if a['href'].startswith('http') else URL_MLBD.rstrip('/') + '/' + a['href'].lstrip('/')
                        players.append({"server_name": f"MLBD {a.text.strip()[:4]}", "player_url": href})
                
                if not players: continue
                tmdb_data = get_tmdb_max_info(title)
                if not tmdb_data or tmdb_data in ["ADULT_REJECT", "ANIME_REJECT"]: continue
                
                m_id = tmdb_data['id']
                if m_id in db_dict:
                    existing_urls = [p['player_url'] for p in db_dict[m_id]['players']]
                    added = False
                    for p in players:
                        if p['player_url'] not in existing_urls: 
                            db_dict[m_id]['players'].append(p)
                            added = True
                    if added:
                        report_log['merged_count'] += 1
                        if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
                else:
                    tmdb_data['players'] = players
                    tmdb_data['_source_site'] = "movielinkbd"
                    db_dict[m_id] = tmdb_data
                    report_log['added_count'] += 1
                    if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
            except: pass
        report_log['site_status']['Movielink BD'] = "✅"
    except Exception as e: print(f"MLBD Error: {e}")

# ================= Source 4: Rtally =================
def scrape_rtally(db_dict):
    print("-> 🌐 Scanning Rtally...")
    scraper = cloudscraper.create_scraper()
    try:
        r = scraper.get(URL_RTALLY, timeout=15)
        links = [a['href'] for a in BeautifulSoup(r.text, 'html.parser').find_all('a', href=True) if len(a['href']) > 10]
        for h in links[:15]:
            f = h if h.startswith('http') else "https://www.rtally.site" + h
            if 'rtally.site' not in f: continue
            try:
                res = scraper.get(f, timeout=10)
                if res.status_code != 200: continue
                soup = BeautifulSoup(res.text, 'html.parser')
                title = soup.title.text.split('|')[0].strip() if soup.title else f.split('/')[-1]
                if is_banned(title): continue
                
                players = [{"server_name": "Rtally Stream", "player_url": iframe.get('src')} for iframe in soup.find_all('iframe') if iframe.get('src') and ('plextream' in iframe.get('src') or 'embed' in iframe.get('src'))]
                if not players: continue
                
                tmdb_data = get_tmdb_max_info(title)
                if not tmdb_data or tmdb_data in ["ADULT_REJECT", "ANIME_REJECT"]: continue
                
                m_id = tmdb_data['id']
                if m_id in db_dict:
                    existing_urls = [p['player_url'] for p in db_dict[m_id]['players']]
                    added = False
                    for p in players:
                        if p['player_url'] not in existing_urls: 
                            db_dict[m_id]['players'].append(p)
                            added = True
                    if added:
                        report_log['merged_count'] += 1
                        if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
                else:
                    tmdb_data['players'] = players
                    tmdb_data['_source_site'] = "rtally"
                    db_dict[m_id] = tmdb_data
                    report_log['added_count'] += 1
                    if tmdb_data['title'] not in report_log['content_names']: report_log['content_names'].append(tmdb_data['title'])
            except: pass
        report_log['site_status']['Rtally'] = "✅"
    except Exception as e: print(f"Rtally Error: {e}")

# ================= Main Execution =================
if __name__ == '__main__':
    print("🚀 Initiating Full Daily Scanner Engine...")
    existing_db = load_db()
    db_dict = {item['id']: item for item in existing_db}
    
    # Isolated Execution (একটা ফেইল করলে অন্যটা থামবে না)
    scrape_moviebox(db_dict)
    scrape_banglaplex(db_dict)
    scrape_mlbd(db_dict)
    scrape_rtally(db_dict)
    
    report_log['total_db'] = len(db_dict)
    
    save_db(list(db_dict.values()))
    send_telegram_report()
    print("✅ Sync Complete!")
