from __future__ import annotations

from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent / "logs"
MAX_BYTES = 2_000_000
KEEP_ROTATIONS = 5
LOG_FILES = [
    "sync.log",
    "launchd.out.log",
    "launchd.err.log",
    "backend_dev.log",
    "frontend_dev.log",
]


def rotate_file(path: Path):
    if not path.exists() or path.stat().st_size < MAX_BYTES:
        return

    oldest = path.with_name(f"{path.name}.{KEEP_ROTATIONS}")
    if oldest.exists():
        oldest.unlink()

    for index in range(KEEP_ROTATIONS - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        target = path.with_name(f"{path.name}.{index + 1}")
        if source.exists():
            source.rename(target)

    path.rename(path.with_name(f"{path.name}.1"))
    path.touch()


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for filename in LOG_FILES:
        rotate_file(LOG_DIR / filename)


if __name__ == "__main__":
    main()
