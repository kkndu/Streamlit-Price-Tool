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

# --- 🎯 調整視窗寬度與留白邊界的 CSS 腳本 ---
st.markdown(
    """
    <style>
    /* 1. 調整主要內容的寬度與內邊距 (核心區域) */
    .block-container {
        /* 修正 max-width: 550px; */
        max-width: 550px; 
        
        /* 減少邊距 */
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.1rem; 
        padding-right: 0.1rem;
    }
    
    /* 2. 減少 Streamlit 頂部和底部容器的間距 */
    .st-emotion-cache-18ni2gq, .st-emotion-cache-z5rd0u {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* 3. 調整頁面標題（讓標題更靠上） */
    .st-emotion-cache-1jm6hrf {
        margin-top: 0rem;
    }
    
    /* 4. 讓按鈕的文字更清晰 */
    .stButton>button {
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 🔹 輔助函數：將大數字格式化為 K 或 M 縮寫
def format_large_number(num):
    """將大數字格式化為帶有 K/M 縮寫的字串，保留一位小數。"""
    if num >= 1_000_000:
        return f"{num / 1_000_000:,.1f} M"
    elif num >= 1_000:
        return f"{num / 1_000:,.1f} K"
    else:
        return f"{num:,.2f}"

# 🔹 抓台灣銀行美元即期賣出匯率
@st.cache_data(ttl=3600)
def get_tw_bank_usd_rate():
    """抓取台灣銀行美元即期賣出匯率。"""
    try:
        url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
        res = requests.get(url, timeout=10)
        res.raise_for_status() 
        
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table.table tbody tr")
        
        for row in rows:
            if "美元" in row.text:
                rate_text = row.select("td")[4].text.strip()
                return float(rate_text)
        return None
    except Exception as e:
        st.error(f"無法取得台銀匯率，請檢查網路或手動輸入。錯誤: {e}")
        return None

# 🔹 計算表格
def calculate_price_table(cost, currency, rate, quantity):
    """根據成本、幣別、匯率和數量計算定價表及總利潤。"""
    
    cost_twd = cost if currency == "TWD" else cost * rate

    rates = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5]
    data = []

    for r in rates:
        # 單個商品售價 (以利潤率計算，採購較常用此法確保最低利潤)
        selling_price = cost_twd / (1 - r) 
        
        data.append({
            "利潤比例_float": r,
            "利潤比例": f"{int(r*100)}%",
            "利潤率售價 (TWD)": round(selling_price, 2),
            "單個利潤 (TWD)": round(selling_price - cost_twd, 2),
            "總利潤 (TWD)": round((selling_price - cost_twd) * quantity, 2)
        })

    return pd.DataFrame(data), cost_twd

# --- 💻 Streamlit 介面配置 ---

st.title("🛒 採購決策與定價評估")
st.markdown("---")

# 1. 元件區塊：輸入
col1, col2, col3, col4 = st.columns([1, 1, 1, 1]) 

with col1:
    cost = st.number_input('單個成本:', min_value=0.0, value=1.3, step=0.1, format="%.2f", key='cost_input')

with col2:
    currency = st.selectbox('幣別:', options=['美金 USD', '台幣 TWD'], index=0, key='currency_input')
    currency_code = currency.split(' ')[1]

with col3:
    if 'usd_rate' not in st.session_state:
        st.session_state.usd_rate = 32.0

    rate = st.number_input(f'{currency_code}→TWD:', value=st.session_state.usd_rate, step=0.01, format="%.4f", disabled=(currency_code == 'TWD'), key='rate_input')
    
with col4:
    quantity = st.number_input('下單數量:', min_value=1, value=100, step=1, key='quantity_input')

st.markdown("---")

# 2. 更新匯率按鈕
if st.button('更新台銀匯率', type="primary", use_container_width=True):
    st.cache_data.clear()
    
    new_rate = get_tw_bank_usd_rate()
    if new_rate:
        st.session_state.usd_rate = new_rate
        st.rerun() 

# 3. 顯示結果和總計 (所有邏輯都包在 if 判斷內，避免 NameError)
if cost > 0:
    df_result, cost_twd = calculate_price_table(cost, currency_code, rate, quantity)
    total_cost = cost_twd * quantity 

    st.subheader("📊 總成本與預期利潤分析 (單位: NTD)")
    
    # 調整欄位比例：[選擇器, 單位成本, 總採購, 預期利潤]
    col_selector, col_kpi_1, col_kpi_2, col_kpi_3 = st.columns([0.8, 1, 1.2, 1.2]) 
    
    with col_selector:
        # 讓使用者從表格中已有的利潤比例中選擇一個作為基準
        profit_ratio_option = [f"{int(r*100)}%" for r in [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5]]
        
        # 預設選擇 20%
        selected_ratio_str = st.selectbox(
            '基準:',
            options=profit_ratio_option,
            index=2, # 20% 是第三個選項 (索引 2)
            key='profit_ratio_selector'
        )
        
        selected_ratio_float = float(selected_ratio_str.strip('%')) / 100
        # 確保在 df_result 中找到對應的行，如果找不到則使用 .iloc[0] (防止空 DataFrame 錯誤)
        row_selected = df_result[df_result['利潤比例_float'] == selected_ratio_float].iloc[0]

        profit_selected = row_selected['總利潤 (TWD)']
        
    # --- 關鍵績效指標 (KPI) 顯示區 ---
    
    with col_kpi_1:
        st.metric(label="單位成本", value=f"{cost_twd:,.2f}") # 移除 NTD
    
    with col_kpi_2:
        st.metric(label=f"總採購 ({quantity}個)", value=f"{format_large_number(total_cost)}") # 移除 NTD
        
    with col_kpi_3:
        st.metric(
            label="預期利潤", 
            value=f"{format_large_number(profit_selected)}",
            delta=f"@{selected_ratio_str}利潤率"
        )
        
    st.markdown("---")
    
    st.header("🛒 定價與利潤分析表")
    
    # 在顯示表格前移除輔助欄位
    df_display = df_result.drop(columns=['利潤比例_float'])
    st.dataframe(df_display, use_container_width=True)
else:
    st.warning("請輸入有效的單個成本金額。")
