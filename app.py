import streamlit as st
import pandas as pd
import numpy as np
import requests
import base64
import io
from PIL import Image
from openai import OpenAI

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Screener, AI Vision (OpenAI) & Pautan Rasmi")
st.markdown("Sistem Imbasan Automatik BOB/BOD, AI Chart Inspector (OpenAI GPT-4 Vision) & Rujukan Pantas")

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
for t_list in sector_benchmarks.values():
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(set(master_bursa_tickers))

# --- FUNGSI AMBIL LIVE DATA DARI TRADINGVIEW SCANNER API ---
def fetch_tradingview_scanner(tickers):
    formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "symbols": {"tickers": formatted_symbols},
        "columns": ["close", "change", "volume", "RSI"]
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
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0
                }
            return results
    except Exception:
        pass
    return {}

# --- SIDEBAR TETAPAN & KALKULATOR POSISI ---
st.sidebar.header("⚙️ Kriteria Tapisan")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -3.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🤖 OpenAI API Tetapan")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", placeholder="sk-...")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Telegram Bot Alert")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

# --- KALKULATOR SAIZ POSISI & RISIKO ---
st.sidebar.markdown("---")
st.sidebar.header("🧮 Kalkulator Saiz Posisi & Risiko")
calc_capital = st.sidebar.number_input("Jumlah Modal (RM):", value=10000.0, step=500.0)
calc_risk_pct = st.sidebar.slider("Risiko Maksimum (% dari Modal):", 1.0, 5.0, 2.0, 0.5)
calc_entry = st.sidebar.number_input("Harga Beli (Entry) (RM):", value=1.00, step=0.01)
calc_sl = st.sidebar.number_input("Harga Stop-Loss (SL) (RM):", value=0.92, step=0.01)
calc_tp = st.sidebar.number_input("Harga Target (TP) (RM):", value=1.20, step=0.01)

if calc_entry > 0 and calc_sl > 0 and calc_entry > calc_sl:
    max_risk_rm = calc_capital * (calc_risk_pct / 100.0)
    risk_per_share = calc_entry - calc_sl
    raw_shares = max_risk_rm / risk_per_share
    suggested_shares = max(100, int(raw_shares // 100) * 100)
    total_investment = suggested_shares * calc_entry
    actual_risk_rm = suggested_shares * risk_per_share
    potential_profit = suggested_shares * (calc_tp - calc_entry) if calc_tp > calc_entry else 0
    risk_reward_ratio = (calc_tp - calc_entry) / risk_per_share if risk_per_share > 0 else 0
    
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; font-size: 13px;">
        <p style="color: #58a6ff; margin:0 0 5px 0; font-weight:bold;">📊 Keputusan Pengiraan (Lot Bursa):</p>
        <p style="margin:2px 0;">📦 <b>Jumlah Unit Saham:</b> {suggested_shares:,} unit ({suggested_shares//100} Lot)</p>
        <p style="margin:2px 0;">💰 <b>Jumlah Modal Diguna:</b> RM {total_investment:,.2f}</p>
        <p style="color: #f85149; margin:2px 0;">⚠️ <b>Risiko Sebenar:</b> RM {actual_risk_rm:,.2f}</p>
        <p style="color: #3fb950; margin:2px 0;">🎯 <b>Potensi Untung (TP):</b> RM {potential_profit:,.2f}</p>
        <p style="color: #e3b341; margin:2px 0;">⚖️ <b>Nisbah R:R:</b> 1 : {risk_reward_ratio:.2f}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.warning("Sila pastikan Harga Entry lebih tinggi daripada Harga Stop-Loss.")

def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

# --- FUNGSI ANALISIS OPENAI VISION ---
def analyze_chart_with_openai(api_key, image, trend, price):
    try:
        client = OpenAI(api_key=api_key)
        
        # Tukar imej kepada mod RGB (mengelakkan ralat RGBA transparent to JPEG)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        prompt = (
            f"Anda adalah seorang penganalisis teknikal saham profesional khusus untuk pasaran Bursa Malaysia (strategi Swing Trading, BOB, BOD). "
            f"Pengguna menetapkan status trend semasa sebagai '{trend}' dengan anggaran harga semasa pada carta sekitar RM {price}. "
            f"Sila teliti imej carta yang diberikan dan berikan laporan analisis yang padu dan profesional merangkumi:\n"
            f"1. Penilaian struktur harga & volum semasa.\n"
            f"2. Cadangan zon Sokongan Kuat (Stop-Loss).\n"
            f"3. Sokongan & Rintangan Terdekat.\n"
            f"4. Target Price (TP).\n"
            f"5. Cadangan taktikal kemasukan posisi (*entry strategy*)."
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ralat menyambung ke OpenAI API: {str(e)}"

# --- SESSION STATE INITIALIZATION ---
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []

# --- NAVIGASI MOD UTAMA ---
app_mode = st.radio(
    "Pilih Mod Utama Sistem:", 
    [
        "🔍 Screener & Prestasi Sektor", 
        "📸 AI Chart Vision (OpenAI) & Analisis Terperinci", 
        "🔗 Pautan Pantas Data Rasmi (Bursa & KLSE)"
    ], 
    horizontal=True
)
st.markdown("---")

if app_mode == "🔗 Pautan Pantas Data Rasmi (Bursa & KLSE)":
    st.subheader("🔗 Rujukan Pantas Data Rasmi Pasaran")
    st.markdown("Klik pautan di bawah untuk terus merujuk data sahih di platform rasmi Bursa Malaysia dan KLSE Screener.")
    
    st.markdown("""
    <div style="background-color: #161b22; padding: 25px; border-radius: 10px; border: 1px solid #30363d;">
        <h3 style="color: #58a6ff; margin-top:0;">📌 Pautan Rasmi Pasaran Saham</h3>
        <p>Pilih platform rujukan di bawah:</p>
        <ul>
            <li>👉 <a href="https://www.bursamalaysia.com/" target="_blank"><b>Bursa Malaysia Official Portal</b></a></li>
            <li>👉 <a href="https://www.klsescreener.com/" target="_blank"><b>KLSE Screener Portal</b></a></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

elif app_mode == "📸 AI Chart Vision (OpenAI) & Analisis Terperinci":
    st.subheader("📸 Modul Analisis Visual Imej Carta Berkuasa OpenAI GPT-4 Vision")
    st.markdown("Muat naik *screenshot* carta TradingView anda. Masukkan **OpenAI API Key** di *sidebar* sebelah kiri untuk membolehkan AI membaca dan menganalisis carta anda secara langsung.")
    
    uploaded_chart = st.file_uploader("Pilih fail imej carta (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])
    
    if uploaded_chart is not None:
        col_img1, col_img2 = st.columns([1, 1])
        with col_img1:
            image = Image.open(uploaded_chart)
            st.image(image, caption="Carta Dimuat Naik", use_column_width=True)
            
        with col_img2:
            st.markdown("### 🤖 Tetapan Analisis AI:")
            selected_trend = st.selectbox(
                "📈 Tentukan Jangkaan Trend Asas:",
                ["🚀 Uptrend (Fasa Kenaikan Kuat)", "📉 Downtrend (Fasa Penurunan)", "⚖️ Sideway (Konsolidasi Tapak)"]
            )
            est_current_price = st.number_input("Masukkan Harga Semasa (RM) pada Carta:", value=0.95, step=0.01)
            
            run_ai_analysis = st.button("✨ Jalankan Analisis OpenAI Vision", type="primary", use_container_width=True)
            
            if run_ai_analysis:
                if not openai_api_key:
                    st.error("⚠️ Sila masukkan **OpenAI API Key** anda di ruangan *sidebar* sebelah kiri terlebih dahulu!")
                else:
                    with st.spinner("🤖 OpenAI sedang meneliti struktur carta dan menjana ulasan taktikal..."):
                        ai_report = analyze_chart_with_openai(openai_api_key, image, selected_trend, est_current_price)
                        
                    st.markdown(f"""
                    <div style="background-color: #161b22; padding: 22px; border-radius: 10px; border: 1px solid #30363d; margin-top: 15px;">
                        <h4 style="color: #58a6ff; margin-top:0;">📊 Laporan Rasmi OpenAI Vision AI</h4>
                        <hr style="border-color: #30363d;">
                        <div style="color: #c9d1d9; line-height: 1.6;">
                            {ai_report.replace(chr(10), '<br>')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

else:
    # --- MOD SCREENER & SEKTOR ---
    scan_mode = st.radio("Pilih Mod Imbasan:", ["🤖 Imbas Automatik Seluruh Pasaran", "📂 Imbas Mengikut Sektor / Manual Kaunter"], horizontal=True)

    if scan_mode == "📂 Imbas Mengikut Sektor / Manual Kaunter":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            sel_sector = st.selectbox("Pilih Sektor:", list(sector_benchmarks.keys()))
            default_t = ", ".join(sector_benchmarks[sel_sector])
        with col_m2:
            custom_input = st.text_area("Atau Edit Kod Kaunter (Koma):", value=default_t, height=75)
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
                
                if price >= min_price and rsi_val <= max_rsi and change >= min_change_pct:
                    entry_price = round(price, 2)
                    if change >= 2.0 and vol > 500000:
                        signal = "🔥 BOB (Breakout)"
                    elif change >= -1.5 and change < 2.0 and vol > 300000:
                        signal = "🔄 BOD (Dip/Reversal)"
                    elif change > 0:
                        signal = "📈 Momentum"
                    else:
                        signal = "📉 Tapak / Pullback"
                    
                    item_data = {
                        "Kaunter": t,
                        "Harga (RM)": entry_price,
                        "Perubahan": f"{'+' if change>=0 else ''}{change:.2f}%",
                        "RSI": round(rsi_val, 1),
                        "Setup Strategi": signal,
                        "Volum": f"{vol:,.0f}"
                    }
                    scan_results.append(item_data)
                    raw_tickers.append(t)
                    
                    if "BOB" in signal or "BOD" in signal:
                        alert_messages.append(f"• *{t}* | Harga: RM {entry_price} | Setup: {signal} | Vol: {vol:,.0f}")
                    
        st.session_state.scan_results = scan_results
        st.session_state.raw_tickers = raw_tickers
        
        if alert_messages and telegram_token and telegram_chat_id:
            full_msg = f"🚨 *MYX SWING ENTRY ALERT* 🚨\nSistem mengesan kaunter berpotensi tinggi:\n" + "\n".join(alert_messages)
            success = send_telegram_message(telegram_token, telegram_chat_id, full_msg)
            if success:
                st.toast("✅ Setup entry alert berjaya dihantar ke Telegram anda!", icon="🚀")

    # --- PAPAN PENDAHUDU SEKTOR ---
    st.subheader("📊 Prestasi Sektor Semasa (Sector Leadership)")
    sector_perf = []
    for sec_name, t_list in sector_benchmarks.items():
        sec_data = fetch_tradingview_scanner(t_list)
        sec_changes = [v["change"] for v in sec_data.values() if "change" in v]
        avg_ret = np.mean(sec_changes) if sec_changes else 0.0
        status_trend = "🔥 Sektor Leader" if avg_ret > 0.5 else ("📈 Positif" if avg_ret >= 0 else "📉 Lemah / Pullback")
        sector_perf.append({
            "Sektor Pasaran": sec_name,
            "Avg Ret": avg_ret,
            "Prestasi (%)": f"{'+' if avg_ret>=0
