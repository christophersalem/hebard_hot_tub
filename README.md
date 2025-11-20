# Steps to configure a new linux machine
```bash
#Clone this repo and cd into it

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

sudo apt update
sudo apt install -y build-essential pkg-config libssl-dev libdbus-1-dev libbluetooth-dev
curl https://sh.rustup.rs -sSf | sh
source $HOME/.cargo/env

git clone https://github.com/wez/govee2mqtt.git
cd govee2mqtt
cargo build
  #(this last step takes a while)
```
---
Below is chatGPT's generated README
# 🌡️ Hot Tub Controller

A Python-based automation script that monitors **hot tub** and **solar heater** temperatures and controls a **Kasa smart plug** to optimize energy use.  
It also logs data locally and pushes updates to a **Google Sheet** for remote monitoring.

---

## ⚙️ Features
- Reads real-time temperature data from **Govee Bluetooth sensors** (via `govee2mqtt`)
- Calculates temperature difference (Δ = Solar - Tub)
- Turns the **solar heater pump ON/OFF** based on configurable thresholds
- Enforces **minimum ON/OFF times** to prevent short cycling
- Pushes readings and actions to a live **Google Sheet**
- Maintains daily log files (`data/log_YYYY-MM-DD.txt`)

---

## 🧩 Requirements
- Python **3.10+** (or 3.9+ if using `main_script_fixed_optional.py`)
- Works on Linux, macOS, and Raspberry Pi  
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```
  or manually:
  ```bash
  pip install python-kasa requests aiohttp cryptography
  ```

If you’re on MX Linux or Debian-based systems, you may also need:
```bash
sudo apt install build-essential pkg-config libssl-dev libffi-dev python3-dev cargo
```

---

## 🗂️ Project Structure
```
hot_tub_controller/
├── main_script.py              # Primary controller script
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── data/                       # Log files (auto-generated)
└── .gitignore                  # Ignore data and venv files
```

---

## 🚀 Setup & Usage

### Clone the repo
```bash
git clone https://github.com/yourusername/hot_tub_controller.git
cd hot_tub_controller
```

### Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the script
```bash
python main_script.py
```

### View logs
```bash
tail -f data/log_2025-10-30.txt
```

---

## 🧠 How It Works
1. The script runs your local `govee2mqtt` command to read sensor data.  
2. It extracts temperature values using pattern offsets and regex.  
3. Compares **Solar vs. Hot Tub** temperature (Δ).  
4. Uses thresholds:  
   - **ON:** Δ > 6°F  
   - **OFF:** Δ < 4°F  
5. Sends data to your Google Sheet endpoint:  
   ```
   https://script.google.com/macros/s/AKfycbz1rrC8Rji1GdDJo6H7GixEkmUKfT52gZ4sFF7YDRhR1-OPiHO4fRLTTNHkN4ahc1A/exec
   ```

---

## 🔒 Safety
- Built-in **failsafe** shuts off the pump after 3 consecutive read failures.  
- Log rollover occurs automatically every 24 hours.  

---

## 🧰 Optional Commands
Run in background:
```bash
nohup python main_script.py > controller.log 2>&1 &
```

Stop:
```bash
pkill -f main_script.py
```

Or use `screen` for live SSH log viewing:
```bash
screen -S hottub
python main_script.py
```

---

## 🪄 Credits
- Developed by **Chris Salem**  
- Powered by [Govee2MQTT](https://github.com/wez/govee2mqtt) and [python-kasa](https://github.com/python-kasa/python-kasa)

---

## 🧾 License
MIT License – feel free to modify, improve, and share.
