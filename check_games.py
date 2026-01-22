import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

def update_log_file(platform_status):
    permanent_games = []
    total_tl = 0.0
    total_usd = 0.0
    
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if "ID:" in line:
                    permanent_games.append(line.strip())
                    # TL ve USD tutarlarını satırlardan ayıkla
                    usd_match = re.search(r"\$ (\d+\.\d+)", line)
                    tl_match = re.search(r"(\d+\.\d+) TL", line)
                    if usd_match:
                        total_usd += float(usd_match.group(1))
                    elif tl_match:
                        total_tl += float(tl_match.group(1))

    now = datetime.now().strftime('%d %B %H:%M')
    
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n")
        f.write(f"{total_tl:.2f} TL ve {total_usd:.2f} $\n\n")
        
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for game in permanent_games:
            f.write(f"{game}\n")
        
        f.write("\n--- 🔍 SON TARAMA BİLGİSİ ---\n")
        f.write(f"Son Tarama Zamanı: {now}\n\n")
        
        for p_name in sorted(platform_status.keys()):
            f.write(f"{p_name}: {platform_status[p_name]}\n")

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(url, timeout=10).json()
        games = response['data']['Catalog']['searchStore']['elements']
        found_new = False
        content = ""
        if os.path.exists(SENT_GAMES_FILE):
            with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f: content = f.read()

        for game in games:
            price_info = game['price']['totalPrice']
            if price_info['discountPrice'] == 0 and game.get('promotions'):
                title = game['title']
                game_id = f"ID:epic_{title.replace(' ', '_')}"
                if game_id in content: continue

                old_price_tl = price_info['originalPrice']/100
                if send_telegram(f"*{title}*\n💰 Eski Fiyat: {old_price_tl:.2f} TL", "https://store.epicgames.com/tr/free-games"):
                    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                        date_str = datetime.now().strftime('%m-%d-%Y')
                        f_app.write(f"{title} | {old_price_tl:.2f} TL ({game_id}) [{date_str}]\n")
                    found_new = True
        return "✅" if found_new else "❌", found_new
    except: return "⚠️", False

def check_reddit_sources():
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=20"
    headers = {'User-agent': 'OyunBotu 12.0'}
    stats = {"Steam": "❌", "GOG": "❌", "Ubisoft": "❌", "EA App": "❌", "Prime Gaming": "❌", "Itch.io": "❌", "IndieGala": "❌", "Microsoft Store": "❌"}
    any_new_found = False
    
    try:
        response = requests.get(url, headers=headers, timeout=10).json()
        posts = response['data']['children']
        content = ""
        if os.path.exists(SENT_GAMES_FILE):
            with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f: content = f.read()

        for post in posts:
            data = post['data']
            title_up = data['title'].upper()
            
            if "100%" in title_up or "FREE" in title_up:
                game_id = f"ID:ext_{data['id']}"
                if game_id in content: continue

                platform_name = "Bilinmeyen Mağaza"
                detected = False
                for p in list(stats.keys()):
                    if p.upper() in title_up:
                        platform_name = p
                        detected = True
                        break
                
                if not detected and "[" in data['title']:
                    platform_name = data['title'].split(']')[0].replace('[', '').strip()
                    if platform_name not in stats: stats[platform_name] = "❌"

                price_match = re.search(r"(\$|£|€)(\d+\.?\d*)", data['title'])
                display_price = "0.00 TL"
                if price_match:
                    display_price = f"$ {price_match.group(2)}"

                if send_telegram(f"*{data['title']}*\n💰 Eski Fiyat: {display_price}", data['url']):
                    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                        date_str = datetime.now().strftime('%m-%d-%Y')
                        f_app.write(f"{data['title']} | {display_price} ({game_id}) [{date_str}]\n")
                    stats[platform_name] = "✅"
                    any_new_found = True
        return stats, any_new_found
    except: return stats, False

def send_telegram(message, game_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Al", "url": game_url}]]}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: return requests.post(url, data={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}).status_code == 200
    except: return False

if __name__ == "__main__":
    if not os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
            f.write("--- 💰 TOPLAM TASARRUF ---\n0.00 TL ve 0.00 $\n\n")
    
    e_s, e_n = check_epic()
    r_stats, r_n = check_reddit_sources()
    final_status = {"Epic Games": e_s}
    final_status.update(r_stats)
    update_log_file(final_status)
