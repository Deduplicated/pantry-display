# Pantry Display

A local-network kitchen display that shows fresh produce sorted by expiry date on a Waveshare 7.5" black-and-white e-paper HAT connected to a Raspberry Pi Zero 2 W. A mobile-friendly web UI lets you manage items from your phone.

---

## Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi Zero 2 W / WH | Any Pi with 40-pin header works |
| Waveshare 7.5" e-Paper HAT (v2) | 800 × 480, black & white |

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

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git \
    libopenjp2-7 libtiff5 libatlas-base-dev fonts-liberation
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

## Run as a systemd service (auto-start on boot)

Create the service file:

```bash
sudo nano /etc/systemd/system/pantry-display.service
```

Paste the following (adjust paths if your username is not `pi`):

```ini
[Unit]
Description=Pantry Display Flask App
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/pantry-display
ExecStart=/home/pi/pantry-display/.venv/bin/python app.py
Restart=on-failure
RestartSec=5
# Remove the line below when running with real e-paper hardware
Environment=DEV_MODE=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pantry-display
sudo systemctl start pantry-display
sudo systemctl status pantry-display
```

---

## Daily display refresh (countdown updates)

The display auto-refreshes when items are added or deleted. To also update the day-countdown each morning, add a scheduled job.

### Option A — cron

```bash
crontab -e
```

Add this line to refresh the display at 07:00 every day:

```cron
0 7 * * * /home/pi/pantry-display/.venv/bin/python -c "import db, display; db.init_db(); display.refresh_display(db.get_all_items())"
```

### Option B — systemd timer

Create `/etc/systemd/system/pantry-refresh.service`:

```ini
[Unit]
Description=Pantry Display daily refresh

[Service]
User=pi
WorkingDirectory=/home/pi/pantry-display
ExecStart=/home/pi/pantry-display/.venv/bin/python -c \
    "import db, display; db.init_db(); display.refresh_display(db.get_all_items())"
```

Create `/etc/systemd/system/pantry-refresh.timer`:

```ini
[Unit]
Description=Run Pantry Display refresh daily at 07:00

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pantry-refresh.timer
sudo systemctl list-timers pantry-refresh.timer
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
