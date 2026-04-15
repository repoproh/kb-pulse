#!/usr/bin/env python3
"""
KB Pulse — Sync your MacBook keyboard backlight to the beat.

Usage:
    python3 kb_pulse.py [--mode MODE] [--sensitivity FLOAT] [--device INDEX]

Modes: pulse, strobe, breathe, bass_hit, vu_meter
"""

__version__ = "1.0.0"

import argparse
import math
import signal
import struct
import sys
import threading
import time
from collections import deque

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODE_LIST = ["pulse", "strobe", "breathe", "bass_hit", "vu_meter"]
MODE_DESCRIPTIONS = {
    "pulse": "Smooth brightness that follows overall amplitude",
    "strobe": "Hard on/off flash on every detected beat",
    "breathe": "Slow sine-wave modulated by music energy",
    "bass_hit": "Lights up only on bass drum hits (FFT isolated)",
    "vu_meter": "Brightness proportional to RMS level like a VU meter",
}

SAMPLE_RATE = 44100
CHUNK = 1024
BASS_LOW = 20
BASS_HIGH = 150
BPM_HISTORY = 40
BEAT_COOLDOWN = 0.12  # seconds

BANNER = r"""
  _  ______    ____        _
 | |/ / __ )  |  _ \ _   _| |___  ___
 | ' /|  _ \  | |_) | | | | / __|/ _ \
 | . \| |_) | |  __/| |_| | \__ \  __/
 |_|\_\____/  |_|    \__,_|_|___/\___|
  v{version}  —  github.com/repoproh/kb-pulse
"""

# ---------------------------------------------------------------------------
# IOKit keyboard backlight control (macOS)
# ---------------------------------------------------------------------------


class KeyboardBacklight:
    """CoreBrightness control of MacBook keyboard backlight — no sudo needed."""

    def __init__(self):
        self._client = None
        self._kb_id = None
        self._brightness = 0.0
        self._original_brightness = 0.5
        self._available = False
        self._init_backlight()

    def _init_backlight(self):
        try:
            import objc
            from Foundation import NSBundle

            bundle = NSBundle.bundleWithPath_(
                "/System/Library/PrivateFrameworks/CoreBrightness.framework"
            )
            if not bundle or not bundle.load():
                return

            KBClient = objc.lookUpClass("KeyboardBrightnessClient")
            self._client = KBClient.alloc().init()

            kb_ids = self._client.copyKeyboardBacklightIDs()
            if kb_ids and len(kb_ids) > 0:
                self._kb_id = kb_ids[0]
                self._original_brightness = self._client.brightnessForKeyboard_(self._kb_id)
                self._brightness = self._original_brightness
                self._available = True
        except Exception:
            self._available = False

    @property
    def available(self):
        return self._available

    def set_brightness(self, level: float):
        """Set keyboard backlight brightness (0.0 to 1.0)."""
        level = max(0.0, min(1.0, level))
        if not self._available:
            self._brightness = level
            return
        try:
            self._client.setBrightness_forKeyboard_(level, self._kb_id)
            self._brightness = level
        except Exception:
            pass

    def get_brightness(self) -> float:
        return self._brightness

    def cleanup(self):
        """Restore backlight to original brightness."""
        if self._available and self._client is not None:
            self.set_brightness(self._original_brightness)


# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------


class AudioCapture:
    """Captures audio via PyAudio (mic or BlackHole loopback)."""

    def __init__(self, device_index=None, rate=SAMPLE_RATE, chunk=CHUNK):
        self.rate = rate
        self.chunk = chunk
        self.device_index = device_index
        self._stream = None
        self._pa = None

    def start(self):
        import pyaudio

        self._pa = pyaudio.PyAudio()
        kwargs = {
            "format": pyaudio.paInt16,
            "channels": 1,
            "rate": self.rate,
            "input": True,
            "frames_per_buffer": self.chunk,
        }
        if self.device_index is not None:
            kwargs["input_device_index"] = self.device_index
        self._stream = self._pa.open(**kwargs)

    def read(self):
        """Read one chunk and return as list of floats normalised to [-1, 1]."""
        data = self._stream.read(self.chunk, exception_on_overflow=False)
        samples = struct.unpack(f"<{self.chunk}h", data)
        return [s / 32768.0 for s in samples]

    def stop(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def list_devices(self):
        import pyaudio

        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append((i, info["name"]))
        pa.terminate()
        return devices


# ---------------------------------------------------------------------------
# DSP helpers
# ---------------------------------------------------------------------------

import numpy as np


def rms(samples):
    """Root mean square of sample buffer."""
    arr = np.array(samples)
    return float(np.sqrt(np.mean(arr ** 2)))


def fft_bass_energy(samples, rate=SAMPLE_RATE, low=BASS_LOW, high=BASS_HIGH):
    """Extract energy in the bass frequency band via FFT."""
    arr = np.array(samples)
    spectrum = np.abs(np.fft.rfft(arr))
    freqs = np.fft.rfftfreq(len(arr), 1.0 / rate)
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return 0.0
    return float(np.mean(spectrum[mask]))


class BeatDetector:
    """Simple energy-based beat detector with BPM estimation."""

    def __init__(self, history_size=43):
        self.energy_history = deque(maxlen=history_size)
        self.beat_times = deque(maxlen=BPM_HISTORY)
        self.last_beat = 0.0
        self.bpm = 0.0

    def detect(self, energy: float) -> bool:
        self.energy_history.append(energy)
        if len(self.energy_history) < 10:
            return False
        avg = sum(self.energy_history) / len(self.energy_history)
        threshold = avg * 1.4
        now = time.time()
        if energy > threshold and (now - self.last_beat) > BEAT_COOLDOWN:
            self.last_beat = now
            self.beat_times.append(now)
            self._update_bpm()
            return True
        return False

    def _update_bpm(self):
        if len(self.beat_times) < 4:
            return
        intervals = [
            self.beat_times[i] - self.beat_times[i - 1]
            for i in range(1, len(self.beat_times))
        ]
        avg_interval = sum(intervals) / len(intervals)
        if avg_interval > 0:
            self.bpm = 60.0 / avg_interval


# ---------------------------------------------------------------------------
# Lighting modes
# ---------------------------------------------------------------------------


def mode_pulse(energy, beat, ctx):
    """Smooth brightness tracking amplitude."""
    target = min(1.0, energy * ctx["sensitivity"] * 3.0)
    ctx["smooth"] = ctx.get("smooth", 0.0) * 0.7 + target * 0.3
    return ctx["smooth"]


def mode_strobe(energy, beat, ctx):
    """Hard flash on beat."""
    if beat:
        ctx["strobe_until"] = time.time() + 0.05
    return 1.0 if time.time() < ctx.get("strobe_until", 0) else 0.0


def mode_breathe(energy, beat, ctx):
    """Slow sine wave modulated by energy."""
    t = time.time()
    base = (math.sin(t * 2.0) + 1.0) / 2.0
    mod = min(1.0, energy * ctx["sensitivity"] * 2.0)
    return base * (0.3 + 0.7 * mod)


def mode_bass_hit(energy, beat, ctx):
    """Light only on bass hits with fast decay."""
    bass = ctx.get("bass_energy", 0.0)
    if bass > ctx.get("bass_threshold", 0.05) * ctx["sensitivity"]:
        ctx["bass_bright"] = 1.0
    else:
        ctx["bass_bright"] = max(0.0, ctx.get("bass_bright", 0.0) - 0.08)
    return ctx["bass_bright"]


def mode_vu_meter(energy, beat, ctx):
    """Direct VU meter — brightness = RMS level."""
    return min(1.0, energy * ctx["sensitivity"] * 4.0)


MODE_FUNCS = {
    "pulse": mode_pulse,
    "strobe": mode_strobe,
    "breathe": mode_breathe,
    "bass_hit": mode_bass_hit,
    "vu_meter": mode_vu_meter,
}

# ---------------------------------------------------------------------------
# Terminal dashboard
# ---------------------------------------------------------------------------


def render_dashboard(mode, brightness, energy, bpm, beat):
    """Draw a live single-line dashboard."""
    bar_width = 30
    filled = int(brightness * bar_width)
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
    beat_indicator = " *BEAT*" if beat else ""
    bpm_str = f"{bpm:5.1f}" if bpm > 0 else "  ---"
    sys.stdout.write(
        f"\r  [{bar}] {brightness:4.0%}  |  mode: {mode:<10s}  |  "
        f"BPM: {bpm_str}  |  energy: {energy:.3f}{beat_indicator}    "
    )
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="KB Pulse — sync MacBook keyboard backlight to music"
    )
    parser.add_argument(
        "--mode",
        choices=MODE_LIST,
        default="pulse",
        help="Lighting mode (default: pulse)",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=1.0,
        help="Sensitivity multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio input device index (use --list-devices to see options)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"KB Pulse {__version__}",
    )
    args = parser.parse_args()

    # List devices mode
    if args.list_devices:
        cap = AudioCapture()
        devices = cap.list_devices()
        print("Available audio input devices:")
        for idx, name in devices:
            print(f"  [{idx}] {name}")
        if not devices:
            print("  (none found — is PortAudio installed?)")
        return

    # Banner
    print(BANNER.format(version=__version__))
    print(f"  Mode: {args.mode} — {MODE_DESCRIPTIONS[args.mode]}")
    print(f"  Sensitivity: {args.sensitivity}")
    print(f"  Device: {args.device or 'default'}")
    print()
    print("  Press Ctrl+C to stop.\n")

    # Init
    kb = KeyboardBacklight()
    if not kb.available:
        print("  [!] IOKit backlight not available — running in preview mode")
        print("      (brightness values shown but not applied to hardware)\n")

    audio = AudioCapture(device_index=args.device)
    audio.start()

    detector = BeatDetector()
    mode_fn = MODE_FUNCS[args.mode]
    ctx = {"sensitivity": args.sensitivity}

    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)

    try:
        while running:
            samples = audio.read()
            energy = rms(samples)
            bass = fft_bass_energy(samples)
            beat = detector.detect(energy)

            ctx["bass_energy"] = bass
            ctx["bass_threshold"] = 0.05

            brightness = mode_fn(energy, beat, ctx)
            kb.set_brightness(brightness)

            render_dashboard(args.mode, brightness, energy, detector.bpm, beat)

            time.sleep(0.005)
    finally:
        print("\n\n  Shutting down...")
        audio.stop()
        kb.cleanup()
        print("  Done. Backlight restored.\n")


if __name__ == "__main__":
    main()
