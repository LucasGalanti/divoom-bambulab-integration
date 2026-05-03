# BambuLab X1C → Divoom Pixoo 64 Integration

Automatically displays real-time 3D print progress on your Divoom Pixoo 64 while the BambuLab X1C is printing — **100% local, no cloud required**.

```
┌────────────────────────────────┐
│  L:47/230            [header]  │
│                                │
│         12:35                  │
│                                │
│    [ 🖨️  printer icon ]        │
│                                │
│  ███████░░░░░░  73%  [bar]     │
├────────────────────────────────┤
│  DONE:14:52          [footer]  │
└────────────────────────────────┘
```

---

## Features

- 🔒 **100% local** — no Bambu cloud, no Divoom cloud, no internet required
- ⚡ **Real-time** via MQTT push (< 100ms latency from printer to display)
- 🎨 **Pixel art sprites** generated programmatically via CLI scripts
- 🔁 **Auto-reconnect** — survives WiFi drops, printer reboots
- 🛡️ **Throttled updates** — protects the Pixoo from counter overflow bugs
- 🏠 **Two paths**: standalone Python daemon _or_ Home Assistant (HACS)

---

## Requirements

- Python 3.11+
- BambuLab X1C on the same WiFi (LAN mode enabled)
- Divoom Pixoo 64 on the same WiFi (fixed IP recommended)

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/YOUR_USER/divoom_bambulab_integration
cd divoom_bambulab_integration
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```env
PIXOO_IP=192.168.1.XXX          # Pixoo 64 fixed IP
BAMBU_PRINTER_IP=192.168.1.XXX  # X1C fixed IP
BAMBU_SERIAL=BBLP00CXXXXXXX     # Serial from printer screen
BAMBU_ACCESS_CODE=XXXXXXXX      # LAN access code (printer → Settings → Network)
```

> 💡 **How to find the LAN access code**: On the X1C touchscreen go to **Settings → Network → LAN Mode** and enable it. The access code is shown there.

### 3. Generate printer sprite

```bash
python scripts/make_sprite.py --type printer --size 20 --out assets/sprites/printer.png
```

### 4. Test connectivity

```bash
# Verify Pixoo responds
python scripts/push_test.py --ip YOUR_PIXOO_IP --mode ping

# Preview the progress screen
python scripts/push_test.py --ip YOUR_PIXOO_IP --mode progress --value 73

# Preview the done screen
python scripts/push_test.py --ip YOUR_PIXOO_IP --mode done
```

### 5. Run

```bash
python src/main.py
```

---

## Running as a Service

### Linux (systemd)

```bash
sudo cp service/divoom-bambulab.service /etc/systemd/system/
# Edit the file to match your user and paths
sudo systemctl daemon-reload
sudo systemctl enable --now divoom-bambulab
sudo journalctl -u divoom-bambulab -f
```

### Windows (Task Scheduler)

```powershell
# Run as Administrator:
.\service\install-windows-task.ps1
```

---

## Pixel Art CLI Workflow

### Create sprites programmatically

```bash
python scripts/make_sprite.py --type printer --size 20
python scripts/make_sprite.py --type done    --size 20
python scripts/make_sprite.py --type failed  --size 20
python scripts/make_sprite.py --type idle    --size 32
python scripts/make_sprite.py --list   # show all available types
```

### Convert PNG to base64 (for HA YAML embedding)

```bash
python scripts/encode_icon.py --file assets/sprites/printer.png --size 20
python scripts/encode_icon.py --file assets/sprites/printer.png --size 20 --clip  # prints YAML snippet
```

### Push images directly to the display

```bash
python scripts/push_test.py --ip 192.168.1.X --mode image --file assets/sprites/printer.png
python scripts/push_test.py --ip 192.168.1.X --mode gif   --file animation.gif --fps 10
python scripts/push_test.py --ip 192.168.1.X --mode brightness --value 80
```

### Recommended external pixel art editors

| Tool | Platform | Price | Best for |
|------|----------|-------|----------|
| [Piskel](https://www.piskelapp.com) | Browser/Desktop | Free | Quick sprites & GIFs |
| [Pixelorama](https://github.com/Orama-Interactive/Pixelorama) | Desktop | Free | 64×64 canvas, animations |
| [Aseprite](https://www.aseprite.org) | Desktop | $20 | Professional animations |

Export as PNG → use `encode_icon.py` to convert.

---

## Alternative: Home Assistant (HACS)

If you already use Home Assistant, you can use the HACS path instead:

1. Install **ha-bambulab** via HACS → adds printer sensors to HA
2. Install **pixoo-homeassistant** via HACS → connects Pixoo to HA
3. Copy `ha_config/pixoo_bambulab.yaml` into your pixoo-homeassistant config
4. Replace entity IDs with yours (check Developer Tools → States → filter `bambu`)
5. Replace `PRINTER_ICON_BASE64` placeholder with the output of:
   ```bash
   python scripts/encode_icon.py --file assets/sprites/printer.png --size 20
   ```

See [`ha_config/pixoo_bambulab.yaml`](ha_config/pixoo_bambulab.yaml) for the full annotated configuration.

---

## Project Structure

```
divoom_bambulab_integration/
├── src/
│   ├── main.py              # Entry point — connects everything
│   ├── bambu_mqtt.py        # Local MQTT client for X1C
│   ├── pixoo_renderer.py    # HTTP sender to Pixoo 64 (with throttling)
│   └── display_layouts.py   # Pillow screen composers (progress, idle, done, failed)
├── scripts/
│   ├── make_sprite.py       # CLI: generate pixel-art sprites
│   ├── encode_icon.py       # CLI: PNG → base64 for YAML embedding
│   └── push_test.py         # CLI: test connectivity and push content
├── assets/
│   ├── sprites/             # PNG sprite files
│   └── generated/           # base64 outputs (gitignored)
├── config/
│   └── config.yaml          # Display and layout preferences
├── ha_config/
│   └── pixoo_bambulab.yaml  # Home Assistant alternative config
├── service/
│   ├── divoom-bambulab.service   # Linux systemd unit
│   └── install-windows-task.ps1 # Windows Task Scheduler script
├── .env.example             # Environment variables template
├── requirements.txt
└── README.md
```

---

## Security Notes

- **All communication is local** — printer ↔ MQTT (TLS, port 8883), display ↔ HTTP (port 80)
- **LAN mode only** — the X1C's LAN access code authenticates MQTT; no Bambu account needed
- **No ports exposed** — nothing listens on external interfaces; only outbound connections
- Set **DHCP reservations** on your router for stable IPs on both devices

---

## How It Works

```
X1C Printer
  │  MQTT (TLS, port 8883, LAN mode)
  │  topic: device/{serial}/report
  │  push: layer_num, mc_percent, mc_remaining_time, gcode_state
  ▼
bambu_mqtt.py ──► on_state_change callback
  │
  ▼
display_layouts.py ──► Pillow Image (64×64 RGB)
  │
  ▼
pixoo_renderer.py ──► HTTP POST http://{pixoo_ip}/post
                       Command: Draw/SendHttpGif
                       PicData: base64(RGB bytes)
  │
  ▼
Divoom Pixoo 64 display
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Cannot reach Pixoo` | Check IP in `.env`, ensure same WiFi, try `ping` |
| `MQTT connection error` | Verify LAN mode enabled on printer, check serial + access code |
| Display freezes after a while | Auto-reset is built in (threshold: 250 frames); if still occurs, restart daemon |
| `sensor.bambu_x1c_*` not found (HA path) | Check entity IDs in Developer Tools → States |
| Sprite not found warning | Run `python scripts/make_sprite.py --type printer` first |

---

## References

- [ha-bambulab](https://github.com/greghesp/ha-bambulab) — HA integration for BambuLab printers
- [pixoo-homeassistant](https://github.com/gickowtf/pixoo-homeassistant) — HA integration for Pixoo displays
- [pixoo Python library](https://github.com/SomethingWithComputers/pixoo) — standalone Python API
- [pixoo-rest](https://github.com/4ch1m/pixoo-rest) — REST API wrapper for Pixoo
- [Discussion #92](https://github.com/gickowtf/pixoo-homeassistant/discussions/92) — original BambuLab display pattern that inspired this project
