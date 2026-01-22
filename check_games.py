import requests
import os
import json
from datetime import datetime

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    response = requests.get(url).json()
    games = response['data']['Catalog']['searchStore']['elements']
    
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
        original_price = price_info['originalPrice']
        
        if discount_price == 0 and game.get('promotions'):
            title = game['title']
            
            promo_info = game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]
            end_date_str = promo_info['endDate']
            end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            
            gun_adi = gunler[end_date.strftime("%A")]
            ay_adi = aylar[end_date.strftime("%B")]
            saat_dakika = end_date.strftime("%H:%M")
            gun_sayisi = end_date.strftime("%d")
            
            # İstediğin yeni sıralama: Gün Ay Saat (Gün İsmi)
            bitis_metni = f"{gun_sayisi} {ay_adi} {saat_dakika} ({gun_adi})"
            
            image_url = ""
            for img in game.get('keyImages', []):
                if img.get('type') == 'Thumbnail' or img.get('type') == 'OfferImageWide':
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
            fmt_original = f"{original_price/100:.2f} TL"
            
            msg = (
                f"*{title}*\n\n"
                f"💰 Güncel Fiyat: {fmt_original}\n\n"
                f"⌛ **Son Tarih:** {bitis_metni}\n\n"
                f"👇 *Hemen Al*"
            )
            
            send_telegram_photo(msg, link, image_url)

def send_telegram_photo(message, game_url, image_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Kütüphanene Ekle", "url": game_url}]]}
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    requests.post(url, data=payload)

if __name__ == "__main__":
    check_epic()
