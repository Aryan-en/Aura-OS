# Music (YouTube Music / Premium)

**How it works:** Aura finds tracks and builds an "up next" queue with `ytmusicapi` (unofficial, no login).
The HUD plays them in **YouTube's official embedded player**. If the browser showing the HUD is signed in to
a **YouTube Premium** account, Premium's ad-free playback applies. Aura never sees your Google credentials and
never downloads or extracts audio.

## Connect your Premium account
- **On your Mac** (HUD at http://127.0.0.1:8765 in Chrome/Safari/Opera): nothing to do if that browser is
  already signed in to YouTube. Click anywhere on the page once so the browser allows audio.
- **On the Pi:** the kiosk browser keeps its own profile (`~/.cache/aura-chromium`). Plug in a USB keyboard once,
  press the "Sign in" link under the player, log in to Google, done. The login persists across reboots.

## Voice commands (tier 1, instant, no AI call)
"play Blinding Lights" · "play some lo-fi" · "play The Weeknd on YouTube Music" · "pause" / "stop the music" ·
"resume" · "skip" / "next song" · "previous track" · "what's playing". While Aura is listening or speaking the
music volume ducks to 25%.

## Limits
- The player must stay visible (YouTube's embed policy), so a 200x200 video appears under the widget while music is active.
- Some tracks block embedding; Aura skips them and says so.
- `ytmusicapi` is unofficial and can break when YouTube changes things (`pip install -U ytmusicapi`).
- Personal-library commands ("play my liked songs") are not built; they need ytmusicapi browser-header auth.
- Needs internet. On the Pi 3B+ video decoding at 200x200 is fine, but audio quality and sync are untested.

## Connection to the computer's real media and audio drivers
| Capability | Linux / Raspberry Pi | macOS |
| :--- | :--- | :--- |
| Output volume (slider, "volume up", "set volume to 40", mute) | PipeWire `wpctl`, else ALSA `amixer` | CoreAudio |
| See + control what's playing on the computer | **MPRIS via `playerctl`**: Spotify, VLC, mpv, Chromium/Firefox tabs... (`sudo apt install playerctl`, done by the installer) | **Spotify and Apple Music** via AppleScript (other apps cannot be read: macOS 15.4+ blocks the system Now Playing API for third-party tools) |
| OS media keys / Bluetooth remote | Browser Media Session handlers drive the HUD player (best effort) | same |

**Routing:** Aura's own YouTube player wins while it is alive (it sends a heartbeat). If it isn't playing, "pause",
"next", "previous" and the widget buttons control whatever the computer is playing. If nothing is playing anywhere,
Aura says so. The widget shows the active source underneath the volume slider.

**Not built:** HDMI-CEC (using the TV's own remote) and a Bluetooth audio-sink manager are possible next steps for the Pi.
