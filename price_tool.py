import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- ⚙️ 頁面設定 ---
st.set_page_config(
    page_title="採購決策與定價工具",
    page_icon="💰",
    layout="centered"
)

# --- 🎯 CSS ---
st.markdown(
    """
    <style>
    .block-container {
        max-width: 550px;
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.1rem;
        padding-right: 0.1rem;
    }
    .stButton>button {
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 🔹 輔助函數 ---
def format_large_number(num):
    if num >= 1_000_000:
        return f"{num / 1_000_000:,.3f} M"
    elif num >= 1_000:
        return f"{num / 1_000:,.3f} K"
    else:
        return f"{num:,.3f}"

# --- 🔹 抓台銀匯率 ---
@st.cache_data(ttl=3600)
def get_tw_bank_usd_rate():
    try:
        url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table.table tbody tr")
        for row in rows:
            if "美元" in row.text:
                return float(row.select("td")[4].text.strip())
        return None
    except Exception:
        return None

# --- 🔹 計算表 ---
def calculate_price_table(cost, currency, rate, quantity):
    cost_twd = cost if currency == "TWD" else cost * rate
    rates = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5]
    data = []

    for r in rates:
        selling_price = cost_twd / (1 - r)
        data.append({
            "利潤比例_float": r,
            "利潤比例": f"{int(r*100)}%",
            "利潤率售價 (TWD)": round(selling_price, 3),
            "單個利潤 (TWD)": round(selling_price - cost_twd, 3),
            "總利潤 (TWD)": round((selling_price - cost_twd) * quantity, 3)
        })

    return pd.DataFrame(data), cost_twd

# ===================== UI =====================

st.title("🛒 採購決策與定價評估")
st.markdown("---")

# --- 輸入區 ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    cost = st.number_input(
        "單個成本",
        min_value=0.0,
        value=1.3,
        step=0.001,
        format="%.3f"
    )

with col2:
    currency = st.selectbox("幣別", ["USD", "TWD"])
    
with col3:
    if "usd_rate" not in st.session_state:
        st.session_state.usd_rate = 32.0

    rate = st.number_input(
        "USD → TWD",
        value=st.session_state.usd_rate,
        step=0.0001,
        format="%.4f",
        disabled=(currency == "TWD")
    )

with col4:
    quantity = st.number_input("下單數量", min_value=1, value=100, step=1)

st.markdown("---")

# --- 匯率更新 ---
if st.button("更新台銀匯率", use_container_width=True):
    st.cache_data.clear()
    new_rate = get_tw_bank_usd_rate()
    if new_rate:
        st.session_state.usd_rate = new_rate
        st.rerun()

# ===================== 計算 =====================
if cost > 0:
    df_result, cost_twd = calculate_price_table(cost, currency, rate, quantity)

    # --- 🎯 利潤 Slider ---
    st.subheader("🎯 定價決策")
    profit_ratio = st.slider(
        "目標利潤率 (%)",
        min_value=0.0,
        max_value=50.0,
        value=20.0,
        step=0.1
    )
    profit_ratio_float = profit_ratio / 100

    selling_price = cost_twd / (1 - profit_ratio_float)
    unit_profit = selling_price - cost_twd
    total_profit = unit_profit * quantity
    total_cost = cost_twd * quantity

    st.markdown("---")

    # --- KPI ---
    col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)

    with col_kpi_1:
        st.metric("單位成本 (TWD)", f"{cost_twd:,.3f}")

    with col_kpi_2:
        st.metric(
            "建議售價 (TWD)",
            f"{selling_price:,.3f}",
            delta=f"{profit_ratio:.1f}% 利潤率"
        )

    with col_kpi_3:
        st.metric(
            "總預期利潤",
            format_large_number(total_profit)
        )

    st.markdown("---")

    # --- 分析表 ---
    st.header("📊 利潤級距比較表")
    df_display = df_result.drop(columns=["利潤比例_float"])
    st.dataframe(df_display, use_container_width=True)

else:
    st.warning("請輸入有效的成本金額")
