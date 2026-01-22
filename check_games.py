import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

def get_epic_image_by_name(game_name):
    """Oyun ismini Epic Games mağazasında arayıp görsel URL'sini döner."""
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={game_name}&locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(search_url, timeout=5).json()
        elements = response['data']['Catalog']['searchStore']['elements']
        if elements:
            # İlk eşleşen sonucun görsellerini kontrol et
            for img in elements[0].get('keyImages', []):
                if img.get('type') in ['OfferImageWide', 'Thumbnail', 'DieselStoreFrontWide']:
                    return img.get('url')
    except:
        return ""
    return ""

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
                    usd_match = re.search(r"\$ (\d+\.\d+)", line)
                    tl_match = re.search(r"(\d+\.\d+) TL", line)
                    if usd_match: total_usd += float(usd_match.group(1))
                    elif tl_match: total_tl += float(tl_match.group(1))

    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n{total_tl:.2f} TL ve {total_usd:.2f} $\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for game in permanent_games: f.write(f"{game}\n")
        f.write(f"\n--- 🔍 SON TARAMA BİLGİSİ ---\nSon Tarama Zamanı: {datetime.now().strftime('%d %B %H:%M')}\n\n")
        for p_name in sorted(platform_status.keys()): f.write(f"{p_name}: {platform_status[p_name]}\n")

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

                image_url = ""
                for img in game.get('keyImages', []):
                    if img.get('type') in ['Thumbnail', 'OfferImageWide', 'DieselStoreFrontWide']:
                        image_url = img.get('url'); break

                old_price_tl = price_info['originalPrice']/100
                message = f"*[{title}]*\n💰 Eski Fiyat: {old_price_tl:.2f} TL\n🎮 Platform: Epic Games"
                
                if send_telegram(message, "https://store.epicgames.com/tr/free-games", "Epic Games", image_url):
                    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                        f_app.write(f"{title} | {old_price_tl:.2f} TL ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]\n")
                    found_new = True
        return "✅" if found_new else "❌", found_new
    except: return "⚠️", False

def check_reddit_sources():
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=20"
    headers = {'User-agent': 'OyunBotu 16.0'}
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

                platform_name = "Bilinmeyen"
                for p in stats.keys():
                    if p.upper() in title_up: platform_name = p; break
                
                # Oyun ismini temizle (Parantezleri kaldırarak Epic'te daha iyi arama yapar)
                clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', data['title']).strip()
                image_url = get_epic_image_by_name(clean_name)

                price_match = re.search(r"(\$|£|€)(\d+\.?\d*)", data['title'])
                display_price = f"$ {price_match.group(2)}" if price_match else "0.00 TL"

                message = f"*[{data['title']}]*\n💰 Eski Fiyat: {display_price}\n🎮 Platform: {platform_name}"
                if send_telegram(message, data['url'], platform_name, image_url):
                    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                        f_app.write(f"{data['title']} | {display_price} ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]\n")
                    stats[platform_name] = "✅"; any_new_found = True
        return stats, any_new_found
    except: return stats, False

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    reply_markup = {"inline_keyboard": [[{"text": f"📖 Oyunu Al [{platform_name}]", "url": game_url}]]}
    
    if image_url:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    
    try: return requests.post(url, data=payload).status_code == 200
    except: return False

if __name__ == "__main__":
    if not os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
            f.write("--- 💰 TOPLAM TASARRUF ---\n0.00 TL ve 0.00 $\n\n")
    e_s, e_n = check_epic(); r_stats, r_n = check_reddit_sources()
    final_status = {"Epic Games": e_s}; final_status.update(r_stats)
    update_log_file(final_status)
