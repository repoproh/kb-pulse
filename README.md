# KB Pulse

**Sync your MacBook keyboard backlight to the beat.**

Built for techno junkies and bedroom DJs. KB Pulse captures audio in real time, detects beats via energy analysis and FFT, and drives your MacBook's keyboard backlight — no sudo required.

## Features

- **5 sync modes** — pulse, strobe, breathe, bass_hit, vu_meter
- **Real-time beat detection** with BPM estimation
- **FFT bass isolation** for kick-drum-only tracking
- **Direct IOKit control** — no sudo, no third-party drivers
- **System audio capture** via BlackHole loopback
- **Live terminal dashboard** with VU meter
- **pip installable** with CLI entry point

## Install

### Prerequisites

```bash
brew install portaudio
```

### Install from source

```bash
git clone https://github.com/repoproh/kb-pulse.git
cd kb-pulse
pip install .
```

### Or just run it directly

```bash
pip install pyaudio numpy
python3 kb_pulse.py
```

## Usage

```bash
# Default mode (pulse)
kb-pulse

# Pick a mode
kb-pulse --mode strobe
kb-pulse --mode bass_hit

# Adjust sensitivity
kb-pulse --mode pulse --sensitivity 1.5

# List audio devices (find BlackHole)
kb-pulse --list-devices

# Use a specific audio device
kb-pulse --device 3
```

## Modes

| Mode | Description |
|------|-------------|
| `pulse` | Smooth brightness that follows overall amplitude |
| `strobe` | Hard on/off flash on every detected beat |
| `breathe` | Slow sine-wave modulated by music energy |
| `bass_hit` | Lights up only on bass drum hits (FFT isolated) |
| `vu_meter` | Brightness proportional to RMS level like a VU meter |

## System Audio Capture (BlackHole)

To sync to your system audio (Spotify, Ableton, browser, etc.):

1. Install [BlackHole](https://existential.audio/blackhole/) (2ch is fine)
2. Open **Audio MIDI Setup** (Spotlight → "Audio MIDI Setup")
3. Create a **Multi-Output Device**:
   - Check your speakers/headphones + BlackHole 2ch
4. Set the Multi-Output Device as your system output
5. Run KB Pulse with BlackHole as input:
   ```bash
   kb-pulse --list-devices    # find BlackHole index
   kb-pulse --device <index>
   ```

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│  Audio Input  │───▶│  DSP Engine  │───▶│  IOKit Bridge │
│  (PyAudio)   │    │  RMS / FFT   │    │  (backlight)  │
└──────────────┘    │  Beat Detect  │    └───────────────┘
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Mode Engine │
                    │  pulse/strobe│
                    │  breathe/etc │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Dashboard   │
                    │  (terminal)  │
                    └──────────────┘
```

## Requirements

- macOS (keyboard backlight control uses IOKit)
- Python 3.9+
- PortAudio (`brew install portaudio`)
- PyAudio + NumPy

## License

MIT — see [LICENSE](LICENSE).

## Links

- [GitHub](https://github.com/repoproh/kb-pulse)
- [Issues](https://github.com/repoproh/kb-pulse/issues)
