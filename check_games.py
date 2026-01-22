import requests
import os
import json
from datetime import datetime

# Hafıza dosyasının adı
SENT_GAMES_FILE = "sent_games.txt"

def get_sent_games():
    if not os.path.exists(SENT_GAMES_FILE):
        return []
    with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_sent_games(game_id):
    with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f:
        f.write(game_id + "\n")

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    response = requests.get(url).json()
    games = response['data']['Catalog']['searchStore']['elements']
    
    sent_games = get_sent_games()
    
    gunler = {
        "Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba",
        "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"
    }
    
    aylar = {
        "January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan",
        "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos",
        "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"
    }

    for game in games:
        price_info = game['price']['totalPrice']
        discount_price = price_info['discountPrice']
        
        # Sadece ücretsiz ve promosyonu olanları al
        if discount_price == 0 and game.get('promotions') and game['promotions']['promotionalOffers']:
            title = game['title']
            game_id = game['id'] # Her oyunun benzersiz bir ID'si vardır
            
            # EĞER BU OYUN DAHA ÖNCE GÖNDERİLDİYSE PAS GEÇ
            if game_id in sent_games:
                continue

            promo_info = game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]
            end_date_str = promo_info['endDate']
            end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            
            gun_adi = gunler[end_date.strftime("%A")]
            ay_adi = aylar[end_date.strftime("%B")]
            saat_dakika = end_date.strftime("%H:%M")
            gun_sayisi = end_date.strftime("%d")
            
            bitis_metni = f"{gun_sayisi} {ay_adi} {saat_dakika} ({gun_adi})"
            
            image_url = ""
            for img in game.get('keyImages', []):
                if img.get('type') in ['Thumbnail', 'OfferImageWide']:
                    image_url = img.get('url')
                    break
            
            slug = "free-games"
            try:
                if game.get('catalogNs', {}).get('mappings'):
                    slug = game['catalogNs']['mappings'][0]['pageSlug']
                elif game.get('urlSlug'):
                    slug = game['urlSlug']
            except: pass
                
            link = f"https://store.epicgames.com/tr/p/{slug}"
            fmt_original = f"{price_info['originalPrice']/100:.2f} TL"
            
            msg = (
                f"*{title}*\n\n"
                f"💰 Güncel Fiyat: {fmt_original}\n\n"
                f"⌛ **Son Tarih:** {bitis_metni}\n\n"
                f"👇 *Hemen Al*"
            )
            
            # Telegram'a gönder
            send_telegram_photo(msg, link, image_url)
            # Hafızaya kaydet
            add_to_sent_games(game_id)

def send_telegram_photo(message, game_url, image_url):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Kütüphanene Ekle", "url": game_url}]]}
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    requests.post(url, data=payload)

if __name__ == "__main__":
    check_epic()
