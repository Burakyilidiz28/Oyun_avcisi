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
    # Harold Halibut (GOG) gibi başlıklardan sadece ismi temizle
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|\bGOG\b|\bPrime\b|\bSteam\b', '', game_name, flags=re.IGNORECASE).strip()
    search_url = f"https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?q={clean_name}&locale=tr&country=TR&allowCountries=TR"
    try:
        res = requests.get(search_url, timeout=7).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        if elements:
            for img in elements[0].get('keyImages', []):
                if img.get('type') in ['OfferImageWide', 'Thumbnail', 'DieselStoreFrontWide']:
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
            lines = f.readlines()
            for line in lines:
                price_match = re.search(r"\| ([\d.]+) (TL|\$)", line)
                if price_match:
                    val = float(price_match.group(1))
                    if price_match.group(2) == "TL": total_tl += val
                    else: total_usd += val
                id_match = re.search(r"\(ID:(.*?)\)", line)
                if id_match: games.append({"full_line": line.strip(), "id": id_match.group(1)})
    return games, total_tl, total_usd

def update_txt_report(games, statuses, total_tl, total_usd):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n{total_tl:.2f} TL\n${total_usd:.2f}\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games: f.write(f"{g['full_line']}\n")
        f.write(f"\n--- 🔍 SON TARAMA BİLGİSİ ---\nSon Tarama: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n")
        for p, s in statuses.items(): f.write(f"{p}: {s}\n")

# ---------------- SCANNER ----------------

def check_games():
    existing_games, total_tl, total_usd = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    
    # 1. EPIC (Aynı kalıyor)
    # ... (Epic kodun buraya gelecek) ...

    # 2. REDDIT (GELİŞTİRİLMİŞ FİLTRE)
    try:
        headers = {"User-Agent": "Mozilla/5.0 OyunAvcisi/3.0"}
        url = "https://www.reddit.com/r/FreeGameFindings/new.json?sort=new&limit=20"
        res = requests.get(url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            posts = res.json().get("data", {}).get("children", [])
            found_any_new = False
            for post in posts:
                data = post["data"]
                t_raw = data["title"].upper()
                
                # GENİŞLETİLMİŞ FİLTRE: complimentary, prime, psa gibi kelimeleri de tara
                keywords = ["FREE", "100%", "GIVEAWAY", "COMPLIMENTARY", "PRIME"]
                if any(word in t_raw for word in keywords):
                    game_id = f"reddit_{data['id']}"
                    if game_id in existing_ids: continue

                    img = get_epic_image(data["title"])
                    
                    # Platform Tahmini
                    platform = "Steam"
                    for p in ["GOG", "UBISOFT", "EA", "PRIME", "ITCH", "XBOX", "PS4", "PS5"]:
                        if p in t_raw:
                            platform = p.capitalize()
                            break
                    
                    msg = f"**[{escape_md(data['title'])}]**\n\n💰 Fiyatı: *Ücretsiz*\n🎮 Platform: *{escape_md(platform)}*\n\n👇 Hemen Al"
                    
                    if send_telegram(msg, data["url"], platform, img):
                        existing_games.append({
                            "full_line": f"{data['title']} | 0.00 $ (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                            "id": game_id
                        })
                        found_any_new = True
            statuses["Steam"] = "✅" if found_any_new else "❌"
    except: statuses["Steam"] = "⚠️"

    update_txt_report(existing_games, statuses, total_tl, total_usd)

if __name__ == "__main__":
    check_games()
