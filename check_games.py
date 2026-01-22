import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

# ---------------- UTILS ----------------

def escape_md(text):
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# ---------------- TELEGRAM ----------------

def send_telegram(message, game_url, image_url):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    reply_markup = {
        "inline_keyboard": [[
            {"text": "🎮 Kütüphanene Ekle [Epic Games]", "url": game_url}
        ]]
    }

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "parse_mode": "MarkdownV2",
        "reply_markup": json.dumps(reply_markup),
        "photo": image_url,
        "caption": message
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

# ---------------- STORAGE ----------------

def load_existing_ids():
    ids = set()
    if not os.path.exists(SENT_GAMES_FILE):
        return ids

    with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m = re.search(r"\(ID:(.*?)\)", line)
            if m:
                ids.add(m.group(1))
    return ids

def update_txt(games, status):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 🏆 BULUNAN OYUNLAR ---\n")
        for g in games:
            f.write(g + "\n")

        f.write("\n--- 🔍 PLATFORM DURUMU ---\n")
        f.write(f"Epic Games: {status}\n")
        f.write(f"\nSon Tarama: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n")

# ---------------- EPIC GAMES ----------------

def check_epic_games():
    existing_ids = load_existing_ids()
    found_games = []
    found_new = False

    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR"
        res = requests.get(url, timeout=10).json()
        elements = res["data"]["Catalog"]["searchStore"]["elements"]

        for game in elements:
            price = game.get("price", {}).get("totalPrice", {})
            promos = game.get("promotions")

            if price.get("discountPrice") != 0 or not promos:
                continue

            game_id = f"epic_{game['id']}"
            if game_id in existing_ids:
                continue

            title_raw = game["title"]
            title = escape_md(title_raw)
            old_price = price.get("originalPrice", 0) / 100

            img = next(
                (i["url"] for i in game.get("keyImages", [])
                 if i["type"] in ["OfferImageWide", "Thumbnail"]),
                ""
            )

            msg = (
                f"*{title}*\n\n"
                f"💰 Fiyatı: *{old_price:.2f} TL*\n"
                f"⏰ Sınırlı Süre Ücretsiz"
            )

            if img and send_telegram(
                msg,
                "https://store.epicgames.com/tr/free-games",
                img
            ):
                found_games.append(
                    f"{title_raw} | {old_price:.2f} TL (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]"
                )
                found_new = True

    except:
        update_txt([], "⚠️")
        return

    status = "✅" if found_new else "❌"
    update_txt(found_games, status)

# ---------------- MAIN ----------------

if __name__ == "__main__":
    check_epic_games()
