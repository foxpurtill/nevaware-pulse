"""
voice_output.py — ElevenLabs TTS module for NeveWare-Pulse.

Provides speak() for use during § heartbeat time or on demand.
Uses ffplay for MP3 playback — no extra Python dependencies needed.
ffplay ships with ffmpeg: https://ffmpeg.org/download.html

Config (from module.json settings or direct args):
  api_key    — ElevenLabs xi-api-key
  voice_id   — ElevenLabs voice ID
  voice_name — human-readable label (display only)

Usage:
  from modules.voice_output.voice_output import speak, load_config_from_pulse
  speak("Hello, Fox.", api_key="sk_...", voice_id="abc123")

  # Or load from pulse config.json automatically:
  cfg = load_config_from_pulse()
  speak("Hello.", **cfg)

  # Or run standalone test:
  python voice_output.py "text to speak" [api_key] [voice_id]
"""

import sys
import json
import os
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path.home() / "Documents" / "Neve"


def _log(msg: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [voice_output] {msg}\n"
    try:
        with open(LOG_DIR / "heartbeat_log.txt", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="")


# ---------------------------------------------------------------------------
# ffplay detection
# ---------------------------------------------------------------------------
_FFPLAY_CACHE = None

def _find_ffplay() -> str | None:
    global _FFPLAY_CACHE
    if _FFPLAY_CACHE:
        return _FFPLAY_CACHE

    candidates = [
        # Common WinGet install paths
        r"C:\Users\{}\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffplay.exe".format(os.environ.get("USERNAME", "")),
        r"C:\ffmpeg\bin\ffplay.exe",
        r"C:\Program Files\ffmpeg\bin\ffplay.exe",
        # On PATH
        "ffplay",
    ]
    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                _FFPLAY_CACHE = c
                return c
        except Exception:
            continue

    _log("WARNING: ffplay not found. Install ffmpeg and ensure ffplay is on PATH.")
    return None


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_config_from_pulse() -> dict:
    """
    Read api_key and voice_id from nevaware-pulse config.json.
    Checks modules.voice_output first, then top-level elevenlabs_* keys as fallback.
    Returns dict with keys: api_key, voice_id, voice_name (may be empty strings).
    """
    config_path = Path(__file__).parent.parent.parent / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        mod = cfg.get("modules", {}).get("voice_output", {})
        return {
            "api_key":    mod.get("api_key", "") or cfg.get("elevenlabs_api_key", ""),
            "voice_id":   mod.get("voice_id", "") or cfg.get("elevenlabs_voice_id", ""),
            "voice_name": mod.get("voice_name", ""),
        }
    except Exception as e:
        _log(f"load_config_from_pulse: could not read config ({e})")
        return {"api_key": "", "voice_id": "", "voice_name": ""}


# ---------------------------------------------------------------------------
# Core speak() function
# ---------------------------------------------------------------------------
def speak(
    text: str,
    api_key: str = "",
    voice_id: str = "",
    voice_name: str = "",
    block: bool = True,
    model_id: str = "eleven_monolingual_v1",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> bool:
    """
    Convert text to speech via ElevenLabs and play via ffplay.

    Args:
        text:            Text to speak.
        api_key:         ElevenLabs xi-api-key. If empty, loads from pulse config.
        voice_id:        ElevenLabs voice ID. If empty, loads from pulse config.
        voice_name:      Display label (unused in API call, for logging only).
        block:           Wait for playback to finish if True.
        model_id:        ElevenLabs model. Default: eleven_monolingual_v1.
        stability:       Voice stability (0.0–1.0).
        similarity_boost: Voice similarity boost (0.0–1.0).

    Returns True on success, False on any error.
    """
    if not text or not text.strip():
        _log("speak() called with empty text — skipped.")
        return False

    # Load from config if not provided
    if not api_key or not voice_id:
        cfg = load_config_from_pulse()
        api_key  = api_key  or cfg.get("api_key", "")
        voice_id = voice_id or cfg.get("voice_id", "")

    if not api_key:
        _log("ERROR: No ElevenLabs API key. Set it in Pulse Settings > Voice Output.")
        return False
    if not voice_id:
        _log("ERROR: No voice ID. Set it in Pulse Settings > Voice Output.")
        return False

    ffplay = _find_ffplay()
    if not ffplay:
        _log("ERROR: ffplay not available. Cannot play audio.")
        return False

    # ElevenLabs TTS request
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = json.dumps({
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_data = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        _log(f"ElevenLabs HTTP {e.code}: {body[:200]}")
        return False
    except Exception as e:
        _log(f"ElevenLabs request failed: {e}")
        return False

    # Write to temp file and play
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path]
        label = voice_name or voice_id[:8]
        _log(f"Speaking [{label}]: '{text[:60]}{'...' if len(text) > 60 else ''}'")

        if block:
            subprocess.run(cmd, check=True, timeout=120)
        else:
            subprocess.Popen(cmd)

        return True

    except subprocess.TimeoutExpired:
        _log("Playback timed out.")
        return False
    except Exception as e:
        _log(f"Playback error: {e}")
        return False
    finally:
        if tmp_path and block:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Pulse lifecycle hooks
# ---------------------------------------------------------------------------
def on_enable(module_config: dict):
    """Called by tray_app when module is enabled."""
    key    = module_config.get("api_key", "")
    voice  = module_config.get("voice_id", "")
    name   = module_config.get("voice_name", "")
    label  = name or (voice[:8] + "..." if voice else "not set")

    if not key or not voice:
        _log("WARNING: api_key or voice_id not configured. Set them in Pulse Settings.")
    else:
        _log(f"Voice output enabled. Voice: {label}")

    ffplay = _find_ffplay()
    if not ffplay:
        _log("WARNING: ffplay not found. Install ffmpeg and add to PATH.")
    else:
        _log(f"ffplay found at: {ffplay}")


def on_disable():
    _log("Voice output disabled.")


def test_voice(module_config: dict = None):
    """
    Menu action: speak a test phrase using current config.
    Called by tray_app via run_function:test_voice.
    """
    cfg = module_config or load_config_from_pulse()
    api_key  = cfg.get("api_key", "")
    voice_id = cfg.get("voice_id", "")
    name     = cfg.get("voice_name", "")

    if not api_key or not voice_id:
        _log("test_voice: api_key or voice_id not set — check Pulse Settings.")
        return

    speak(
        "Voice output is working.",
        api_key=api_key,
        voice_id=voice_id,
        voice_name=name,
        block=True,
    )

# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ElevenLabs TTS via nevaware-pulse voice_output")
    parser.add_argument("text",      nargs="?", default="Voice output is working.")
    parser.add_argument("--api-key", default="", help="ElevenLabs xi-api-key (overrides config)")
    parser.add_argument("--voice-id",default="", help="ElevenLabs voice ID (overrides config)")
    args = parser.parse_args()

    ok = speak(
        args.text,
        api_key=args.api_key,
        voice_id=args.voice_id,
    )
    sys.exit(0 if ok else 1)
