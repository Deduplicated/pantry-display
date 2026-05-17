# Pantry Display

A local-network kitchen display that shows fresh produce sorted by expiry date on a Waveshare 7.5" black-and-white e-paper HAT connected to a Raspberry Pi Zero 2 W. A mobile-friendly web UI lets you manage items from your phone.

---

## Hardware


| Component                       | Notes                           |
| ------------------------------- | ------------------------------- |
| Raspberry Pi Zero 2 W / WH      | Any Pi with 40-pin header works |
| Waveshare 7.5" e-Paper HAT (v2) | 800 × 480, black & white        |


---

## Project structure

```
pantry-display/
  app.py          Flask web server and API routes
  db.py           SQLite helpers
  display.py      Pillow renderer + Waveshare driver wrapper
  defaults.py     Default produce shelf-life dictionary
  requirements.txt
  templates/
    index.html    Mobile web UI
  static/
    styles.css
    app.js
```

---

## Raspberry Pi OS setup

### 1. Flash the SD card

Download **Raspberry Pi OS Lite (64-bit)** from [raspberrypi.com/software](https://www.raspberrypi.com/software/). Use Raspberry Pi Imager to flash and pre-configure:

- Hostname: `pantry` (or your choice)
- Enable SSH
- Set your Wi-Fi SSID and password

### 2. Enable SPI (required for the e-paper HAT)

SSH in, then:

```bash
sudo raspi-config
```

Navigate to **Interface Options → SPI → Enable**, then reboot.

Alternatively, add the following line to `/boot/config.txt` and reboot:

```
dtparam=spi=on
```

Verify SPI is active after reboot:

```bash
ls /dev/spi*
# Should show: /dev/spidev0.0  /dev/spidev0.1
```

### 3. Install system dependencies

On **Debian Bookworm / Trixie** (current Raspberry Pi OS), some older package names no longer exist:

- `libtiff5` was replaced by `**libtiff6`**
- `**libatlas-base-dev`** is gone and **not needed** here — NumPy/Pillow install from pre-built wheels for this app

Install the essentials plus common Pillow image libraries (harmless if already present):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git fonts-liberation \
    libopenjp2-7 libtiff6 zlib1g libjpeg62-turbo
```

If `apt` reports that `libopenjp2-7` has no candidate (some releases use a `t64` rename), install the suggested alternative it prints, or omit it — the PyPI **Pillow** wheel usually bundles what it needs for basic use.

Minimal install (often enough when using `pip install pillow` wheels):

```bash
sudo apt install -y python3 python3-venv git fonts-liberation
```

### 4. Clone or copy this project onto the Pi

```bash
cd ~
git clone <your-repo-url> pantry-display
# — or — copy the folder via scp / rsync
```

### 5. Create a virtual environment and install dependencies

```bash
cd ~/pantry-display
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 6. Install the Waveshare e-paper library

The Waveshare library is not on PyPI. Clone their repo and install it into your venv:

```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
pip install .
```

> **Driver version note:** The code in `display.py` uses the `epd7in5_V2` driver.
> If you have a different version of the HAT (v1, v3, etc.), edit the import
> line marked `# WAVESHARE DRIVER IMPORT` in `display.py`:
>
> ```python
> from waveshare_epd import epd7in5_V2 as epd_driver   # ← change this
> ```

---

## Running the app

### Development mode (no hardware required)

Set the `DEV_MODE` environment variable to skip all hardware calls. The rendered image is saved as `preview.png` and served at `/preview.png`.

```bash
DEV_MODE=1 python app.py
```

Open `http://localhost:5000` in your browser (or `http://pantry.local:5000` from your phone if on the same Wi-Fi).

### Production mode (with e-paper hardware)

```bash
cd ~/pantry-display
source .venv/bin/activate
python app.py
```

Open `http://pantry.local:5000` from your phone.

---

## Raspberry Pi hardware Python packages

After `pip install -r requirements.txt`, install the e-paper extras (inside your venv):

```bash
pip install -r requirements-pi.txt
cd ~/e-Paper/RaspberryPi_JetsonNano/python && pip install .
```

If `lgpio` fails to build, install `sudo apt install -y swig liblgpio-dev` first.

---

## Run constantly (systemd + daily refresh)

The app refreshes the e-paper when you add or delete items. A **daily timer** at 07:00 updates the dates on the panel even if nothing changed.

From the project directory on the Pi:

```bash
cd ~/pantry-display
git pull
sudo bash deploy/install-services.sh
```

This installs:

- `pantry-display.service` — Flask on port 5000, starts on boot, restarts on failure
- `pantry-refresh.timer` — runs `scripts/daily_refresh.py` every day at 07:00

Do **not** set `DEV_MODE=1` in the service when using the real HAT.

Check status:

```bash
sudo systemctl status pantry-display
sudo systemctl list-timers pantry-refresh.timer
sudo journalctl -u pantry-display -f
```

To stop the manual `python app.py` session first (only one process should bind port 5000):

```bash
sudo systemctl stop pantry-display   # if testing manually
# or Ctrl+C in the terminal running python app.py, then:
sudo systemctl start pantry-display
```

---

## Finding the Pi's address on your phone

If mDNS is working, `http://pantry.local:5000` should resolve automatically on iOS and macOS.

If it does not, find the Pi's IP address:

```bash
hostname -I
```

Then open `http://<ip-address>:5000` on your phone.

---

## Checking logs

```bash
sudo journalctl -u pantry-display -f
```

---

## Resetting the database

```bash
rm ~/pantry-display/pantry.db
python app.py   # recreates the table on startup
```

