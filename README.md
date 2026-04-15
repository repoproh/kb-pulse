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
pip install pyaudio numpy pyobjc-core pyobjc-framework-Cocoa
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

## Auto-start at login

A plain LaunchAgent **will not work**: macOS classifies any audio input capture (including virtual devices like BlackHole) as microphone access, and processes spawned by `launchd` have no app identity to request that permission against — they just read silence.

The fix is to wrap `kb_pulse.py` in a proper Cocoa app bundle (so TCC can grant the bundle mic permission) and register that as a login item.

```bash
# 1. Write a one-line AppleScript that launches the script in the background.
cat > /tmp/kbpulse.applescript <<'EOF'
do shell script "/usr/bin/arch -arm64 /usr/bin/python3 /ABSOLUTE/PATH/TO/kb_pulse.py --mode strobe --device 2 --sensitivity 1.0 >/tmp/kbpulse.log 2>&1 &"
EOF

# 2. Compile it into an .app bundle (a real Cocoa applet with NSMicrophoneUsageDescription).
osacompile -o ~/Applications/KBPulse.app /tmp/kbpulse.applescript

# 3. Mark it as a background agent (no Dock icon) and give it a stable bundle id.
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" ~/Applications/KBPulse.app/Contents/Info.plist
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.kbpulse.app" ~/Applications/KBPulse.app/Contents/Info.plist

# 4. Ad-hoc codesign for a stable TCC identity.
codesign --force --deep --sign - ~/Applications/KBPulse.app

# 5. Launch once — macOS will show a microphone permission dialog. Click Allow.
open ~/Applications/KBPulse.app

# 6. Add to login items so it auto-starts.
osascript -e 'tell application "System Events" to make login item at end with properties {path:"'"$HOME"'/Applications/KBPulse.app", hidden:true}'
```

Replace `/ABSOLUTE/PATH/TO/kb_pulse.py` with the real path, and `--device 2` with your BlackHole index (check `kb-pulse --list-devices`). Change mode/sensitivity to taste.

To change settings later, edit `/tmp/kbpulse.applescript`, recompile with `osacompile -x -o /tmp/kbpulse.scpt` and copy the result into `~/Applications/KBPulse.app/Contents/Resources/Scripts/main.scpt`, then re-sign — this preserves your mic permission grant.

## Requirements

- macOS (keyboard backlight control uses CoreBrightness via pyobjc)
- Python 3.9+
- PortAudio (`brew install portaudio`)
- `pyaudio`, `numpy`, `pyobjc-core`, `pyobjc-framework-Cocoa`

## License

MIT — see [LICENSE](LICENSE).

## Links

- [GitHub](https://github.com/repoproh/kb-pulse)
- [Issues](https://github.com/repoproh/kb-pulse/issues)
