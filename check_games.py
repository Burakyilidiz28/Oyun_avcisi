def check_epic():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=tr&country=TR&allowCountries=TR"
    days_tr = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    months_tr = {"January": "Ocak", "February": "Şubat", "March": "Mart", "April": "Nisan", "May": "Mayıs", "June": "Haziran", "July": "Temmuz", "August": "Ağustos", "September": "Eylül", "October": "Ekim", "November": "Kasım", "December": "Aralık"}

    try:
        response = requests.get(url, timeout=10).json()
        games = response['data']['Catalog']['searchStore']['elements']
        found_new = False
        content = ""
        if os.path.exists(SENT_GAMES_FILE):
            with open(SENT_GAMES_FILE, "r", encoding="utf-8") as f: content = f.read()

        for game in games:
            promotions = game.get('promotions')
            if promotions and promotions.get('promotionalOffers'):
                offers = promotions['promotionalOffers'][0]['promotionalOffers']
                for offer in offers:
                    if game['price']['totalPrice']['discountPrice'] == 0:
                        title = game['title']
                        game_id = f"ID:epic_{title.replace(' ', '_')}"
                        if game_id in content: continue

                        # Bitiş Tarihi Hesaplama
                        end_date_raw = offer['endDate'].replace('Z', '+00:00')
                        end_dt = datetime.fromisoformat(end_date_raw)
                        # Türkiye saati (UTC+3) ve formatlama
                        day = end_dt.strftime('%d')
                        month = months_tr[end_dt.strftime('%B')]
                        hour = end_dt.strftime('%H:%M')
                        day_name = days_tr[end_dt.strftime('%A')]
                        expiry_str = f"{day} {month} {hour} ({day_name})"

                        # Görsel
                        image_url = ""
                        for img in game.get('keyImages', []):
                            if img.get('type') in ['OfferImageWide', 'Thumbnail']:
                                image_url = img.get('url'); break

                        old_price = game['price']['totalPrice']['originalPrice']/100
                        message = (f"*[{title}]*\n\n"
                                   f"💰 *Eski Fiyat:* {old_price:.2f} TL\n"
                                   f"⏳ *Son Tarih:* {expiry_str}\n\n"
                                   f"🎮 Platform: Epic Games")
                        
                        if send_telegram(message, "https://store.epicgames.com/tr/free-games", "Epic Games", image_url):
                            with open(SENT_GAMES_FILE, "a", encoding="utf-8") as f_app:
                                f_app.write(f"{title} | {old_price:.2f} TL ({game_id}) [{datetime.now().strftime('%d-%m-%Y')}]\n")
                            found_new = True
        return "✅" if found_new else "❌", found_new
    except Exception as e:
        print(f"Epic Hata: {e}")
        return "⚠️", False
