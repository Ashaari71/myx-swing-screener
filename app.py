import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide"
)

st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title(
    "📈 MYX Swing Pro: Sector Rotation & Automated BOB/BOD Screener"
)
st.markdown(
    "Sistem Pemantauan Sektor Live & Imbasan Automatik Seluruh Pasaran Bursa"
    " Malaysia"
)

# --- SENARAI MASTER SEKTOR & KAUNTER BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": [
        "GAMUD",
        "SUNCON",
        "IJM",
        "MRCB",
        "WCT",
        "KERJAYA",
    ],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": [
        "CITAGLB",
        "SAMAIDEN",
        "PEKAT",
        "TENAGA",
        "YTLPOWR",
        "SOLARVEST",
    ],
    "💻 Teknologi & Semikonduktor (Tech)": [
        "FRONTKN",
        "INARI",
        "KGB",
        "MYEG",
        "UNISEM",
        "GTRONIC",
        "VITROX",
    ],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": [
        "KLK",
        "IOICORP",
        "FGV",
        "SIMEPROP",
    ],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": [
        "CDB",
        "MAXIS",
        "SIME",
        "PMETAL",
        "ANCOMNY",
        "WASCO",
    ],
}

# Gabungkan semua kaunter untuk master screener automatik
master_bursa_tickers = []
for t_list in sector_benchmarks.values():
  master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(
    set(master_bursa_tickers)
)  # Buang duplikasi jika ada

# --- FUNGSI AMBIL LIVE DATA DARI TRADINGVIEW SCANNER API ---


def fetch_tradingview_scanner(tickers):
  formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
  url = "https://scanner.tradingview.com/malaysia/scan"
  payload = {
      "symbols": {"tickers": formatted_symbols},
      "columns": ["close", "change", "volume", "RSI", "recommend.all"],
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
            "rsi": (
                vals[3] if len(vals) > 3 and vals[3] is not None else 50.0
            ),
        }
      return results
  except Exception:
    pass
  return {}


# --- SIDEBAR: TETAPAN LANJUTAN & PENAPIS ---
st.sidebar.header("⚙️ Kriteria Tapisan (Screener Filters)")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.15, step=0.05)
max_rsi = st.sidebar.slider(
    "Had Maksimum RSI (Elak Overbought)", 70, 95, 80, 1
)
min_change_pct = st.sidebar.slider(
    "Perubahan Harga Harian Minimum (%)", -2.0, 5.0, 0.0, 0.5
)

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 Kalkulator Risiko & Modal")
total_capital = st.sidebar.number_input(
    "Jumlah Modal Dagangan (RM)", value=10000.0, step=1000.0
)
risk_per_trade_pct = st.sidebar.slider(
    "Risiko Yang Dibenarkan (%)", 0.5, 3.0, 1.0, 0.5
)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Tetapan Telegram Bot")
telegram_token = st.sidebar.text_input(
    "Telegram Bot Token", type="password", placeholder="Masukkan token bot..."
)
telegram_chat_id = st.sidebar.text_input(
    "Telegram Chat ID", placeholder="Masukkan chat ID..."
)


def send_telegram_message(token, chat_id, message):
  try:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    response = requests.post(url, json=payload)
    return response.status_code == 200
  except Exception:
    return False


st.info(
    "🟢 **FBM KLCI: Live Market Aktif**   |   ✨ **Status"
    " Live:** Sektor Rotation & Screener Aktif"
)

# --- 1. PAPAN PENDAHUDU SEKTOR (SECTOR ROTATION LIVE) ---
st.subheader(
    "📊 Prestasi Sektor Semasa (Sector Leadership - Tersusun Ikut Kekuatan"
    " Live)"
)
sector_perf = []

for sec_name, t_list in sector_benchmarks.items():
  sec_data = fetch_tradingview_scanner(t_list)
  sec_changes = [v["change"] for v in sec_data.values() if "change" in v]

  if sec_changes:
    avg_ret = np.mean(sec_changes)
  else:
    avg_ret = 0.0

  if avg_ret > 0.5:
    status_trend = "🔥 Sektor Leader (Uptrend Kuat)"
  elif avg_ret >= 0:
    status_trend = "📈 Positif Perlahan"
  elif avg_ret >= -1.0:
    status_trend = "📉 Pullback Sihat"
  else:
    status_trend = "⚠️ Lemah / Tekanan Jualan"

  sector_perf.append({
      "Sektor Pasaran": sec_name,
      "Prestasi Purata": avg_ret,
      "Prestasi (%)": f"{'+' if avg_ret>=0 else ''}{avg_ret:.2f}%",
      "Status Trend Sektor": status_trend,
  })

if sector_perf:
  perf_df = pd.DataFrame(sector_perf)
  perf_df = perf_df.sort_values(by="Prestasi Purata", ascending=False)
  display_df = perf_df[["Sektor Pasaran", "Prestasi (%)", "Status Trend Sektor"]]
  st.dataframe(display_df, use_container_width=True, hide_index=True)

st.markdown("---")

# --- 2. PANEL KAWALAN IMBSAN AUTOMATIK SELURUH PASARAN ---
st.markdown("### 🔍 Panel Imbasan Automatik Seluruh Pasaran Bursa")
st.markdown(
    "Sistem akan mengimbas kesemua kaunter di atas secara serentak untuk"
    " mencari setup **BOB / BOD** dan momentum positif."
)

run_scan = st.button(
    "🚀 Mulakan Imbasan Automatik Seluruh Pasaran Sekarang",
    type="primary",
    use_container_width=True,
)

if run_scan:
  status_text = st.empty()
  status_text.text(
      f"Sedang mengimbas {len(master_bursa_tickers)} kaunter utama Bursa"
      " Malaysia..."
  )

  tv_results = fetch_tradingview_scanner(master_bursa_tickers)
  status_text.text("Imbasan selesai!")

  scan_results = []
  raw_tickers = []

  for t in master_bursa_tickers:
    if t in tv_results:
      info = tv_results[t]
      price = info["close"]
      change = info["change"]
      rsi_val = info["rsi"]
      vol = info["volume"]

      if (
          price >= min_price
          and rsi_val <= max_rsi
          and change >= min_change_pct
      ):
        if change > 2.0 and rsi_val > 55:
          signal = "🔥 BOB (Breakout of Base) + Momentum"
        elif change > 0 and rsi_val <= 55:
          signal = "🔄 BOD (Breakout of Downtrend Setup)"
        elif change > 0:
          signal = "📈 Uptrend Sihat"
        else:
          signal = "📉 Pullback / Tapak Bertapak"

        scan_results.append({
            "Kaunter": f"{t}",
            "Harga (MYR)": round(price, 2),
            "Perubahan (%)": f"{'+' if change>=0 else ''}{change:.2f}%",
            "RSI": round(rsi_val, 1),
            "Volum": f"{vol:,.0f}",
            "Isyarat Teknikal": signal,
            "Cadangan SL (ATR)": round(price * 0.93, 2),
        })
        raw_tickers.append(t)

  if scan_results:
    st.success(
        f"🎉 Berjaya menemui **{len(scan_results)} kaunter** yang melepasi"
        " tapisan kriteria!"
    )
    result_df = pd.DataFrame(scan_results)
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    if telegram_token and telegram_chat_id:
      if st.button("📲 Hantar Keputusan Imbasan ke Telegram"):
        msg_text = "🚨 *MYX AUTOMATED SWING PRO ALERT* 🚨\n\nKaunter Lepas Tapisan:\n"
        for item in scan_results:
          name = item["Kaunter"]
          price_val = item["Harga (MYR)"]
          chg = item["Perubahan (%)"]
          sig = item["Isyarat Teknikal"]
          msg_text += (
              f"• *{name}* | Harga: RM{price_val} ({chg}) | {sig}\n"
          )

        success = send_telegram_message(
            telegram_token, telegram_chat_id, msg_text
        )
        if success:
          st.success("Mesej berjaya dihantar ke Telegram!")
        else:
          st.error("Gagal menghantar Telegram.")

    # --- PAUTAN PANTAS TRADINGVIEW ---
    st.markdown("---")
    st.subheader("🔗 Pautan Terus ke Carta Rasmi TradingView")
    st.markdown(
        "Klik pautan di bawah untuk melakukan analisis terperinci dan melukis"
        " garisan (*drawing tools*) pada kaunter yang dikesan:"
    )

    cols = st.columns(3)
    for i, t_name in enumerate(raw_tickers):
      tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
      with cols[i % 3]:
        st.markdown(
            f"👉 **[{t_name} - Buka Carta]"
            f"({tv_url})**",
            unsafe_allow_html=True,
        )

    # --- PENGURUSAN RISIKO ---
    st.markdown("---")
    st.subheader("🧮 Simulasi Pengurusan Risiko & Saiz Pembelian")

    for item in scan_results:
      name = item["Kaunter"]
      price = item["Harga (MYR)"]
      sl = item["Cadangan SL (ATR)"]

      risk_amount = total_capital * (risk_per_trade_pct / 100.0)
      risk_per_share = price - sl

      if risk_per_share > 0:
        shares_to_buy = int(risk_amount / risk_per_share)
        total_investment = shares_to_buy * price
      else:
        shares_to_buy = 0
        total_investment = 0

      col1, col2, col3, col4 = st.columns(4)
      col1.metric(label=f"📌 Kaunter: {name}", value=f"RM {price:.2f}")
      col2.metric(label="🛡️ Cadangan Stop-Loss", value=f"RM {sl:.2f}")
      col3.metric(label="📦 Unit Disyorkan", value=f"{shares_to_buy:,} unit")
      col4.metric(
          label="💰 Modal Digunakan", value=f"RM {total_investment:,.2f}"
      )
      st.markdown("---")

    csv_data = result_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Muat Turun Laporan Screener (CSV)",
        data=csv_data,
        file_name="bursa_automated_screener.csv",
        mime="text/csv",
    )
  else:
    st.warning(
        "⚠️ Tiada kaunter yang melepasi kriteria tapisan semasa. Cuba longgarkan"
        " sedikit tetapan RSI atau perubahan harga di sidebar."
    )
else:
  st.info(
      "👈 Rujuk jadual prestasi sektor di atas untuk kenal pasti sektor paling"
      " kuat, kemudian klik **Mulakan Imbasan Automatik Seluruh Pasaran"
      " Sekarang**."
  )
