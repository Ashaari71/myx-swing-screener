import base64
import io
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
st.caption("Penapis Uptrend Patuh Syariah (EMA20/EMA50/RSI/RVOL), Imbasan Penuh Mengikut Sektor & Heatmap")

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
    "🔥 Pembinaan & Infrastruktur": ["Construction"],
    "⚡ Tenaga Boleh Baharu & Utiliti": ["Utilities", "Energy Minerals"],
    "💻 Teknologi & Semikonduktor": ["Technology Services", "Electronic Technology"],
    "🏥 Penjagaan Kesihatan": ["Health Services", "Health Technology"],
    "🌾 Perladangan & Komoditi": ["Agricultural Commodities", "Producer Manufacturing"],
    "⚙️ Perindustrian & Telco": ["Industrial Services", "Communications", "Distribution Services"],
}

master_bursa_tickers = []
ticker_to_sector = {}
for sec_name, t_list in sector_benchmarks.items():
    for t in t_list:
        ticker_to_sector[t] = sec_name
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(dict.fromkeys(master_bursa_tickers))


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
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = {}
            for item in data.get("data", []):
                sym = item["s"].replace("MYX:", "")
                vals = item["d"]
                results[sym] = {}
                    "close": vals[0] if len(vals) > 0 and vals[0] is not None else 0.0,
                    "change": vals[1] if len(vals) > 1 and vals[1] is not None else 0.0,
                    "volume": vals[2] if len(vals) > 2 and vals[2] is not None else 0,
                    "prev_volume": vals[10] if len(vals) > 10 and vals[10] is not None else 0,
                    "rvol": vals[11] if len(vals) > 11 and vals[11] is not None else 0.0,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0,
                    "macd": vals[4] if len(vals) > 4 and vals[4] is not None else 0.0,
                    "macd_signal": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "bb_upper": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    
