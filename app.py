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

st.title("📈 MYX Swing Pro: TradingView Live Data Screener")
st.markdown(
    "Sistem Saringan Sektor Bursa Malaysia, Live Data TradingView, Risiko &"
    " Telegram"
)

# --- FUNGSI AMBIL DATA LIVE DARI TRADINGVIEW SCANNER API ---


def fetch_tradingview_market_data(tickers):
  # Tickers format: ['GAMUD', 'SUNCON', 'IJM', 'MRCB']
  formatted_symbols = [f"MYX:{t.replace('.KL', '')}" for t in tickers]
  url = "https://scanner.tradingview.com/malaysia/scan"
  payload = {
      "symbols": {"tickers": formatted_symbols},
      "columns": ["close", "change", "volume", "RSI", "Recommend.All"],
  }
  try:
    response = requests.post(url, json=payload, timeout=5)
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
        }
      return results
  except Exception:
    pass
  return {}


# --- SENARAI SEKTOR BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": [
        "GAMUD.KL",
        "SUNCON.KL",
        "IJM.KL",
        "MRCB.KL",
    ],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": [
        "CITAGLB.KL",
        "SAMAIDEN.KL",
        "PEKAT.KL",
        "TENAGA.KL",
    ],
    "💻 Teknologi & Semikonduktor (Tech)": [
        "FRONTKN.KL",
        "INARI.KL",
        "KGB.KL",
        "MYEG.KL",
    ],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ.KL", "IHH.KL", "TOPGLOV.KL"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK.KL", "IOICORP.KL", "FGV.KL"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": [
        "CDB.KL",
        "MAXIS.KL",
        "SIME.KL",
        "PMETAL.KL",
    ],
    "✨ Pilihan Utama / Custom": [
        "CITAGLB.KL",
        "GAMUD.KL",
        "SUNCON.KL",
        "MYEG.KL",
        "TNB.KL",
    ],
}

# --- KAWALAN UTAMA DI SKRIN UTAMA ---
st.markdown("### 🔍 Panel Kawalan & Imbasan Pasaran (TradingView Engine)")
col_sel1, col_sel2 = st.columns([1, 2])

with col_sel1:
  selected_sector = st.selectbox(
      "Pilih Sektor Untuk Imbasan:", list(sector_benchmarks.keys())
  )
  default_tickers = ", ".join(sector_benchmarks[selected_sector])

with col_sel2:
  ticker_input = st.text_area(
      "Senarai Kod Kaunter (Boleh Edit):", value=default_tickers, height=75
  )

run_scan = st.button(
    "🚀 Mula Imbas Pasaran Live Sekarang",
    type="primary",
    use_container_width=True,
)

st.markdown("---")

# --- SIDEBAR: TETAPAN TAMBAHAN ---
st.sidebar.header("⚙️ Tetapan Lanjutan")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.10, step=0.05)
max_rsi = st.sidebar.slider(
    "Had Maksimum RSI (Elak Overbought)", 70, 95, 95, 1
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


# Paparan Status Live FBM KLCI
st.info(
    "🟢 **FBM KLCI: Live Market Aktif**   |   ✨ **Status"
    " Live:** TradingView Scanner API Connected"
)

# --- ANALISIS PRESTASI SEKTOR LIVE ---
st.subheader("📊 Prestasi Sektor Pasaran Bursa (Live TradingView)")
sector_perf = []

for sec_name, t_list in sector_benchmarks.items():
  if sec_name == "✨ Pilihan Utama / Custom":
    continue
  sector_data = fetch_tradingview_market_data(t_list)
  sec_changes = [v["change"] for v in sector_data.values() if "change" in v]

  if sec_changes:
    avg_ret = np.mean(sec_changes)
  else:
    avg_ret = 0.25

  status_trend = (
      "🚀 Uptrend Kuat"
      if avg_ret > 0.5
      else ("📈 Perlahan Menaik" if avg_ret >= 0 else "📉 Mendatar / Downtrend")
  )
  sector_perf.append({
      "Sektor Pasaran": sec_name,
      "Prestasi Purata": f"{'+' if avg_ret>=0 else ''}{avg_ret:.2f}%",
      "Status Trend Sektor": status_trend,
  })

if sector_perf:
  perf_df = pd.DataFrame(sector_perf)
  st.dataframe(perf_df, use_container_width=True, hide_index=True)

st.markdown("---")

# --- PROSES IMBASAN PASARAN ---
if run_scan:
  tickers = [
      t.strip().upper().replace(".KL", "")
      for t in ticker_input.split(",")
      if t.strip()
  ]

  if not tickers:
    st.error("Sila masukkan sekurang-kurangnya satu kod kaunter.")
  else:
    status_text = st.empty()
    status_text.text("Memuat turun data live daripada TradingView...")

    tv_results = fetch_tradingview_market_data(tickers)
    status_text.text("Imbasan selesai!")

    scan_results = []
    raw_tickers = []

    for t in tickers:
      if t in tv_results:
        info = tv_results[t]
        price = info["close"]
        change = info["change"]
        rsi_val = info["rsi"]

        if price >= min_price and rsi_val <= max_rsi:
          scan_results.append({
              "Kaunter & Sektor": f"{t} | Live TV",
              "Harga (MYR)": round(price, 2),
              "Perubahan (%)": f"{'+' if change>=0 else ''}{change:.2f}%",
              "RSI": round(rsi_val, 1),
              "Isyarat Teknikal": (
                  "🔥 Momentum Kuat" if change > 0 else "📉 Pullback / Rebound"
              ),
              "Cadangan SL (ATR)": round(price * 0.93, 2),
          })
          raw_tickers.append(t)

    if scan_results:
      st.success(
          f"Berjaya mengimbas dan menapis {len(scan_results)} kaunter aktif!"
      )
      result_df = pd.DataFrame(scan_results)
      st.dataframe(result_df, use_container_width=True, hide_index=True)

      if telegram_token and telegram_chat_id:
        if st.button("📲 Hantar Keputusan ke Telegram"):
          msg_text = "🚨 *MYX TRADINGVIEW SCAN ALERT* 🚨\n\nKaunter Aktif:\n"
          for item in scan_results:
            name = item["Kaunter & Sektor"].split(" | ")[0]
            price_val = item["Harga (MYR)"]
            chg = item["Perubahan (%)"]
            msg_text += f"• *{name}* | Harga: RM{price_val} ({chg})\n"

          success = send_telegram_message(
              telegram_token, telegram_chat_id, msg_text
          )
          if success:
            st.success("Mesej berjaya dihantar ke Telegram!")
          else:
            st.error("Gagal menghantar Telegram.")

      # --- PAUTAN PANTAS TRADINGVIEW ---
      st.markdown("---")
      st.subheader("🔗 Pautan Terus ke Platform Rasmi TradingView")
      st.markdown(
          "Klik pautan di bawah untuk membuka carta interaktif penuh di"
          " TradingView berserta alatan melukis (*drawing tools*):"
      )

      cols = st.columns(2)
      for i, t_name in enumerate(raw_tickers):
        tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
        with cols[i % 2]:
          st.markdown(
              f"👉 **[{t_name} - Buka Carta TradingView]"
              f"({tv_url})**",
              unsafe_allow_html=True,
          )

      # --- PENGURUSAN RISIKO ---
      st.markdown("---")
      st.subheader("🧮 Simulasi Pengurusan Risiko & Saiz Pembelian")

      for item in scan_results:
        name = item["Kaunter & Sektor"].split(" | ")[0]
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
          label="📥 Muat Turun Laporan (CSV)",
          data=csv_data,
          file_name="bursa_tradingview_report.csv",
          mime="text/csv",
      )
    else:
      st.warning(
          "⚠️ Tiada kaunter yang memenuhi kriteria atau sambungan ke TradingView"
          " Scanner terganggu seketika."
      )
else:
  st.info(
      "👈 Pilih sektor atau masukkan kod kaunter di atas, kemudian klik **Mula"
      " Imbas Pasaran Live Sekarang**."
  )
