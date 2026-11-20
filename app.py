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
st.caption("Penapis Uptrend Patuh Syariah (EMA20/EMA50/RSI/RVOL), Heatmap Sektor, AI Chart Inspector & Multi-TP")

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
                }
            return results
    except Exception:
        pass
    return {}


def semak_uptrend_menaik(info, rsi_min=50.0, rsi_max=80.0):
    harga = info.get("close", 0.0)
    ema20 = info.get("ema20", 0.0)
    ema50 = info.get("ema50", 0.0)
    rsi_val = info.get("rsi", 0.0)
    ema_valid = (ema20 > 0) and (ema50 > 0) and (harga > ema20) and (ema20 > ema50)
    rsi_valid = (rsi_val >= rsi_min) and (rsi_val <= rsi_max)
    return ema_valid and rsi_valid


st.sidebar.header("⚙️ Kriteria Tapisan Asas")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
filter_shariah_only = st.sidebar.checkbox("Tapis Keluar Saham Bukan Syariah", value=True)
filter_uptrend_only = st.sidebar.checkbox("Hanya Uptrend Menaik (Harga > EMA20 > EMA50)", value=True)
min_rsi = st.sidebar.slider("Had Minimum RSI", 30, 65, 50, 1)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -2.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Indikator & Volum")
min_rvol = st.sidebar.slider("RVOL Minimum (10D)", 0.0, 3.0, 0.0, 0.1)
filter_vol_higher = st.sidebar.checkbox("Hanya Volum > Volum Sebelumnya", value=False)
filter_macd = st.sidebar.checkbox("Hanya MACD Bullish Crossover", value=False)
filter_bb_squeeze = st.sidebar.checkbox("Hanya Bollinger Bands Squeeze", value=False)

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


def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        res = requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}, timeout=10)
        return res.status_code == 200
    except Exception:
        return False


def analyze_chart_bob_bod(api_key, image, trend, price):
    if not OPENAI_AVAILABLE or OpenAI is None:
        return "⚠️ Pakej `openai` tidak dipasang."
    try:
        client = OpenAI(api_key=api_key)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        prompt = (
            f"Nilai struktur carta trend '{trend}', harga semasa RM {price}. "
            "Beri analisis ringkas dalam Bahasa Melayu: 1) Struktur trend, 2) Setup BOB atau BOD, "
            "3) Stop-Loss, Sokongan, Rintangan, TP1 & TP2, 4) Cadangan Watchlist."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            max_tokens=700,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ralat OpenAI: {e}"


for k in ["scan_results", "raw_tickers", "watchlist", "sector_perf", "heatmap_rows"]:
    if k not in st.session_state:
        st.session_state[k] = []

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
    uploaded = st.file_uploader("Muat naik carta (PNG/JPG):", type=["png", "jpg", "jpeg"])
    if uploaded is not None:
        img = Image.open(uploaded)
        st.image(img, caption="Carta Dimuat Naik", use_column_width=True)
        trend = st.selectbox("Trend Asas:", ["🚀 Uptrend", "📉 Downtrend", "⚖️ Sideway"])
        cur_price = st.number_input("Harga Semasa (RM):", value=0.95, step=0.01)
        if st.button("✨ Analisis BOB / BOD", type="primary"):
            if not openai_api_key:
                st.error("Masukkan OpenAI API Key di sidebar.")
            else:
                with st.spinner("Menganalisis carta..."):
                    st.markdown(analyze_chart_bob_bod(openai_api_key, img, trend, cur_price))

else:
    scan_mode = st.radio("Mod Imbasan:", ["🤖 Seluruh Pasaran", "📂 Ikut Sektor"], horizontal=True)
    if scan_mode == "📂 Ikut Sektor":
        sel_sec = st.selectbox("Pilih Sektor:", list(sector_benchmarks.keys()))
        raw_in = st.text_area("Kod Kaunter:", value=", ".join(sector_benchmarks[sel_sec]), height=70)
        targets = [x.strip().upper().replace(".KL", "") for x in raw_in.split(",") if x.strip()]
    else:
        targets = master_bursa_tickers

    if filter_shariah_only:
        targets = [t for t in targets if t not in NON_SHARIAH_EXCLUDED]

    if st.button("🚀 Mula Imbas Pasaran Sekarang", type="primary", use_container_width=True):
        tv_data = fetch_tradingview_scanner(targets)
        rows = []
        alerts = []
        heatmap_rows = []

        for t in targets:
            info = tv_data.get(t)
            if not info:
                continue
            price = info["close"]
            change = info["change"]
            rsi_val = info["rsi"]
            vol = info["volume"]
            prev_vol = info["prev_volume"]
            rvol = info["rvol"]
            sec_name = ticker_to_sector.get(t, "Lain-lain")

            heatmap_rows.append({
                "Kaunter": t,
                "Sektor": sec_name,
                "Harga (RM)": price,
                "Perubahan": f"{'+' if change >= 0 else ''}{change:.2f}%",
                "Perubahan_Num": change,
                "RSI": rsi_val,
                "Volum": max(float(vol), 1.0),
            })

            if price < min_price or rsi_val > max_rsi or change < min_change_pct:
                continue
            if min_rvol > 0 and rvol < min_rvol:
                continue

            is_up = semak_uptrend_menaik(info, rsi_min=min_rsi, rsi_max=max_rsi)
            if filter_uptrend_only and not is_up:
                continue

            vol_up = prev_vol > 0 and vol > prev_vol
            if filter_vol_higher and not vol_up:
                continue
            if filter_macd and info["macd"] <= info["macd_signal"]:
                continue
            if filter_bb_squeeze and price > 0:
                if (info["bb_upper"] - info["bb_lower"]) / price > 0.08:
                    continue

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
                "Perubahan": f"{'+' if change >= 0 else ''}{change:.2f}%",
                "RSI": round(rsi_val, 1),
                "RVOL": f"{rvol:.2f}x" if rvol > 0 else "-",
                "Volum": f"{vol:,.0f}",
                "Fokus": fokus,
            })
            if is_up:
                alerts.append(f"• *{t}* | RM {price:.2f} | RSI {rsi_val:.1f} | {fokus}")

        st.session_state.scan_results = rows
        st.session_state.raw_tickers = [r["Kaunter"] for r in rows]
        st.session_state.heatmap_rows = heatmap_rows

        if alerts and telegram_token and telegram_chat_id:
            send_telegram_message(telegram_token, telegram_chat_id, "🚨 *MYX SCREENER ALERT*\n" + "\n".join(alerts))

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
           
