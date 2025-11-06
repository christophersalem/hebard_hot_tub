import asyncio
import time
from datetime import datetime
import subprocess, shlex, re, csv, os
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
SOLAR_MARKER = 'Solar heater\\'
SOLAR_OFFSET = 104
int_pattern = re.compile(r"(\d+),")

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
# LOG FILE SETUP
# ==============================
os.makedirs("data", exist_ok=True)
csv_path = os.path.join("data", "calibration_log.csv")
if not os.path.exists(csv_path):
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "HotTub_F", "Solar_F", "Delta", "Pump", "Heater"])

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
                    with open(csv_path, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                            t_tub, t_solar, delta,
                            "ON" if pump_state else "OFF",
                            "ON" if heater_state else "OFF"
                        ])
                    print(f"[{now}] Logged calibration sample: Tub={t_tub}°F | Solar={t_solar}°F | Δ={delta}°F")
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
