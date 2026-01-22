import requests
import os
import json
import re
from datetime import datetime

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

def update_txt_report(games, statuses, total_tl, total_usd, titles):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n{total_tl:.2f} TL\n${total_usd:.2f}\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games: f.write(f"{g['full_line']}\n")
        f.write(f"\n--- 🔍 SON TARAMA BİLGİSİ ---\nSon Tarama Zamanı: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n")
        for p, s in statuses.items(): f.write(f"{p}: {s}\n")
        f.write("\n--- 📝 REDDIT'TEN OKUNAN SON BAŞLIKLAR (RSS KÖPRÜSÜ) ---\n")
        if not titles: f.write("Hic baslik bulunamadi.\n")
        for t in titles: f.write(f"- {t}\n")

# ---------------- SCANNER ----------------

def check_games():
    existing_games, total_tl, total_usd = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    raw_titles = []
    
    # 1. EPIC GAMES (Sorunsuz Calisiyor)
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

    # 2. REDDIT (RSS KÖPRÜSÜ - 403 HATASINI ASAR)
    try:
        # Reddit'in RSS beslemesini JSON'a ceviren ucretsiz bir servis kullanıyoruz
        rss_url = "https://www.reddit.com/r/FreeGameFindings/new.rss"
        api_url = f"https://api.rss2json.com/v1/api.json?rss_url={rss_url}"
        
        res = requests.get(api_url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            reddit_ok = False
            for item in data.get("items", []):
                title_raw = item.get("title", "")
                raw_titles.append(title_raw)
                
                t_up = title_raw.upper()
                keywords = ["FREE", "100%", "GIVEAWAY", "PRIME", "COMPLIMENTARY", "PSA", "AMAZON"]
                if any(k in t_up for k in keywords):
                    # RSS'de ID olarak linki veya guid'i kullanabiliriz
                    game_id = f"rss_{item.get('guid', '').split('/')[-1]}"
                    if game_id in existing_ids: continue

                    img = get_epic_image(title_raw)
                    platform = "Steam"
                    for p in ["GOG", "UBISOFT", "EA", "PRIME", "ITCH", "MICROSOFT"]:
                        if p in t_up: platform = p.capitalize(); break

                    msg = f"**[{escape_md(title_raw)}]**\n\n💰 Fiyatı: *Ücretsiz*\n🎮 Platform: *{escape_md(platform)}*\n\n👇 Hemen Al"
                    # RSS item linki genellikle Reddit konusuna gider
                    if send_telegram(msg, item.get("link", ""), platform, img):
                        existing_games.append({"full_line": f"{title_raw} | 0.00 $ (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]", "id": game_id})
                        reddit_ok = True
            statuses["Steam"] = "✅" if reddit_ok else "❌"
        else:
            raw_titles.append(f"RSS Servis Hatasi: {res.status_code}")
            statuses["Steam"] = "⚠️"
    except Exception as e:
        raw_titles.append(f"Baglanti Hatasi: {str(e)}")
        statuses["Steam"] = "⚠️"

    update_txt_report(existing_games, statuses, total_tl, total_usd, raw_titles)

if __name__ == "__main__":
    check_games()
