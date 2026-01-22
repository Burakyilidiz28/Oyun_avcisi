import requests
import os
import json
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

def write_log(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")

def load_sent_games_list():
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            return f.read().splitlines()
    return []

def check_epic():
    found_titles = []
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(url).json()
        games = response['data']['Catalog']['searchStore']['elements']
    except: return []

    gunler = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    aylar = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}
    
    # Dosyadaki tüm satırları oku (ID kontrolü için)
    full_logs = load_sent_games_list()

    for game in games:
        price_info = game['price']['totalPrice']
        if price_info['discountPrice'] == 0 and game.get('promotions'):
            title = game['title']
            game_id = f"ID:epic_{title.replace(' ', '_')}"
            
            # Daha önce gönderildi mi kontrol et
            if any(game_id in line for line in full_logs): continue

            promo_info = game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]
            end_date = datetime.strptime(promo_info['endDate'], "%Y-%m-%dT%H:%M:%S.%fZ")
            bitis_metni = f"{end_date.strftime('%d')} {aylar[end_date.strftime('%B')]} {end_date.strftime('%H:%M')} ({gunler[end_date.strftime('%A')]})"
            
            image_url = next((img['url'] for img in game.get('keyImages', []) if img['type'] in ['Thumbnail', 'OfferImageWide']), "")
            slug = game.get('urlSlug') or (game.get('catalogNs', {}).get('mappings') or [{}])[0].get('pageSlug') or "free-games"
            link = f"https://store.epicgames.com/tr/p/{slug}"

            msg = f"*{title}*\n\n💰 Fiyat: {price_info['originalPrice']/100:.2f} TL\n⌛ Son: {bitis_metni}\n\n👇 *Hemen Al*"
            
            if send_telegram(msg, link, image_url):
                write_log(f"TELEGRAM GÖNDERİLDİ: {title} ({game_id})")
                found_titles.append(title)
    return found_titles

def check_other_platforms():
    found_titles = []
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=15"
    headers = {'User-agent': 'OyunBotu 2.0'}
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
    except: return []

    full_logs = load_sent_games_list()

    for post in posts:
        data = post['data']
        title_upper = data['title'].upper()
        
        if "100%" in title_upper or "FREE" in title_upper:
            if "PRIME" in title_upper: continue
            
            game_id = f"ID:ext_{data['id']}"
            if any(game_id in line for line in full_logs): continue

            link = data['url']
            msg = f"*{data['title']}*\n\n💰 Fiyat: 0.00 TL\nℹ️ Yeni Fırsat!\n\n👇 *Hemen Al*"
            
            if send_telegram(msg, link, ""):
                write_log(f"TELEGRAM GÖNDERİLDİ: {data['title']} ({game_id})")
                found_titles.append(data['title'])
    return found_titles

def send_telegram(message, game_url, image_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Kütüphanene Ekle", "url": game_url}]]}
    
    if image_url:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    
    r = requests.post(url, data=payload)
    return r.status_code == 200

if __name__ == "__main__":
    e_found = check_epic()
    o_found = check_other_platforms()
    
    if not e_found and not o_found:
        write_log("KONTROL TAMAMLANDI: Yeni oyun bulunamadı.")
