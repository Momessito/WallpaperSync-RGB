# WallpaperSync RGB

**Sync your Wallpaper Engine colors with your RGB LEDs via SignalRGB � with music-reactive beat detection.**

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![SignalRGB](https://img.shields.io/badge/SignalRGB-Effect-purple)
![License](https://img.shields.io/badge/License-MIT-green)

---

## The Problem

**SignalRGB** has no native integration with **Wallpaper Engine**. There's no API to control LEDs externally, and custom HTML effects run inside an embedded Chromium at `https://signalrgbmarketplace.pages.dev/` � a remote HTTPS domain that **blocks**:

- `fetch()` / `XMLHttpRequest` to localhost (CORS + mixed content)
- `<script src="http://...">` (mixed content blocking)
- WebSocket `ws://` and `wss://` to localhost (mixed content + untrusted cert in embedded Chromium)
- Local file reading via `<script src="file:///...">` (sandbox)
- `getDisplayMedia()` (requires user gesture, impossible inside SignalRGB)
- Self-signed SSL certs and mkcert (embedded Chromium doesn't read the Windows certificate store)

## The Solution

`<img>` tags are **exempt from mixed content blocking** � Chromium allows HTTPS pages to **display** HTTP images (classified as "optionally-blockable" / "passive mixed content"). SignalRGB logs a warning, but **allows the load**.

**Architecture:**
```
+-------------------+     capture     +----------------+
| Wallpaper Engine  | ---- screen --> |   Python       |
| (Desktop)         |                 |   Server       |
+-------------------+                 |                |
                                      |  +-----------+ |
                                      |  | Screen    | |
                                      |  | Capture   | |
                                      |  +-----+-----+ |
                                      |        |       |
                                      |  +-----v-----+ |
                                      |  | Beat      | |
                                      |  | Detection | |
                                      |  +-----+-----+ |
                                      |        |       |
                                      |  +-----v-----+ |    HTTP BMP
                                      |  | Gen BMP   | +-------------+
                                      |  +-----------+ |             |
                                      +----------------+             |
                                                                     v
                                      +----------------+   +----------------+
                                      |  SignalRGB     |<--| <img> tag      |
                                      |  Reads canvas  |   | in HTML        |
                                      |  pixels        |   | (no CORS!)     |
                                      +-------+--------+   +----------------+
                                              |
                                      +-------v--------+
                                      |   Your LEDs    |
                                      +----------------+
```

1. **Python** captures the screen (where Wallpaper Engine renders), applies color adjustments and generates a BMP image
2. **Beat detection** via WASAPI loopback captures system audio and modulates brightness/saturation to the music
3. Image is served via local HTTP as **BMP**
4. The HTML effect in SignalRGB loads the image via `<img>` tag (CORS exempt) and draws it on canvas
5. SignalRGB reads the canvas pixels and maps them to LEDs

---

## Installation

### Requirements
- Windows 10/11
- Python 3.8+
- [SignalRGB](https://signalrgb.com/)
- [Wallpaper Engine](https://store.steampowered.com/app/431960/Wallpaper_Engine/) (Steam)

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USER/wallpapersync-rgb.git
cd wallpapersync-rgb
```

### 2. Run
Double-click `run_sync.bat` or run manually:
```bash
pip install mss numpy pillow pyaudiowpatch
python wallpaper_to_signalrgb.py
```

The script automatically:
- Installs dependencies
- Copies the HTML effect to the SignalRGB effects folder
- Starts the server + screen capture + beat detection

### 3. Configure SignalRGB
1. Open **SignalRGB**
2. Go to **Layouts** (or Effects)
3. Find the effect **"Wallpaper Engine Sync"**
4. Apply it to your RGB devices

### 4. (Optional) Auto-start
In SignalRGB, create a **Macro**:
- **WHEN:** Application Started
- **THEN:** Run Application -> point to `run_sync.bat`

---

## Configuration

All parameters are at the top of `wallpaper_to_signalrgb.py`:

### Color Parameters

| Parameter | Default | Description |
|---|---|---|
| `SATURATION_BOOST` | `1.8` | Color intensity (1.0 = normal, 3.0 = very vibrant) |
| `BRIGHTNESS_BOOST` | `0.4` | Base brightness � low to leave room for beat |
| `CONTRAST` | `1.5` | Contrast (1.0 = normal, 2.0 = high) |
| `MIN_SATURATION` | `0.2` | Minimum saturation � prevents white/gray LEDs |
| `GAMMA` | `1.3` | Brightness curve (< 1.0 = brighter, > 1.0 = darker) |
| `BLACK_CUTOFF` | `20` | Pixels below this value become pure black |

### Beat Parameters

| Parameter | Default | Description |
|---|---|---|
| `BEAT_ENABLED` | `True` | Enable/disable beat detection |
| `BEAT_SENSITIVITY` | `1.2` | Sensitivity (lower = catches more beats) |
| `BEAT_BRIGHTNESS_KICK` | `6.0` | Brightness multiplier on beat |
| `BEAT_SATURATION_KICK` | `1.2` | Saturation multiplier on beat |
| `BEAT_DECAY` | `0.65` | Fade speed (lower = shorter pulse) |
| `BASS_FREQ_MAX` | `350` | Max frequency for beat detection (Hz) |

### Capture Parameters

| Parameter | Default | Description |
|---|---|---|
| `MONITOR` | `1` | Monitor to capture (1 = primary) |
| `GRID_COLS` | `16` | Horizontal screen divisions |
| `GRID_ROWS` | `9` | Vertical screen divisions |
| `UPDATE_INTERVAL` | `0.033` | Capture interval (~30fps) |

---

## Beat Detection

Beat detection uses **WASAPI loopback** via `pyaudiowpatch` to capture system audio output � no extra configuration like Stereo Mix needed.

- Analyzes **bass frequencies** (< 350Hz) via FFT
- Detects energy peaks (kick drum, bass)
- Modulates LED brightness in real time
- Minimal latency: 512 sample chunk + ~0.15s history

### Result
- **No beat** -> LEDs dim with wallpaper colors
- **On beat** -> LEDs **explode** in brightness while keeping colors

---

## Project Structure

```
wallpapersync-rgb/
??? wallpaper_to_signalrgb.py   # Main script (server + capture + beat)
??? WallpaperSync.html          # HTML effect for SignalRGB
??? run_sync.bat                # Run script
??? README.md
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Black LEDs | Make sure `run_sync.bat` is running and the server shows in terminal |
| Port in use (PermissionError) | Kill old instances: `taskkill /f /im python.exe` |
| Beat not working | `pyaudiowpatch` needs an active audio device (playing music) |
| Colors too white | Increase `SATURATION_BOOST` and `MIN_SATURATION` |
| Colors too dark | Increase `BRIGHTNESS_BOOST` or decrease `GAMMA` |
| Beat delay | Decrease `CHUNK` (min 256) and `history_size` |

---

## License

MIT License � use, modify and distribute freely.
#
