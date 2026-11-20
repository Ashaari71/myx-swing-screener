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
                    model=model,
                    temperature=0.1,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Anda ialah penganalisis teknikal yang berdisiplin, objektif, "
                                "dan ketat menapis setup dagangan tanpa rekaan."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        },
                    ],
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                if percubaan < max_retries:
                    time.sleep(1.5 * (percubaan + 1))
                    continue
                return f"1. **Status Setup:** TIADA SETUP - TUNGGU\n⚠️ Ralat OpenAI: {exc}"
    except Exception as e:
        return f"1. **Status Setup:** TIADA SETUP - TUNGGU\n⚠️ Ralat OpenAI: {e}"

    return "1. **Status Setup:** TIADA SETUP - TUNGGU"


st.sidebar.header("⚙️ Kriteria Tapisan Asas")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
filter_shariah_only = st.sidebar.checkbox("Tapis Keluar Saham Bukan Syariah", value=True)
filter_uptrend_only = st.sidebar.checkbox("Hanya Uptrend Menaik (Harga > EMA20 > EMA50)", value=True)
min_rsi = st.sidebar.slider("Had Minimum RSI", 30, 65, 36, 1)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -10.0, 5.0, -5.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Indikator & Volum")
min_rvol = st.sidebar.slider("RVOL Minimum (10D)", 0.0, 3.0, 0.0, 0.1)
filter_vol_higher = st.sidebar.checkbox("Hanya Volum > Volum Sebelumnya", value=False)
filter_macd = st.sidebar.checkbox("Hanya MACD Bullish Crossover", value=False)
filter_bb_squeeze = st.sidebar.checkbox("Hanya Bollinger Bands Squeeze", value=False)
filter_52wh = st.sidebar.checkbox("Hanya Dekat / Breakout 52WH", value=False)
max_52wh_dist_pct = st.sidebar.slider("Jarak Maksimum Dari 52WH (%)", 0.0, 15.0, 3.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🤖 OpenAI & Telegram")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

st.sidebar.markdown("---")
st.sidebar.header("🧮 Kalkulator Risiko & Multi-TP")
calc_capital = st.sidebar.number_input("Jumlah Modal (RM)", value=10000.0, step=500.0)
calc_risk_pct = st.sidebar.slider("Risiko Maksimum (%)", 1.0, 5.0, 2.0, 0.5)
calc_entry = st.sidebar.number_input("Harga Entry (RM)", value=1.00, step=0.01)
calc_sl = st.sidebar.number_input("Harga Stop-Loss (RM)", value=0.92, step=0.01)
calc_tp1 = st.sidebar.number_input("Target 1 - TP1 (RM)", value=1.10, step=0.01)
calc_tp2 = st.sidebar.number_input("Target 2 - TP2 (RM)", value=1.25, step=0.01)

if calc_entry > 0 and calc_sl > 0 and calc_entry > calc_sl:
    max_risk_rm = calc_capital * (calc_risk_pct / 100.0)
    risk_per_share = calc_entry - calc_sl
    suggested_shares = max(100, int((max_risk_rm / risk_per_share) // 100) * 100)
    half_shares = suggested_shares // 2
    profit_tp1 = half_shares * (calc_tp1 - calc_entry) if calc_tp1 > calc_entry else 0.0
    profit_tp2 = half_shares * (calc_tp2 - calc_entry) if calc_tp2 > calc_entry else 0.0
    rr_ratio = (calc_tp2 - calc_entry) / risk_per_share
    st.sidebar.info(
        f"Lot: {suggested_shares // 100} lot ({suggested_shares:,} unit)\n"
        f"Modal: RM {suggested_shares * calc_entry:,.2f}\n"
        f"Risiko Maks: RM {suggested_shares * risk_per_share:,.2f}\n"
        f"TP1: RM {profit_tp1:,.2f} | TP2: RM {profit_tp2:,.2f}\n"
        f"R:R (TP2): 1 : {rr_ratio:.2f}"
    )
else:
    st.sidebar.warning("Harga Entry mesti lebih tinggi daripada Stop-Loss.")


for k in ["scan_results", "raw_tickers", "watchlist", "sector_perf", "heatmap_rows", "ai_chart_history"]:
    if k not in st.session_state:
        st.session_state[k] = []

if "raw_scan_map" not in st.session_state:
    st.session_state["raw_scan_map"] = {}

app_mode = st.radio(
    "Mod Sistem:",
    ["🔍 Screener & Sektor", "📸 AI Chart Vision", "⭐ Watchlist", "🔗 Pautan Rasmi"],
    horizontal=True,
)
st.markdown("---")

if app_mode == "🔗 Pautan Rasmi":
    st.markdown("* [Bursa Malaysia](https://www.bursamalaysia.com/)")
    st.markdown("* [KLSE Screener](https://www.klsescreener.com/)")
    st.markdown("* [Senarai Patuh Syariah SC](https://www.sc.com.my/development/icm/shariah-compliant-securities/list-of-shariah-compliant-securities)")

elif app_mode == "⭐ Watchlist":
    if st.session_state.watchlist:
        st.dataframe(pd.DataFrame(st.session_state.watchlist), use_container_width=True, hide_index=True)
        if st.button("🗑️ Kosongkan Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.info("Watchlist masih kosong.")

elif app_mode == "📸 AI Chart Vision":
    st.subheader("Penapis Ketat Carta AI (BOB / BOD & Kebarangkalian Hala Tuju)")

    pilihan_screener = ["(Manual / Taip Sendiri)"] + st.session_state.get("raw_tickers", [])

    def _isi_data_dari_screener():
        terpilih = st.session_state.get("pilih_kaunter_screener", "(Manual / Taip Sendiri)")
        if terpilih == "(Manual / Taip Sendiri)":
            return
        st.session_state["ai_ticker_val"] = terpilih
        data_t = st.session_state.get("raw_scan_map", {}).get(terpilih, {})

        harga_baru = float(data_t.get("close") or 0.0)
        if harga_baru > 0:
            st.session_state["ai_price_val"] = harga_baru

        rvol_baru = float(data_t.get("rvol") or 0.0)
        if rvol_baru > 0:
            st.session_state["ai_rvol_val"] = rvol_baru

        ema20_baru = float(data_t.get("ema20") or 0.0)
        if ema20_baru > 0:
            st.session_state["ai_ema20_val"] = ema20_baru

        ema50_baru = float(data_t.get("ema50") or 0.0)
        if ema50_baru > 0:
            st.session_state["ai_ema50_val"] = ema50_baru

    st.session_state.setdefault("ai_ticker_val", "PEKAT")
    st.session_state.setdefault("ai_price_val", 0.95)
    st.session_state.setdefault("ai_rvol_val", 0.0)
    st.session_state.setdefault("ai_ema20_val", 0.0)
    st.session_state.setdefault("ai_ema50_val", 0.0)

    st.selectbox(
        "Pilih Kaunter Dari Hasil Imbasan (Auto-Isi Data):",
        options=pilihan_screener,
        key="pilih_kaunter_screener",
        on_change=_isi_data_dari_screener,
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        ai_ticker = st.text_input("Kaunter:", key="ai_ticker_val").strip().upper()
        ai_tf = st.selectbox("Timeframe:", ["Daily", "15m", "1H"])
    with col_b:
        trend = st.selectbox("Trend Asas:", ["🚀 Uptrend", "⚖️ Sideway", "📉 Downtrend"])
        cur_price = st.number_input(
            "Harga Semasa (RM):",
            min_value=0.0,
            step=0.005,
            format="%.3f",
            key="ai_price_val",
        )
    with col_c:
        ai_rvol = st.number_input(
            "RVOL:",
            min_value=0.0,
            step=0.10,
            format="%.2f",
            key="ai_rvol_val",
        )
        ai_ema20 = st.number_input(
            "EMA 20:",
            min_value=0.0,
            step=0.005,
            format="%.3f",
            key="ai_ema20_val",
        )
        ai_ema50 = st.number_input(
            "EMA 50:",
            min_value=0.0,
            step=0.005,
            format="%.3f",
            key="ai_ema50_val",
        )

    uploaded = st.file_uploader("Muat naik carta (PNG/JPG):", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        img = Image.open(uploaded)
        st.image(img, caption="Carta Dimuat Naik", use_column_width=True)

        if st.button("✨ Analisis BOB / BOD", type="primary"):
            active_key = dapatkan_openai_key(openai_api_key)
            if not active_key:
                st.error("Masukkan OpenAI API Key di sidebar atau tetapkan OPENAI_API_KEY.")
            else:
                with st.spinner("Menganalisis struktur carta & kebarangkalian..."):
                    hasil_teks = analyze_chart_bob_bod(
                        api_key=active_key,
                        image=img,
                        trend=trend,
                        price=cur_price,
                        ticker=ai_ticker,
                        timeframe=ai_tf,
                        rvol=ai_rvol if ai_rvol > 0 else None,
                        ema20=ai_ema20 if ai_ema20 > 0 else None,
                        ema50=ai_ema50 if ai_ema50 > 0 else None,
                    )
                    status_setup = ekstrak_status_setup(hasil_teks)
                    dihantar_tg = False

                    if status_setup in ("BOB Valid", "BOD Valid") and telegram_token and telegram_chat_id:
                        tajuk_tg = f"<b>{ai_ticker or 'CARTA'}</b> ({ai_tf}) — <b>{status_setup}</b>"
                        dihantar_tg = send_telegram_message(
                            telegram_token,
                            telegram_chat_id,
                            f"{tajuk_tg}\n\n{hasil_teks}",
                            parse_mode="HTML",
                        )

                    st.session_state.ai_chart_history.insert(
                        0,
                        {
                            "Kaunter": ai_ticker or "-",
                            "TF": ai_tf,
                            "Status": status_setup,
                            "Telegram": "Dihantar" if dihantar_tg else "-",
                            "Analisis": hasil_teks,
                        },
                    )

                if status_setup in ("BOB Valid", "BOD Valid"):
                    st.success(f"Status: **{status_setup}**" + (" — Notifikasi Telegram dihantar." if dihantar_tg else ""))
                else:
                    st.warning("Status: **TIADA SETUP - TUNGGU** (Tidak dihantar ke Telegram)")
                st.markdown(hasil_teks)
                if ai_ticker:
                    tv_link = f"https://www.tradingview.com/chart/?symbol=MYX%3A{ai_ticker.replace('.KL', '')}"
                    st.markdown(f"👉 [Buka Carta {ai_ticker} di TradingView]({tv_link})")

    if st.session_state.ai_chart_history:
        st.divider()
        col_tajuk, col_butang = st.columns([4, 1])
        with col_tajuk:
            st.markdown("**Sejarah Analisis Carta Sesi Ini**")
        with col_butang:
            if st.button("🗑️ Kosongkan Sejarah", key="kosongkan_sejarah_ai"):
                st.session_state.ai_chart_history = []
                st.rerun()

        for item in st.session_state.ai_chart_history:
            label_row = f"{item['Kaunter']} ({item['TF']}) — `{item['Status']}` | TG: {item['Telegram']}"
            with st.expander(label_row, expanded=False):
                st.markdown(item["Analisis"])

else:
    scan_mode = st.radio("Mod Imbasan:", ["🤖 Seluruh Pasaran", "📂 Ikut Sektor"], horizontal=True)
    sel_sec = None
    if scan_mode == "📂 Ikut Sektor":
        sel_sec = st.selectbox("Pilih Sektor (Semua Saham Dalam Sektor):", list(sector_benchmarks.keys()))
        targets = []
    else:
        targets = master_bursa_tickers
        if filter_shariah_only:
            targets = [t for t in targets if t not in NON_SHARIAH_EXCLUDED]

    if st.button("🚀 Mula Imbas Pasaran Sekarang", type="primary", use_container_width=True):
        st.session_state.raw_scan_map = {}

        if scan_mode == "📂 Ikut Sektor" and sel_sec:
            tv_data = fetch_sector_all_stocks(sel_sec, limit=120)
            if filter_shariah_only:
                tv_data = {k: v for k, v in tv_data.items() if k not in NON_SHARIAH_EXCLUDED}
            scan_list = list(tv_data.keys())
        else:
            tv_data = fetch_tradingview_scanner(targets)
            scan_list = targets

        rows = []
        alerts = []
        heatmap_rows = []

        for t in scan_list:
            info = tv_data.get(t)
            if not info:
                continue
            price = info["close"]
            change = info["change"]
            rsi_val = info["rsi"]
            vol = info["volume"]
            prev_vol = info["prev_volume"]
            rvol = info["rvol"]
            high_52w = info.get("high_52w", 0.0)
            sec_name = sel_sec if (scan_mode == "📂 Ikut Sektor" and sel_sec) else ticker_to_sector.get(t, "Lain-lain")

            st.session_state.raw_scan_map[t] = {
                "close": float(price or 0.0),
                "rvol": float(rvol or 0.0),
                "ema20": float(info.get("ema20") or 0.0),
                "ema50": float(info.get("ema50") or 0.0),
            }

            heatmap_rows.append({
                "Kaunter": t,
                "Sektor": sec_name,
                "Harga (RM)": price,
                "Perubahan": f"{'+' if change >= 0 else ''}{change:.2f}%",
                "Perubahan_Num": change,
                "RSI": rsi_val,
                "Volum": max(float(vol), 1.0),
            })

            if price < min_price or change < min_change_pct:
                continue
            if min_rvol > 0 and rvol < min_rvol:
                continue

            if filter_52wh:
                if high_52w <= 0:
                    continue
                dist_52wh_pct = ((high_52w - price) / high_52w) * 100.0
                if dist_52wh_pct > max_52wh_dist_pct:
                    continue

            is_up = semak_uptrend_menaik(info, rsi_min=min_rsi, rsi_max=max_rsi)
            if filter_uptrend_only:
                if not is_up:
                    continue
            else:
                if rsi_val > max_rsi:
                    continue

            vol_up = prev_vol > 0 and vol > prev_vol
            if filter_vol_higher and not vol_up:
                continue
            if filter_macd and info["macd"] <= info["macd_signal"]:
                continue
            if filter_bb_squeeze and price > 0:
                if (info["bb_upper"] - info["bb_lower"]) / price > 0.08:
                    continue

            if high_52w > 0 and price >= high_52w:
                jarak_52wh_str = "🔥 Breakout 52WH"
            elif high_52w > 0 and price > 0:
                jarak_52wh_str = f"-{((high_52w - price) / high_52w) * 100.0:.1f}%"
            else:
                jarak_52wh_str = "-"

            if is_up and change >= 2.0 and vol > 500000:
                fokus = "🔥 Kaji BOB"
            elif is_up and -1.5 <= change < 2.0 and vol > 300000:
                fokus = "🔄 Kaji BOD"
            elif is_up:
                fokus = "📈 Uptrend Menaik"
            else:
                fokus = "⚖️ Semak Carta"

            rows.append({
                "Kaunter": t,
                "Sektor": sec_name,
                "Harga (RM)": round(price, 2),
                "52WH (RM)": round(high_52w, 2) if high_52w > 0 else "-",
                "Jarak 52WH": jarak_52wh_str,
                "Perubahan": f"{'+' if change >= 0 else ''}{change:.2f}%",
                "RSI": round(rsi_val, 1),
                "RVOL": f"{rvol:.2f}x" if rvol > 0 else "-",
                "Volum": f"{vol:,.0f}",
                "Fokus": fokus,
            })
            if is_up:
                alerts.append(f"• <b>{t}</b> | RM {price:.2f} | 52WH: {jarak_52wh_str} | RSI {rsi_val:.1f} | {fokus}")

        st.session_state.scan_results = rows
        st.session_state.raw_tickers = [r["Kaunter"] for r in rows]
        st.session_state.heatmap_rows = heatmap_rows

        if alerts and telegram_token and telegram_chat_id:
            send_telegram_message(
                telegram_token,
                telegram_chat_id,
                "🚨 <b>MYX SCREENER ALERT</b>\n" + "\n".join(alerts),
                parse_mode="HTML",
            )

        sec_rows = []
        for s_name, t_list in sector_benchmarks.items():
            if filter_shariah_only:
                t_list = [x for x in t_list if x not in NON_SHARIAH_EXCLUDED]
            s_data = fetch_tradingview_scanner(t_list)
            vals = [v["change"] for v in s_data.values()]
            avg = float(np.mean(vals)) if vals else 0.0
            sec_rows.append({
                "Sektor": s_name,
                "Purata (%)": f"{'+' if avg >= 0 else ''}{avg:.2f}%",
                "Status": "🔥 Leader" if avg > 0.5 else ("📈 Positif" if avg >= 0 else "📉 Lemah"),
            })
        st.session_state.sector_perf = sec_rows

    st.subheader("🗺️ Heatmap Sektor & Kaunter")
    if st.session_state.heatmap_rows:
        df_hm = pd.DataFrame(st.session_state.heatmap_rows)
        fig_hm = px.treemap(
            df_hm,
            path=["Sektor", "Kaunter"],
            values="Volum",
            color="Perubahan_Num",
            color_continuous_scale=["#b91c1c", "#4b5563", "#15803d"],
            color_continuous_midpoint=0,
            range_color=[-5, 5],
            labels={"Perubahan_Num": "Perubahan (%)"},
            hover_data={"Harga (RM)": ":.2f", "Perubahan": True, "RSI": ":.1f", "Volum": ":,"},
        )
        fig_hm.update_traces(
            texttemplate="<b>%{label}</b><br>RM %{customdata[0]:.2f}<br>%{customdata[1]}",
            textposition="middle center",
        )
        fig_hm.update_layout(height=540, margin=dict(t=20, l=10, r=10, b=10))
        st.plotly_chart(fig_hm, use_container_width=True)
    else:
        st.info("Klik **Mula Imbas Pasaran Sekarang** untuk menjana heatmap sektor.")

    st.subheader("📊 Prestasi Sektor")
    if st.session_state.sector_perf:
        st.dataframe(pd.DataFrame(st.session_state.sector_perf), use_container_width=True, hide_index=True)

    st.subheader("📋 Hasil Imbasan")
    if st.session_state.scan_results:
        df_res = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(df_res, use_container_width=True, hide_index=True)

        pick = st.selectbox("Pilih kaunter ke Watchlist:", st.session_state.raw_tickers)
        if st.button("➕ Tambah ke Watchlist"):
            item = next((x for x in st.session_state.scan_results if x["Kaunter"] == pick), None)
            if item and item not in st.session_state.watchlist:
                st.session_state.watchlist.append(item)
                st.success(f"{pick} ditambah ke Watchlist.")

        st.markdown("**Carta TradingView:**")
        cols_tv = st.columns(6)
        for idx, t_name in enumerate(st.session_state.raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols_tv[idx % 6]:
                st.markdown(f"👉 [{t_name}]({tv_url})")

        csv_bytes = df_res.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Muat Turun CSV", data=csv_bytes, file_name="myx_screener.csv", mime="text/csv")
    else:
        st.info("Klik **Mula Imbas Pasaran Sekarang** untuk melihat hasil.")


*Peringatan:* Pastikan anda menyalin dari baris `import base64` hingga ke baris `st.info("Klik **Mula Imbas Pasaran Sekarang** untuk melihat hasil.")` sahaja sebelum *commit* ke GitHub supaya tiada teks tambahan di bawah[cite: 2, 10, 11].
