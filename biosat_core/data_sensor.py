import time, random

def get_demo_telemetry():
    ts = int(time.time()*1000)
    hr = int(max(50, min(120, 75 + random.gauss(0,6))))
    spo2 = int(max(85, min(100, 98 + random.gauss(0,1.2))))
    temp = round(max(34.0, min(40.0, 36.5 + random.gauss(0,0.3))),2)
    return {"ts": ts, "hr": hr, "spo2": spo2, "temp": temp, "device":"ARD01"}
