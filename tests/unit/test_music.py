"""Music: queue building, tools, voice intents (YouTube Music client is faked, no network)."""

import asyncio

import aura.music as music
from aura.core.events import bus
from tests.unit.test_agentic_os import make_router


class FakeYT:
    def search(self, q: str, filter: str = "songs", limit: int = 5):  # noqa: A002
        if "nothing" in q:
            return []
        return [{"videoId": "AAA", "title": "Blinding Lights", "artists": [{"name": "The Weeknd"}],
                 "thumbnails": [{"url": "http://t/small"}, {"url": "http://t/big"}]},
                {"videoId": "BBB", "title": "Other", "artists": []}]

    def get_watch_playlist(self, video_id: str, limit: int = 25):
        return {"tracks": [{"videoId": "AAA", "title": "dup", "artists": []},
                           {"videoId": "CCC", "title": "Starboy", "artists": [{"name": "The Weeknd"}, {"name": "Daft Punk"}],
                            "thumbnail": [{"url": "http://t/c"}]}]}


def setup_function() -> None:
    music._yt = FakeYT()
    music.now_playing.state = {}


def test_queue_is_best_match_then_radio_without_duplicates() -> None:
    q = music.build_queue("blinding lights")
    assert [t["videoId"] for t in q] == ["AAA", "CCC"]
    assert q[0]["artist"] == "The Weeknd" and q[0]["thumb"] == "http://t/big"
    assert q[1]["artist"] == "The Weeknd, Daft Punk"
    assert music.build_queue("nothing here") == []


def test_voice_play_emits_queue_and_replies_tier1() -> None:
    async def _run() -> None:
        r, _, _ = make_router()
        start = bus.last_id
        out = await r.handle("play blinding lights on YouTube Music")
        assert out["tier"] == 1 and out["reply"] == "Playing Blinding Lights by The Weeknd."
        ev = [e for e in bus.since(start) if e["type"] == "music.queue"][-1]
        assert ev["index"] == 0 and ev["tracks"][0]["videoId"] == "AAA"
        out = await r.handle("play nothing at all")
        assert out["success"] is False and "couldn't find" in out["reply"]

    asyncio.run(_run())


def test_transport_commands_and_now_playing() -> None:
    async def _run() -> None:
        r, _, _ = make_router()
        music.now_playing.update({"title": "x", "artist": "y", "playing": True})  # HUD player is alive
        for phrase, action in [("pause the music", "pause"), ("skip", "next"), ("next song", "next"),
                               ("previous track", "previous"), ("resume", "resume"), ("stop the music", "pause")]:
            start = bus.last_id
            out = await r.handle(phrase)
            assert out["tier"] == 1, phrase
            assert [e["action"] for e in bus.since(start) if e["type"] == "music.control"] == [action], phrase
        music.now_playing.state = {}
        assert (await r.handle("what's playing"))["reply"] == "Nothing is playing."
        music.now_playing.update({"title": "Starboy", "artist": "The Weeknd", "playing": True})
        assert "Starboy by The Weeknd" in (await r.handle("what song is this"))["reply"]

    asyncio.run(_run())


# ---------------------------------------------------------------- system drivers (OS commands faked)
import platform  # noqa: E402

from aura import audio  # noqa: E402
from aura.music import system_media as sm  # noqa: E402

SEP = sm.SEP


def fake_os(monkeypatch, outputs, calls):  # type: ignore[no-untyped-def]
    """Replace audio.run: `outputs` maps a command prefix to (rc, text); every call is recorded."""
    async def fake_run(*cmd: str, timeout: float = 5.0):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        for prefix, res in outputs.items():
            if " ".join(cmd).startswith(prefix):
                return res
        return 1, ""
    monkeypatch.setattr(audio, "run", fake_run)


def test_playerctl_parsing_prefers_playing_over_paused() -> None:
    out = (f"Paused{SEP}Adele{SEP}Hello{SEP}file:///x.png{SEP}vlc\n"
           f"Playing{SEP}The Weeknd{SEP}Starboy{SEP}https://img/x.jpg{SEP}spotify\n"
           f"Stopped{SEP}{SEP}{SEP}{SEP}mpv\n")
    players = sm.parse_playerctl(out)
    assert len(players) == 3 and players[0]["art"] == ""  # local file:// art is not exposed to the HUD
    best = sm._pick(players)
    assert best["player"] == "spotify" and best["art"] == "https://img/x.jpg"


def test_mac_applescript_parsing() -> None:
    assert sm.parse_mac("Spotify", "playing\nStarboy\nThe Weeknd")["title"] == "Starboy"
    assert sm.parse_mac("Music", "") is None


def test_system_control_targets_the_active_player(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def _run() -> None:
        calls: list = []
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.setattr(sm.shutil, "which", lambda n: "/usr/bin/playerctl" if n == "playerctl" else None)
        meta = f"Playing{SEP}Artist{SEP}Song{SEP}{SEP}spotify\n"
        fake_os(monkeypatch, {"playerctl -a metadata": (0, meta), "playerctl -p spotify": (0, "")}, calls)
        assert (await sm.status())["title"] == "Song"
        res = await sm.control("next")
        assert res == {"player": "spotify", "action": "next"}
        assert ("playerctl", "-p", "spotify", "next") in calls

        fake_os(monkeypatch, {"playerctl -a metadata": (0, "")}, [])
        try:
            await sm.control("pause")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert "No media player" in str(e)

    asyncio.run(_run())


def test_music_control_prefers_hud_then_system_then_says_nothing_playing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from aura.tools.music import tool_control

    async def _run() -> None:
        calls: list = []
        async def fake_control(action: str):  # type: ignore[no-untyped-def]
            calls.append(action)
            return {"player": "spotify", "action": action}
        monkeypatch.setattr(sm, "control", fake_control)
        start = bus.last_id

        music.now_playing.state = {}
        assert (await tool_control("pause"))["target"] == "system" and calls == ["pause"]

        music.now_playing.update({"title": "t", "artist": "a", "playing": True})
        assert (await tool_control("next"))["target"] == "hud" and calls == ["pause"]
        assert [e["action"] for e in bus.since(start) if e["type"] == "music.control"] == ["next"]

        async def none(action: str):  # type: ignore[no-untyped-def]
            raise RuntimeError("No media player is active on this computer.")
        monkeypatch.setattr(sm, "control", none)
        music.now_playing.state = {}
        for act in ("resume", "pause", "next"):
            try:
                await tool_control(act)
                raise AssertionError("expected ValueError")
            except ValueError as e:
                assert "Nothing is playing" in str(e)

    asyncio.run(_run())


def test_volume_driver_pipewire_and_clamping(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def _run() -> None:
        calls: list = []
        monkeypatch.setattr(audio.platform, "system", lambda: "Linux")
        monkeypatch.setattr(audio.shutil, "which", lambda n: "/usr/bin/wpctl" if n == "wpctl" else None)
        fake_os(monkeypatch, {"wpctl get-volume": (0, "Volume: 0.45 [MUTED]")}, calls)
        st = await audio.set_volume("250")
        assert ("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "100%") in calls  # clamped, never above 100%
        assert st == {"percent": 45, "muted": True, "backend": "pipewire"}
        for bad in ("loud", "-5", "1; rm -rf /"):
            try:
                await audio.set_volume(bad)
                raise AssertionError(bad)
            except ValueError:
                pass

    asyncio.run(_run())
