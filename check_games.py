import requests
import os
import json
import re
import time
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

def get_epic_image_by_name(game_name):
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', game_name).strip()
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={clean_name}&locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(search_url, timeout=5).json()
        elements = response['data']['Catalog']['searchStore']['elements']
        if elements:
            for img in elements[0].get('keyImages', []):
                if img.get('type') in ['OfferImageWide', 'Thumbnail']:
                    return img.get('url')
    except: return ""
    return ""

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return False

    reply_markup = {"inline_keyboard": [[{"text": f"🎮 Kütüphanene Ekle [{platform_name}]", "url": game_url}]]}
    endpoint = "sendPhoto" if image_url else "sendMessage"
    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    
    payload = {'chat_id': chat_id, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    if image_url:
        payload['photo'] = image_url
        payload['caption'] = message
    else:
        payload['text'] = message

    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except: return False

def parse_old_data():
    """Mevcut txt dosyasındaki oyunları ve tasarrufu okur."""
    games = []
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            # ID'leri ve oyun satırlarını yakala
            pattern = r"^(.*?) \| (.*?)(?: \((ID:.*?)\)) \[.*?\]"
            for line in content.split('\n'):
                match = re.search(pattern, line)
                if match:
                    games.append({
                        'full_line': line,
                        'id': match.group(3),
                        'price_str': match.group(2)
                    })
    return games

def update_txt_report(games_list, statuses):
    """Txt dosyasını senin istediğin şık formatta baştan yazar."""
    total_tl = 0.0
    total_usd = 0.0
    
    for g in games_list:
        p_str = g['price_str']
        if "TL" in p_str:
            try: total_tl += float(p_str.replace(" TL", ""))
            except: pass
        elif "$" in p_str:
            try: total_usd += float(p_str.replace("$ ", "").replace("$", ""))
            except: pass

    now_str = datetime.now().strftime('%d %B %H:%M').replace('January', 'Ocak').replace('February', 'Şubat') # Basit ay çeviri

    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 💰 TOPLAM TASARRUF ---\n")
        f.write(f"{total_tl:.2f} TL\n")
        f.write(f"${total_usd:.2f}\n\n")
        
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games_list:
            f.write(f"{g['full_line']}\n")
        
        f.write("\n--- 🔍 SON TARAMA BİLGİSİ ---\n")
        f.write(f"Son Tarama Zamanı: {datetime.now().strftime('%d %B %H:%M')}\n\n")
        for platform, status in statuses.items():
            f.write(f"{platform}: {status}\n")

def check_games():
    existing_games = parse_old_data()
    existing_ids = [g['id'] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    new_found = False

    # 1. EPIC GAMES KONTROL
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
        res = requests.get(url, timeout=10).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        for game in elements:
            price_info = game.get('price', {}).get('totalPrice', {})
            if price_info.get('discountPrice') == 0 and game.get('promotions'):
                title = game['title']
                game_id = f"ID:epic_{title.replace(' ', '_')}"
                if game_id in existing_ids: continue

                old_price = price_info.get('originalPrice', 0) / 100
                img = next((i['url'] for i in game.get('keyImages', []) if i['type'] in ['OfferImageWide', 'Thumbnail']), "")
                
                # Telegram Formatı
                msg = (f"**[{title}]**\n\n💰 **Fiyatı:** {old_price:.2f} TL\n"
                       f"⏳ **Son Tarih:** Kampanya Aktif\n\n👇 **Hemen Al**")
                
                if send_telegram(msg, "https://store.epicgames.com/tr/free-games", "Epic Games", img):
                    existing_games.append({
                        'full_line': f"{title} | {old_price:.2f} TL ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                        'id': game_id,
                        'price_str': f"{old_price:.2f} TL"
                    })
                    statuses["Epic Games"] = "✅"
                    new_found = True
    except: statuses["Epic Games"] = "⚠️"

    # 2. REDDIT (STEAM VB) KONTROL
    try:
        url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=10"
        res = requests.get(url, headers={'User-agent': 'OyunBot'}, timeout=10).json()
        for post in res['data']['children']:
            data = post['data']
            if "100%" in data['title'].upper() or "FREE" in data['title'].upper():
                game_id = f"ID:ext_{data['id']}"
                if game_id in existing_ids: continue

                img = get_epic_image_by_name(data['title'])
                price_match = re.search(r"(\$|£|€)(\d+\.?\d*)", data['title'])
                price_val = f"$ {price_match.group(2)}" if price_match else "Ücretsiz"
                
                msg = (f"**[{data['title']}]**\n\n💰 **Fiyatı:** {price_val}\n\n👇 **Hemen Al**")
                
                platform = "Steam" if "STEAM" in data['title'].upper() else "Mağaza"
                if send_telegram(msg, data['url'], platform, img):
                    existing_games.append({
                        'full_line': f"{data['title']} | {price_val} ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                        'id': game_id,
                        'price_str': price_val
                    })
                    statuses["Steam"] = "✅"
                    new_found = True
    except: statuses["Steam"] = "⚠️"

    update_txt_report(existing_games, statuses)

if __name__ == "__main__":
    check_games()
