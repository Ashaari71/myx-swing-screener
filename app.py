import streamlit as st
import pandas as pd
import numpy as np
import requests
import base64
import io
from PIL import Image
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Auto Scheduler, Screener, AI Vision & Watchlist")
st.markdown("Sistem Imbasan Automatik Berjadual, Penapis MACD/BB Squeeze, AI Chart Inspector & Multi-TP")

# --- MASTER SEKTOR & KAUNTER UTAMA BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUD", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"],
    "🏦 Perbankan & Kewangan (Banking/Finance)": ["MAYBANK", "CIMB", "PBBANK", "HLBANK", "RHBBANK", "AMBANK"]
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
        "columns": ["close", "change", "volume", "RSI", "MACD.macd", "MACD.signal", "BB.upper", "BB.lower"]
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
                results[sym] = {
                    "close": vals[0] if vals[0] is not None else 0.0,
                    "change": vals[1] if vals[1] is not None else 0.0,
                    "volume": vals[2] if vals[2] is not None else 0,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0,
                    "macd": vals[4] if len(vals) > 4 and vals[4] is not None else 0.0,
                    "macd_signal": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "bb_upper": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    "bb_lower": vals[7] if len(vals) > 7 and vals[7] is not None else 0.0,
                }
            return results
    except Exception:
        pass
    return {}

# --- FUNGSI IMBASAN LATAR BELAKANG (BACKGROUND SCHEDULER JOB) ---
def background_scan_job():
    try:
        tv_results = fetch_tradingview_scanner(master_bursa_tickers)
        alert_messages = []
        for t in master_bursa_tickers:
            if t in tv_results:
                info = tv_results[t]
                price = info["close"]
                change = info["change"]
                rsi_val = info["rsi"]
                vol = info["volume"]
                
                if price >= 0.50 and rsi_val <= 80 and change >= -3.0:
                    if change >= 2.0 and vol > 500000:
                        signal = "🔥 BOB (Breakout)"
                    elif change >= -1.5 and change < 2.0 and vol > 300000:
                        signal = "🔄 BOD (Dip/Reversal)"
                    else:
                        continue
                    sec_name = ticker_to_sector.get(t, "Lain-lain")
                    alert_messages.append(f"• *{t}* ({sec_name}) | RM {price:.2f} | {signal} | Vol: {vol:,.0f}")
        
        # Ambil token dari st.secrets (pastikan diset di Streamlit Cloud Secrets)
        token = st.secrets.get("TELEGRAM_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        if alert_messages and token and chat_id:
            full_msg = f"🚨 *MYX AUTOMATED SCHEDULED ALERT* 🚨\nSistem mengesan setup berpotensi tinggi:\n" + "\n".join(alert_messages)
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": full_msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Background job error: {e}")

# Mulakan Background Scheduler sekali sahaja menggunakan st.cache_resource
@st.cache_resource
def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kuala_Lumpur"))
    # Imbasan automatik setiap hari bekerja pada jam 9:00 pagi (Buka Pasaran) & 5:00 petang (Tutup Pasaran)
    scheduler.add_job(background_scan_job, 'cron', hour=9, minute=0, day_of_week='mon-fri')
    scheduler.add_job(background_scan_job, 'cron', hour=17, minute=0, day_of_week='mon-fri')
    scheduler.start()
    return scheduler

start_scheduler()

# --- SIDEBAR TETAPAN & PENAPIS LANJUTAN ---
st.sidebar.header("⚙️ Kriteria Tapisan Asas")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -3.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Penapisan Indikator Lanjutan")
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
calc_capital = st.sidebar.number_input("Jumlah Modal (RM):", value=10000.0, step=500.0)
calc_risk_pct = st.sidebar.slider("Risiko Maksimum (% dari Modal):", 1.0, 5.0, 2.0, 0.5)
calc_entry = st.sidebar.number_input("Harga Beli (Entry) (RM):", value=1.00, step=0.01)
calc_sl = st.sidebar.number_input("Harga Stop-Loss (SL) (RM):", value=0.92, step=0.01)
calc_tp1 = st.sidebar.number_input("Target 1 (TP1 - 50% Lot):", value=1.10, step=0.01)
calc_tp2 = st.sidebar.number_input("Target 2 (TP2 - 50% Lot):", value=1.25, step=0.01)

if calc_entry > 0 and calc_sl > 0 and calc_entry > calc_sl:
    max_risk_rm = calc_capital * (calc_risk_pct / 100.0)
    risk_per_share = calc_entry - calc_sl
    raw_shares = max_risk_rm / risk_per_share
    suggested_shares = max(100, int(raw_shares // 100) * 100)
    total_investment = suggested_shares * calc_entry
    actual_risk_rm = suggested_shares * risk_per_share
    
    half_shares = suggested_shares // 2
    profit_tp1 = half_shares * (calc_tp1 - calc_entry) if calc_tp1 > calc_entry else 0
    profit_tp2 = half_shares * (calc_tp2 - calc_entry) if calc_tp2 > calc_entry else 0
    rr_ratio = (calc_tp2 - calc_entry) / risk_per_share if risk_per_share > 0 else 0
    
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; font-size: 13px;">
        <p style="color: #58a6ff; margin:0 0 5px 0; font-weight:bold;">📊 Pengiraan Multi-TP (Lot Bursa):</p>
        <p style="margin:2px 0;">📦 <b>Jumlah Saham:</b> {suggested_shares:,} unit ({suggested_shares//100} Lot)</p>
        <p style="margin:2px 0;">💰 <b>Modal Diguna:</b> RM {total_investment:,.2f}</p>
        <p style="color: #f85149; margin:2px 0;">⚠️ <b>Risiko Maks:</b> RM {actual_risk_rm:,.2f}</p>
        <p style="color: #3fb950; margin:2px 0;">🎯 <b>Potensi TP1:</b> RM {profit_tp1:,.2f}</p>
        <p style="color: #3fb950; margin:2px 0;">🎯 <b>Potensi TP2:</b> RM {profit_tp2:,.2f}</p>
        <p style="color: #e3b341; margin:2px 0;">⚖️ <b>Nisbah R:R (TP2):</b> 1 : {rr_ratio:.2f}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.warning("Sila pastikan Harga Entry lebih tinggi daripada Stop-Loss.")

def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

# --- FUNGSI ANALISIS OPENAI VISION KHUSUS BOB & BOD ---
def analyze_chart_bob_bod(api_key, image, trend, price):
    try:
        client = OpenAI(api_key=api_key)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = (
            f"Anda adalah Ketua Penganalisis Teknikal Bursa Malaysia pakar strategi BOB & BOD. "
            f"Trend asas: '{trend}', Harga Semasa: RM {price}. "
            f"Sila beri laporan dalam Bahasa Melayu merangkumi:\n"
            f"1. Analisis Hala Tuju & Struktur Fasa.\n"
            f"2. Penilaian Potensi Setup (BOB vs BOD).\n"
            f"3. Zon Harga Kritikal (Stop-Loss, Sokongan, Rintangan, TP1 & TP2).\n"
            f"4. Cadangan Taktikal Watchlist."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }],
            max_tokens=800
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ralat OpenAI API: {str(e)}"

# --- SESSION STATE INITIALIZATION ---
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# --- NAVIGASI MOD UTAMA ---
app_mode = st.radio(
    "Pilih Mod Utama Sistem:", 
    [
        "🔍 Screener & Prestasi Sektor", 
        "📸 AI Chart Vision (BOB/BOD)", 
        "⭐ Watchlist Peribadi",
        "🔗 Pautan Rasmi Bursa"
    ], 
    horizontal=True
)
st.markdown("---")

if app_mode == "🔗 Pautan Rasmi Bursa":
    st.subheader("🔗 Rujukan Pantas Data Rasmi Pasaran")
    st.markdown("""
    <div style="background-color: #161b22; padding: 25px; border-radius: 10px; border: 1px solid #30363d;">
        <h3 style="color: #58a6ff; margin-top:0;">📌 Pautan Rasmi Pasaran Saham</h3>
        <ul>
            <li>👉 <a href="https://www.bursamalaysia.com/" target="_blank"><b>Bursa Malaysia Portal</b></a></li>
            <li>👉 <a href="https://www.klsescreener.com/" target="_blank"><b>KLSE Screener Portal</b></a></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

elif app_mode == "⭐ Watchlist Peribadi":
    st.subheader("⭐ Senarai Tontonan Peribadi (My Watchlist)")
    if st.session_state.watchlist:
        wl_df = pd.DataFrame(st.session_state.watchlist)
        st.dataframe(wl_df, use_container_width=True, hide_index=True)
        if st.button("🗑️ Kosongkan Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.info("Tiada kaunter dalam watchlist. Tambah kaunter daripada hasil imbasan screener di tab utama.")

elif app_mode == "📸 AI Chart Vision (BOB/BOD)":
    st.subheader("📸 Modul Analisis AI Khusus Teknik BOB & BOD")
    uploaded_chart = st.file_uploader("Pilih fail imej carta (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])
    
    if uploaded_chart is not None:
        col_img, col_settings = st.columns([1, 1])
        with col_img:
            image = Image.open(uploaded_chart)
            st.image(image, caption="Carta Dimuat Naik", use_column_width=True)
        with col_settings:
            st.markdown("### 🤖 Tetapan Penilaian AI:")
            selected_trend = st.selectbox("Hala Tuju Asas:", ["🚀 Uptrend", "📉 Downtrend", "⚖️ Sideway"])
            est_current_price = st.number_input("Harga Semasa (RM):", value=0.95, step=0.01)
            run_ai_analysis = st.button("✨ Analisis Setup BOB / BOD", type="primary", use_container_width=True)
            
        st.markdown("---")
        if run_ai_analysis:
            if not openai_api_key:
                st.error("⚠️ Sila masukkan OpenAI API Key di sidebar!")
            else:
                with st.spinner("🤖 OpenAI sedang menilai carta..."):
                    ai_report = analyze_chart_bob_bod(openai_api_key, image, selected_trend, est_current_price)
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 25px; border-radius: 10px; border: 1px solid #30363d; width: 100%;">
                    <h3 style="color: #58a6ff; margin-top:0;">📊 Laporan Analisis Taktikal AI</h3>
                    <hr style="border-color: #30363d;">
                    <div style="color: #c9d1d9; line-height: 1.7; font-size: 15px;">
                        {ai_report.replace(chr(10), '<br>')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

else:
    # --- MOD SCREENER & SEKTOR ---
    scan_mode = st.radio("Pilih Mod Imbasan:", ["🤖 Imbas Automatik Seluruh Pasaran", "📂 Imbas Mengikut Sektor"], horizontal=True)

    if scan_mode == "📂 Imbas Mengikut Sektor":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            sel_sector = st.selectbox("Pilih Sektor:", list(sector_benchmarks.keys()))
            default_t = ", ".join(sector_benchmarks[sel_sector])
        with col_m2:
            custom_input = st.text_area("Kod Kaunter:", value=default_t, height=75)
            target_tickers = [t.strip().upper().replace('.KL', '') for t in custom_input.split(",") if t.strip()]
    else:
        target_tickers = master_bursa_tickers

    run_scan = st.button("🚀 Mula Imbas Pasaran Sekarang", type="primary", use_container_width=True)
    st.markdown("---")

    if run_scan:
        tv_results = fetch_tradingview_scanner(target_tickers)
        scan_results = []
        raw_tickers = []
        alert_messages = []
        
        for t in target_tickers:
            if t in tv_results:
                info = tv_results[t]
                price = info["close"]
                change = info["change"]
                rsi_val = info["rsi"]
                vol = info["volume"]
                macd = info["macd"]
                macd_sig = info["macd_signal"]
                bb_up = info["bb_upper"]
                bb_low = info["bb_lower"]
                
                if price < min_price or rsi_val > max_rsi or change < min_change_pct:
                    continue
                
                if filter_macd and macd <= macd_sig:
                    continue
                
                if filter_bb_squeeze:
                    bb_width = (bb_up - bb_low) / price if price > 0 else 1.0
                    if bb_width > 0.08:
                        continue
                
                entry_price = round(price, 2)
                if change >= 2.0 and vol > 500000:
                    signal = "🔥 BOB (Breakout)"
                elif change >= -1.5 and change < 2.0 and vol > 300000:
                    signal = "🔄 BOD (Dip/Reversal)"
                elif change > 0:
                    signal = "📈 Momentum"
                else:
                    signal = "📉 Pullback"
                
                sec_name = ticker_to_sector.get(t, "Lain-lain")
                item_data = {
                    "Kaunter": t,
                    "Sektor": sec_name,
                    "Harga (RM)": entry_price,
                    "Perubahan": f"{'+' if change>=0 else ''}{change:.2f}%",
                    "RSI": round(rsi_val, 1),
                    "Setup": signal,
                    "Volum": f"{vol:,.0f}"
                }
                scan_results.append(item_data)
                raw_tickers.append(t)
                
                if "BOB" in signal or "BOD" in signal:
                    alert_messages.append(f"• *{t}* ({sec_name}) | RM {entry_price} | {signal} | Vol: {vol:,.0f}")
                    
        st.session_state.scan_results = scan_results
        st.session_state.raw_tickers = raw_tickers
        
        if alert_messages and telegram_token and telegram_chat_id:
            full_msg = f"🚨 *MYX SWING ENTRY ALERT* 🚨\nSistem mengesan kaunter berpotensi:\n" + "\n".join(alert_messages)
            send_telegram_message(telegram_token, telegram_chat_id, full_msg)

    # Prestasi Sektor
    st.subheader("📊 Prestasi Sektor Semasa")
    sector_perf = []
    for sec_name, t_list in sector_benchmarks.items():
        sec_data = fetch_tradingview_scanner(t_list)
        sec_changes = [v["change"] for v in sec_data.values() if "change" in v]
        avg_ret = np.mean(sec_changes) if sec_changes else 0.0
        status_trend = "🔥 Sektor Leader" if avg_ret > 0.5 else ("📈 Positif" if avg_ret >= 0 else "📉 Lemah")
        sector_perf.append({
            "Sektor Pasaran": sec_name,
            "Prestasi (%)": f"{'+' if avg_ret>=0 else ''}{avg_ret:.2f}%",
            "Status Trend": status_trend
        })
    if sector_perf:
        st.dataframe(pd.DataFrame(sector_perf), use_container_width=True, hide_index=True)

    st.markdown("---")

    if st.session_state.scan_results:
        st.success(f"Berjaya menemui **{len(st.session_state.scan_results)} kaunter** sepadan!")
        df_display = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("### ⭐ Simpan ke Watchlist Peribadi:")
        selected_to_wl = st.selectbox("Pilih kaunter untuk dimasukkan ke Watchlist:", st.session_state.raw_tickers)
        if st.button("➕ Tambah ke Watchlist"):
            match_item = next((item for item in st.session_state.scan_results if item["Kaunter"] == selected_to_wl), None)
            if match_item and match_item not in st.session_state.watchlist:
                st.session_state.watchlist.append(match_item)
                st.success(f"✅ {selected_to_wl} berjaya dimasukkan ke Watchlist!")
            else:
                st.warning("Kaunter sudah ada dalam Watchlist.")

        st.markdown("🔗 **Pautan Cepat Carta TradingView:**")
        cols_tv = st.columns(6)
        for i, t_name in enumerate(st.session_state.raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols_tv[i % 6]:
                st.markdown(f"👉 [{t_name}]({tv_url})", unsafe_allow_html=True)
                
        st.markdown("---")
        csv_data = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Muat Turun Laporan (CSV)", data=csv_data, file_name="myx_screener_report.csv", mime="text/csv")
    else:
        st.info("👈 Pilih penapis di sidebar dan klik **Mula Imbas Pasaran Sekarang** di atas untuk memaparkan senarai kaunter.")
