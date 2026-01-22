import requests
import os
import json
from datetime import datetime

# Hafıza dosyası
SENT_GAMES_FILE = "sent_games.txt"

def load_sent_games():
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r") as f:
            return f.read().splitlines()
    return []

def save_sent_game(game_id):
    with open(SENT_GAMES_FILE, "a") as f:
        f.write(game_id + "\n")

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(url).json()
        games = response['data']['Catalog']['searchStore']['elements']
    except: return

    gunler = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    aylar = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}
    
    sent_list = load_sent_games()

    for game in games:
        price_info = game['price']['totalPrice']
        if price_info['discountPrice'] == 0 and game.get('promotions'):
            title = game['title']
            # Benzersiz ID oluştur
            game_id = f"epic_{title.replace(' ', '_')}"
            
            if game_id in sent_list: continue

            # Tarih Formatı: 29 Ocak 19:00 (Perşembe)
            promo_info = game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]
            end_date = datetime.strptime(promo_info['endDate'], "%Y-%m-%dT%H:%M:%S.%fZ")
            bitis_metni = f"{end_date.strftime('%d')} {aylar[end_date.strftime('%B')]} {end_date.strftime('%H:%M')} ({gunler[end_date.strftime('%A')]})"
            
            image_url = next((img['url'] for img in game.get('keyImages', []) if img['type'] in ['Thumbnail', 'OfferImageWide']), "")
            slug = game.get('urlSlug') or (game.get('catalogNs', {}).get('mappings') or [{}])[0].get('pageSlug') or "free-games"
            link = f"https://store.epicgames.com/tr/p/{slug}"

            msg = (
                f"*{title}*\n\n"
                f"💰 Güncel Fiyat: {price_info['originalPrice']/100:.2f} TL\n\n"
                f"⌛ **Son Tarih:** {bitis_metni}\n\n"
                f"👇 *Hemen Al*"
            )
            
            if send_telegram(msg, link, image_url):
                save_sent_game(game_id)

def check_other_platforms():
    # Reddit üzerinden tüm platformları tarar
    url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=15"
    headers = {'User-agent': 'OyunBotu 2.0'}
    try:
        response = requests.get(url, headers=headers).json()
        posts = response['data']['children']
    except: return

    sent_list = load_sent_games()

    for post in posts:
        data = post['data']
        title_upper = data['title'].upper()
        
        # Filtre: Sadece %100 indirimli ve abonelik istemeyen (Prime hariç) oyunlar
        if "100%" in title_upper or "FREE" in title_upper:
            if "PRIME" in title_upper: continue # Prime oyunlarını atla
            
            game_id = f"ext_{data['id']}"
            if game_id in sent_list: continue

            link = data['url']
            # Başlıktaki [Steam] gibi platform bilgisini temizle veya kullan
            clean_title = data['title']
            
            msg = (
                f"*{clean_title}*\n\n"
                f"💰 Güncel Fiyat: 0.00 TL (Ücretsiz)\n\n"
                f"ℹ️ Yeni bir fırsat yakalandı!\n\n"
                f"👇 *Hemen Al*"
            )
            
            # Resim yoksa sadece mesaj gönderir
            if send_telegram(msg, link, ""):
                save_sent_game(game_id)

def send_telegram(message, game_url, image_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Kütüphanene Ekle", "url": game_url}]]}
    
    try:
        if image_url:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
        
        r = requests.post(url, data=payload)
        return r.status_code == 200
    except:
        return False

if __name__ == "__main__":
    check_epic()
    check_other_platforms()
