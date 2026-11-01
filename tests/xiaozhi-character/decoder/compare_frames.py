"""Compare the unchanged firmware GIF decoder output with Pillow, byte for byte."""
from pathlib import Path
from PIL import Image
import hashlib
import json
import sys

here = Path(sys.argv[1]).resolve()
assets = Path(sys.argv[2]).resolve()
results = []
for stem, short in [("character_idle", "idle"), ("character_talking", "talking")]:
    with Image.open(assets / f"{stem}.gif") as image:
        frames = []
        delays = []
        assert image.size == (96, 96)
        assert image.info["loop"] == 0
        for index in range(image.n_frames):
            image.seek(index)
            frames.append(image.convert("RGBA").tobytes("raw", "BGRA"))
            delays.append(image.info["duration"])
        expected = b"".join(frames) * 5
        for cache in (0, 1):
            actual = (here / f"{short}{cache}.bgra").read_bytes()
            assert actual == expected, f"{stem}: cache={cache} mismatch"
            results.append({"asset": stem, "cache": cache, "frames": len(frames),
                            "loops_compared": 5, "durations_ms": delays,
                            "decoded_bytes": len(actual),
                            "sha256": hashlib.sha256(actual).hexdigest(),
                            "pillow_byte_comparison": "PASS"})
(here / "comparison-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
