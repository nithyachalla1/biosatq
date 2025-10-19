import streamlit as st
import requests, time
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
from biosat_core import OrbitSimulator, estimate_radiation 

API_ROOT = "http://localhost:8000"

st.set_page_config(
    page_title="BioSat-Q+ Mission Control", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
        padding: 2rem;
    }
    
    h1 {
        color: #2d3748;
        font-size: 3rem;
        text-align: center;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }
    
    h3 {
        color: #4a5568;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    .subtitle {
        text-align: center;
        color: #718096;
        font-size: 1.2rem;
        margin-bottom: 3rem;
    }
    
    [data-testid="stSidebar"] {
        background: white;
        padding: 2rem 1rem;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #5a67d8;
        font-weight: 600;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s;
        width: 100%;
        margin: 0.5rem 0;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 2rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        color: #718096;
        border: 2px solid #e2e8f0;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
    }
    
    .caption {
        color: #718096;
        font-size: 0.9rem;
        text-align: center;
        margin: 1rem 0;
    }
    
    hr {
        margin: 2rem 0;
        border: none;
        border-top: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

if 'telemetry_data' not in st.session_state:
    st.session_state['telemetry_data'] = []
if 'orbit_frame' not in st.session_state:
    st.session_state['orbit_frame'] = 0
if 'orbit_playing' not in st.session_state:
    st.session_state['orbit_playing'] = False
if 'last_telemetry_update' not in st.session_state:
    st.session_state['last_telemetry_update'] = 0


st.markdown("<h1>🛰️ BioSat-Q+ Mission Control</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtitle'>Quantum-Secured Biomedical Satellite System</p>", unsafe_allow_html=True)

st.sidebar.header("🎮 Mission Controls")
st.sidebar.markdown("---")

st.sidebar.subheader("🔐 QKD & Telemetry")
alt_km = st.sidebar.slider("Altitude (km)", 200, 1200, 500)
inc_deg = st.sidebar.slider("Inclination (deg)", 0, 98, 51)
sat_lat = st.sidebar.slider("Sat sub-latitude", -90, 90, 0)
sat_lon = st.sidebar.slider("Sat sub-longitude", -180, 180, 0)
n_photons = st.sidebar.number_input("Photons per QKD session", 1000, 5000, 2000)
error_prob = st.sidebar.slider("Measurement error prob", 0.0, 0.2, 0.02)

if st.sidebar.button("🔑 Run QKD Session"):
    try:
        r = requests.post(f"{API_ROOT}/qkd/run_session", params={
            "n_photons": n_photons, "alt_km": alt_km, "sat_lat": sat_lat, 
            "sat_lon": sat_lon, "error_prob": error_prob
        }, timeout=10).json()
        st.sidebar.success(f"Added {r.get('added_bits',0)} bits — buffer {r.get('key_buffer_len')}")
    except:
        st.sidebar.error("Backend unreachable")

st.sidebar.markdown("---")

st.sidebar.subheader("🌍 Orbit Simulation")
a = st.sidebar.slider("Semi-Major Axis (km)", 6700.0, 42000.0, 7000.0, step=100.0)
e = st.sidebar.slider("Eccentricity", 0.0, 0.9, 0.3, step=0.01)

if st.sidebar.button("🚀 Run Orbit Simulation"):
    with st.spinner('Calculating orbit...'):
        try:
            response = requests.post(f"{API_ROOT}/simulate_orbit",
                json={"semi_major_axis": a, "eccentricity": e})
            
            if response.status_code == 200 and response.json().get("status") == "success":
                orbit_data = response.json()["data"]
                st.session_state['orbit_data'] = orbit_data
                st.session_state['orbit_calculated'] = True
                st.session_state['orbit_frame'] = 0
                st.session_state['orbit_playing'] = True
                st.sidebar.success("Orbit calculated!")
            else:
                st.sidebar.error("Calculation failed")
        except:
            st.sidebar.error("Backend unreachable")

col1, col2, col3 = st.columns([0.25, 1, 0.5], gap="small")

with col1:
    st.markdown("### 📊 System Status")
    
    try:
        status = requests.get(f"{API_ROOT}/status", timeout=3).json()
        st.success("🟢 Backend Online")
    except:
        status = {"key_buffer_len": 0, "last_qkd": {}}
        st.warning("🔴 Backend Offline")
    
    st.metric("Key Buffer", f"{status.get('key_buffer_len', 0)} bits")
    
    with st.expander("Last QKD Session"):
        st.json(status.get("last_qkd", {}))
    
    if st.button("📡 Ingest Telemetry"):
        try:
            tele = requests.get(f"{API_ROOT}/simtelemetry", timeout=3).json()
            radiation = estimate_radiation(alt_km)
            res = requests.post(f"{API_ROOT}/ingest", json=tele, 
                params={"radiation": radiation}, timeout=5).json()
            st.success("Telemetry ingested")
            with st.expander("Response"):
                st.json(res)
        except:
            st.error("Ingest failed")

with col2:
    st.markdown("### 🌌 Orbital Trajectory")
    if st.session_state.get('orbit_calculated', False):
        data = st.session_state['orbit_data']
        max_r = data['max_radius']
        limit = max_r * 1.1
        current_frame = st.session_state.get('orbit_frame', 0)
        
        path_df = pd.DataFrame({
            'x': data['x_path'],
            'y': data['y_path'],
            'type': 'Orbit Path'
        })
        
        earth_df = pd.DataFrame({'x': [0], 'y': [0], 'type': 'Earth'})
        
        if current_frame < len(data['x_anim']):
            satellite_df = pd.DataFrame({
                'x': [data['x_anim'][current_frame]],
                'y': [data['y_anim'][current_frame]],
                'type': 'Satellite'
            })
        else:
            st.session_state['orbit_frame'] = 0
            st.session_state['orbit_playing'] = False
            satellite_df = pd.DataFrame({
                'x': [data['x_anim'][0]],
                'y': [data['y_anim'][0]],
                'type': 'Satellite'
            })
        
        frame_df = pd.concat([path_df, earth_df, satellite_df], ignore_index=True)
        
        chart = alt.Chart(frame_df).mark_circle().encode(
            x=alt.X('x:Q', scale=alt.Scale(domain=[-limit, limit]), 
                axis=alt.Axis(title='X (km)')),
            y=alt.Y('y:Q', scale=alt.Scale(domain=[-limit, limit]), 
                axis=alt.Axis(title='Y (km)')),
            color=alt.Color('type:N', scale=alt.Scale(
                domain=['Orbit Path', 'Earth', 'Satellite'],
                range=['#cbd5e0', '#4299e1', '#f56565']
            )),
            size=alt.Size('type:N', scale=alt.Scale(
                domain=['Orbit Path', 'Earth', 'Satellite'],
                range=[3, 400, 200]
            ), legend=None),
            tooltip=['type:N', 'x:Q', 'y:Q']
        ).properties(
            width=500,
            height=500
        )
        
        st.altair_chart(chart, use_container_width=False)
        
        st.markdown(f"<p class='caption'>a={data['semi_major_axis']} km, e={data['eccentricity']} | Frame {current_frame + 1}/{len(data['x_anim'])}</p>", unsafe_allow_html=True)
        

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("▶️ Play"):
                st.session_state['orbit_playing'] = True
                st.rerun()
        with col_b:
            if st.button("⏸️ Pause"):
                st.session_state['orbit_playing'] = False
                st.rerun()
        with col_c:
            if st.button("🔄 Reset"):
                st.session_state['orbit_frame'] = 0
                st.session_state['orbit_playing'] = False
                st.rerun()
        
        if st.session_state.get('orbit_playing', False):
            st.session_state['orbit_frame'] = (current_frame + 1) % len(data['x_anim'])
    else:
        st.info("Run orbit simulation in sidebar to visualize")

with col3:
    st.markdown("### 📡 Live Telemetry")
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        run_live = st.checkbox("Auto-poll telemetry", value=False)
    with col_b:
        poll_interval = st.slider("Interval", 1, 5, 1, label_visibility="collapsed")
    
    data_log = st.session_state.get('telemetry_data', [])
    current_time = time.time()
    should_update = run_live and (current_time - st.session_state['last_telemetry_update'] >= poll_interval)
    
    if should_update:
        try:
            tele = requests.get(f"{API_ROOT}/simtelemetry", timeout=3).json()
            radiation = estimate_radiation(alt_km)
            res = requests.post(f"{API_ROOT}/ingest", json=tele, 
                params={"radiation": radiation}, timeout=5).json()
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            data_log.append([
                timestamp, 
                tele["hr"], 
                tele["spo2"], 
                tele["temp"], 
                res.get("ml", {}).get("risk_prob", 0), 
                res.get("secure", False), 
                res.get("key_buffer_len", 0)
            ])
            
            if len(data_log) > 100:
                data_log = data_log[-100:]
            
            st.session_state['telemetry_data'] = data_log
            st.session_state['last_telemetry_update'] = current_time
        except:
            st.error("Backend error")
    
    if data_log:
        df = pd.DataFrame(data_log, 
            columns=["Time", "HR", "SpO2", "Temp", "RiskProb", "Secure", "KeyBufLen"]).set_index("Time")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("💓 Avg HR", f"{df['HR'].mean():.0f} bpm")
        with col_b:
            st.metric("🫁 SpO2", f"{df['SpO2'].mean():.1f}%")
        with col_c:
            latest_risk = df['RiskProb'].iloc[-1]
            st.metric("⚠️ Risk", f"{latest_risk:.1%}")
        
        tab1, tab2 = st.tabs(["📊 Chart", "📋 Table"])
        
        with tab1:
            chart_data = df[["RiskProb", "KeyBufLen"]].fillna(0)
            melted = chart_data.reset_index().melt('Time', var_name='Metric', value_name='Value')
            
            chart = alt.Chart(melted).mark_line(point=True, strokeWidth=2).encode(
                x=alt.X('Time:N', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Value:Q'),
                color=alt.Color('Metric:N', scale=alt.Scale(
                    domain=['RiskProb', 'KeyBufLen'],
                    range=['#f56565', '#48bb78']
                )),
                tooltip=['Time', 'Metric', 'Value']
            ).properties(height=300)
            
            st.altair_chart(chart, use_container_width=True)
        
        with tab2:
            st.dataframe(df.tail(10), use_container_width=True)
    else:
        st.info("Enable auto-poll to stream telemetry")


needs_rerun = False
if st.session_state.get('orbit_playing', False):
    needs_rerun = True
    time.sleep(0.05)
elif run_live:
    needs_rerun = True
    time.sleep(0.5)

if needs_rerun:
    st.rerun()

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #718096; padding: 1rem;'>
    <p><strong>BioSat-Q+</strong> | Quantum-Secured Biomedical Satellite System</p>
    <p style='font-size: 0.9rem;'>QKD & Quantum ML simulated for demo | BioSat-Q.tech</p>
</div>
""", unsafe_allow_html=True)