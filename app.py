import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
import re
import time
import concurrent.futures

# ==========================================
# Token Streamlit Secrets
# ==========================================
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    GITHUB_TOKEN = ""

st.set_page_config(layout="wide", page_title="Vol2Vol Gold Data Tracker", page_icon=":abacus:")

# ==========================================
# Custom CSS + Mobile Responsive
# ==========================================
st.markdown("""
<style>
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 1rem !important;
    }
    .header-box { 
        background-color: var(--secondary-background-color); 
        color: var(--text-color) !important; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 20px; 
        text-align: center; 
        border: 1px solid var(--border-color); 
    }
    .header-title { font-size: 20px; font-weight: bold; color: var(--text-color); margin-bottom: 10px; }
    .header-metrics span { font-size: 16px; margin: 0 15px; font-weight: bold; }
    .t-put { color: #F59E0B; }
    .t-call { color: #3B82F6; }
    .t-vol { color: #EF4444; }
    .t-neutral { color: #718096; } 
    div[data-baseweb="select"] {
        user-select: none;
        -webkit-user-select: none;
        -ms-user-select: none;
        cursor: pointer !important;
    }
    div[data-baseweb="select"] * { cursor: pointer !important; }
    div[data-baseweb="select"] input { caret-color: transparent !important; }
    div[data-testid="stButton"] button {
        padding-left: 0.2rem !important;
        padding-right: 0.2rem !important;
    }
    div[data-testid="stButton"] button p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: 0.9rem !important;
    }  
    [data-testid="stElementToolbar"], [data-testid="stDataFrameToolbar"] {
        display: none !important;
    }

    /* 📱 การจัดเรียง UI เฉพาะบนมือถือ */
    @media (max-width: 768px) {
        /* ชุดแถว 3 คอลัมน์ (ดึงข้อมูลแถวบนขึ้นไป 100% แล้วเอา 2 อันหลังมาเรียงแนวนอน) */
        div[data-testid="stElementContainer"]:has(.wrap-row) + div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: wrap !important;
            align-items: flex-end !important;
            gap: 0.5rem !important;
        }
        div[data-testid="stElementContainer"]:has(.wrap-row) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) {
            min-width: 100% !important;
            order: 1;
            margin-bottom: 5px;
        }
        div[data-testid="stElementContainer"]:has(.wrap-row) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
            flex: 2 1 60% !important;
            order: 2;
        }
        div[data-testid="stElementContainer"]:has(.wrap-row) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3) {
            flex: 1 1 30% !important;
            order: 3;
        }

        /* ชุดปุ่ม Timeline + Back Play Next */
        div[data-testid="stElementContainer"]:has(.playback-row) + div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        div[data-testid="stElementContainer"]:has(.playback-row) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1) {
            order: 2; /* ดึงชุดปุ่มลงมาข้างล่าง */
            width: 100% !important;
        }
        div[data-testid="stElementContainer"]:has(.playback-row) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {
            order: 1; /* ดึงแถบ Timeline ขึ้นไปด้านบน */
            width: 100% !important;
            margin-bottom: -15px !important;
        }
        /* บังคับปุ่ม Back | Play | Next ให้เรียงแนวนอน */
        div[data-testid="stElementContainer"]:has(.playback-row) + div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 0.2rem !important;
        }
        div[data-testid="stElementContainer"]:has(.playback-row) + div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            width: auto !important;
            flex: 1 1 0% !important;
            min-width: 0 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

REPO = "pageth/Vol2VolData"

# ==========================================
# ฟังก์ชันตรวจสอบ Market Session (รองรับ DST)
# ==========================================
def get_market_session(dt_bkk):
    try:
        dt_utc = dt_bkk.tz_convert('UTC')
        dt_ny = dt_utc.tz_convert('America/New_York')
        dt_lon = dt_utc.tz_convert('Europe/London')
        dt_tokyo = dt_utc.tz_convert('Asia/Tokyo')
        
        sessions = []
        if 8 <= dt_tokyo.hour < 15:
            sessions.append("Tokyo")
        if 8 <= dt_lon.hour < 16 or (dt_lon.hour == 16 and dt_lon.minute <= 30):
            sessions.append("London")
        if 8 <= dt_ny.hour < 17:
            sessions.append("New York")
            
        if not sessions:
            return "After Hours"
        return " & ".join(sessions)
    except Exception:
        return ""

# ==========================================
# Strike Price History Popup
# ==========================================
@st.dialog("Strike Price Details")
def show_strike_history(strike_price, df_intra_all, df_oi_all):
    history_df = df_intra_all[df_intra_all['Strike'] == strike_price].copy()
    history_df = history_df.sort_values('Datetime')
    
    oi_hist = df_oi_all[df_oi_all['Strike'] == strike_price].copy()
    oi_hist = oi_hist.sort_values('Datetime')
    
    if not history_df.empty:
        i_call = int(history_df.iloc[-1]['Call'])
        i_put = int(history_df.iloc[-1]['Put'])
        i_tot = i_call + i_put
        i_vol = history_df.iloc[-1]['Vol Settle']
        if history_df['Vol Settle'].max() < 1:
            i_vol *= 100
    else:
        i_call = i_put = i_tot = i_vol = 0
        
    if not oi_hist.empty:
        o_call = int(oi_hist.iloc[-1]['Call'])
        o_put = int(oi_hist.iloc[-1]['Put'])
        o_tot = o_call + o_put
        o_vol = oi_hist.iloc[-1]['Vol Settle']
        if oi_hist['Vol Settle'].max() < 1:
            o_vol *= 100
    else:
        o_call = o_put = o_tot = o_vol = 0

    vol_display = i_vol if i_vol > 0 else o_vol

    html_table = f"""
        <div style='margin-top: -15px; font-size: 22px; font-weight: bold;'>
            Strike: {strike_price} &nbsp;&nbsp;<span class='t-vol' style='font-size: 18px;'>Vol Settle: {vol_display:.2f}</span>
        </div>
        <div style='margin-top: 15px; margin-bottom: 20px; color: var(--text-color);'>
            <table style="width: 100%; border-collapse: collapse; font-size: 15px;">
                <tr style="border-bottom: 1px solid rgba(128,128,128,0.2);">
                    <th style="padding: 8px 0; border: none;"></th>
                    <th style="padding: 8px 0; border: none; text-align: center;" class="t-call">Call</th>
                    <th style="padding: 8px 0; border: none; text-align: center;" class="t-put">Put</th>
                    <th style="padding: 8px 0; border: none; text-align: center;">Total</th>
                </tr>
                <tr style="border-bottom: 1px solid rgba(128,128,128,0.2); background-color: transparent;">
                    <td style="padding: 12px 0; border: none; font-weight: bold; white-space: nowrap;">Intraday Volume</td>
                    <td style="padding: 12px 0; border: none; text-align: center;" class="t-call">{i_call}</td>
                    <td style="padding: 12px 0; border: none; text-align: center;" class="t-put">{i_put}</td>
                    <td style="padding: 12px 0; border: none; text-align: center;">{i_tot}</td>
                </tr>
                <tr style="background-color: transparent;">
                    <td style="padding: 12px 0; border: none; font-weight: bold; white-space: nowrap;">Open Interest (OI)</td>
                    <td style="padding: 12px 0; border: none; text-align: center;" class="t-call">{o_call}</td>
                    <td style="padding: 12px 0; border: none; text-align: center;" class="t-put">{o_put}</td>
                    <td style="padding: 12px 0; border: none; text-align: center;">{o_tot}</td>
                </tr>
            </table>
        </div>
        """
    st.markdown(html_table, unsafe_allow_html=True)
    
    if not history_df.empty:
        st.markdown("##### :material/schedule: Intraday Strike Price History")
        
        display_df = history_df[['Time', 'Call', 'Put']].copy()
            
        display_df['Time'] = display_df['Time'] + " น." 
        display_df['Total Vol'] = display_df['Call'] + display_df['Put']
        
        call_diff = display_df['Call'].diff().fillna(0).astype(int)
        put_diff = display_df['Put'].diff().fillna(0).astype(int)
        total_diff = display_df['Total Vol'].diff().fillna(0).astype(int)
        
        def format_diff(val, diff):
            if diff > 0:
                return f"{val} ( ▲ +{diff} )"
            elif diff < 0:
                return f"{val} ( ▼ {diff} )"
            return str(val)
            
        display_df['Call'] = [format_diff(v, d) for v, d in zip(display_df['Call'], call_diff)]
        display_df['Put'] = [format_diff(v, d) for v, d in zip(display_df['Put'], put_diff)]
        display_df['Total Vol'] = [format_diff(v, d) for v, d in zip(display_df['Total Vol'], total_diff)]
        
        display_df = display_df.iloc[::-1].reset_index(drop=True)
        
        def color_bg(val):
            if isinstance(val, str):
                if '▲' in val:
                    return 'background-color: rgba(16, 185, 129, 0.15); color: #10B981; font-weight: bold;'
                elif '▼' in val:
                    return 'background-color: rgba(239, 68, 68, 0.15); color: #EF4444; font-weight: bold;'
            return ''

        try:
            styled_df = display_df.style.map(color_bg, subset=['Call', 'Put', 'Total Vol'])
        except AttributeError:
            styled_df = display_df.style.applymap(color_bg, subset=['Call', 'Put', 'Total Vol'])
        
        st.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True, 
            height=400,
            column_order=["Time", "Call", "Put", "Total Vol"],
            column_config={
                "Time": "Time",
                "Call": "Call",
                "Put": "Put",
                "Total Vol": "Total"
            }
        )
    else:
        st.info("ไม่มีข้อมูลประวัติ Intraday สำหรับ Strike Price นี้")

def safe_max(series):
    try:
        if series.empty:
            return 1
        m = float(series.max())
        if pd.isna(m) or m <= 0:
            return 1
        return int(m)
    except:
        return 1

def extract_atm(header_text):
    match = re.search(r'vs\s+([\d\.,]+)', str(header_text))
    if match:
        return float(match.group(1).replace(',', ''))
    return None

def _get_chart_points(chart_key):
    state = st.session_state.get(chart_key)
    if state is None:
        return []

    try:
        return state.selection.points
    except Exception:
        try:
            return state["selection"]["points"]
        except Exception:
            return []

def handle_intra_chart_select():
    points = _get_chart_points("intra_main_chart")
    if points:
        try:
            st.session_state.is_playing = False
            st.session_state.dialog_strike = int(points[0]["x"])
        except Exception:
            pass

def handle_oi_chart_select():
    points = _get_chart_points("oi_main_chart")
    if points:
        try:
            st.session_state.is_playing = False
            st.session_state.dialog_strike = int(points[0]["x"])
        except Exception:
            pass

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

def filter_session_data(df, data_type):
    if df.empty:
        return df
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    now = pd.Timestamp.now(tz='Asia/Bangkok')
    if now.hour < 10:
        session_date = (now - timedelta(days=1)).date()
    else:
        session_date = now.date()
    start_time = pd.Timestamp(datetime.combine(session_date, datetime.min.time())).tz_localize('Asia/Bangkok') + timedelta(hours=10)
    end_time = start_time + timedelta(hours=15)

    if data_type == "Intraday":
        df = df[~df['Header1'].str.contains("Open Interest", case=False, na=False)]
    elif data_type == "OI":
        df = df[df['Header1'].str.contains("Open Interest", case=False, na=False)]

    df_filtered = df[(df['Datetime'] >= start_time) & (df['Datetime'] <= end_time)]
    df_filtered = df_filtered.sort_values('Datetime').reset_index(drop=True)
    return df_filtered

@st.cache_data(show_spinner=False, ttl=180) 
def fetch_github_history(file_path, max_commits=200):
    headers = {'User-Agent': 'Mozilla/5.0'}
    if GITHUB_TOKEN.strip():
        headers['Authorization'] = f'token {GITHUB_TOKEN.strip()}'
        
    now = pd.Timestamp.now(tz='Asia/Bangkok')
    if now.hour < 10:
        session_date = (now - timedelta(days=1)).date()
    else:
        session_date = now.date()
        
    per_page = 100
    pages_to_fetch = (max_commits // per_page) + (1 if max_commits % per_page > 0 else 0)
    
    commit_metadata = []
    keep_fetching = True
    
    for page in range(1, pages_to_fetch + 1):
        if not keep_fetching: break
        api_url = f"https://api.github.com/repos/{REPO}/commits?path={file_path}&per_page={per_page}&page={page}"
        
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
        except Exception: break
            
        if response.status_code != 200: break
        commits = response.json()
        if not commits: break
            
        for commit in commits:
            sha = commit['sha']
            date_str = commit['commit']['author']['date'] 
            dt = pd.to_datetime(date_str).tz_convert('Asia/Bangkok') if pd.to_datetime(date_str).tzinfo else pd.to_datetime(date_str).tz_localize('UTC').tz_convert('Asia/Bangkok')
            
            if dt.date() < session_date: 
                keep_fetching = False
                break
                
            time_label = dt.strftime("%H:%M:%S")
            commit_metadata.append((sha, time_label, dt))
            
            if len(commit_metadata) >= max_commits:
                keep_fetching = False
                break

    def download_file(meta):
        sha, time_label, dt = meta
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
                return df
        except Exception:
            pass
        return None

    all_data = []
    if commit_metadata:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(download_file, commit_metadata)
            for res in results:
                if res is not None:
                    all_data.append(res)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

def style_df(df, col, color_hex):
    if df.empty: return df
    try:
        return df.style.map(lambda _: f'color: {color_hex}; font-weight: bold;', subset=[col])
    except AttributeError:
        return df.style.applymap(lambda _: f'color: {color_hex}; font-weight: bold;', subset=[col])

# ==========================================
# Initialize Session State
# ==========================================
if 'is_playing' not in st.session_state:
    st.session_state.is_playing = False
if 'anim_idx' not in st.session_state:
    st.session_state.anim_idx = 0
if 'focus_slider' not in st.session_state:
    st.session_state.focus_slider = False
if 'dialog_strike' not in st.session_state:
    st.session_state.dialog_strike = None

if 'my_intraday_data' not in st.session_state:
    raw_intra = fetch_github_history("IntradayData.txt", max_commits=200)
    raw_oi = fetch_github_history("OIData.txt", max_commits=1)
    st.session_state.my_intraday_data = filter_session_data(raw_intra, "Intraday")
    st.session_state.my_oi_data = filter_session_data(raw_oi, "OI")


# --- ชุดควบคุมส่วนบน (ตอบโจทย์ภาพที่ 1) ---
st.markdown('<div class="wrap-row"></div>', unsafe_allow_html=True)
col_spin, col_dropdown, col_refresh = st.columns([7, 2, 1.5])

with col_spin:
    status_placeholder = st.empty()
    df_intraday = st.session_state.my_intraday_data
    df_oi = st.session_state.my_oi_data
    if not df_intraday.empty:
        last_fetch = df_intraday['Datetime'].max().strftime("%H:%M:%S")
        status_placeholder.caption(f"⏱ ข้อมูลล่าสุด: **{last_fetch} น.**")

with col_dropdown:
    chart_mode = st.selectbox("โหมดแสดงกราฟ", ["Call / Put Vol", "Total Vol"], label_visibility="collapsed")

with col_refresh:
    if st.button(":material/refresh: Refresh", use_container_width=True):
        start_time = time.time()
        with status_placeholder:
            with st.spinner("กำลังอัปเดต..."):
                raw_intra_new = fetch_github_history("IntradayData.txt", max_commits=200)
                raw_oi_new = fetch_github_history("OIData.txt", max_commits=1)
                st.session_state.my_intraday_data = filter_session_data(raw_intra_new, "Intraday")
                st.session_state.my_oi_data = filter_session_data(raw_oi_new, "OI")
                elapsed_time = time.time() - start_time
                if elapsed_time < 3.0:
                    time.sleep(3.0 - elapsed_time)
        if 'selected_time_state' in st.session_state:
            del st.session_state['selected_time_state']
        st.session_state.is_playing = False
        st.rerun()

if not df_intraday.empty:
    available_times = df_intraday['Time'].unique()
    
    session_map = {}
    for val in available_times:
        dt_first = df_intraday[df_intraday['Time'] == val]['Datetime'].iloc[0]
        session_map[val] = get_market_session(dt_first)
        
    if 'selected_time_state' not in st.session_state or st.session_state.selected_time_state not in available_times:
        st.session_state.selected_time_state = available_times[-1]

    if st.session_state.is_playing:
        if 'anim_idx' in st.session_state and st.session_state.anim_idx < len(available_times):
            st.session_state.selected_time_state = available_times[st.session_state.anim_idx]

    tab1, tab2, tab3 = st.tabs([":material/show_chart: Intraday Volume", ":material/account_balance: Open Interest (OI)", ":material/leaderboard: Top Ranking"])
    
    # ==========================================
    # Tab 1: Intraday Volume
    # ==========================================
    with tab1:
        time_val = st.session_state.selected_time_state
        frame_data = df_intraday[df_intraday['Time'] == time_val].copy().sort_values('Strike')
        if frame_data['Vol Settle'].max() < 1:
            frame_data['Vol Settle'] = (frame_data['Vol Settle'] * 100).round(2)
            
        h1_intra = frame_data['Header1'].iloc[0]
        market_ses = session_map.get(time_val, "")
        if market_ses:
            h1_intra = f"{h1_intra} &nbsp;🌍 <span style='font-size: 0.9em; color:#888;'>({market_ses})</span>"
            
        h2_intra = frame_data['Header2'].iloc[0]
        st.markdown(get_styled_header(h1_intra, h2_intra), unsafe_allow_html=True)
        
        fig_intra = make_subplots(specs=[[{"secondary_y": True}]])
        total_vol = frame_data['Call'] + frame_data['Put']
        
        put_w = [1 if v > 0 else 0 for v in frame_data['Put']]
        call_w = [1 if v > 0 else 0 for v in frame_data['Call']]
        tot_w = [1 if v > 0 else 0 for v in total_vol]
        
        if chart_mode == "Call / Put Vol":
            fig_intra.add_trace(go.Bar(x=frame_data['Strike'], y=frame_data['Put'], name='Put Vol', 
                marker=dict(color='#F59E0B', line=dict(color='#F59E0B', width=put_w)),
                hovertemplate="%{y:,.0f}",
                selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)
                
            fig_intra.add_trace(go.Bar(x=frame_data['Strike'], y=frame_data['Call'], name='Call Vol', 
                marker=dict(color='#3B82F6', line=dict(color='#3B82F6', width=call_w)),
                hovertemplate="%{y:,.0f}",
                selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)
                
            fig_intra.add_trace(go.Scatter(x=frame_data['Strike'], y=total_vol, name='Total Vol', mode='markers', 
                marker=dict(color='rgba(0,0,0,0)', size=1), showlegend=False,
                hovertemplate="%{y:,.0f}"), secondary_y=False)
        else:
            fig_intra.add_trace(go.Bar(x=frame_data['Strike'], y=total_vol, name='Total Vol', 
                marker=dict(color='#10B981', line=dict(color='#10B981', width=tot_w)),
                hovertemplate="%{y:,.0f}",
                selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)

        vol_intra_y = [val if val > 0 else None for val in frame_data['Vol Settle']]
        fig_intra.add_trace(go.Scatter(x=frame_data['Strike'], y=vol_intra_y, name='Vol Settle', mode='lines+markers', 
            line=dict(color='#EF4444', width=3, shape='spline'), marker=dict(size=6, color='#EF4444'),
            hovertemplate="%{y:.2f}",
            selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=True)
        
        atm_intra = extract_atm(h1_intra)
        if atm_intra:
            fig_intra.add_vline(x=atm_intra, line_dash="dash", line_color="#888888", opacity=0.8, annotation_text="ATM", annotation_position="top")
            
        fig_intra.update_layout(barmode='group', bargap=0.15, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',clickmode="event+select", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5), margin=dict(l=10, r=10, t=10, b=10))
        
        fig_intra.update_xaxes(title_text="Strike Price", showgrid=True, gridcolor='rgba(128,128,128,0.2)', hoverformat=".0f", fixedrange=True)
        fig_intra.update_yaxes(title_text="Volume", secondary_y=False, showgrid=True, gridcolor='rgba(128,128,128,0.2)', fixedrange=True)
        fig_intra.update_yaxes(title_text="Volatility", secondary_y=True, showgrid=False, fixedrange=True)
        
        st.plotly_chart(
            fig_intra,
            use_container_width=True,
            on_select=handle_intra_chart_select,
            selection_mode="points",
            config={'displayModeBar': False},
            key="intra_main_chart"
        )

        if st.session_state.dialog_strike is not None:
            show_strike_history(int(st.session_state.dialog_strike), df_intraday, df_oi)
            st.session_state.dialog_strike = None
        
        # --- ชุดควบคุม Playback (ตอบโจทย์ภาพที่ 2) ---
        st.markdown('<div class="playback-row"></div>', unsafe_allow_html=True)
        col_controls, col_slider = st.columns([1.5, 10])
        
        with col_controls:
            c1, c2, c3 = st.columns(3)
            try:
                current_idx = list(available_times).index(st.session_state.selected_time_state)
            except ValueError:
                current_idx = len(available_times) - 1
                
            with c1:
                if st.button(":material/skip_previous:", help="Back", use_container_width=True):
                    st.session_state.is_playing = False
                    new_idx = max(0, current_idx - 1)
                    st.session_state.selected_time_state = available_times[new_idx]
                    st.session_state.focus_slider = True
                    st.rerun()
            with c2:
                if st.session_state.is_playing:
                    if st.button(":material/pause:", help="Pause", use_container_width=True):
                        st.session_state.is_playing = False
                        st.session_state.focus_slider = True  
                        st.rerun()
                else:
                    if st.button(":material/play_arrow:", help="Play", use_container_width=True):
                        st.session_state.is_playing = True
                        if current_idx == len(available_times) - 1:
                            st.session_state.anim_idx = 0
                        else:
                            st.session_state.anim_idx = current_idx
                        st.session_state.selected_time_state = available_times[st.session_state.anim_idx]
                        st.rerun()
            with c3:
                if st.button(":material/skip_next:", help="Next", use_container_width=True):
                    st.session_state.is_playing = False
                    new_idx = min(len(available_times) - 1, current_idx + 1)
                    st.session_state.selected_time_state = available_times[new_idx]
                    st.session_state.focus_slider = True
                    st.rerun()
                    
        with col_slider:
            st.select_slider(
                "Timeline", 
                options=available_times, 
                key="selected_time_state",
                format_func=lambda x: f"{x} น. ({session_map.get(x, '')})" if session_map.get(x, '') else f"{x} น.",
                label_visibility="collapsed"
            )

        if st.session_state.focus_slider:
            components.html("""<script>const sliders = window.parent.document.querySelectorAll('div[role="slider"]'); if (sliders.length > 0) { sliders[0].focus(); } </script>""", height=0, width=0)
            st.session_state.focus_slider = False

        st.markdown("---")
        
        # --- ชุดค้นหา (ตอบโจทย์ภาพที่ 3) ---
        st.markdown('<div class="wrap-row"></div>', unsafe_allow_html=True)
        col_tb_head, col_tb_search1, col_tb_search2 = st.columns([6, 2.5, 1.5])
        with col_tb_head:
            st.markdown("### :material/analytics: Intraday Volume Data")
            
        with col_tb_search1:
            strike_options = sorted(frame_data['Strike'].unique().tolist())
            default_strike_val = int(atm_intra) if atm_intra else (int(frame_data['Strike'].median()) if not frame_data.empty else 4900)
            
            if default_strike_val in strike_options:
                default_index = strike_options.index(default_strike_val)
            else:
                if strike_options:
                    nearest = min(strike_options, key=lambda x: abs(x - default_strike_val))
                    default_index = strike_options.index(nearest)
                else:
                    default_index = 0
                    
            search_strike = st.selectbox("ค้นหา Strike Price", options=strike_options, index=default_index, label_visibility="collapsed", key="intra_search_dropdown")
            
        with col_tb_search2:
            if st.button(":material/search: ดูรายละเอียด", use_container_width=True, key="intra_search_btn"):
                st.session_state.is_playing = False
                show_strike_history(int(search_strike), df_intraday, df_oi)
        
        table_df_intra = frame_data[['Strike', 'Call', 'Put', 'Vol Settle']].copy()
        table_df_intra['Total Vol'] = table_df_intra['Call'] + table_df_intra['Put']
        table_df_intra = table_df_intra[['Strike', 'Call', 'Put', 'Total Vol', 'Vol Settle']] 
        
        st.dataframe(
            table_df_intra,
            column_order=["Strike", "Call", "Put", "Total Vol", "Vol Settle"],
            column_config={
                "Strike": st.column_config.NumberColumn("Strike Price", format="%d"),
                "Call": st.column_config.ProgressColumn("Call Vol", format="%d", min_value=0, max_value=safe_max(table_df_intra['Call'])),
                "Put": st.column_config.ProgressColumn("Put Vol", format="%d", min_value=0, max_value=safe_max(table_df_intra['Put'])),
                "Total Vol": st.column_config.ProgressColumn("Total Vol", format="%d", min_value=0, max_value=safe_max(table_df_intra['Total Vol'])),
                "Vol Settle": st.column_config.NumberColumn("Vol Settle", format="%.2f"),
            },
            hide_index=True, 
            use_container_width=True, 
            height=800
        )

        if st.session_state.is_playing:
            time.sleep(0.6)
            st.session_state.anim_idx += 1
            if st.session_state.anim_idx < len(available_times):
                st.rerun()
            else:
                st.session_state.is_playing = False
                st.rerun()

    # ==========================================
    # Tab 2: OI
    # ==========================================
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
            total_oi = latest_oi['Call'] + latest_oi['Put']

            oi_put_w = [1 if v > 0 else 0 for v in latest_oi['Put']]
            oi_call_w = [1 if v > 0 else 0 for v in latest_oi['Call']]
            oi_tot_w = [1 if v > 0 else 0 for v in total_oi]
            
            if chart_mode == "Call / Put Vol":
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=latest_oi['Put'], name='Put OI', 
                    marker=dict(color='#F59E0B', line=dict(color='#F59E0B', width=oi_put_w)),
                    hovertemplate="%{y:,.0f}",
                    selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)
                    
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=latest_oi['Call'], name='Call OI', 
                    marker=dict(color='#3B82F6', line=dict(color='#3B82F6', width=oi_call_w)),
                    hovertemplate="%{y:,.0f}",
                    selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)
                    
                fig_oi.add_trace(go.Scatter(x=latest_oi['Strike'], y=total_oi, name='Total OI', mode='markers', 
                    marker=dict(color='rgba(0,0,0,0)', size=1), showlegend=False, 
                    hovertemplate="%{y:,.0f}"), secondary_y=False)
            else:
                fig_oi.add_trace(go.Bar(x=latest_oi['Strike'], y=total_oi, name='Total OI', 
                    marker=dict(color='#10B981', line=dict(color='#10B981', width=oi_tot_w)), 
                    hovertemplate="%{y:,.0f}",
                    selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=False)
                
            vol_oi_y = [val if val > 0 else None for val in latest_oi['Vol Settle']]
            fig_oi.add_trace(go.Scatter(x=latest_oi['Strike'], y=vol_oi_y, name='Vol Settle', mode='lines+markers', 
                line=dict(color='#EF4444', width=3, shape='spline'), marker=dict(size=6, color='#EF4444'),
                hovertemplate="%{y:.2f}",
                selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))), secondary_y=True)
            
            if atm_oi:
                fig_oi.add_vline(x=atm_oi, line_dash="dash", line_color="#888888", opacity=0.8, annotation_text="ATM", annotation_position="top")
                
            fig_oi.update_layout(
                barmode='group',
                bargap=0.15,
                height=500,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                clickmode="event+select",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
                margin=dict(l=10, r=10, t=10, b=10)
            )

            fig_oi.update_xaxes(title_text="Strike Price", showgrid=True, gridcolor='rgba(128,128,128,0.2)', hoverformat=".0f", fixedrange=True)
            fig_oi.update_yaxes(title_text="Open Interest", secondary_y=False, showgrid=True, gridcolor='rgba(128,128,128,0.2)', fixedrange=True)
            fig_oi.update_yaxes(title_text="Volatility", secondary_y=True, showgrid=False, fixedrange=True)
            
            st.plotly_chart(
                fig_oi,
                use_container_width=True,
                on_select=handle_oi_chart_select,
                selection_mode="points",
                config={'displayModeBar': False},
                key="oi_main_chart"
            )

            if st.session_state.dialog_strike is not None:
                show_strike_history(int(st.session_state.dialog_strike), df_intraday, df_oi)
                st.session_state.dialog_strike = None

            st.markdown("---")
            
            st.markdown('<div class="wrap-row"></div>', unsafe_allow_html=True)
            col_tb_head_oi, col_tb_search1_oi, col_tb_search2_oi = st.columns([6, 2.5, 1.5])
            with col_tb_head_oi:
                st.markdown("### :material/analytics: OI Volume Data")
                
            with col_tb_search1_oi:
                strike_options_oi = sorted(latest_oi['Strike'].unique().tolist())
                default_strike_val_oi = int(atm_oi) if atm_oi else (int(latest_oi['Strike'].median()) if not latest_oi.empty else 4900)
                
                if default_strike_val_oi in strike_options_oi:
                    default_index_oi = strike_options_oi.index(default_strike_val_oi)
                else:
                    if strike_options_oi:
                        nearest = min(strike_options_oi, key=lambda x: abs(x - default_strike_val_oi))
                        default_index_oi = strike_options_oi.index(nearest)
                    else:
                        default_index_oi = 0
                        
                search_strike_oi = st.selectbox("ค้นหา Strike Price", options=strike_options_oi, index=default_index_oi, label_visibility="collapsed", key="oi_search_dropdown")
                
            with col_tb_search2_oi:
                if st.button(":material/search: ดูรายละเอียด", use_container_width=True, key="oi_search_btn"):
                    st.session_state.is_playing = False
                    show_strike_history(int(search_strike_oi), df_intraday, df_oi)
            
            table_df_oi = latest_oi[['Strike', 'Call', 'Put', 'Vol Settle']].copy()
            table_df_oi['Total Vol'] = table_df_oi['Call'] + table_df_oi['Put']
            table_df_oi = table_df_oi[['Strike', 'Call', 'Put', 'Total Vol', 'Vol Settle']] 
            
            st.dataframe(
                table_df_oi,
                column_order=["Strike", "Call", "Put", "Total Vol", "Vol Settle"],
                column_config={
                    "Strike": st.column_config.NumberColumn("Strike Price", format="%d"),
                    "Call": st.column_config.ProgressColumn("Call OI", format="%d", min_value=0, max_value=safe_max(table_df_oi['Call'])),
                    "Put": st.column_config.ProgressColumn("Put OI", format="%d", min_value=0, max_value=safe_max(table_df_oi['Put'])),
                    "Total Vol": st.column_config.ProgressColumn("Total OI", format="%d", min_value=0, max_value=safe_max(table_df_oi['Total Vol'])),
                    "Vol Settle": st.column_config.NumberColumn("Vol Settle", format="%.2f"),
                },
                hide_index=True, 
                use_container_width=True, 
                height=800
            )

    # ==========================================
    # Tab 3: Top Ranking 
    # ==========================================
    with tab3:
        if not df_intraday.empty:
            df_intra_latest = df_intraday[df_intraday['Datetime'] == df_intraday['Datetime'].max()].copy()
            df_intra_latest['Total'] = df_intra_latest['Call'] + df_intra_latest['Put']
            
            df_oi_latest = pd.DataFrame()
            if not df_oi.empty:
                df_oi_latest = df_oi[df_oi['Datetime'] == df_oi['Datetime'].max()].copy()
                df_oi_latest['Total'] = df_oi_latest['Call'] + df_oi_latest['Put']

            st.markdown("### :material/emoji_events: Top Intraday Volume (สะสมสูงสุด 5 อันดับ)")

            c1, c2, c3 = st.columns(3)
            c1.dataframe(style_df(df_intra_latest.nlargest(5, 'Call')[['Strike', 'Call']], 'Call', '#3B82F6'), hide_index=True, use_container_width=True)
            c2.dataframe(style_df(df_intra_latest.nlargest(5, 'Put')[['Strike', 'Put']], 'Put', '#F59E0B'), hide_index=True, use_container_width=True)
            c3.dataframe(style_df(df_intra_latest.nlargest(5, 'Total')[['Strike', 'Total']], 'Total', '#10B981'), hide_index=True, use_container_width=True)

            if not df_oi_latest.empty:
                st.markdown("---")
                st.markdown("### :material/account_balance: Top Open Interest (OI) (สะสมสูงสุด 5 อันดับ)")
                c1, c2, c3 = st.columns(3)
                c1.dataframe(style_df(df_oi_latest.nlargest(5, 'Call')[['Strike', 'Call']], 'Call', '#3B82F6'), hide_index=True, use_container_width=True)
                c2.dataframe(style_df(df_oi_latest.nlargest(5, 'Put')[['Strike', 'Put']], 'Put', '#F59E0B'), hide_index=True, use_container_width=True)
                c3.dataframe(style_df(df_oi_latest.nlargest(5, 'Total')[['Strike', 'Total']], 'Total', '#10B981'), hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("### :material/local_fire_department: Top Active Intraday Volume (การเปลี่ยนแปลงมากสุดตลอดวัน 10 อันดับ)")
            
            df_first_day = df_intraday.sort_values('Datetime').groupby('Strike').first()[['Call', 'Put']]
            df_last_day = df_intraday.sort_values('Datetime').groupby('Strike').last()[['Call', 'Put']]
            df_day_diff = (df_last_day - df_first_day).reset_index()
            df_day_diff['Total'] = df_day_diff['Call'] + df_day_diff['Put']

            st.markdown("#### :material/trending_up: เพิ่มขึ้นมากที่สุด (Increase)")
            c1, c2, c3 = st.columns(3)
            c1.dataframe(style_df(df_day_diff[df_day_diff['Call']>0].nlargest(10, 'Call')[['Strike', 'Call']], 'Call', '#3B82F6'), hide_index=True, use_container_width=True)
            c2.dataframe(style_df(df_day_diff[df_day_diff['Put']>0].nlargest(10, 'Put')[['Strike', 'Put']], 'Put', '#F59E0B'), hide_index=True, use_container_width=True)
            c3.dataframe(style_df(df_day_diff[df_day_diff['Total']>0].nlargest(10, 'Total')[['Strike', 'Total']], 'Total', '#10B981'), hide_index=True, use_container_width=True)

            st.markdown("#### :material/trending_down: ลดลงมากที่สุด (Decrease)")
            c1, c2, c3 = st.columns(3)
            c1.dataframe(style_df(df_day_diff[df_day_diff['Call']<0].nsmallest(10, 'Call')[['Strike', 'Call']], 'Call', '#3B82F6'), hide_index=True, use_container_width=True)
            c2.dataframe(style_df(df_day_diff[df_day_diff['Put']<0].nsmallest(10, 'Put')[['Strike', 'Put']], 'Put', '#F59E0B'), hide_index=True, use_container_width=True)
            c3.dataframe(style_df(df_day_diff[df_day_diff['Total']<0].nsmallest(10, 'Total')[['Strike', 'Total']], 'Total', '#10B981'), hide_index=True, use_container_width=True)

else:
    st.info("รอข้อมูลอัปเดตตั้งแต่เวลา 10:00 น. เป็นต้นไป", icon=":material/lightbulb:")
