# -*- coding: utf-8 -*-
"""
Wallpaper Engine -> SignalRGB Color Sync
Com parametros de cor e beat detection por audio via WASAPI loopback.

Uso:
  pip install mss numpy pillow pyaudiowpatch
  python wallpaper_to_signalrgb.py
"""

import threading
import time
import io
import colorsys
import numpy as np
import mss
from PIL import Image as PILImage
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================================================================
#                        PARAMETROS
# ================================================================

# --- Servidor ---
HTTP_PORT = 16040
UPDATE_INTERVAL = 0.033      # 30fps (era 0.05 = 20fps)

# --- Captura ---
SAMPLE_SIZE = (160, 90)
MONITOR = 1
GRID_COLS = 16
GRID_ROWS = 9

# --- Cor (base sem beat - valores mais baixos pra dar espaco pro beat brilhar) ---
SATURATION_BOOST = 1.8       # Saturacao alta sempre
BRIGHTNESS_BOOST = 0.4       # Base BEM ESCURA - sem beat os LEDs ficam bem fracos
CONTRAST = 1.5               # Contraste
MIN_SATURATION = 0.2         # Saturacao minima alta (sempre colorido, nunca branco)
GAMMA = 1.3                  # Mais escuro na base
BLACK_CUTOFF = 20            # Corta mais preto

# --- Beat / Audio ---
BEAT_ENABLED = True
BEAT_SENSITIVITY = 1.2       # Mais sensivel
BEAT_BRIGHTNESS_KICK = 6.0   # EXPLOSAO de brilho no beat (0.4 * 6.0 = 2.4x)
BEAT_SATURATION_KICK = 1.2   # Saturacao quase nao muda (ja ta alta)
BEAT_DECAY = 0.65            # Cai rapido
BASS_FREQ_MAX = 350          # Pega mais do kick/bass

# ================================================================

current_png = None
lock = threading.Lock()

# Estado do beat
beat_intensity = 0.0
beat_lock = threading.Lock()


def capture_screen():
    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR]
        screenshot = sct.grab(monitor)
        img = PILImage.frombytes("RGB", screenshot.size, screenshot.rgb)
        img = img.resize(SAMPLE_SIZE, PILImage.LANCZOS)
        return img


def apply_contrast(value, contrast):
    v = ((value / 255.0 - 0.5) * contrast + 0.5) * 255.0
    return max(0, min(255, v))


def boost_color(r, g, b, extra_brightness=1.0, extra_saturation=1.0):
    r = apply_contrast(r, CONTRAST)
    g = apply_contrast(g, CONTRAST)
    b = apply_contrast(b, CONTRAST)

    if r < BLACK_CUTOFF and g < BLACK_CUTOFF and b < BLACK_CUTOFF:
        return 0, 0, 0

    r2 = pow(r / 255.0, GAMMA)
    g2 = pow(g / 255.0, GAMMA)
    b2 = pow(b / 255.0, GAMMA)

    h, s, v = colorsys.rgb_to_hsv(r2, g2, b2)

    s = min(1.0, s * SATURATION_BOOST * extra_saturation)
    if s < MIN_SATURATION and v > 0.3:
        s = MIN_SATURATION

    v = min(1.0, v * BRIGHTNESS_BOOST * extra_brightness)

    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def make_grid_image(img, cols, rows):
    pixels = np.array(img)
    h, w, _ = pixels.shape
    cell_h = h // rows
    cell_w = w // cols

    with beat_lock:
        bi = beat_intensity

    extra_bright = 1.0 + (BEAT_BRIGHTNESS_KICK - 1.0) * bi
    extra_sat = 1.0 + (BEAT_SATURATION_KICK - 1.0) * bi

    grid_img = PILImage.new("RGB", (cols, rows))
    for r in range(rows):
        for c in range(cols):
            cell = pixels[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
            avg = cell.mean(axis=(0, 1)).astype(int)
            boosted = boost_color(int(avg[0]), int(avg[1]), int(avg[2]),
                                  extra_bright, extra_sat)
            grid_img.putpixel((c, r), boosted)

    grid_img = grid_img.resize((320, 180), PILImage.NEAREST)
    return grid_img


def color_capture_loop():
    global current_png
    print(">> Capturando tela a cada {}s...".format(UPDATE_INTERVAL))
    while True:
        try:
            img = capture_screen()
            grid_img = make_grid_image(img, GRID_COLS, GRID_ROWS)

            buf = io.BytesIO()
            grid_img.save(buf, format="BMP")

            with lock:
                current_png = buf.getvalue()
        except Exception as e:
            print("  Erro captura: {}".format(e))
        time.sleep(UPDATE_INTERVAL)


# ================================================================
#                     BEAT DETECTION (WASAPI LOOPBACK)
# ================================================================

def beat_detection_loop():
    """Detecta beats capturando audio direto da saida (WASAPI loopback)."""
    global beat_intensity

    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print(">> pyaudiowpatch nao instalado, beat desativado")
        print("   pip install pyaudiowpatch")
        return

    p = pyaudio.PyAudio()

    # Acha o dispositivo WASAPI loopback do output padrao
    wasapi_info = None
    default_output = None

    try:
        # Acha o WASAPI host api
        for i in range(p.get_host_api_count()):
            api = p.get_host_api_info_by_index(i)
            if "wasapi" in api["name"].lower():
                wasapi_info = api
                break

        if wasapi_info is None:
            print(">> WASAPI nao encontrado!")
            p.terminate()
            return

        # Acha o dispositivo de saida padrao do WASAPI
        default_output_idx = wasapi_info["defaultOutputDevice"]
        default_output = p.get_device_info_by_index(default_output_idx)
        print(">> Saida padrao: {}".format(default_output["name"]))

        # Procura o loopback correspondente
        loopback_device = None
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev.get("isLoopbackDevice", False):
                # Verifica se e o loopback do dispositivo padrao
                if default_output["name"] in dev["name"]:
                    loopback_device = dev
                    break

        # Se nao achou por nome, pega qualquer loopback
        if loopback_device is None:
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    loopback_device = dev
                    break

        if loopback_device is None:
            print(">> Nenhum dispositivo loopback encontrado!")
            print("   Dispositivos disponiveis:")
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                print("    [{}] {} (in:{} out:{} loopback:{})".format(
                    i, dev["name"],
                    dev["maxInputChannels"],
                    dev["maxOutputChannels"],
                    dev.get("isLoopbackDevice", False)
                ))
            p.terminate()
            return

        print(">> Loopback encontrado: {}".format(loopback_device["name"]))

    except Exception as e:
        print(">> Erro ao procurar dispositivos: {}".format(e))
        p.terminate()
        return

    RATE = int(loopback_device["defaultSampleRate"])
    CHANNELS = loopback_device["maxInputChannels"]
    CHUNK = 512              # Menor = menos latencia (era 2048)

    energy_history = []
    history_size = 15         # ~0.15s de historico (era 43 = ~1s)

    print(">> Beat detection ativo! ({}Hz, {}ch)".format(RATE, CHANNELS))
    print()

    def audio_callback(in_data, frame_count, time_info, status):
        global beat_intensity

        audio = np.frombuffer(in_data, dtype=np.float32)

        # Se stereo, pega so um canal
        if CHANNELS > 1:
            audio = audio[::CHANNELS]

        # Silencio
        if len(audio) == 0 or np.max(np.abs(audio)) < 0.001:
            with beat_lock:
                beat_intensity *= BEAT_DECAY
            return (None, pyaudio.paContinue)

        # FFT
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1.0 / RATE)

        # Energia no bass
        bass_mask = freqs <= BASS_FREQ_MAX
        bass_energy = np.sum(fft[bass_mask] ** 2)

        energy_history.append(bass_energy)
        if len(energy_history) > history_size:
            energy_history.pop(0)

        if len(energy_history) < 5:
            return (None, pyaudio.paContinue)

        avg_energy = np.mean(energy_history)
        threshold = avg_energy * BEAT_SENSITIVITY

        with beat_lock:
            if bass_energy > threshold and avg_energy > 0:
                beat_intensity = min(1.0, bass_energy / (avg_energy * 2))
            else:
                beat_intensity *= BEAT_DECAY

        return (None, pyaudio.paContinue)

    try:
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=loopback_device["index"],
            frames_per_buffer=CHUNK,
            stream_callback=audio_callback
        )
        stream.start_stream()

        print(">> Audio capturando de: {}".format(loopback_device["name"]))

        while stream.is_active():
            time.sleep(0.5)
            with beat_lock:
                bi = beat_intensity
            if bi > 0.3:
                bar = "#" * int(bi * 20)
                print("  BEAT: [{}] {:.2f}".format(bar.ljust(20), bi))

    except Exception as e:
        print(">> Erro no audio: {}".format(e))
    finally:
        p.terminate()


class ImageHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        with lock:
            data = current_png

        if data:
            self.send_response(200)
            self.send_header("Content-Type", "image/bmp")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(503)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    print("=" * 50)
    print("  Wallpaper Engine -> SignalRGB Color Sync")
    print("=" * 50)
    print()
    print("Parametros de cor:")
    print("  Saturacao:  {}x".format(SATURATION_BOOST))
    print("  Brilho:     {}x".format(BRIGHTNESS_BOOST))
    print("  Contraste:  {}x".format(CONTRAST))
    print("  Gamma:      {}".format(GAMMA))
    print("  Black cut:  {}".format(BLACK_CUTOFF))
    print()
    print("Beat detection: {}".format("ATIVO" if BEAT_ENABLED else "DESATIVADO"))
    if BEAT_ENABLED:
        print("  Sensibilidade:  {}".format(BEAT_SENSITIVITY))
        print("  Kick brilho:    {}x".format(BEAT_BRIGHTNESS_KICK))
        print("  Kick saturacao: {}x".format(BEAT_SATURATION_KICK))
        print("  Decay:          {}".format(BEAT_DECAY))
        print("  Bass freq max:  {}Hz".format(BASS_FREQ_MAX))
    print()

    capture_thread = threading.Thread(target=color_capture_loop, daemon=True)
    capture_thread.start()

    if BEAT_ENABLED:
        beat_thread = threading.Thread(target=beat_detection_loop, daemon=True)
        beat_thread.start()

    time.sleep(1)

    server = HTTPServer(("127.0.0.1", HTTP_PORT), ImageHandler)
    print("Servidor rodando em http://127.0.0.1:{}".format(HTTP_PORT))
    print("Pressione Ctrl+C para parar")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nParado.")
        server.server_close()


if __name__ == "__main__":
    main()
