import base64
import io
import numpy as np
import pandas as pd
import pytz
import requests
import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI
from PIL import Image

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Auto Scheduler, Screener, AI Vision & Watchlist")
st.markdown("Sistem Imbasan Automatik Berjadual, Penapis Uptrend Patuh Syariah (EMA20/EMA50/RSI/RVOL), AI Chart Inspector & Multi-TP")

# --- SENARAI PENGECUALIAN KAUNTER BUKAN PATUH SYARIAH ---
NON_SHARIAH_EXCLUDED = {
    "MAYBANK", "CIMB", "PBBANK", "HLBANK", "RHBBANK", "AMBANK",
    "ABMB", "AFFIN", "MBSB", "BIMB", "HLFG", "LPI", "ALLIANZ",
    "TAKAFUL", "BURSA", "GENTING", "GENM", "MAGNUM", "SPTOTO",
    "CARLSBG", "HEIM", "BAT", "ASTRO", "CAPITALA",
}

# --- MASTER SEKTOR & KAUNTER UTAMA BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUD", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"],
}

master_bursa_tickers = []
ticker_to_sector = {}
for sec_name, t_list in sector_benchmarks.items():
    for t in t_list:
        ticker_to_sector[t] = sec_name
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(set(master_bursa_tickers))


# --- FUNGSI AMBIL LIVE DATA DARI TRADINGVIEW SCANNER API ---
def fetch_tradingview_scanner(tickers):
    formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "symbols": {"tickers": formatted_symbols},
        "columns": [
            "close", "change", "volume", "RSI",
            "MACD.macd", "MACD.signal", "BB.upper", "BB.lower",
            "EMA20", "EMA50", "volume[1]", "relative_volume_10d_calc",
        ],
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = {}
            for item in data.get("data", []):
                sym = item["s"].replace("MYX:", "")
                vals = item["d"]
                close_val = vals[0] if len(vals) > 0 and vals[0] is not None else 0.0
                ema20_val = vals[8] if len(vals) > 8 and vals[8] is not None else 0.0
                ema50_val = vals[9] if len(vals) > 9 and vals[9] is not None else 0.0
                prev_vol_val = vals[10] if len(vals) > 10 and vals[10] is not None else 0
                rvol_val = vals[11] if len(vals) > 11 and vals[11] is not None else 0.0
                results[sym] = {
                    "close": close_val,
                    "change": vals[1] if len(vals) > 1 and vals[1] is not None else 0.0,
                    "volume": vals[2] if len(vals) > 2 and vals[2] is not None else 0,
                    "prev_volume": prev_vol_val,
                    "rvol": rvol_val,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0,
                    "macd": vals[4] if len(vals) > 4 and vals[4] is not None else 0.0,
                    "macd_signal": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "bb_upper": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    "bb_lower": vals[7] if len(vals) > 7 and vals[7] is not None else 0.0,
                    "ema20": ema20_val,
                    "ema50": ema50_val,
                }
            return results
    except Exception:
        pass
    return {}


def semak_uptrend_menaik(info, rsi_min=50.0, rsi_max=80.0):
    """
    Menyemak sama ada kaunter berada dalam fasa uptrend menaik:
    - Harga semasa berada di atas EMA20 dan EMA20 berada di atas EMA50
    - RSI berada dalam julat menaik yang ditetapkan
    """
    harga = info.get("close", 0.0)
    ema20 = info.get("ema20", 0.0)
    ema50 = info.get("ema50", 0.0)
    rsi_val = info.get("rsi", 0.0)

    ema_valid = (ema20 > 0) and (ema50 > 0) and (harga > ema20) and (ema20 > ema50)
    rsi_valid = (rsi_val >= rsi_min) and (rsi_val <= rsi_max)
    return ema_valid and rsi_valid


# --- FUNGSI IMBASAN LATAR BELAKANG (BACKGROUND SCHEDULER JOB) ---
def background_scan_job():
    try:
        shariah_tickers = [t for t in master_bursa_tickers if t not in NON_SHARIAH_EXCLUDED]
        tv_results = fetch_tradingview_scanner(shariah_tickers)
        alert_messages = []
        for t in shariah_tickers:
            if t in tv_results:
                info = tv_results[t]
                price = info["close"]
                change = info["change"]
                rsi_val = info["rsi"]
                vol = info["volume"]
                rvol = info.get("rvol", 0.0)

                is_uptrend = semak_uptrend_menaik(info, rsi_min=50.0, rsi_max=80.0)
                if price >= 0.50 and is_uptrend and change >= -2.0:
                    if change >= 2.0 and vol > 500000:
                        signal = "🔥 Uptrend + Momentum Kuat (Kaji BOB)"
                    elif -1.5 <= change < 2.0 and vol > 300000:
                        signal = "🔄 Uptrend + Pullback/Reversal (Kaji BOD)"
                    else:
                        signal = "📈 Uptrend Menaik"
                    sec_name = ticker_to_sector.get(t, "Lain-lain")
                    alert_messages.append(
                        f"• *{t}* ({sec_name}) | RM {price:.2f} | RSI {rsi_val:.1f} | RVOL {rvol:.2f}x | {signal}"
                    )

        token = st.secrets.get("TELEGRAM_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        if alert_messages and token and chat_id:
            full_msg = (
                "🚨 *MYX AUTOMATED SCHEDULED ALERT (UPTREND SHARIAH)* 🚨\n"
                "Kaunter uptrend menaik berpotensi untuk dikaji pada carta:\n"
                + "\n".join(alert_messages)
            )
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": full_msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Background job error: {e}")


@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kuala_Lumpur"))
    scheduler.add_job(background_scan_job, "cron", hour=9, minute=0, day_of_week="mon-fri")
    scheduler.add_job(background_scan_job, "cron", hour=17, minute=0, day_of_week="mon-fri")
    scheduler.start()
    return scheduler


start_scheduler()

# --- SIDEBAR TETAPAN & PENAPIS LANJUTAN ---
st.sidebar.header("⚙️ Kriteria Tapisan Asas")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
filter_shariah_only = st.sidebar.checkbox("Tapis Keluar Saham Bukan Syariah (Bank/Konvensional)", value=True)
filter_uptrend_only = st.sidebar.checkbox("Hanya Uptrend Menaik (Harga > EMA20 > EMA50)", value=True)
min_rsi = st.sidebar.slider("Had Minimum RSI (Uptrend)", 30, 65, 50, 1)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -2.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Penapisan Indikator & Volum")
min_rvol = st.sidebar.slider("RVOL Minimum (10D) [0 = Semua, 1.2 = Sihat, 1.5 = Kuat]", 0.0, 3.0, 0.0, 0.1)
filter_vol_higher = st.sidebar.checkbox("Hanya Volum > Volum Sebelumnya", value=False)
filter_macd = st.sidebar.checkbox("Hanya MACD Bullish Crossover (MACD > Signal)", value=False)
filter_bb_squeeze = st.sidebar.checkbox("Hanya Bollinger Bands Squeeze (Konsolidasi Sempit)", value=False)

st.sidebar.markdown("---")
st.sidebar.header("🤖 OpenAI API Tetapan")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", placeholder="sk-...")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Telegram Bot Alert (Manual Test)")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

# --- KALKULATOR RISIKO & MULTI-TP ---
st.sidebar.markdown("---")
st.sidebar.header("🧮 Kalkulator Risiko & Multi-TP")
calc_
