import asyncio
import time
from datetime import datetime
import subprocess, shlex, re, csv, os
import requests
try:
    from kasa import SmartPlug  # modern version
except ImportError:
    from kasa.iot import IotPlug as SmartPlug  # legacy / fallback version
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


# ==============================
# CONFIG
# ==============================
cmd = "govee2mqtt/target/debug/govee serve --govee-email hebardiansbehardians@gmail.com --govee-password 777Markofthebeast!"
PUMP_IP = "192.168.0.10"
HEATER_IP = "192.168.0.8"

CHECK_INTERVAL = 60       # check every 1 minute
LOG_INTERVAL = 600        # record every 10 minutes when conditions are met
HOT_TUB_MARKER = 'Hot Tub Thermometer\\'
HOT_TUB_OFFSET = 159
SOLAR_MARKER = 'Solar Thermometer\\'
SOLAR_OFFSET = 104
int_pattern = re.compile(r"(\d+),")

# Weather API Configuration for zip code 95060
ZIP_CODE = "95060"
# Coordinates for Santa Cruz, CA (zip 95060): 36.974, -122.031
LATITUDE = 36.974
LONGITUDE = -122.031

# ==============================
# TEMP PARSER
# ==============================
def extract_temp_f(output, marker, offset):
    idx = output.find(marker)
    if idx == -1:
        return None
    snippet = output[idx + len(marker) + offset : idx + len(marker) + offset + 20]
    match = int_pattern.search(snippet)
    if not match:
        return None
    celsius = int(match.group(1)) / 100
    return round((celsius * 9/5) + 32, 2)

# ==============================
# WEATHER API
# ==============================
def get_local_temperature():
    """
    Fetch local temperature for zip code 95060 using National Weather Service API.
    Returns temperature in Fahrenheit or None if fetch fails.
    """
    try:
        # Use National Weather Service API (free, no key required)
        headers = {'User-Agent': 'Hot Tub Controller (contact: hebardiansbehardians@gmail.com)'}
        
        # Get grid point data for the location
        point_url = f'https://api.weather.gov/points/{LATITUDE},{LONGITUDE}'
        point_response = requests.get(point_url, headers=headers, timeout=10)
        
        if point_response.status_code == 200:
            point_data = point_response.json()
            forecast_url = point_data['properties']['forecastHourly']
            
            # Get current temperature from hourly forecast
            forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
            
            if forecast_response.status_code == 200:
                forecast_data = forecast_response.json()
                current_temp_f = forecast_data['properties']['periods'][0]['temperature']
                return round(float(current_temp_f), 2)
    except Exception as e:
        print(f"[WARN] Could not fetch local temperature: {e}")
    
    return None

# ==============================
# LOG FILE SETUP
# ==============================
os.makedirs("data", exist_ok=True)
csv_path = os.path.join("data", "calibration_log.csv")
if not os.path.exists(csv_path):
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "HotTub_F", "Solar_F", "Delta", "Pump", "Heater", "LocalTemp_F"])

# ==============================
# STATE FUNCTIONS
# ==============================
async def get_plug_state(ip):
    plug = SmartPlug(ip)
    try:
        await plug.update()
        return plug.is_on
    except Exception as e:
        print(f"[WARN] Could not read plug {ip}: {e}")
        return None

def get_temps():
    try:
        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
        output = str(result)
        t_tub = extract_temp_f(output, HOT_TUB_MARKER, HOT_TUB_OFFSET)
        t_solar = extract_temp_f(output, SOLAR_MARKER, SOLAR_OFFSET)
        return t_tub, t_solar
    except Exception as e:
        print(f"[WARN] Failed to read temps: {e}")
        return None, None

# ==============================
# MAIN LOOP
# ==============================
last_log_time = 0

while True:
    try:
        pump_state = asyncio.run(get_plug_state(PUMP_IP))
        heater_state = asyncio.run(get_plug_state(HEATER_IP))
        now = datetime.now()

        if pump_state and not heater_state:
            # Eligible for calibration logging
            if (time.time() - last_log_time) >= LOG_INTERVAL:
                t_tub, t_solar = get_temps()
                if t_tub is not None and t_solar is not None:
                    delta = round(t_solar - t_tub, 2)
                    local_temp = get_local_temperature()
                    local_temp_str = f"{local_temp}" if local_temp is not None else "N/A"
                    
                    with open(csv_path, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                            t_tub, t_solar, delta,
                            "ON" if pump_state else "OFF",
                            "ON" if heater_state else "OFF",
                            local_temp_str
                        ])
                    
                    local_temp_display = f"{local_temp}°F" if local_temp is not None else "N/A"
                    print(f"[{now}] Logged calibration sample: Tub={t_tub}°F | Solar={t_solar}°F | Δ={delta}°F | Local={local_temp_display}")
                    last_log_time = time.time()
                else:
                    print(f"[{now}] Skipped log — temperature read failed.")
            else:
                print(f"[{now}] Conditions met — waiting for next 10-min log.")
        else:
            print(f"[{now}] Conditions not met (Pump:{pump_state}, Heater:{heater_state}).")

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        break
    except Exception as e:
        print(f"[ERROR] {e}")
        time.sleep(CHECK_INTERVAL)
