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
                    "rsi": vals[3] if len
