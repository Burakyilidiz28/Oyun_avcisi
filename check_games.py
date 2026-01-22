import requests
import os
import json
import re
from datetime import datetime
import time

SENT_GAMES_FILE = "sent_games.txt"

# ---------------- UTILS ----------------

def escape_md(text):
    if not text: return ""
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

def get_epic_image(game_name):
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|\b(GOG|Prime|Steam|PSA|Amazon)\b', '', game_name, flags=re.IGNORECASE).strip()
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={clean_name}&locale=tr&country=TR"
    try:
        res = requests.get(search_url, timeout=7).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        if elements:
            for img in elements[0].get('keyImages', []):
                if img.get('type') in ['OfferImageWide', 'Thumbnail']:
                    return img.get('url')
    except: pass
    return ""

# ---------------- TELEGRAM ----------------

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return False

    reply_markup = {"inline_keyboard": [[{"text": f"🎮 Kütüphanene Ekle [{platform_name}]", "url": game_url}]]}
    endpoint = "sendPhoto" if image_url else "sendMessage"
    url = f"https://api.telegram.org/bot{token}/{endpoint}"

    payload = {"chat_id": chat_id, "parse_mode": "MarkdownV2", "reply_markup": json.dumps(reply_markup)}
    if image_url:
        payload["photo"] = image_url
        payload["caption"] = message
    else:
        payload["text"] = message

    try:
        r = requests.post(url, data=payload, timeout=12)
        return r.status_code == 200
    except: return False

# ---------------- STORAGE ----------------

def parse_old_data():
    games = []
    total_tl, total_usd = 0.0, 0.0
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            tl_m = re.search(r"([\d.]+) TL", content)
            usd_m = re.search(r"\$([\d.]+)", content)
            if tl_m: total_tl = float(tl_m.group(1))
            if usd_m: total_usd = float(usd_m.group(1))
            f.seek(0)
            for line in f:
                id_m = re.search(r"\(ID:(.*?)\)", line)
                if id_m: games.append({"full_line": line.strip(), "id": id_m.group(1)})
    return games, total_tl, total_usd

def update_txt_report(games, statuses, total_tl, total_usd, reddit_titles):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n{total_tl:.2f} TL\n${total_usd:.2f}\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games: f.write(f"{g['full_line']}\n")
        f.write(f"\n--- 🔍 SON TARAMA BİLGİSİ ---\nSon Tarama Zamanı: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n")
        for p, s in statuses.items(): f.write(f"{p}: {s}\n")
        f.write("\n--- 📝 REDDIT'TEN OKUNAN SON BAŞLIKLAR (HAM VERİ) ---\n")
        if not reddit_titles: f.write("Veri okunamadı (403 Devam ediyor).\n")
        for t in reddit_titles: f.write(f"- {t}\n")

# ---------------- SCANNER ----------------

def check_games():
    existing_games, total_tl, total_usd = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    reddit_titles = []
    
    # 1. EPIC GAMES
    try:
        res = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR", timeout=10).json()
        for game in res['data']['Catalog']['searchStore']['elements']:
            price = game.get("price", {}).get("totalPrice", {})
            if price.get("discountPrice") == 0 and game.get("promotions"):
                game_id = f"epic_{game['id']}"
                if game_id in existing_ids: continue
                title = game["title"]
                old_p = price.get("originalPrice", 0) / 100
                img = next((i["url"] for i in game.get("keyImages", []) if i["type"] in ["OfferImageWide", "Thumbnail"]), "")
                msg = f"**[{escape_md(title)}]**\n\n💰 Fiyatı: *{escape_md(f'{old_p:.2f} TL')}*\n\n👇 Hemen Al"
                if send_telegram(msg, "https://store.epicgames.com/tr/free-games", "Epic Games", img):
                    total_tl += old_p
                    existing_games.append({"full_line": f"{title} | {old_p:.2f} TL (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]", "id": game_id})
                    statuses["Epic Games"] = "✅"
    except: statuses["Epic Games"] = "⚠️"

    # 2. REDDIT (ZIRHLI BAĞLANTI)
    try:
        session = requests.Session()
        # Reddit'in 403 atmasını zorlaştıran zırhlı başlıklar
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        })
        
        # Önce ana sayfaya bir 'vuruş' yapıp çerez alalım (isteğe bağlı ama etkili)
        session.get("https://www.reddit.com", timeout=10)
        time.sleep(2) # İnsan gibi bekle
        
        # Şimdi JSON verisini isteyelim
        res = session.get("https://www.reddit.com/r/FreeGameFindings/new.json?limit=20", timeout=15)
        
        if res.status_code == 200:
            posts = res.json().get("data", {}).get("children", [])
            reddit_ok = False
            for post in posts:
                title_raw = post["data"]["title"]
                reddit_titles.append(title_raw)
                
                t_up = title_raw.upper()
                keywords = ["FREE", "100%", "GIVEAWAY", "PRIME", "COMPLIMENTARY", "PSA", "AMAZON"]
                if any(k in t_up for k in keywords):
                    game_id = f"reddit_{post['data']['id']}"
                    if game_id in existing_ids: continue

                    img = get_epic_image(title_raw)
                    platform = "Steam"
                    for p in ["GOG", "UBISOFT", "EA", "PRIME", "ITCH", "MICROSOFT"]:
                        if p in t_up: platform = p.capitalize(); break

                    msg = f"**[{escape_md(title_raw)}]**\n\n💰 Fiyatı: *Ücretsiz*\n🎮 Platform: *{escape_md(platform)}*\n\n👇 Hemen Al"
                    if send_telegram(msg, post["data"]["url"], platform, img):
                        existing_games.append({"full_line": f"{title_raw} | 0.00 $ (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]", "id": game_id})
                        reddit_ok = True
            statuses["Steam"] = "✅" if reddit_ok else "❌"
        else:
            reddit_titles.append(f"HATA: {res.status_code}")
            statuses["Steam"] = "⚠️"
    except Exception as e:
        reddit_titles.append(f"HATA: {str(e)}")
        statuses["Steam"] = "⚠️"

    update_txt_report(existing_games, statuses, total_tl, total_usd, reddit_titles)

if __name__ == "__main__":
    check_games()
