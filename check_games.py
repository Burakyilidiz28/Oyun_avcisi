import requests
import os

def check_epic():
    # Epic Games API'sine bağlan (Türkiye ayarlarıyla)
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    response = requests.get(url).json()
    games = response['data']['Catalog']['searchStore']['elements']
    
    for game in games:
        # Fiyat bilgilerini al
        price_info = game['price']['totalPrice']
        discount_price = price_info['discountPrice']
        original_price = price_info['originalPrice']
        
        # Sadece fiyatı 0 olan ve aktif bir promosyonu olanları seç
        if discount_price == 0 and game['promotions']:
            title = game['title']
            # Oyunun link uzantısını bul
            slug = game.get('catalogNs', {}).get('mappings', [{}])[0].get('pageSlug', '')
            if not slug:
                slug = game.get('urlSlug', '')
                
            link = f"https://store.epicgames.com/tr/p/{slug}"
            
            # Fiyatı TL formatına çevir (Epic API kuruşsuz verir, son iki rakamı ayırmalıyız)
            fmt_original = f"{original_price/100:.2f} TL"
            
            # Mesaj içeriği
            msg = (
                f"🎮 *YENİ ÜCRETSİZ OYUN!*\n\n"
                f"🕹 *Oyun:* {title}\n"
                f"💰 *Eski Fiyat:* ~{fmt_original}~\n"
                f"🔥 *Yeni Fiyat:* 0.00 TL (BEDAVA)\n\n"
                f"👇 *Hemen Kütüphanene Ekle:*\n"
                f"{link}"
            )
            send_telegram(msg)

def send_telegram(message):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    check_epic()
