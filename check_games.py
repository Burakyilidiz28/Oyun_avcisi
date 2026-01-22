import requests
import os
import json
import re
from datetime import datetime

# Dosya isimleri
SENT_GAMES_FILE = "sent_games.txt"
LOG_FILE = "bot_logs.txt"

def write_log(message):
    """İşlemleri log dosyasına tarihle kaydeder."""
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    log_entry = f"[{now}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(log_entry.strip())

def get_sent_games():
    """Dosya içindeki (ID:...) formatındaki ID'leri ayıklar."""
    if not os.path.exists(SENT_GAMES_FILE):
        return []
    with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        # Düzenli ifade (regex) ile ID'leri yakalar
        return re.findall(r"\(ID:(.*?)\)", content)

def add_to_sent_games(game_id, title, original_price_raw):
    """Dosyayı yeni formatta günceller ve toplam kazancı hesaplar."""
    lines = []
    total_gain = 0.0
    games_list = []
    new_price = float(original_price_raw / 100)

    if os.path.exists(SENT_GAMES_FILE):
        with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Mevcut toplam kazancı ve oyun listesini ayıkla
    current_section = ""
    for i, line in enumerate(lines):
        if "--- 💰 TOPLAM KAZANÇ ---" in line:
            if i + 1 < len(lines):
                try:
                    total_gain = float(lines[i+1].replace(" TL", "").strip())
                except: total_gain = 0.0
        elif "|" in line and "(ID:" in line:
            games_list.append(line.strip())

    # Verileri güncelle
    total_gain += new_price
    now_date = datetime.now().strftime("%d-%m-%Y")
    new_game_entry = f"{title} | {new_price:.2f} TL (ID:{game_id}) [{now_date}]"
    games_list.append(new_game_entry)

    # Dosyayı baştan yarat
    with open(SENT_GAMES_FILE, "w", encoding="utf-8") as f:
        f.write("--- 💰 TOPLAM KAZANÇ ---\n")
        f.write(f"{total_gain:.2f} TL\n\n")
        f.write("--- 🏆 BUGÜNE KADAR BULUNAN OYUNLAR ---\n")
        for g in games_list:
            f.write(g + "\n")

def check_epic():
    write_log("--- Kontrol Başlatıldı ---")
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    
    try:
        response = requests.get(url).json()
        games = response['data']['Catalog']['searchStore']['elements']
    except Exception as e:
        write_log(f"HATA: API bağlantısı kurulamadı: {e}")
        return

    sent_games = get_sent_games()
    found_any = False
    
    # Tarihleri Türkçeleştirmek için sözlükler
    gunler = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    aylar = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}

    for game in games:
        try:
            price_info = game['price']['totalPrice']
            # Sadece ücretsiz (0 TL) ve aktif promosyonu olanları al
            if price_info['discountPrice'] == 0 and game.get('promotions') and game['promotions']['promotionalOffers']:
                
                game_id = game['id']
                title = game['title']

                if game_id in sent_games:
                    write_log(f"Atlandı (Zaten gönderildi): {title}")
                    continue

                found_any = True
                promo_info = game['promotions']['promotionalOffers'][0]['promotionalOffers'][0]
                end_date_str = promo_info['endDate']
                end_date = datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                
                bitis_metni = f"{end_date.strftime('%d')} {aylar[end_date.strftime('%B')]} {end_date.strftime('%H:%M')} ({gunler[end_date.strftime('%A')]})"
                image_url = next((img['url'] for img in game.get('keyImages', []) if img.get('type') in ['Thumbnail', 'OfferImageWide']), "")
                
                slug = game.get('urlSlug', "free-games")
                if game.get('catalogNs', {}).get('mappings'):
                    slug = game['catalogNs']['mappings'][0]['pageSlug']
                
                link = f"https://store.epicgames.com/tr/p/{slug}"
                fmt_original = f"{price_info['originalPrice']/100:.2f} TL"
                
                msg = (
                    f"🎮 *{title}*\n\n"
                    f"💰 **Orijinal Fiyat:** {fmt_original}\n"
                    f"⌛ **Son Tarih:** {bitis_metni}\n\n"
                    f"👇 *Hemen Kütüphanene Ekle*"
                )
                
                if send_telegram_photo(msg, link, image_url):
                    add_to_sent_games(game_id, title, price_info['originalPrice'])
                    write_log(f"BAŞARILI: {title} gönderildi ve dosyaya işlendi.")
                else:
                    write_log(f"HATA: {title} gönderilirken Telegram hatası oluştu.")

        except Exception as e:
            write_log(f"HATA: Oyun işlenirken hata oluştu: {e}")
            continue
            
    if not found_any:
        write_log("Bilgi: Şu an yeni bir ücretsiz oyun bulunamadı.")
    write_log("--- Kontrol Bitti ---")

def send_telegram_photo(message, game_url, image_url):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return False
    
    reply_markup = {"inline_keyboard": [[{"text": "📖 Oyunu Al", "url": game_url}]]}
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {'chat_id': chat_id, 'photo': image_url, 'caption': message, 'parse_mode': 'Markdown', 'reply_markup': json.dumps(reply_markup)}
    
    try:
        r = requests.post(url, data=payload)
        return r.status_code == 200
    except:
        return False

if __name__ == "__main__":
    check_epic()
