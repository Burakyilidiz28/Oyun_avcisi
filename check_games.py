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
        
        if discount_price == 0 and game.get('promotions'):
            title = game['title']
            
            # Kapak resmini seç
            image_url = ""
            for img in game.get('keyImages', []):
                if img.get('type') == 'Thumbnail' or img.get('type') == 'OfferImageWide':
                    image_url = img.get('url')
                    break
            
            # Link oluşturma
            slug = "free-games"
            try:
                if game.get('catalogNs', {}).get('mappings'):
                    slug = game['catalogNs']['mappings'][0]['pageSlug']
                elif game.get('urlSlug'):
                    slug = game['urlSlug']
            except:
                pass
                
            link = f"https://store.epicgames.com/tr/p/{slug}"
            fmt_original = f"{original_price/100:.2f} TL"
            
            # Daha temiz ve ferah mesaj tasarımı
            msg = (
                f"🕹 *{title}*\n\n"
                f"💰 ~~{fmt_original}~~  ➡️  *BEDAVA*\n\n"
                f"⏳ Son şans kaçırmadan kütüphanene ekle!"
            )
            
            send_telegram_photo(msg, link, image_url)

def send_telegram_photo(message, game_url, image_url):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🎮 Oyunu Kütüphanene Ekle", "url": game_url}
        ]]
    }
    
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        'chat_id': chat_id,
        'photo': image_url,
        'caption': message,
        'parse_mode': 'Markdown',
        'reply_markup': json.dumps(reply_markup)
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    check_epic()
