import json
import os
from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import requests

# ================== CẤU HÌNH TELEGRAM ==================
TELEGRAM_TOKEN = "8372947939:AAE4epPhF_l_HOuw2dYDf4owCHDSAcp82gw"
TELEGRAM_CHAT_ID = "993391522"
# =====================================================

EXCEL_FILE = "danh_sach_tinh.xlsx"
SEEN_FILE = "seen_titles.json"
REPORT_CSV = "ket_qua_du_thao_tat_ca.csv"

KEYWORDS = ["Dự thảo", "dự thảo", "Nghị quyết", "nghị quyết", "Quyết định", "quyết định"]
BLACKLIST = ["TẢI VỀ", "Bản so sánh", "thuyết minh", "Lượt xem", "File đính kèm", ".doc", ".pdf", ".zip", "HS dự thảo"]

def send_telegram(message, file_path=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
   
    # Gửi tin nhắn văn bản
    try:
        requests.post(url + "/sendMessage", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
    except:
        pass

    # Gửi file nếu có
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                requests.post(url + "/sendDocument", data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": message
                }, files={"document": f})
            print(f"📤 Đã gửi file {file_path} qua Telegram")
        except Exception as e:
            print(f"❌ Không gửi được file: {e}")

def load_seen_titles():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen_titles(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def extract_titles(url):
    titles = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(10000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        for td in soup.find_all('td'):
            text = td.get_text(strip=True)
            if not text or len(text) < 20 or len(text) > 280:
                continue
            if not any(kw in text for kw in KEYWORDS):
                continue
            if any(bad in text for bad in BLACKLIST):
                continue
            cleaned = " ".join(text.split())
            if cleaned not in titles and "Dự thảo" in cleaned:
                titles.append(cleaned)

        if not titles:
            for tag in soup.find_all(['a', 'h1', 'h2', 'h3', 'h4', 'li']):
                text = tag.get_text(strip=True)
                if not text or len(text) < 20 or len(text) > 280:
                    continue
                if not any(kw in text for kw in KEYWORDS):
                    continue
                if any(bad in text for bad in BLACKLIST):
                    continue
                cleaned = " ".join(text.split())
                if cleaned not in titles and "Dự thảo" in cleaned:
                    titles.append(cleaned)
    except Exception as e:
        print(f"❌ Lỗi {url}: {e}")
    return titles

def main():
    print("🚀 Đang quét...")

    df = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    df.columns = ["STT", "province", "url"] if len(df.columns) >= 3 else df.columns
    df = df.dropna(subset=["url"]).reset_index(drop=True)

    seen = load_seen_titles()
    all_new_rows = []
    total_new = 0

    for _, row in df.iterrows():
        province = str(row["province"]).strip()
        url = str(row["url"]).strip()
        print(f"📍 Đang quét {province}...")

        current_titles = extract_titles(url)
        print(f"   → Tìm thấy {len(current_titles)} tiêu đề thô")

        seen_list = seen.setdefault(province, [])
        new_titles = [t for t in current_titles if t not in seen_list]

        if new_titles:
            print(f"   ✅ Tìm thấy {len(new_titles)} văn bản MỚI")
            for title in new_titles:
                all_new_rows.append({"Tỉnh": province, "Tên dự thảo": title})
            seen_list.extend(new_titles)
            total_new += len(new_titles)

        time.sleep(2)

    save_seen_titles(seen)

    if all_new_rows:
        report_df = pd.DataFrame(all_new_rows)
        report_df['ngay_scrape'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Lưu file CSV (append)
        if os.path.exists(REPORT_CSV):
            report_df.to_csv(REPORT_CSV, mode='a', header=False, index=False, encoding='utf-8-sig')
            print(f"✅ ĐÃ THÊM {len(report_df)} dự thảo MỚI vào file tổng hợp")
        else:
            report_df.to_csv(REPORT_CSV, mode='w', header=True, index=False, encoding='utf-8-sig')
            print(f"✅ ĐÃ TẠO file tổng hợp mới")

        msg = f"🎉 <b>Có {total_new} dự thảo MỚI</b>\n📄 File tổng hợp: {REPORT_CSV}"
        send_telegram(msg, REPORT_CSV)

        print(f"\n🎉 HOÀN TẤT! Tìm thấy {total_new} dự thảo MỚI.")
        print(f"📄 File tổng hợp: {REPORT_CSV}")
    else:
        print("\n✅ Hôm nay không có dự thảo mới.")
        send_telegram("✅ Hôm nay không có dự thảo mới.")

if __name__ == "__main__":
    main()
