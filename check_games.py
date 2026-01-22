import requests
import os
import json
import re
import time
from datetime import datetime

# Dosya ismi
SENT_GAMES_FILE = "sent_games.txt"

def get_epic_image_by_name(game_name):
    """Epic Games mağazasında isimle görsel arar."""
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', game_name).strip()
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={clean_name}&locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(search_url, timeout=5).json()
        elements = response['data']['Catalog']['searchStore']['elements']
        if elements:
            for img in elements[0].get('keyImages', []):
                if img.get('type') in ['OfferImageWide', 'Thumbnail', 'DieselStoreFrontWide']:
                    return img.get('url')
    except:
        return ""
    return ""

def send_telegram(message, game_url, platform_name, image_url=""):
    """Telegram'a mesaj veya fotoğraflı mesaj gönderir."""
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("HATA: Telegram Token veya Chat ID bulunamadı!")
        return False

    # İSTEDİĞİN DİNAMİK BUTON YAPISI
    reply_markup = {"inline_keyboard": [[{"text": f"🎮 Kütüphanene Ekle [{platform_name}]", "url": game_url}]]}
    
    if image_url:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {
            'chat_id': chat_id, 
            'photo': image_url, 
            'caption': message, 
            'parse_mode': 'Markdown', 
            'reply_markup': json.dumps(reply_markup)
        }
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id, 
            'text': message, 
            'parse_mode': 'Markdown', 
            'reply_markup': json.dumps(reply_markup)
        }
    
    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Bağlantı Hatası: {e}")
        return False

def check_epic():
    """Epic Games mağazasını tarar."""
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    days_tr = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    months_tr = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}

    try:
        response = requests.get(url, timeout=10).json()
        games = response['data']['Catalog']['searchStore']['elements']
        found_new = False
        content = ""
        if os.path.exists(SENT_GAMES_FILE):
            with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f: content = f.read()

        for game in games:
            price_info = game.get('price', {}).get('totalPrice', {})
            promotions = game.get('promotions')
            
            if price_info.get('discountPrice') == 0 and promotions:
                offers = promotions.get('promotionalOffers', [])
                if not offers: continue
                
                actual_offers = offers[0].get('promotionalOffers', [])
                for offer in actual_offers:
                    title = game['title']
                    game_id = f"ID:epic_{title.replace(' ', '_')}"
                    
                    if game_id in content: continue

                    end_date_raw = offer['endDate'].replace('Z', '+00:00')
                    end_dt = datetime.fromisoformat(end_date_raw)
                    expiry_str = f"{end_dt.strftime('%d')} {months_tr.get(end_dt.strftime('%B'))} {end_dt.strftime('%H:%M')} ({days_tr.get(end_dt.strftime('%A'))})"

                    image_url = ""
                    for img in game.get('keyImages', []):
                        if img.get('type') in ['OfferImageWide', 'Thumbnail']:
                            image_url = img.get('url'); break

                    old_price = price_info.get('originalPrice', 0) / 100
                    
                    # İSTEDİĞİN MESAJ FORMATI
                    message = (f"**[{title}]**\n\n"
                               f"💰 **Fiyatı:** {old_price:.2f} TL\n"
                               f"⏳ **Son Tarih:** {expiry_str}\n\n"
                               f"👇 **Hemen Al**")
                    
                    if send_telegram(message, "https://store.epicgames.com/tr/free-games", "Epic Games", image_url):
                        with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                            f_app.write(f"{title} | {old_price:.2f} TL ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]\n")
                        found_new = True
        return "✅" if found_new else "❌", found_new
    except Exception as e:
        print(f"Epic Tarama Hatası: {e}")
        return "⚠️", False

def check_reddit_sources():
    """Reddit üzerinden Steam, GOG vb. tarar."""
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=15"
    headers = {'User-agent': 'OyunAvcisiBot 2.0'}
    platforms = ["Steam", "GOG", "Ubisoft", "EA App", "Prime Gaming", "Itch.io"]
    found_new = False
    
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

                detected_platform = "Mağaza"
                for p in platforms:
                    if p.upper() in title_up:
                        detected_platform = p; break
                
                image_url = get_epic_image_by_name(data['title'])
                
                price_match = re.search(r"(\$|£|€)(\d+\.?\d*)", data['title'])
                display_price = f"{price_match.group(1)} {price_match.group(2)}" if price_match else "Ücretsiz"

                # İSTEDİĞİN MESAJ FORMATI (REDDIT/DIĞER)
                message = (f"**[{data['title']}]**\n\n"
                           f"💰 **Fiyatı:** {display_price}\n\n"
                           f"👇 **Hemen Al**")

                if send_telegram(message, data['url'], detected_platform, image_url):
                    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                        f_app.write(f"{data['title']} | {display_price} ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]\n")
                    found_new = True
        return "✅" if found_new else "❌", found_new
    except Exception as e:
        print(f"Reddit Tarama Hatası: {e}")
        return "⚠️", False

if __name__ == "__main__":
    print(f"Tarama Başladı: {datetime.now().strftime('%H:%M:%S')}")
    start_time = time.time()
    
    if not os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
            f.write("--- 🏆 OYUN AVIMIZ ---\n\n")

    check_epic()
    check_reddit_sources()
    
    duration = time.time() - start_time
    print(f"Tarama Tamamlandı. Süre: {duration:.2f} saniye.")
