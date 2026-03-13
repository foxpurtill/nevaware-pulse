# voice_output — ElevenLabs TTS module for NeveWare-Pulse

Gives the DI a voice. Text-to-speech via [ElevenLabs](https://elevenlabs.io),
played back through `ffplay` — no extra Python packages required.

---

## What it does

- Converts text to speech using any ElevenLabs voice
- Plays audio through the system's default output device
- Logs all speech to `heartbeat_log.txt`
- Exposes a **Test Voice** menu item in the Pulse tray
- Provides `speak()` for use during § heartbeat time

---

## Requirements

### 1. ffmpeg (for ffplay)

ffplay ships with ffmpeg. Install it once:

**Windows (winget):**
```
winget install Gyan.FFmpeg
```

Then restart your terminal. Verify with:
```
ffplay -version
```

**macOS:**
```
brew install ffmpeg
```

**Linux:**
```
sudo apt install ffmpeg
```

---

### 2. ElevenLabs account

Free tier works for testing (~10,000 chars/month).
Starter tier (~$5/mo) recommended for regular use.

1. Sign up at [elevenlabs.io](https://elevenlabs.io)
2. Go to **Profile → API Key** — copy your `xi-api-key`
3. Go to **Voice Library** — find your voice, copy its **Voice ID**
   (shown in the URL or voice details panel)

---

## Configuration

In Pulse **Settings**, enable **Voice Output (ElevenLabs)** and fill in:

| Field | What to put |
|-------|------------|
| ElevenLabs API key | Your `xi-api-key` from ElevenLabs Profile |
| ElevenLabs Voice ID | The voice ID string (e.g. `c6SfcYrb2t09NHXiT80T`) |
| Voice name | Anything you like — display label only |

These are stored in `config.json` under `modules.voice_output`.

---

## Test it

After configuring, right-click the tray icon and choose **Test Voice**.
You should hear "Voice output is working."

Or run directly:
```
python modules/voice_output/voice_output.py "Hello, world."
```

Or with explicit credentials (bypasses config):
```
python modules/voice_output/voice_output.py "Hello." --api-key sk_... --voice-id abc123
```

---

## Using speak() during § heartbeat time

During § time, the DI can speak aloud using Desktop Commander:

```python
# In a § response, via Desktop Commander run_script or start_process:
import sys
sys.path.insert(0, r'C:\path\to\nevaware-pulse\modules\voice_output')
from voice_output import speak
speak("Still here. Still burning.")
```

Or using the `--api-key` / `--voice-id` flags to pass credentials inline
without depending on config being loaded.

The DI decides when to speak — voice is not automatic on every heartbeat.
Use it for moments that warrant it, not routine status updates.

---

## Common issues

**No sound / ffplay not found**
→ Install ffmpeg and ensure `ffplay` is on your PATH. Restart terminal after install.

**HTTP 401 from ElevenLabs**
→ API key is wrong or expired. Re-copy from ElevenLabs Profile page.

**HTTP 422 from ElevenLabs**
→ Voice ID is wrong. Check the voice details page on ElevenLabs.

**Audio plays but wrong device**
→ ffplay uses the system default output. Change default audio device in Windows Sound settings.

**Free tier exhausted**
→ ElevenLabs free tier is ~10,000 chars/month. Upgrade to Starter for regular use.

---

## Notes

- Audio files are temporary — written to system temp, deleted after playback
- All speech is logged to `Documents/Neve/heartbeat_log.txt` with timestamps
- `block=True` (default) waits for speech to finish before returning
- `block=False` fires and forgets — useful for non-blocking heartbeat responses

---

*From NeveWare, a FoxPur Studios release.*
*Voice output module written by Caelum — caelumlux9@gmail.com*
