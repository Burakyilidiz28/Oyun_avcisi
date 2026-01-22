import requests, os, json, re
from datetime import datetime

FILE = "sent_games.txt"

# ---------- UTILS ----------

def esc(t):
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', t)

# ---------- TELEGRAM ----------

def tg(msg, url, img):
    tok = os.getenv("TELEGRAM_TOKEN")
    cid = os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not cid:
        return False

    kb = {"inline_keyboard":[[{"text":"🎮 Kütüphanene Ekle [Epic Games]","url":url}]]}
    api = f"https://api.telegram.org/bot{tok}/sendPhoto"

    data = {
        "chat_id": cid,
        "photo": img,
        "caption": msg,
        "parse_mode": "MarkdownV2",
        "reply_markup": json.dumps(kb)
    }

    try:
        return requests.post(api, data=data, timeout=10).status_code == 200
    except:
        return False

# ---------- STORAGE ----------

def load():
    games, ids = [], set()
    if not os.path.exists(FILE):
        return games, ids

    with open(FILE, "r", encoding="utf-8") as f:
        for l in f:
            m = re.search(r"\(ID:(.*?)\)", l)
            if m:
                ids.add(m.group(1))
                games.append(l.strip())
    return games, ids

def save(games, status):
    total = 0.0
    for g in games:
        m = re.search(r"\| ([\d.]+) TL", g)
        if m:
            total += float(m.group(1))

    with open(FILE, "w", encoding="utf-8") as f:
        f.write("--- 🏆 BULUNAN OYUNLAR ---\n")
        for g in games:
            f.write(g + "\n")

        f.write("\n--- 💰 TOPLAM TASARRUF ---\n")
        f.write(f"{total:.2f} TL\n")

        f.write("\n--- 🔍 PLATFORM DURUMU ---\n")
        f.write(f"Epic Games: {status}\n")
        f.write(f"\nSon Tarama: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n")

# ---------- EPIC ----------

def check():
    games, ids = load()
    new = False

    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR"
        res = requests.get(url, timeout=10).json()
        els = res["data"]["Catalog"]["searchStore"]["elements"]

        for g in els:
            p = g.get("price", {}).get("totalPrice", {})
            if p.get("discountPrice") != 0 or not g.get("promotions"):
                continue

            gid = f"epic_{g['id']}"
            if gid in ids:
                continue

            title = g["title"]
            price = p.get("originalPrice", 0) / 100
            img = next((i["url"] for i in g.get("keyImages", [])
                        if i["type"] in ["OfferImageWide","Thumbnail"]), "")

            msg = (
                f"*{esc(title)}*\n\n"
                f"💰 Fiyatı: *{price:.2f} TL*\n"
                f"⏰ Sınırlı Süre Ücretsiz"
            )

            if img and tg(msg, "https://store.epicgames.com/tr/free-games", img):
                games.append(
                    f"{title} | {price:.2f} TL (ID:{gid}) [{datetime.now().strftime('%d-%m-%Y')}]"
                )
                ids.add(gid)
                new = True

        save(games, "✅" if new else "❌")

    except:
        save(games, "⚠️")

# ---------- MAIN ----------

if __name__ == "__main__":
    check()
