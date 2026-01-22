import requests
import os
import json
import re
from datetime import datetime

SENT_GAMES_FILE = "sent_games.txt"

# ---------------- UTILS ----------------

def escape_md(text):
    """Telegram MarkdownV2 için özel karakterleri (.-! vb) güvenli hale getirir."""
    if not text: return ""
    # MarkdownV2'de hata veren tüm özel karakterlerin önüne \ ekler
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

def get_epic_image(game_name):
    """Herhangi bir platformdaki oyunun ismini Epic'te arayıp görselini bulur."""
    # İsimdeki [Steam], (Free) gibi ekleri temizle
    clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', game_name).strip()
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
        r = requests.post(url, data=payload, timeout=12)
        if r.status_code != 200:
            print(f"Telegram Hatası: {r.text}")
        return r.status_code == 200
    except: return False

# ---------------- STORAGE & REPORT ----------------

def parse_old_data():
    """Txt dosyasından eski oyunları ve toplam tasarrufu okur."""
    games = []
    total_tl = 0.0
    total_usd = 0.0
    
    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                # Tasarruf miktarlarını topla
                price_match = re.search(r"\| ([\d.]+) (TL|\$)", line)
                if price_match:
                    val = float(price_match.group(1))
                    if price_match.group(2) == "TL": total_tl += val
                    else: total_usd += val
                
                # Oyun ID'lerini listeye ekle
                id_match = re.search(r"\(ID:(.*?)\)", line)
                if id_match:
                    games.append({"full_line": line.strip(), "id": id_match.group(1)})
    
    return games, total_tl, total_usd

def update_txt_report(games, statuses, total_tl, total_usd):
    """Txt dosyasını profesyonel rapor formatında günceller."""
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 💰 TOPLAM TASARRUF ---\n")
        f.write(f"{total_tl:.2f} TL\n")
        f.write(f"${total_usd:.2f}\n\n")
        
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games:
            f.write(f"{g['full_line']}\n")
            
        f.write("\n--- 🔍 SON TARAMA BİLGİSİ ---\n")
        f.write(f"Son Tarama Zamanı: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n")
        for p, s in statuses.items():
            f.write(f"{p}: {s}\n")

# ---------------- SCANNERS ----------------

def check_games():
    existing_games, total_tl, total_usd = parse_old_data()
    existing_ids = [g["id"] for g in existing_games]
    statuses = {"Epic Games": "❌", "Steam": "❌"}
    
    # Tarih çevirileri
    months_tr = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}
    days_tr = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}

    # --- 1. EPIC GAMES KONTROLÜ ---
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR"
        res = requests.get(url, timeout=10).json()
        elements = res['data']['Catalog']['searchStore']['elements']
        epic_found = False

        for game in elements:
            price_info = game.get("price", {}).get("totalPrice", {})
            promos = game.get("promotions", {})
            
            if price_info.get("discountPrice") == 0 and promos and promos.get("promotionalOffers"):
                game_id = f"epic_{game['id']}"
                if game_id in existing_ids: continue

                title = game["title"]
                old_price = price_info.get("originalPrice", 0) / 100
                
                # Son Tarih Çekme
                offer = promos["promotionalOffers"][0]["promotionalOffers"][0]
                end_dt = datetime.fromisoformat(offer["endDate"].replace("Z", "+00:00"))
                expiry_str = f"{end_dt.strftime('%d')} {months_tr.get(end_dt.strftime('%B'))} {end_dt.strftime('%H:%M')} ({days_tr.get(end_dt.strftime('%A'))})"

                img = next((i["url"] for i in game.get("keyImages", []) if i["type"] in ["OfferImageWide", "Thumbnail"]), "")
                
                msg = (f"**[{escape_md(title)}]**\n\n"
                       f"💰 Fiyatı: *{escape_md(f'{old_price:.2f} TL')}*\n"
                       f"⏳ Son Tarih: *{escape_md(expiry_str)}*\n\n"
                       f"👇 Hemen Al")
                
                if send_telegram(msg, "https://store.epicgames.com/tr/free-games", "Epic Games", img):
                    total_tl += old_price
                    existing_games.append({
                        "full_line": f"{title} | {old_price:.2f} TL (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                        "id": game_id
                    })
                    epic_found = True
        statuses["Epic Games"] = "✅" if epic_found else "❌"
    except Exception as e: 
        print(f"Epic Hata: {e}")
        statuses["Epic Games"] = "⚠️"

    # --- 2. REDDIT (STEAM/GOG/DIĞER) KONTROLÜ ---
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OyunAvcisi/2.0"}
        # /new.json?sort=new ile en yenileri çekiyoruz
        reddit_url = "https://www.reddit.com/r/FreeGameFindings/new.json?sort=new&limit=15"
        res = requests.get(reddit_url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            print(f"Reddit Baglanti Sorunu: {res.status_code}")
            statuses["Steam"] = "⚠️"
        else:
            reddit_found = False
            posts = res.json().get("data", {}).get("children", [])
            for post in posts:
                data = post["data"]
                t_raw = data["title"]
                
                # Sadece gerçek fırsatları filtrele
                if any(word in t_raw.upper() for word in ["FREE", "100%", "GIVEAWAY"]):
                    game_id = f"reddit_{data['id']}"
                    if game_id in existing_ids: continue

                    # Reddit başlığındaki oyunu Epic'te arayıp görselini al
                    img = get_epic_image(t_raw)
                    
                    # Fiyat tahmini (Varsa)
                    price_match = re.search(r"(\$|£|€)(\d+\.?\d*)", t_raw)
                    price_val = float(price_match.group(2)) if price_match else 0.0
                    price_str = f"{price_val:.2f} $" if price_val > 0 else "Ücretsiz"

                    msg = (f"**[{escape_md(t_raw)}]**\n\n"
                           f"💰 Fiyatı: *{escape_md(price_str)}*\n\n"
                           f"👇 Hemen Al")
                    
                    platform = "Steam"
                    for p in ["GOG", "UBISOFT", "EA", "ORIGIN", "PRIME", "ITCH", "MICROSOFT"]:
                        if p in t_raw.upper():
                            platform = p.capitalize()
                            break

                    if send_telegram(msg, data["url"], platform, img):
                        total_usd += price_val
                        existing_games.append({
                            "full_line": f"{t_raw} | {price_val:.2f} $ (ID:{game_id}) [{datetime.now().strftime('%d-%m-%Y')}]",
                            "id": game_id
                        })
                        reddit_found = True
            statuses["Steam"] = "✅" if reddit_found else "❌"
    except Exception as e:
        print(f"Reddit Genel Hata: {e}")
        statuses["Steam"] = "⚠️"

    # Raporu yazdır
    update_txt_report(existing_games, statuses, total_tl, total_usd)

if __name__ == "__main__":
    check_games()
