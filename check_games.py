import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

# ---------------- UTILS ----------------

def escape_md(text):
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def clean_game_name(name):
    return re.sub(r'\[.*?\]|\(.*?\)', '', name).strip()

# ---------------- IMAGE SOURCES ----------------

def get_epic_image_by_name(game_name):
    try:
        q = clean_game_name(game_name)
        url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={q}&locale=en-US"
        res = requests.get(url, timeout=6).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        if not elements:
            return ""
        for img in elements[0].get("keyImages", []):
            if img.get("type") in ["OfferImageWide", "Thumbnail"]:
                return img.get("url")
    except:
        pass
    return ""

def get_xbox_image_by_name(game_name):
    try:
        q = clean_game_name(game_name)
        url = (
            "https://displaycatalog.mp.microsoft.com/v7.0/products"
            f"?market=US&languages=en-us&query={q}&top=1"
        )
        res = requests.get(url, timeout=6).json()
        products = res.get("Products", [])
        if not products:
            return ""

        images = products[0].get("LocalizedProperties", [{}])[0].get("Images", [])
        for img in images:
            if img.get("ImagePurpose") in ["Poster", "Hero"]:
                return img.get("Uri")
    except:
        pass
    return ""

def get_best_image(game_name):
    img = get_epic_image_by_name(game_name)
    if img:
        return img
    return get_xbox_image_by_name(game_name)

# ---------------- TELEGRAM ----------------

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    reply_markup = {
        "inline_keyboard": [[
            {"text": f"🎮 Kütüphanene Ekle [{platform_name}]", "url": game_url}
        ]]
    }

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
        return r.status_code == 200
    except:
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
                games.append({"id": m.group(1), "full_line": line})
    return games

def update_txt_report(games, statuses):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 🏆 BULUNAN OYUNLAR ---\n")
        for g in games:
            f.write(f"{g['full_line']}\n")

        f.write("\n--- 🔍 PLATFORM DURUMU ---\n")
        for p, s in statuses.items():
            f.write(f"{p}: {s}\n")

        f.write(f"\nSon Tarama: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n")

# ---------------- EPIC GAMES ----------------

def check_epic(existing_ids, games, statuses):
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR"
        res = requests.get(url, timeout=10).json()
        elements = res['data']['Catalog']['searchStore']['elements']

        found = False

        for game in elements:
            price = game.get("price", {}).get("totalPrice", {})
            promos = game.get("promotions", {})

            if price.get("discountPrice") == 0 and promos:
                gid = f"epic_{game.get('id')}"
                if gid in existing_ids:
                    continue

                title = game["title"]
                img = next((i["url"] for i in game.get("keyImages", [])
                            if i["type"] in ["OfferImageWide", "Thumbnail"]), "")

                msg = (
                    f"*{escape_md(title)}*\n\n"
                    f"💰 Fiyatı: *{price.get('originalPrice',0)/100:.2f} TL*\n"
                    f"👇 Hemen Al"
                )

                if send_telegram(msg, "https://store.epicgames.com/tr/free-games", "Epic Games", img):
                    games.append({
                        "id": gid,
                        "full_line": f"{title} | {price.get('originalPrice',0)/100:.2f} TL (ID:{gid}) [{datetime.now().strftime('%d-%m-%Y')}]"
                    })
                    found = True

        statuses["Epic Games"] = "✅" if found else "❌"

    except:
        statuses["Epic Games"] = "⚠️"

# ---------------- REDDIT ----------------

def check_reddit(existing_ids, games, statuses):
    try:
        url = "https://www.reddit.com/r/FreeGameFindings/new.json?limit=10"
        res = requests.get(url, headers={"User-Agent": "GameDealsBot"}, timeout=10).json()

        found = False

        for post in res["data"]["children"]:
            data = post["data"]
            title_raw = data["title"]

            if "FREE" not in title_raw.upper() and "100%" not in title_raw.upper():
                continue

            gid = f"reddit_{data['id']}"
            if gid in existing_ids:
                continue

            clean = clean_game_name(title_raw)
            img = get_best_image(clean)
            platform = "Steam" if "STEAM" in title_raw.upper() else "Other"

            msg = f"*{escape_md(title_raw)}*\n\n👇 Hemen Al"

            if send_telegram(msg, data["url"], platform, img):
                games.append({
                    "id": gid,
                    "full_line": f"{title_raw} | Ücretsiz (ID:{gid}) [{datetime.now().strftime('%d-%m-%Y')}]"
                })
                found = True

        statuses["Steam"] = "✅" if found else "❌"

    except:
        statuses["Steam"] = "⚠️"

# ---------------- MAIN ----------------

def check_games():
    games = parse_old_data()
    existing_ids = [g["id"] for g in games]

    statuses = {
        "Epic Games": "❌",
        "Steam": "❌",
        "Microsoft Store": "❌"
    }

    check_epic(existing_ids, games, statuses)
    check_reddit(existing_ids, games, statuses)

    update_txt_report(games, statuses)

if __name__ == "__main__":
    check_games()
