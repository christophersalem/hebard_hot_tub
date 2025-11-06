import asyncio

try:
    from kasa import SmartPlug  # modern version
except ImportError:
    from kasa.iot import IotPlug as SmartPlug  # legacy / fallback version
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import subprocess
import shlex
import re
import time
from datetime import datetime, timedelta
from collections import deque
import os
import sys
import requests
from typing import Optional

# ==============================
# CONFIGURATION
# ==============================
cmd = "govee2mqtt/target/debug/govee serve --govee-email hebardiansbehardians@gmail.com --govee-password 777Markofthebeast!"
interval = 600  # seconds between readings
plug_ip = "192.168.0.10"   # Kasa plug controlling solar heater pump
heater_ip = "192.168.0.8"  # Kasa plug controlling hot tub heater

HOT_TUB_MARKER = 'Hot Tub Thermometer\\'
HOT_TUB_OFFSET = 159
SOLAR_MARKER = 'Solar heater\\'
SOLAR_OFFSET = 104

int_pattern = re.compile(r"(\d+),")

DELTA_ON = 6.0
DELTA_OFF = 4.0
MIN_ON_MINUTES = 30
MIN_OFF_MINUTES = 20

SOLAR_LAG_SEC = 0
lag_steps = max(0, int(round(SOLAR_LAG_SEC / interval)))
solar_buffer = deque(maxlen=lag_steps + 1)

pump_on_state = None
pump_on_time = None
pump_off_time = None
read_fail_count = 0
FAILSAFE_THRESHOLD = 3

# ==============================
# GOOGLE SHEET LOGGING
# ==============================
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzj7hDMnP12V0457VYh3NZiaRR7w3f9fzKaQZr7gAcpN2DdwM-KjUsHbB7HKAAyUCcB/exec"

def send_to_google_sheet(temp_tub, temp_solar, delta, pump_state, action, note, heater_state):
    try:
        params = {
            "tub": temp_tub,
            "solar": temp_solar,
            "delta": round(delta, 2),
            "pump": "🔆" if pump_state else "🌙",
            "heater": "🟢" if heater_state else "",
            "action": action,
            "note": note
        }
        requests.get(GOOGLE_SHEET_URL, params=params, timeout=30)
    except Exception as e:
        print(f"Warning: could not send data to Google Sheet ({e})")

# ==============================
# LOGGING SETUP
# ==============================
log_dir = "data"
os.makedirs(log_dir, exist_ok=True)

def open_daily_log():
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(log_dir, f"log_{date_str}.txt")
    return open(filename, "a", buffering=1)

class TeeLogger:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, message):
        for s in self.streams:
            s.write(message)
            s.flush()
    def flush(self):
        for s in self.streams:
            s.flush()

current_log_date = datetime.now().date()
log_file = open_daily_log()
sys.stdout = TeeLogger(sys.__stdout__, log_file)
sys.stderr = TeeLogger(sys.__stderr__, log_file)

def print_header():
    print(f"\n--- Hot Tub Controller Started: {datetime.now().isoformat()} ---")
    print(f"Control rule: Δ = Solar - Tub | ON when Δ > {DELTA_ON}°F | OFF when Δ < {DELTA_OFF}°F")
    print(f"Minimum ON time: {MIN_ON_MINUTES} min | Minimum OFF time: {MIN_OFF_MINUTES} min")
    print(f"Failsafe: shuts off pump after {FAILSAFE_THRESHOLD} consecutive read failures.\n")

print_header()

# ==============================
# FUNCTIONS
# ==============================
def extract_temp_f(output: str, marker: str, offset: int) -> Optional[float]:
    idx = output.find(marker)
    if idx == -1:
        return None
    snippet = output[idx + len(marker) + offset : idx + len(marker) + offset + 20]
    match = int_pattern.search(snippet)
    if not match:
        return None
    value = int(match.group(1))
    celsius = value / 100
    fahrenheit = (celsius * 9 / 5) + 32
    return round(fahrenheit, 2)

async def control_pump(turn_on: bool):
    plug = SmartPlug(plug_ip)
    await plug.update()
    if turn_on and not plug.is_on:
        await plug.turn_on()
        print("Pump turned ON")
    elif not turn_on and plug.is_on:
        await plug.turn_off()
        print("Pump turned OFF")
    else:
        print("Pump state unchanged (already in desired state)")

async def check_heater_state(ip: str) -> bool:
    plug = SmartPlug(ip)
    await plug.update()
    return plug.is_on

# ==============================
# MAIN LOOP
# ==============================
while True:
    try:
        today = datetime.now().date()
        if today != current_log_date:
            log_file.close()
            log_file = open_daily_log()
            sys.stdout = TeeLogger(sys.__stdout__, log_file)
            sys.stderr = TeeLogger(sys.__stderr__, log_file)
            current_log_date = today
            print("\n--- Log Rolled Over ---")
            print_header()

        result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
        output = str(result)

        temp_hot_tub = extract_temp_f(output, HOT_TUB_MARKER, HOT_TUB_OFFSET)
        temp_solar_raw = extract_temp_f(output, SOLAR_MARKER, SOLAR_OFFSET)

        if temp_hot_tub is None or temp_solar_raw is None:
            read_fail_count += 1
            print(f"Warning: Missing temperature data (failure #{read_fail_count})")
            if read_fail_count >= FAILSAFE_THRESHOLD:
                print(f"⚠️  {FAILSAFE_THRESHOLD} consecutive read failures — shutting off pump for safety.")
                asyncio.run(control_pump(False))
                pump_on_state = False
                pump_on_time = None
                pump_off_time = datetime.now()
                read_fail_count = 0
            time.sleep(interval)
            continue
        else:
            read_fail_count = 0

        solar_buffer.append(temp_solar_raw)
        if len(solar_buffer) < solar_buffer.maxlen:
            print("Warming up lag buffer...")
            time.sleep(interval)
            continue

        temp_solar_surface = solar_buffer[0] if lag_steps > 0 else temp_solar_raw
        now = datetime.now()
        print(f"{now.strftime('%Y-%m-%d %H:%M:%S')}")

        delta = temp_solar_surface - temp_hot_tub

        if pump_on_state and pump_on_time:
            elapsed_on = (now - pump_on_time).total_seconds() / 60
            if elapsed_on < MIN_ON_MINUTES:
                print(f"No Change — still within minimum ON time ({elapsed_on:.1f}/{MIN_ON_MINUTES} min)")
                print(f"Hot Tub: {temp_hot_tub}°F | Solar Surface: {temp_solar_surface}°F | Δ = {round(delta, 2)}°F")
                print(f"[STATUS] 🔆 Pump: ON | Current run time: {elapsed_on:.1f} min\n")
                heater_on = asyncio.run(check_heater_state(heater_ip))
                send_to_google_sheet(temp_hot_tub, temp_solar_surface, delta, True, "No Change", "Within minimum ON time", heater_on)
                time.sleep(interval)
                continue

        if (not pump_on_state) and pump_off_time:
            elapsed_off = (now - pump_off_time).total_seconds() / 60
            if elapsed_off < MIN_OFF_MINUTES:
                print(f"No Change — still within minimum OFF time ({elapsed_off:.1f}/{MIN_OFF_MINUTES} min)")
                print(f"Hot Tub: {temp_hot_tub}°F | Solar Surface: {temp_solar_surface}°F | Δ = {round(delta, 2)}°F")
                print(f"[STATUS] 🌙 Pump: OFF | Current off time: {elapsed_off:.1f} min\n")
                heater_on = asyncio.run(check_heater_state(heater_ip))
                send_to_google_sheet(temp_hot_tub, temp_solar_surface, delta, False, "No Change", "Within minimum OFF time", heater_on)
                time.sleep(interval)
                continue

        if (pump_on_state is None or not pump_on_state) and delta > DELTA_ON:
            asyncio.run(control_pump(True))
            pump_on_state = True
            pump_on_time = now
            pump_off_time = None
            action = "ON"
            note = f"Δ > {DELTA_ON}°F → pump turned on"
        elif pump_on_state and delta < DELTA_OFF:
            asyncio.run(control_pump(False))
            pump_on_state = False
            pump_off_time = now
            pump_on_time = None
            action = "OFF"
            note = f"Δ < {DELTA_OFF}°F → pump turned off"
        elif not pump_on_state and delta <= 0:
            action = "No Change"
            note = "Solar colder — pump remains off"
        elif pump_on_state and delta >= 0:
            action = "No Change"
            note = "Solar still warmer — pump stays on"
        else:
            action = "No Change"
            note = "Within hysteresis range"

        print(f"Hot Tub: {temp_hot_tub}°F | Solar Surface: {temp_solar_surface}°F | Δ = {round(delta, 2)}°F")

        emoji = "🔆" if pump_on_state else "🌙"
        print(f"[STATUS] {emoji} Pump: {'ON' if pump_on_state else 'OFF'}\n")

        heater_on = asyncio.run(check_heater_state(heater_ip))
        send_to_google_sheet(temp_hot_tub, temp_solar_surface, delta, pump_on_state, action, note, heater_on)
        time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped by user.")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(interval)

log_file.close()
