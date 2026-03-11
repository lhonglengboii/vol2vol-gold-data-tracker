import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
import re

st.set_page_config(layout="wide", page_title="Options Flow Tracker", page_icon="📈")

# --- Custom CSS ---
st.markdown("""
<style>
    /* ลดช่องว่างด้านบนสุดของหน้าเว็บ */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    .header-box { background-color: #1E1E1E; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; border: 1px solid #333; }
    .header-title { font-size: 20px; font-weight: bold; color: #E2E8F0; margin-bottom: 10px; }
    .header-metrics span { font-size: 16px; margin: 0 15px; font-weight: bold; }
    .t-put { color: #F59E0B; }
    .t-call { color: #3B82F6; }
    .t-vol { color: #EF4444; }
    .t-neutral { color: #A0AEC0; }
    
    /* ป้องกันการ Drag ลากข้อความใน Dropdown */
    div[data-baseweb="select"] {
        user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
    }
</style>
""", unsafe_allow_html=True)

REPO = "pageth/Vol2VolData"

# ฟังก์ชันตัวช่วยดึงราคา Underlying (ATM) จาก Header
def extract_atm(header_text):
    match = re.search(r'vs\s+([\d\.,]+)', str(header_text))
    if match:
        return float(match.group(1).replace(',', ''))
    return None

# ฟังก์ชันตัวช่วยสร้างกล่อง Header
def get_styled_header(h1_text, h2_text):
    h2_styled = h2_text.replace("Put:", "<span class='t-put'>Put:</span>")\
                       .replace("Call:", "<span class='t-call'>Call:</span>")\
                       .replace("Vol:", "<span class='t-vol'>Vol:</span>")\
                       .replace("Vol Chg:", "<span class='t-neutral'>Vol Chg:</span>")\
                       .replace("Future Chg:", "<span class='t-neutral'>Future Chg:</span>")
    return f"""
    <div class="header-box" style="margin-bottom: 5px;">
        <div class="header-title">{h1_text}</div>
        <div class="header-metrics">{h2_styled}</div>
    </div>
    """

# ฟังก์ชันดึงข้อมูล (ปรับ max_commits เป็น 1000)
@st.cache_data(ttl=300) 
def fetch_github_history(file_path, max_commits=1000):
    api_url = f"https://api.github.com/repos/{REPO}/commits?path={file_path}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
    except Exception: return pd.DataFrame()
    if response.status_code != 200: return pd.DataFrame()
        
    commits = response.json()
    if not commits: return pd.DataFrame()
        
    all_data = []
    today_date = pd.Timestamp.now(tz='Asia/Bangkok').date()
    
    for commit in commits[:max_commits]:
        sha = commit['sha']
        date_str = commit['commit']['author']['date'] 
        dt = pd.to_datetime(date_str).tz_convert('Asia/Bangkok') if pd.to_datetime(date_str).tzinfo else pd.to_datetime(date_str).tz_localize('UTC').tz_convert('Asia/Bangkok')
        
        if dt.date() != today_date: break
            
        time_label = dt.strftime("%H:%M:%S")
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{sha}/{file_path}"
        
        try:
            raw_response = requests.get(raw_url, headers=headers, timeout=10)
            if raw_response.status_code == 200:
                text_data = raw_response.text
                lines = text_data.split('\n')
                h1 = lines[0].strip() if len(lines) > 0 else ""
                h2 = lines[1].strip() if len(lines) > 1 else ""
                
                df = pd.read_csv(StringIO(text_data), skiprows=2)
                df['Time'] = time_label
                df['Datetime'] = dt
                df['Header1'] = h1
                df['Header2'] = h2
                all_data.append(df)
        except Exception: continue
            
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    return pd.DataFrame()

# โหลดข้อมูล (ดึง Intraday 1000 commits)
with st.spinner("กำลังซิงค์ข้อมูลล่าสุด..."):
    df_intraday = fetch_github_history("IntradayData.txt", max_commits=1000)
    df_oi = fetch_github_history("OIData.txt", max_commits=1)

if not df_intraday.empty:
    df_intraday = df_intraday.sort_values('Datetime', ascending=True)
    available_times = df_intraday['Time'].unique()
    
    # ดึงค่า Dropdown ก่อน เพื่อให้ Layout ขนานกับ Tab ได้ดีขึ้น
    col1, col2 = st.columns([5, 1])
    with col2:
        st.markdown("<div style='margin-bottom: -15px;'></div>", unsafe_allow_html=True) # ปรับลดช่องว่าง
        chart_mode = st.selectbox("โหมดแสดงกราฟ", ["แยก Call / Put", "รวมยอด (Total)"], label_visibility="collapsed")
        
    # เลือก Time เริ่มต้นเป็นข้อมูลล่าสุด
    if 'selected_time_state' not in st.session_state:
        st.session_state.selected_time_state = available_times[-1]

    current_data = df_intraday[df_intraday['Time'] == st.session_state.selected_time_state].copy().sort_values('Strike')
    if current_data['Vol Settle'].max() < 1:
        current_data['Vol Settle'] = (current_data['Vol Settle'] * 100).round(2)
        
    tab1, tab2 = st.tabs(["📈 Intraday Volume", "🏦 Open Interest (OI)"])
    
    # =============== TAB 1: Intraday ===============
    with tab1:
        h1_intra = current_data['Header1'].iloc[0]
        h2_intra = current_data['Header2'].iloc[0]
        atm_intra = extract_atm(h1_intra)
        
        st.markdown(get_styled_header(h1_intra, h2_intra), unsafe_allow_html=True)
        
        fig_intra = make_subplots(specs=[[{"secondary_y": True}]])
        
        if chart_mode == "แยก Call / Put":
            fig_intra.add_trace(go.Bar(x=current_data['Strike'], y=current_data['Put'], name='Put Vol', marker=dict(color='rgba(245, 158, 11, 0.85)', line=dict(color='#F59E0B', width=1))), secondary_y=False)
            fig_intra.add_trace(go.Bar(x=current_data['Strike'], y=current_data['Call'], name='Call Vol', marker=dict(color='rgba(59, 130, 246, 0.85)', line=dict(color='#3B82F6', width=1))), secondary_y=False)
        else:
            total_vol = current_data['Call'] + current_data['Put']
            fig_intra.add_trace(go.Bar(x=current_data['Strike'], y=total_vol, name='Total Vol', marker=dict(color='rgba(16, 185, 129, 0.85)', line=dict(color='#10B981', width=1))), secondary_y=False)

        fig_intra.add_trace(go.Scatter(x=current_data['Strike'], y=current_data['Vol Settle'], name='Vol Settle', mode='lines+markers', line=dict(color='#EF4444', width=3, shape='spline'), marker=dict(size=6, color='#EF4444')), secondary_y=True)
        
        if atm_intra:
            fig_intra.add_vline(x=atm_intra, line_dash="dash", line_color="white", opacity=0.6, annotation_text="ATM", annotation_position="top")
            
        fig_intra.update_layout(barmode='group', bargap=0.15, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5), margin=dict(l=10, r=10, t=10, b=10))
        fig_intra.update_xaxes(title_text="Strike Price", showgrid=True, gridcolor='rgba(255,255,255,0.05)')
        fig_intra.update_yaxes(title_text="Volume", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.05)')
        fig_intra.update_yaxes(title_text="Volatility", secondary_y=True, showgrid=False)
        st.plotly_chart(fig_intra, use_container_width=True)

        # ---------------------------------------------------------
        # แถบ Timeline (ย้ายมาอยู่ใต้กราฟ)
        # ---------------------------------------------------------
        st.markdown("<br>", unsafe_allow_html=True)
        selected_time = st.select_slider(
            "Timeline", 
            options=available_times, 
            value=st.session_state.selected_time_state,
            label_visibility="collapsed",
            key="timeline_slider_intra"
        )
        if selected_time != st.session_state.selected_time_state:
            st.session_state.selected_time_state = selected_time
            st.rerun()

        # ตารางข้อมูลของ Intraday
        st.markdown("---")
        st.markdown("### 📊 Intraday Volume Data")
        table_df_intra = current_data[['Strike', 'Call', 'Put', 'Vol Settle']].copy()
        table_df_intra['Total Vol'] = table_df_intra['Call'] + table_df_intra['Put']
        table_df_intra = table_df_intra[['Strike', 'Call', 'Put', 'Total Vol', 'Vol Settle']] 
        
        st.dataframe(
            table_df_intra,
            column_config={
                "Strike": st.column_config.NumberColumn("Strike Price", format="%d"),
                "Call": st.column_config.ProgressColumn("Call Volume", format="%d", min_value=0, max_value=int(table_df_intra['Call'].max()) if not table_df_intra.empty else 100),
                "Put": st.column_config.ProgressColumn("Put Volume", format="%d", min_value=0, max_value=int(table_df_intra['Put'].max()) if not table_df_intra.empty else 100),
                "Total Vol": st.column_config.ProgressColumn("Total Vol", format="%d", min_value=0, max_value=int(table_df_intra['Total Vol'].max()) if not table_df_intra.empty else 100),
                "Vol Settle": st.column_config.NumberColumn("Vol Settle", format="%.2f"),
            },
            hide_index=True, use_container_width=True, height=800 # ปรับความสูงเพิ่มเป็น 800
        )

    # =============== TAB 2: OI ===============
    with tab2:
        if not df_oi.empty:
            latest_oi = df_oi[df_oi['Datetime'] == df_oi['Datetime'].max()].copy().sort_values('Strike')
            if latest_oi['Vol Settle'].max() < 1:
                latest_oi['Vol Settle'] = (latest_oi['Vol Settle'] * 100).round(2)
            
            h1_oi = latest_oi['Header1'].iloc[0]
            h2_oi = latest_oi['Header2'].iloc[0]
            atm_oi = extract_atm(h1_oi)
            
            st.markdown(get_styled_header(h1_oi, h2_oi), unsafe_allow_html=True)
                
            fig_oi = make_subplots(specs=[[{"secondary_y": True}]])
            
            if chart_mode == "แยก Call / Put":
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=latest_oi['Put'], name='Put OI', marker=dict(color='rgba(245, 158, 11, 0.85)', line=dict(color='#F59E0B', width=1))), secondary_y=False)
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=latest_oi['Call'], name='Call OI', marker=dict(color='rgba(59, 130, 246, 0.85)', line=dict(color='#3B82F6', width=1))), secondary_y=False)
            else:
                total_oi = latest_oi['Call'] + latest_oi['Put']
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=total_oi, name='Total OI', marker=dict(color='rgba(16, 185, 129, 0.85)', line=dict(color='#10B981', width=1))), secondary_y=False)
                
            fig_oi.add_trace(go.Scatter(x=latest_oi['Strike'], y=latest_oi['Vol Settle'], name='Vol Settle', mode='lines+markers', line=dict(color='#EF4444', width=3, shape='spline'), marker=dict(size=6, color='#EF4444')), secondary_y=True)
            
            if atm_oi:
                fig_oi.add_vline(x=atm_oi, line_dash="dash", line_color="white", opacity=0.6, annotation_text="ATM", annotation_position="top")
                
            fig_oi.update_layout(barmode='group', bargap=0.15, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5), margin=dict(l=10, r=10, t=10, b=10))
            fig_oi.update_xaxes(title_text="Strike Price", showgrid=True, gridcolor='rgba(255,255,255,0.05)')
            fig_oi.update_yaxes(title_text="Open Interest", secondary_y=False, showgrid=True, gridcolor='rgba(255,255,255,0.05)')
            fig_oi.update_yaxes(title_text="Volatility", secondary_y=True, showgrid=False)
            st.plotly_chart(fig_oi, use_container_width=True)

            # ตารางข้อมูลของ OI
            st.markdown("---")
            st.markdown("### 📊 OI Volume Data")
            table_df_oi = latest_oi[['Strike', 'Call', 'Put', 'Vol Settle']].copy()
            table_df_oi['Total Vol'] = table_df_oi['Call'] + table_df_oi['Put']
            table_df_oi = table_df_oi[['Strike', 'Call', 'Put', 'Total Vol', 'Vol Settle']] 
            
            st.dataframe(
                table_df_oi,
                column_config={
                    "Strike": st.column_config.NumberColumn("Strike Price", format="%d"),
                    "Call": st.column_config.ProgressColumn("Call Volume", format="%d", min_value=0, max_value=int(table_df_oi['Call'].max()) if not table_df_oi.empty else 100),
                    "Put": st.column_config.ProgressColumn("Put Volume", format="%d", min_value=0, max_value=int(table_df_oi['Put'].max()) if not table_df_oi.empty else 100),
                    "Total Vol": st.column_config.ProgressColumn("Total Vol", format="%d", min_value=0, max_value=int(table_df_oi['Total Vol'].max()) if not table_df_oi.empty else 100),
                    "Vol Settle": st.column_config.NumberColumn("Vol Settle", format="%.2f"),
                },
                hide_index=True, use_container_width=True, height=800 # ปรับความสูงเพิ่มเป็น 800
            )

else:
    st.info("💡 รอการอัปเดตข้อมูลของ 'วันนี้' จากระบบของคุณครับ")