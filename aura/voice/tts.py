"""
AURA OS — Text-To-Speech
Backends: macOS `say`, Piper (neural, needs a downloaded .onnx voice), espeak-ng (tiny, works
on every Pi). Playback runs as a child process group so barge-in / palm-pause can kill it instantly.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shlex
import shutil
import signal
from pathlib import Path
from typing import List, Optional

from aura.core.logger import logger


def find_piper_model(voice: str) -> Optional[Path]:
    if voice.endswith(".onnx") and Path(voice).is_file():
        return Path(voice)
    for base in (Path.home() / ".local/share/piper", Path("/usr/share/piper-voices"),
                 Path("/opt/piper/voices"), Path.cwd() / "models"):
        cand = base / f"{voice}.onnx"
        if cand.is_file():
            return cand
    return None


class TextToSpeech:
    def __init__(
        self,
        voice: str = "en_US-lessac-medium",
        backend: Optional[str] = None,
        output_device: Optional[str] = None,
    ) -> None:
        self.voice = voice
        self.requested_backend = backend or os.environ.get("AURA_TTS_BACKEND", "auto")
        self.output_device = output_device
        self.is_speaking = False
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._backend: Optional[str] = None

    @property
    def backend(self) -> str:
        if self._backend is None:
            want = self.requested_backend
            choices: List[str] = []
            if want == "auto":
                if platform.system() == "Darwin" and shutil.which("say"):
                    choices.append("say")
                if shutil.which("piper") and find_piper_model(self.voice):
                    choices.append("piper")
                if shutil.which("espeak-ng") or shutil.which("espeak"):
                    choices.append("espeak")
            else:
                choices.append(want)
            self._backend = next((c for c in choices if self._usable(c)), "none")
            logger.info(f"TTS backend: {self._backend}")
        return self._backend

    def _usable(self, name: str) -> bool:
        return {
            "say": bool(shutil.which("say")),
            "piper": bool(shutil.which("piper") and find_piper_model(self.voice)),
            "espeak": bool(shutil.which("espeak-ng") or shutil.which("espeak")),
            "none": True,
        }.get(name, False)

    def _command(self, backend: str) -> Optional[str]:
        """Shell pipeline that reads the text on stdin (so text is never shell-interpolated)."""
        dev = f"-D {shlex.quote(self.output_device)}" if self.output_device else ""
        if backend == "say":
            return "say -f -"
        if backend == "espeak":
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            return f"{shlex.quote(str(exe))} -v en-us -s 165 --stdin"
        if backend == "piper":
            model = find_piper_model(self.voice)
            return (f"{shlex.quote(str(shutil.which('piper')))} --model {shlex.quote(str(model))} "
                    f"--output-raw | aplay -q {dev} -r 22050 -f S16_LE -t raw -")
        return None

    async def speak(self, text: str) -> None:
        self.stop()
        text = text.strip()
        if not text:
            return
        self.is_speaking = True
        logger.info(f'AURA speaking: "{text}"')
        try:
            cmd = self._command(self.backend)
            if cmd is None:
                await asyncio.sleep(min(6.0, max(0.2, len(text) * 0.04)))  # silent: simulate duration
                return
            self._proc = await asyncio.create_subprocess_shell(
                cmd, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
            assert self._proc.stdin is not None
            self._proc.stdin.write(text.encode("utf-8"))
            await self._proc.stdin.drain()
            self._proc.stdin.close()
            await self._proc.wait()
        except asyncio.CancelledError:
            logger.info("Speech cancelled.")
        except Exception as e:
            logger.warning(f"TTS playback error: {e}")
        finally:
            self._kill()
            self.is_speaking = False

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc and proc.returncode is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

    def stop(self) -> None:
        """Silence speech immediately."""
        self._kill()
        self.is_speaking = False
