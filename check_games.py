import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

def escape_md(text):
    if not text: return ""
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

def clean_title(title):
    return title.replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")

def find_direct_link(game_name, platform, reddit_link):
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|\b(GOG|Prime|Steam|PSA|Amazon|Epic|Free|Giveaway|complimentary|with)\b', '', game_name, flags=re.IGNORECASE).strip()
    search_query = clean_name.replace(' ', '+')
    
    p_up = platform.upper()
    t_up = game_name.upper()
    
    # Özel Prime/Amazon Araması
    if "PRIME" in t_up or "AMAZON" in t_up:
        return f"https://www.google.com/search?q={search_query}+Amazon+Prime+Code"
    
    if "STEAM" in p_up:
        return f"https://store.steampowered.com/search/?term={search_query}"
    elif "EPIC" in p_up:
        return f"https://store.epicgames.com/tr/browse?q={search_query}"
    elif "GOG" in p_up:
        return f"https://www.gog.com/en/games?query={search_query}"
    
    return reddit_link

def get_epic_image(game_name):
    clean_name = re.sub(r'\[.*?\]|\(.*?\)|\b(GOG|Prime|Steam|PSA|Amazon|Epic)\b', '', game_name, flags=re.IGNORECASE).strip()
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

def send_telegram(message, game_url, platform_name, image_url=""):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return False

    button_text = "🎁 Kodu Al / Mağazaya Git"
    reply_markup = {"inline_keyboard": [[{"text": button_text, "url": game_url}]]}
    
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

def update_txt_report(games, statuses, total_tl, total_usd, raw_titles):
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- 💰 TOPLAM TASARRUF ---\n{total_tl:.2f} TL\n${total_usd:.2f}\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games: f.write(f"{g['full_line']}\n")
        f.write(f"\n--- 🔍 SON TARAMA BİLGİSİ ---\nSon Tarama Zamanı: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n")
        for p, s in statuses.items(): f.write(f"{p}: {s}\n")
        f.write("\n--- 📝 REDDIT'TEN OKUNAN SON BAŞLIKLAR (RSS) ---\n")
        for t in raw_titles: f.write(f"- {t}\n")

def check_games():
    existing_games, total_tl, total_usd = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    raw_titles = []
    
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

    # 2. REDDIT RSS
    try:
        rss_url = "https://www.reddit.com/r/FreeGameFindings/new.rss"
        api_url = f"https://api.rss2json.com/v1/api.json?rss_url={rss_url}"
        res = requests.get(api_url, timeout=15).json()
        
        reddit_any = False
        for item in res.get("items", []):
            title_raw = clean_title(item.get("title", ""))
            raw_titles.append(title_raw)
            t_up = title_raw.upper()
            
            keywords = ["FREE", "100%", "GIVEAWAY", "PRIME", "COMPLIMENTARY", "PSA", "AMAZON"]
            if any(k in t_up for k in keywords) and "MEGA THREAD" not in t_up:
                game_id = f"rss_{item.get('guid', '').split('/')[-1]}"
                if game_id in existing_ids: continue

                platform = "Steam"
                for p in ["GOG", "UBISOFT", "EA", "PRIME", "ITCH", "MICROSOFT", "EPIC"]:
                    if p in t_up: platform = p.capitalize(); break

                final_link = find_direct_link(title_raw, platform, item.get("link", ""))
                img = get_epic_image(title_raw)
                msg = f"**[{escape_md(title_raw)}]**\n\n💰 Fiyatı: *Ücretsiz*\n🎮 Platform: *{escape_md(platform)}*\n\n👇 Fırsatı Yakala"
                
                if send_telegram(msg, final_link, platform, img):
                    existing_games.append({"full_line": f"{title_raw} | 0.00 $ (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]", "id": game_id})
                    reddit_any = True
        statuses["Steam"] = "✅" if reddit_any else "❌"
    except: statuses["Steam"] = "⚠️"

    update_txt_report(existing_games, statuses, total_tl, total_usd, raw_titles)

if __name__ == "__main__":
    check_games()
