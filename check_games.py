import requests
import os
import json

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    response = requests.get(url).json()
    games = response['data']['Catalog']['searchStore']['elements']
    
    for game in games:
        price_info = game['price']['totalPrice']
        discount_price = price_info['discountPrice']
        original_price = price_info['originalPrice']
        
        # Sadece bedava olan ve promosyonu aktif olanları seç
        if discount_price == 0 and game.get('promotions'):
            title = game['title']
            
            # Link oluşturma mantığı
            slug = "free-games" # Varsayılan
            try:
                if game.get('catalogNs', {}).get('mappings'):
                    slug = game['catalogNs']['mappings'][0]['pageSlug']
                elif game.get('urlSlug'):
                    slug = game['urlSlug']
            except:
                pass
                
            link = f"https://store.epicgames.com/tr/p/{slug}"
            fmt_original = f"{original_price/100:.2f} TL"
            
            msg = (
                f"🎮 *YENİ ÜCRETSİZ OYUN!*\n\n"
                f"🕹 *Oyun:* {title}\n"
                f"💰 *Eski Fiyat:* ~{fmt_original}~\n"
                f"🔥 *Yeni Fiyat:* BEDAVA\n\n"
                f"📅 *Hemen kütüphanene eklemeyi unutma!*"
            )
            send_telegram(msg, link)

def send_telegram(message, game_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    
    # Buton yapısı
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🚀 Oyunu Kütüphanene Ekle", "url": game_url}
        ]]
    }
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
        'reply_markup': json.dumps(reply_markup)
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    check_epic()
