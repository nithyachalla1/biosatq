import numpy as np

R_EARTH_KM = 6371.0
MU = 398600.4418 # km^3/s^2

class ConstellationSimulator:
    """Simulates a basic constellation of satellites for proximity detection."""
    def __init__(self, count=20, alt_km=600.0, inc_deg=86.0):
        self.count = count
        self.a = R_EARTH_KM + alt_km
        self.inc_deg = inc_deg
        np.random.seed(42)
        self.e_list = np.random.uniform(0.01, 0.05, count)
        self.theta_offset = np.random.uniform(0, 2 * np.pi, count)

    def get_positions(self, current_phase):
        """Calculates the current 3D position of all constellation satellites."""
        positions = []
        for i in range(self.count):
            theta = 2 * np.pi * (current_phase + self.theta_offset[i]) % (2 * np.pi)
            e = self.e_list[i]
            
            r = (self.a * (1 - e**2)) / (1 + e * np.cos(theta))
            
            x_orbit = r * np.cos(theta)
            y_orbit = r * np.sin(theta)
            

            x_inclined = x_orbit * np.cos(np.deg2rad(self.inc_deg))
            y_inclined = y_orbit
            
            positions.append({'r': r, 'x': x_inclined, 'y': y_inclined})

        return positions

class OrbitSimulator:
    def __init__(self, alt_km=500.0, inc_deg=51.6):
        self.alt_km = float(alt_km)
        self.inc_deg = float(inc_deg)

    def orbital_period_min(self):
        a = R_EARTH_KM + self.alt_km
        T = 2 * np.pi * np.sqrt(a**3 / MU) # seconds
        return float(T/60.0)

    def subpoint(self, phase=0.0):
        theta = 2 * np.pi * (phase % 1.0)
        lat = (self.inc_deg) * np.sin(theta)
        lon = (np.degrees(theta) + 180) % 360 - 180
        return float(lat), float(lon)

def sat_ground_distance_km(alt_km, gs_lat_deg=0.0, gs_lon_deg=0.0, sat_lat_deg=0.0, sat_lon_deg=0.0):
    def sph_to_cart(lat, lon, r):
        lr = np.deg2rad(lat); lo = np.deg2rad(lon)
        x = r * np.cos(lr) * np.cos(lo)
        y = r * np.cos(lr) * np.sin(lo)
        z = r * np.sin(lr)
        return np.array([x,y,z])
    sat_r = R_EARTH_KM + alt_km
    sat_cart = sph_to_cart(sat_lat_deg, sat_lon_deg, sat_r)
    gs_cart = sph_to_cart(gs_lat_deg, gs_lon_deg, R_EARTH_KM)
    return float(np.linalg.norm(sat_cart - gs_cart))

def estimate_radiation(alt_km):
    return float(np.clip((alt_km - 200.0) / 800.0, 0.0, 1.0))

def calculate_orbit(a: float, e: float) -> dict:
    """
    Calculates the full elliptical orbit path and 1000 animation points.
    Includes constellation position data for each animation frame.
    """
    if not (0 <= e < 1):
        if e < 0: e = 0.0
        if e >= 1: e = 0.99 
        
    theta_path = np.linspace(0, 2 * np.pi, 500)
    r_path = (a * (1 - e**2)) / (1 + e * np.cos(theta_path))
    x_path = r_path * np.cos(theta_path)
    y_path = r_path * np.sin(theta_path)

    num_frames = 1000
    phase_anim = np.linspace(0, 1.0, num_frames, endpoint=False)
    theta_anim = 2 * np.pi * phase_anim
    
    r_anim = (a * (1 - e**2)) / (1 + e * np.cos(theta_anim))
    x_anim = r_anim * np.cos(theta_anim)
    y_anim = r_anim * np.sin(theta_anim)
    

    max_r = np.max(r_path)

    return {
        "x_path": x_path.tolist(),
        "y_path": y_path.tolist(),
        "x_anim": x_anim.tolist(),
        "y_anim": y_anim.tolist(),
        "max_radius": float(max_r),
        "semi_major_axis": a,
        "eccentricity": e,
        "earth_radius": R_EARTH_KM 
    }
