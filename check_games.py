import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

# ---------------- UTILS ----------------

def escape_md(text):
    """MarkdownV2 için özel karakterleri temizler. (Hata almamak için kritik)"""
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def get_epic_image(game_name):
    """Oyun ismini Epic Games'te arar ve bulursa görsel linkini döner."""
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', game_name).strip()
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={clean_name}&locale=tr&country=TR&allowCountries=TR"
    try:
        response = requests.get(search_url, timeout=5).json()
        elements = response['data']['Catalog']['searchStore']['elements']
        if elements:
            for img in elements[0].get('keyImages', []):
                # Geniş veya Thumbnail görseli tercih et
                if img.get('type') in ['OfferImageWide', 'Thumbnail', 'DieselStoreFrontWide']:
                    return img.get('url')
    except:
        pass
    return ""

# ---------------- TELEGRAM ----------------

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("HATA: Token veya Chat ID eksik!")
        return False

    reply_markup = {
        "inline_keyboard": [[
            {"text": f"🎮 Kütüphanene Ekle [{platform_name}]", "url": game_url}
        ]]
    }

    # Eğer görsel yoksa otomatik olarak sendMessage kullan
    endpoint = "sendPhoto" if image_url else "sendMessage"
    url = f"https://api.telegram.org/bot{token}/{endpoint}"

    payload = {
        "chat_id": chat_id,
        "parse_mode": "MarkdownV2",
        "reply_markup": json.dumps(reply_markup)
    }

    if image_url:
        payload["photo"] = image_url
        payload["caption"] = message
    else:
        payload["text"] = message

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"Telegram Hatası: {r.text}") # Hata kodunu konsolda gör
        return r.status_code == 200
    except Exception as e:
        print(f"Bağlantı Hatası: {e}")
        return False

# ---------------- STORAGE ----------------

def parse_old_data():
    games = []
    if not os.path.exists(SENT_GAMES_FILE):
        return games
    with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
        for line in f.read().splitlines():
            m = re.search(r"\(ID:(.*?)\)", line)
            if m:
                games.append({"full_line": line, "id": m.group(1)})
    return games

def update_txt_report(games, statuses):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 🏆 BULUNAN OYUNLAR ---\n")
        for g in games:
            f.write(f"{g['full_line']}\n")
        f.write("\n--- 🔍 PLATFORM DURUMU ---\n")
        for platform, status in statuses.items():
            f.write(f"{platform}: {status}\n")
        f.write(f"\nSon Tarama: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n")

# ---------------- EPIC GAMES ----------------

def check_epic(existing_ids, games, statuses):
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR"
        res = requests.get(url, timeout=10).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        found_new = False

        for game in elements:
            price = game.get("price", {}).get("totalPrice", {})
            promos = game.get("promotions", {})
            if price.get("discountPrice") == 0 and promos.get("promotionalOffers"):
                game_id = f"epic_{game.get('id')}"
                if game_id in existing_ids: continue

                title = escape_md(game["title"])
                old_price = price.get("originalPrice", 0) / 100
                img = next((i["url"] for i in game.get("keyImages", []) if i["type"] in ["OfferImageWide", "Thumbnail"]), "")

                msg = f"*{title}*\n\n💰 Fiyatı: *{escape_md(str(old_price))} TL*\n👇 Hemen Al"
                
                if send_telegram(msg, "https://store.epicgames.com/tr/free-games", "Epic Games", img):
                    games.append({
                        "full_line": f"{game['title']} | {old_price:.2f} TL (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                        "id": game_id
                    })
                    found_new = True
        statuses["Epic Games"] = "✅" if found_new else "❌"
    except:
        statuses["Epic Games"] = "⚠️"

# ---------------- REDDIT ----------------

def check_reddit(existing_ids, games, statuses):
    try:
        url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=10"
        res = requests.get(url, headers={"User-Agent": "GameDealsBot"}, timeout=10).json()
        found_new = False

        for post in res["data"]["children"]:
            data = post["data"]
            title_raw = data["title"]
            if "FREE" not in title_raw.upper() and "100%" not in title_raw.upper(): continue

            game_id = f"reddit_{data['id']}"
            if game_id in existing_ids: continue

            # EPIC'TEN GÖRSEL ARA
            img = get_epic_image(title_raw)
            
            title = escape_md(title_raw)
            platform = "Steam" if "STEAM" in title_raw.upper() else "Other"
            msg = f"*{title}*\n\n👇 Hemen Al"

            if send_telegram(msg, data["url"], platform, img):
                games.append({
                    "full_line": f"{title_raw} | Ücretsiz (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                    "id": game_id
                })
                found_new = True
        statuses["Steam"] = "✅" if found_new else "❌"
    except:
        statuses["Steam"] = "⚠️"

def check_games():
    existing_games = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}

    check_epic(existing_ids, existing_games, statuses)
    check_reddit(existing_ids, existing_games, statuses)
    update_txt_report(existing_games, statuses)

if __name__ == "__main__":
    check_games()
