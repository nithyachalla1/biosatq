import uvicorn
import json
from fastapi import FastAPI, Request
from pydantic import BaseModel
from biosat_core import (get_demo_telemetry, OrbitSimulator,
                         estimate_radiation, sat_ground_distance_km,
                         trans_prob_from_distance, transmit_bb84,
                         aesgcm_encrypt_with_bits, aesgcm_decrypt_with_bits,
                         predict_risk)
from biosat_core import orbit_sim 


app = FastAPI(title="BioSat-Q+ Backend")

KEY_BUFFER = ""  
LAST_QKD = {}

GS_LAT, GS_LON = 0.0, 0.0

class OrbitParams(BaseModel):
    """Defines the input parameters for the orbital calculation."""
    semi_major_axis: float = 7000.0
    eccentricity: float = 0.3


@app.post("/simulate_orbit")
async def simulate_orbit(params: OrbitParams):
    """
    Calculates the satellite's trajectory based on semi-major axis (a) 
    and eccentricity (e) and returns the coordinates for frontend plotting.
    """
    try:
        trajectory_data = orbit_sim.calculate_orbit(
            a=params.semi_major_axis, 
            e=params.eccentricity
        )
        return {
            "status": "success",
            "data": trajectory_data
        }
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"An unexpected error occurred during orbit simulation: {str(e)}"
        }


@app.post("/qkd/run_session")
async def run_qkd(n_photons: int = 2000, alt_km: float = 500.0, sat_lat: float = 0.0, sat_lon: float = 0.0, error_prob: float = 0.02):
    d = sat_ground_distance_km(alt_km, GS_LAT, GS_LON, sat_lat, sat_lon)
    trans_prob = trans_prob_from_distance(d)
    res = transmit_bb84(n_photons, trans_prob, error_prob)
    global KEY_BUFFER, LAST_QKD
    KEY_BUFFER += res["sifted_key"]
    LAST_QKD = {"distance_km": d, "trans_prob": trans_prob, **res}
    return {"added_bits": res["R_secure_bits"], "key_buffer_len": len(KEY_BUFFER), "qkd_stats": LAST_QKD}

@app.post("/ingest")
async def ingest(request: Request):
    data = await request.json()
    global KEY_BUFFER
    payload_bytes = json.dumps(data).encode()
    try:
        radiation = float(request.query_params.get("radiation", 0.1))
    except ValueError:
        radiation = 0.1

    if len(KEY_BUFFER) >= 128:
        key_bits = KEY_BUFFER[:128]
        KEY_BUFFER = KEY_BUFFER[128:]
        
        ct = aesgcm_encrypt_with_bits(key_bits, payload_bytes)
        
        try:
            pt = aesgcm_decrypt_with_bits(key_bits, ct)
            telemetry = json.loads(pt.decode())
        except Exception as e:
            telemetry = data 
            return {"status":"error", "error": f"Decryption Failed: {str(e)}", "key_buffer_len": len(KEY_BUFFER)}
        
        ml_res = predict_risk(
            telemetry.get("hr", 75), 
            telemetry.get("spo2", 98), 
            telemetry.get("temp", 36.5), 
            radiation
        )
        return {"status":"ok", "secure":True, "ml": ml_res, "key_buffer_len": len(KEY_BUFFER)}
    else:
        ml_res = predict_risk(
            data.get("hr", 75), 
            data.get("spo2", 98), 
            data.get("temp", 36.5), 
            radiation
        )
        return {"status":"ok", "secure":False, "ml": ml_res, "reason":"not_enough_qkd_bits", "key_buffer_len": len(KEY_BUFFER)}

@app.get("/status")
async def status():
    return {"key_buffer_len": len(KEY_BUFFER), "last_qkd": LAST_QKD}

@app.get("/simtelemetry")
async def simtelemetry():
    return get_demo_telemetry()

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

