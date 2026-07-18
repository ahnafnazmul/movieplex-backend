import os
import json

MASTER_DB = 'movie_master_db.json'
MANUAL_DATA = 'manualdata.json'

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {filename}: {e}")
    return []

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    print("🚀 Starting Smart Manual Merge Engine...")
    
    # ফাইল দুটি লোড করা হচ্ছে
    master_list = load_json(MASTER_DB)
    manual_list = load_json(MANUAL_DATA)
    
    if not manual_list:
        print("ℹ️ manualdata.json is empty or not a valid list. Nothing to merge.")
        return
        
    # সহজে ম্যাচ করার জন্য মাস্টার ডেটাকে ডিকশনারিতে রূপান্তর (Key: id)
    master_dict = {item['id']: item for item in master_list}
    
    added_count = 0
    merged_count = 0
    
    for new_item in manual_list:
        m_id = new_item.get('id')
        if not m_id:
            print(f"⚠️ Skipping item due to missing 'id' key: {new_item.get('title', 'Unknown Title')}")
            continue
            
        # ১. কন্টেন্ট যদি অলরেডি মাস্টার ডেটাবেজে থাকে
        if m_id in master_dict:
            # ক্যাটাগরি ইউনিকভাবে মার্জ করা
            if 'categories' in new_item and 'categories' in master_dict[m_id]:
                for cat in new_item['categories']:
                    if cat not in master_dict[m_id]['categories']:
                        master_dict[m_id]['categories'].append(cat)
            
            # প্লেয়ার লিংক ইউনিকভাবে চেক ও মার্জ করা
            existing_urls = [p['player_url'] for p in master_dict[m_id].get('players', [])]
            link_added = False
            
            for player in new_item.get('players', []):
                if player['player_url'] not in existing_urls:
                    master_dict[m_id].setdefault('players', []).append(player)
                    link_added = True
            
            if link_added:
                merged_count += 1
                print(f"   🔵 Updated new links inside: {master_dict[m_id]['title']}")
                
        # ২. কন্টেন্ট যদি একদম ফ্রেশ/নতুন হয়
        else:
            master_dict[m_id] = new_item
            added_count += 1
            print(f"   ✅ Added brand new content: {new_item['title']}")
            
    # মাস্টার ডেটাবেজ ফাইল আপডেট ও সেভ
    save_json(MASTER_DB, list(master_dict.values()))
    print(f"📊 Merge Summary -> Fresh Added: {added_count} | Links Updated: {merged_count}")
    
    # 🧹 কাজ শেষ হওয়ার পর manualdata.json ফাইলটি একদম ফাঁকা করে দেওয়া হচ্ছে
    # যাতে পরের বার আপনি নতুন করে ফ্রেশ ডেটা পেস্ট করতে পারেন
    save_json(MANUAL_DATA, [])
    print(f"🧹 Cleared manualdata.json for next input cycle.")

if __name__ == '__main__':
    main()
