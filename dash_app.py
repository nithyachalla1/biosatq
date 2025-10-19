import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objs as go
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add parent directory to path to import biosat_core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from biosat_core import OrbitSimulator, estimate_radiation
except ImportError:
    # Fallback: define a simple estimate_radiation function if module not found
    def estimate_radiation(alt_km):
        """Simple radiation estimation based on altitude"""
        return 0.1 + (alt_km / 1000) * 0.05

API_ROOT = "http://localhost:8000"

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "BioSat-Q+ Dashboard"

# --- LAYOUT ---
app.layout = html.Div([
    html.H1("BioSat-Q+ Dashboard", style={'textAlign': 'center'}),
    
    html.Div([
        # --- SIDEBAR ---
        html.Div([
            html.H3("Mission Controls"),
            
            html.H4("QKD & Telemetry"),
            html.Label("Altitude (km)"),
            dcc.Slider(id='alt-slider', min=200, max=1200, value=500, step=10, 
                      marks={200: '200', 500: '500', 800: '800', 1200: '1200'}),
            
            html.Label("Inclination (deg)"),
            dcc.Slider(id='inc-slider', min=0, max=98, value=51, step=1,
                      marks={0: '0', 51: '51', 98: '98'}),
            
            html.Label("Sat sub-latitude"),
            dcc.Slider(id='sat-lat-slider', min=-90, max=90, value=0, step=1,
                      marks={-90: '-90', 0: '0', 90: '90'}),
            
            html.Label("Sat sub-longitude"),
            dcc.Slider(id='sat-lon-slider', min=-180, max=180, value=0, step=1,
                      marks={-180: '-180', 0: '0', 180: '180'}),
            
            html.Label("Photons per QKD session"),
            dcc.Input(id='n-photons', type='number', value=2000, min=1000, max=5000),
            
            html.Label("Measurement error prob"),
            dcc.Slider(id='error-prob-slider', min=0.0, max=0.2, value=0.02, step=0.01,
                      marks={0: '0', 0.1: '0.1', 0.2: '0.2'}),
            
            html.Button('Run QKD Session', id='run-qkd-btn', n_clicks=0),
            html.Div(id='qkd-output', style={'marginTop': '10px'}),
            
            html.Hr(),
            
            html.H4("Orbit Simulation"),
            html.Label("Semi-Major Axis (a, km)"),
            dcc.Slider(id='sma-slider', min=6700, max=42000, value=7000, step=100,
                      marks={6700: '6700', 20000: '20000', 42000: '42000'}),
            
            html.Label("Eccentricity (e, 0=Circular)"),
            dcc.Slider(id='ecc-slider', min=0.0, max=0.9, value=0.3, step=0.01,
                      marks={0: '0', 0.5: '0.5', 0.9: '0.9'}),
            
            html.Button('Run Orbit Simulation', id='run-orbit-btn', n_clicks=0),
            html.Div(id='orbit-status', style={'marginTop': '10px'}),
            
        ], style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
        
        # --- MAIN CONTENT ---
        html.Div([
            # System Status
            html.Div([
                html.H3("System Status"),
                html.Div(id='system-status'),
                html.Button('Ingest Simulated Telemetry', id='ingest-btn', n_clicks=0),
                html.Div(id='ingest-output'),
            ], style={'width': '30%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
            
            # Orbit Animation
            html.Div([
                html.H3("Orbital Trajectory Animation"),
                dcc.Graph(id='orbit-graph', style={'height': '600px'}),
                dcc.Interval(id='orbit-interval', interval=50, disabled=True, n_intervals=0),
            ], style={'width': '35%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
            
            # Live Telemetry
            html.Div([
                html.H3("Live Telemetry Stream"),
                dcc.Checklist(id='auto-poll', options=[{'label': 'Auto-poll telemetry', 'value': 'on'}], value=[]),
                html.Label("Poll interval (s)"),
                dcc.Slider(id='poll-interval', min=1, max=5, value=1, step=1,
                          marks={1: '1', 3: '3', 5: '5'}),
                html.Div(id='telemetry-output'),
                dcc.Graph(id='telemetry-chart'),
                dcc.Interval(id='telemetry-interval', interval=1000, disabled=True),
            ], style={'width': '35%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'}),
            
        ], style={'width': '80%', 'display': 'inline-block'}),
    ]),
    
    html.Hr(),
    html.P("Notes: QKD & quantum ML are simulated for demo purposes. Frontend deployed at BioSat-Q.tech."),
    
    # Hidden divs to store data
    dcc.Store(id='orbit-data-store'),
    dcc.Store(id='telemetry-data-store', data=[]),
], style={'fontFamily': 'Arial, sans-serif'})

# --- CALLBACKS ---

# System Status Update
@app.callback(
    Output('system-status', 'children'),
    Input('orbit-interval', 'n_intervals')  # Update periodically
)
def update_status(n):
    try:
        status = requests.get(f"{API_ROOT}/status", timeout=3).json()
        return html.Div([
            html.P(f"Key buffer length: {status.get('key_buffer_len', 0)} bits", style={'fontWeight': 'bold'}),
            html.P("Last QKD Session:"),
            html.Pre(str(status.get('last_qkd', {})))
        ])
    except:
        return html.Div([
            html.P("Backend service connection lost.", style={'color': 'orange'}),
            html.P("Key buffer length: 0 bits")
        ])

# QKD Session
@app.callback(
    Output('qkd-output', 'children'),
    Input('run-qkd-btn', 'n_clicks'),
    State('n-photons', 'value'),
    State('alt-slider', 'value'),
    State('sat-lat-slider', 'value'),
    State('sat-lon-slider', 'value'),
    State('error-prob-slider', 'value')
)
def run_qkd(n_clicks, n_photons, alt_km, sat_lat, sat_lon, error_prob):
    if n_clicks == 0:
        return ""
    try:
        r = requests.post(f"{API_ROOT}/qkd/run_session", params={
            "n_photons": n_photons, "alt_km": alt_km, "sat_lat": sat_lat, 
            "sat_lon": sat_lon, "error_prob": error_prob
        }, timeout=10).json()
        return html.Div(f"✓ Added {r.get('added_bits',0)} bits — buffer {r.get('key_buffer_len')}", 
                       style={'color': 'green'})
    except:
        return html.Div("✗ Backend unreachable", style={'color': 'red'})

# Orbit Simulation Start
@app.callback(
    [Output('orbit-data-store', 'data'),
     Output('orbit-status', 'children'),
     Output('orbit-interval', 'disabled')],
    Input('run-orbit-btn', 'n_clicks'),
    State('sma-slider', 'value'),
    State('ecc-slider', 'value')
)
def start_orbit_simulation(n_clicks, a, e):
    if n_clicks == 0:
        return None, "", True
    
    try:
        response = requests.post(
            f"{API_ROOT}/simulate_orbit",
            json={"semi_major_axis": a, "eccentricity": e}
        )
        
        if response.status_code == 200 and response.json().get("status") == "success":
            orbit_data = response.json()["data"]
            orbit_data['current_frame'] = 0
            return orbit_data, html.Div("✓ Orbit Calculated! Animating...", style={'color': 'green'}), False
        else:
            return None, html.Div(f"✗ Error: {response.json().get('message', 'Unknown')}", 
                                 style={'color': 'red'}), True
    except:
        return None, html.Div("✗ Backend unreachable", style={'color': 'red'}), True

# Orbit Animation Update
@app.callback(
    [Output('orbit-graph', 'figure'),
     Output('orbit-data-store', 'data', allow_duplicate=True),
     Output('orbit-interval', 'disabled', allow_duplicate=True)],
    Input('orbit-interval', 'n_intervals'),
    State('orbit-data-store', 'data'),
    prevent_initial_call=True
)
def update_orbit_animation(n_intervals, orbit_data):
    if not orbit_data:
        empty_fig = go.Figure()
        empty_fig.update_layout(title="Click 'Run Orbit Simulation' to visualize")
        return empty_fig, None, True
    
    current_frame = orbit_data.get('current_frame', 0)
    
    # Check if animation is complete
    if current_frame >= len(orbit_data['x_anim']):
        orbit_data['current_frame'] = 0  # Reset for replay
        return dash.no_update, orbit_data, True  # Stop animation
    
    max_r = orbit_data['max_radius']
    limit = max_r * 1.1
    
    # Create figure
    fig = go.Figure()
    
    # Orbit path (static)
    fig.add_trace(go.Scatter(
        x=orbit_data['x_path'],
        y=orbit_data['y_path'],
        mode='markers',
        marker=dict(size=2, color='lightgray'),
        name='Orbit Path',
        hovertemplate='Orbit Path<br>x: %{x:.1f}<br>y: %{y:.1f}<extra></extra>'
    ))
    
    # Earth (static)
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode='markers',
        marker=dict(size=20, color='blue'),
        name='Earth',
        hovertemplate='Earth<extra></extra>'
    ))
    
    # Satellite (animated)
    fig.add_trace(go.Scatter(
        x=[orbit_data['x_anim'][current_frame]],
        y=[orbit_data['y_anim'][current_frame]],
        mode='markers',
        marker=dict(size=15, color='red'),
        name='Satellite',
        hovertemplate='Satellite<br>x: %{x:.1f}<br>y: %{y:.1f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=f"Elliptical Orbit (a={orbit_data['semi_major_axis']} km, e={orbit_data['eccentricity']})",
        xaxis=dict(title='X (km)', range=[-limit, limit], scaleanchor='y', scaleratio=1),
        yaxis=dict(title='Y (km)', range=[-limit, limit]),
        showlegend=True,
        hovermode='closest',
        height=600
    )
    
    # Increment frame
    orbit_data['current_frame'] = current_frame + 1
    
    return fig, orbit_data, False

# Telemetry Polling Control
@app.callback(
    Output('telemetry-interval', 'disabled'),
    Input('auto-poll', 'value'),
    State('poll-interval', 'value')
)
def toggle_telemetry_polling(auto_poll, poll_interval):
    return 'on' not in auto_poll

# Update poll interval
@app.callback(
    Output('telemetry-interval', 'interval'),
    Input('poll-interval', 'value')
)
def update_poll_interval(interval):
    return interval * 1000

# Telemetry Update
@app.callback(
    [Output('telemetry-output', 'children'),
     Output('telemetry-chart', 'figure'),
     Output('telemetry-data-store', 'data')],
    Input('telemetry-interval', 'n_intervals'),
    State('telemetry-data-store', 'data'),
    State('alt-slider', 'value')
)
def update_telemetry(n, data_log, alt_km):
    if not data_log:
        data_log = []
    
    try:
        tele = requests.get(f"{API_ROOT}/simtelemetry", timeout=3).json()
        radiation = estimate_radiation(alt_km)
        res = requests.post(f"{API_ROOT}/ingest", json=tele, params={"radiation": radiation}, timeout=5).json()
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        data_log.append({
            'Time': timestamp,
            'HR': tele["hr"],
            'SpO2': tele["spo2"],
            'Temp': tele["temp"],
            'RiskProb': res.get("ml", {}).get("risk_prob", 0),
            'Secure': res.get("secure", False),
            'KeyBufLen': res.get("key_buffer_len", 0)
        })
        
        # Keep only last 50 entries
        if len(data_log) > 50:
            data_log = data_log[-50:]
        
        df = pd.DataFrame(data_log)
        
        # Create charts
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Time'], y=df['RiskProb'], name='Risk Prob', mode='lines'))
        fig.add_trace(go.Scatter(x=df['Time'], y=df['KeyBufLen'], name='Key Buffer', mode='lines', yaxis='y2'))
        
        fig.update_layout(
            title="Live Telemetry Metrics",
            xaxis=dict(title='Time'),
            yaxis=dict(title='Risk Probability'),
            yaxis2=dict(title='Key Buffer Length', overlaying='y', side='right'),
            hovermode='x unified'
        )
        
        table = html.Table([
            html.Thead(html.Tr([html.Th(col) for col in df.columns])),
            html.Tbody([
                html.Tr([html.Td(df.iloc[i][col]) for col in df.columns])
                for i in range(max(0, len(df)-10), len(df))
            ])
        ], style={'fontSize': '12px'})
        
        return table, fig, data_log
        
    except:
        return html.Div("Backend error", style={'color': 'red'}), go.Figure(), data_log

# Ingest Telemetry Button
@app.callback(
    Output('ingest-output', 'children'),
    Input('ingest-btn', 'n_clicks'),
    State('alt-slider', 'value')
)
def ingest_telemetry(n_clicks, alt_km):
    if n_clicks == 0:
        return ""
    try:
        tele = requests.get(f"{API_ROOT}/simtelemetry", timeout=3).json()
        radiation = estimate_radiation(alt_km)
        res = requests.post(f"{API_ROOT}/ingest", json=tele, params={"radiation": radiation}, timeout=5).json()
        return html.Pre(str(res))
    except:
        return html.Div("Backend error", style={'color': 'red'})

if __name__ == '__main__':
    app.run(debug=True, port=8050)