import requests
import os

def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    response = requests.get(url).json()
    games = response['data']['Catalog']['searchStore']['elements']
    
    for game in games:
        price = game['price']['totalPrice']['discountPrice']
        if price == 0 and game['promotions']:
            title = game['title']
            slug = game['catalogNs']['mappings'][0]['pageSlug']
            link = f"https://store.epicgames.com/tr/p/{slug}"
            msg = f"🎮 *YENİ ÜCRETSİZ OYUN!*\n\n🕹 *Oyun:* {title}\n\n👇 *Hemen Al:*\n{link}"
            send_telegram(msg)

def send_telegram(message):
    token = os.environ['TELEGRAM_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown"
    requests.get(url)

if __name__ == "__main__":
    check_epic()
