import shutil
import subprocess
from pathlib import Path
from typing import Any


class SystemDependencyError(RuntimeError):
    """Raised when an external system binary is required but not found in PATH."""

    def __init__(self, binary_name: str, install_hint: str):
        super().__init__(
            f"Required system binary '{binary_name}' was not found in PATH. {install_hint}"
        )
        self.binary_name = binary_name
        self.install_hint = install_hint


class SystemEnvironment:
    """Centralized checker for external command-line tools and system capabilities."""

    INSTALL_HINTS = {
        "ffmpeg": "Please install ffmpeg (e.g. 'sudo pacman -S ffmpeg' or 'sudo apt install ffmpeg').",
        "ffprobe": "Please install ffprobe / ffmpeg (e.g. 'sudo pacman -S ffmpeg' or 'sudo apt install ffmpeg').",
        "fpcalc": "Please install chromaprint (e.g. 'sudo pacman -S chromaprint' or 'sudo apt install libchromaprint-tools').",
        "notify-send": "Please install libnotify (e.g. 'sudo pacman -S libnotify' or 'sudo apt install libnotify-bin').",
    }

    @classmethod
    def get_binary_path(cls, binary: str) -> Path | None:
        which_path = shutil.which(binary)
        return Path(which_path) if which_path else None

    @classmethod
    def is_available(cls, binary: str) -> bool:
        return cls.get_binary_path(binary) is not None

    @classmethod
    def require_binary(cls, binary: str) -> Path:
        path = cls.get_binary_path(binary)
        if not path:
            hint = cls.INSTALL_HINTS.get(binary, f"Please install {binary} on your system.")
            raise SystemDependencyError(binary, hint)
        return path

    @classmethod
    def check_ffmpeg(cls) -> bool:
        return cls.is_available("ffmpeg")

    @classmethod
    def check_ffprobe(cls) -> bool:
        return cls.is_available("ffprobe")

    @classmethod
    def check_fpcalc(cls) -> bool:
        return cls.is_available("fpcalc")

    @classmethod
    def check_notify_send(cls) -> bool:
        return cls.is_available("notify-send")

    @classmethod
    def get_tool_version(cls, binary: str) -> str | None:
        path = cls.get_binary_path(binary)
        if not path:
            return None
        try:
            if binary in ["ffmpeg", "ffprobe"]:
                proc = subprocess.run(
                    [str(path), "-version"], capture_output=True, text=True, timeout=3
                )
                if proc.returncode == 0:
                    first_line = proc.stdout.splitlines()[0]
                    return (
                        first_line.split(" Copyright")[0]
                        .replace("ffmpeg version ", "")
                        .replace("ffprobe version ", "")
                        .strip()
                    )
            elif binary == "fpcalc":
                proc = subprocess.run([str(path), "-v"], capture_output=True, text=True, timeout=3)
                output = proc.stdout or proc.stderr
                if output:
                    return output.strip().splitlines()[0].replace("fpcalc version ", "").strip()
        except Exception:
            pass
        return "installed"

    @classmethod
    def get_diagnostics(cls) -> dict[str, dict[str, Any]]:
        tools = ["ffmpeg", "ffprobe", "fpcalc", "notify-send"]
        diagnostics = {}
        for tool in tools:
            path = cls.get_binary_path(tool)
            is_present = path is not None
            diagnostics[tool] = {
                "available": is_present,
                "path": str(path) if path else None,
                "version": cls.get_tool_version(tool) if is_present else None,
                "hint": cls.INSTALL_HINTS.get(tool, ""),
                "required": tool in ["ffmpeg"],
            }
        return diagnostics
