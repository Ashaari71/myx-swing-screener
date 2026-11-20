import base64
import io
import os
import re
import time

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from PIL import Image

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OpenAI = None
    OPENAI_AVAILABLE = False

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.title("📈 MYX Swing Pro: Screener, Heatmap, AI Vision & Watchlist")
st.caption("Penapis Uptrend Patuh Syariah (EMA20/EMA50/RSI/RVOL/52WH), Imbasan Penuh Mengikut Sektor & Heatmap")

NON_SHARIAH_EXCLUDED = {
    "MAYBANK", "CIMB", "PBBANK", "HLBANK", "RHBBANK", "AMBANK",
    "ABMB", "AFFIN", "MBSB", "BIMB", "HLFG", "LPI", "ALLIANZ",
    "TAKAFUL", "BURSA", "GENTING", "GENM", "MAGNUM", "SPTOTO",
    "CARLSBG", "HEIM", "BAT", "ASTRO", "CAPITALA",
}

sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur": ["GAMUDA", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX", "DNEX"],
    "🏥 Penjagaan Kesihatan": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"],
}

SECTOR_TV_MAP = {
    "🔥 Pembinaan & Infrastruktur": ["Construction", "Engineering & Construction", "Industrials"],
    "⚡ Tenaga Boleh Baharu & Utiliti": ["Utilities", "Energy Minerals"],
    "💻 Teknologi & Semikonduktor": ["Technology Services", "Electronic Technology"],
    "🏥 Penjagaan Kesihatan": ["Health Services", "Health Technology"],
    "🌾 Perladangan & Komoditi": ["Agricultural Commodities", "Producer Manufacturing"],
    "⚙️ Perindustrian & Telco": ["Industrial Services", "Communications", "Distribution Services"],
}

PROMPT_PENAPIS_PENUH = """
Bertindak sebagai penapis setup teknikal yang ketat untuk strategi Buy on Breakout (BOB) dan Buy on Dip (BOD).
Fokus utama analisis adalah hala tuju pergerakan (market direction), kebarangkalian senario, dan idea dagangan yang berdisiplin.

Nilai carta ini secara objektif. Berikan idea dagangan HANYA JIKA salah satu syarat di bawah dipenuhi secara jelas pada struktur harga semasa:

1. SYARAT BOB KETAT (Anti-Fake Breakout):
Setup BOB hanya dianggap berpotensi sah jika memenuhi sekurang-kurangnya 3 daripada 4 kriteria berikut:
- Penutupan Kukuh (Close Confirmation): Harga berjaya ditutup (close) melepasi zon rintangan/konsolidasi, bukan sekadar mencucuk atau meninggalkan ekor atas (upper wick) yang panjang dan ditolak semula ke bawah rintangan.
- Sokongan Volume / RVOL: Pergerakan tembusan disokong oleh lonjakan volume atau RVOL yang jelas lebih tinggi berbanding purata/hari sebelumnya.
- Struktur Trend Menyokong: Harga berada dalam struktur uptrend atau keluar dari fasa konsolidasi yang kemas, dengan paras sokongan terdekat / EMA tidak terlalu jauh sehingga risiko cut loss menjadi tidak masuk akal.
- Ruang Pergerakan (Clear Path): Tiada halangan rintangan major yang terlalu rapat tepat di atas paras breakout.

AMARAN FAKE BREAKOUT (Wajib Tolak / Tunggu jika berlaku):
- Lilin tembusan mempunyai upper shadow/wick panjang menandakan penolakan penjual.
- Harga sekadar "spike" singkat melepasi rintangan tetapi gagal mengekalkan kedudukan.
- Breakout berlaku dalam keadaan volume mendatar/lemah atau pasaran choppy/sideways.
Jika tanda-tanda ini kelihatan, anggap ia sebagai potensi FALSE BREAKOUT dan tandakan status sebagai [TIADA SETUP - TUNGGU].

2. SYARAT BOD KETAT (Anti-Pisau Jatuh):
Setup BOD hanya dianggap berpotensi sah jika memenuhi sekurang-kurangnya 3 daripada 4 kriteria berikut:
- Konteks Trend Menaik Terpelihara: Struktur keseluruhan masih menunjukkan kecenderungan menaik dan harga belum memecahkan paras sokongan struktur utama secara jelas.
- Penurunan Terkawal (Bukan Menjunam): Pullback berlaku secara berperingkat atau perlahan menuju zon sokongan (EMA 20 / EMA 50 / support), bukan siri lilin merah besar yang agresif.
- Isyarat Penolakan / Kestabilan di Sokongan: Terdapat tanda pembeli mula mempertahankan zon sokongan (lower shadow / wick panjang di bawah, lilin pemulihan, atau kestabilan harga).
- Volume Terkawal / Tidak Panik: Penurunan tidak disertai lonjakan volume jualan yang luar biasa.

AMARAN PISAU JATUH / DOWNTREND (Wajib Tolak / Tunggu jika berlaku):
- Harga jatuh melepasi paras sokongan penting atau EMA utama secara jelas dan gagal bertahan.
- Terdapat lilin merah besar berturut-turut atau tekanan jualan agresif dengan volume tinggi.
- Struktur harga membentuk lower high dan lower low yang jelas.
Jika tanda-tanda ini kelihatan, anggap ia sebagai RISIKO PISAU JATUH / DOWNTREND dan tandakan status sebagai [TIADA SETUP - TUNGGU].

ATURAN PENAPISAN MUTLAK:
Jika carta berada dalam keadaan mendatar (sideways) yang bercelaru, downtrend yang jelas, atau tiada isyarat BOB/BOD yang meyakinkan, JANGAN paksa beri idea kemasukan. Tetapkan status sebagai [TIADA SETUP - TUNGGU]. Elakkan penerangan teori indikator secara panjang lebar.

Format output (ringkas & terus ke inti pati):
1. **Status Setup:** [BOB Valid / BOD Valid / TIADA SETUP - TUNGGU]
2. **Hala Tuju & Kebarangkalian:**
   - **Senario Utama (~60-70%):** [Hala tuju pergerakan seterusnya berdasarkan struktur & volume semasa]
   - **Senario Alternatif (~30-40%):** [Perubahan hala tuju jika paras kritikal ditembusi atau gagal bertahan]
3. **Paras Kritikal:** Rintangan [paras] | Sokongan [paras]
4. **Idea Tindakan (Jika Valid Sahaja):**
   - **Jenis:** [BOB / BOD / Tiada]
   - **Trigger Masuk:** [Syarat pengesahan]
   - **Paras Batal:** [Paras harga jika struktur gagal]
"""

master_bursa_tickers = []
ticker_to_sector = {}
for sec_name, t_list in sector_benchmarks.items():
    for t in t_list:
        ticker_to_sector[t] = sec_name
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(dict.fromkeys(master_bursa_tickers))


def dapatkan_openai_key(ui_key: str) -> str:
    if ui_key and ui_key.strip():
        return ui_key.strip()
    if "OPENAI_API_KEY" in st.secrets:
        return str(st.secrets["OPENAI_API_KEY"]).strip()
    return os.getenv("OPENAI_API_KEY", "").strip()


def fetch_tradingview_scanner(tickers):
    formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "symbols": {"tickers": formatted_symbols},
        "columns": [
            "close", "change", "volume", "RSI",
            "MACD.macd", "MACD.signal", "BB.upper", "BB.lower",
            "EMA20", "EMA50", "volume[1]", "relative_volume_10d_calc",
            "price_52_week_high",
        ],
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = {}
            for item in data.get("data", []):
                sym = item["s"].replace("MYX:", "")
                vals = item["d"]
                results[sym] = {
                    "close": vals[0] if len(vals) > 0 and vals[0] is not None else 0.0,
                    "change": vals[1] if len(vals) > 1 and vals[1] is not None else 0.0,
                    "volume": vals[2] if len(vals) > 2 and vals[2] is not None else 0,
                    "prev_volume": vals[10] if len(vals) > 10 and vals[10] is not None else 0,
                    "rvol": vals[11] if len(vals) > 11 and vals[11] is not None else 0.0,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0,
                    "macd": vals[4] if len(vals) > 4 and vals[4] is not None else 0.0,
                    "macd_signal": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "bb_upper": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    "bb_lower": vals[7] if len(vals) > 7 and vals[7] is not None else 0.0,
                    "ema20": vals[8] if len(vals) > 8 and vals[8] is not None else 0.0,
                    "ema50": vals[9] if len(vals) > 9 and vals[9] is not None else 0.0,
                    "high_52w": vals[12] if len(vals) > 12 and vals[12] is not None else 0.0,
                }
            return results
    except Exception:
        pass
    return {}


def fetch_sector_all_stocks(sector_label, limit=120):
    tv_sectors = SECTOR_TV_MAP.get(sector_label, [])
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "markets": ["malaysia"],
        "symbols": {"query": {"types": ["stock"]}},
        "options": {"lang": "en"},
        "columns": [
            "name", "close", "change", "volume", "RSI",
            "MACD.macd", "MACD.signal", "BB.upper", "BB.lower",
            "EMA20", "EMA50", "volume[1]", "relative_volume_10d_calc",
            "price_52_week_high", "sector",
        ],
        "filter": [{"left": "sector", "operation": "in_range", "right": tv_sectors}] if tv_sectors else [],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "range": [0, limit],
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    results = {}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            for item in response.json().get("data", []):
                vals = item.get("d", [])
                sym = str(vals[0]).upper() if len(vals) > 0 and vals[0] else item["s"].replace("MYX:", "")
                results[sym] = {
                    "close": vals[1] if len(vals) > 1 and vals[1] is not None else 0.0,
                    "change": vals[2] if len(vals) > 2 and vals[2] is not None else 0.0,
                    "volume": vals[3] if len(vals) > 3 and vals[3] is not None else 0,
                    "rsi": vals[4] if len(vals) > 4 and vals[4] is not None else 50.0,
                    "macd": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "macd_signal": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    "bb_upper": vals[7] if len(vals) > 7 and vals[7] is not None else 0.0,
                    "bb_lower": vals[8] if len(vals) > 8 and vals[8] is not None else 0.0,
                    "ema20": vals[9] if len(vals) > 9 and vals[9] is not None else 0.0,
                    "ema50": vals[10] if len(vals) > 10 and vals[10] is not None else 0.0,
                    "prev_volume": vals[11] if len(vals) > 11 and vals[11] is not None else 0,
                    "rvol": vals[12] if len(vals) > 12 and vals[12] is not None else 0.0,
                    "high_52w": vals[13] if len(vals) > 13 and vals[13] is not None else 0.0,
                }
    except Exception:
        pass

    fallback_tickers = sector_benchmarks.get(sector_label, [])
    if fallback_tickers:
        fb_data = fetch_tradingview_scanner(fallback_tickers)
        for k, v in fb_data.items():
            if k not in results:
                results[k] = v

    return results


def semak_uptrend_menaik(info, rsi_min=50.0, rsi_max=80.0):
    harga = info.get("close", 0.0)
    ema20 = info.get("ema20", 0.0)
    ema50 = info.get("ema50", 0.0)
    rsi_val = info.get("rsi", 0.0)
    ema_valid = (ema20 > 0) and (ema50 > 0) and (harga > ema20) and (ema20 > ema50)
    rsi_valid = (rsi_val >= rsi_min) and (rsi_val <= rsi_max)
    return ema_valid and rsi_valid


def ekstrak_status_setup(teks_analisis: str) -> str:
    if not teks_analisis:
        return "TIADA SETUP - TUNGGU"

    padanan = re.search(
        r"status\s*setup\s*[:\-]?\s*\*?\*?([^\n\r]+)",
        teks_analisis,
        flags=re.IGNORECASE,
    )
    rujukan = padanan.group(1) if padanan else teks_analisis
    kecil = rujukan.lower()

    if re.search(r"\b(bukan|tidak|tiada)\b[^\n]{0,25}\b(bob valid|bod valid)\b", kecil):
        return "TIADA SETUP - TUNGGU"

    if "bob valid" in kecil:
        return "BOB Valid"
    if "bod valid" in kecil:
        return "BOD Valid"
    return "TIADA SETUP - TUNGGU"


def bersihkan_html_untuk_telegram(teks: str) -> str:
    if not teks:
        return ""
    teks_format = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", teks)
    teks_format = re.sub(r"<(?!(?:/?(?:b|i|u|s|code|pre|a)\b))", "<", teks_format)
    teks_format = teks_format.replace(">", ">")
    teks_format = re.sub(
        r"<(/?(?:b|i|u|s|code|pre|a))(>)",
        r"<\1>",
        teks_format,
        flags=re.IGNORECASE,
    )
    return teks_format


def send_telegram_message(token, chat_id, message, parse_mode="HTML"):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    teks_bersih = bersihkan_html_untuk_telegram(message) if parse_mode == "HTML" else message
    if len(teks_bersih) > 4000:
        teks_bersih = teks_bersih[:3990] + "\n..."
    try:
        res = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": teks_bersih,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if res.ok and res.json().get("ok"):
            return True
        fallback = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": re.sub(r"<[^>]+>", "", teks_bersih),
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return bool(fallback.ok and fallback.json().get("ok"))
    except Exception:
        return False


def analyze_chart_bob_bod(
    api_key,
    image,
    trend,
    price,
    ticker="",
    timeframe="Daily",
    rvol=None,
    ema20=None,
    ema50=None,
    model="gpt-4o",
    max_retries=2,
):
    if not OPENAI_AVAILABLE or OpenAI is None:
        return "1. **Status Setup:** TIADA SETUP - TUNGGU\n⚠️ Pakej `openai` tidak dipasang."
    if not api_key:
        return "1. **Status Setup:** TIADA SETUP - TUNGGU\n⚠️ OpenAI API Key tidak dijumpai."

    try:
        client = OpenAI(api_key=api_key)
        img_copy = image.copy()
        if img_copy.mode in ("RGBA", "P"):
            img_copy = img_copy.convert("RGB")
        buf = io.BytesIO()
        img_copy.save(buf, format="JPEG", quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        konteks = [
            f"Timeframe: {timeframe}",
            f"Trend Asas: {trend}",
            f"Harga Semasa: RM {price:.3f}",
        ]
        if ticker:
            konteks.append(f"Kaunter: {ticker.upper()}")
        if rvol is not None and rvol > 0:
            konteks.append(f"RVOL: {rvol:.2f}x")
        if ema20 is not None and ema20 > 0:
            konteks.append(f"EMA 20: {ema20:.3f}")
        if ema50 is not None and ema50 > 0:
            konteks.append(f"EMA 50: {ema50:.3f}")

        user_prompt = f"Data Rujukan: {' | '.join(konteks)}\n\n{PROMPT_PENAPIS_PENUH}"

        for percubaan in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model
