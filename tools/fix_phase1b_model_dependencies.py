from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path("transfer")
INVENTORY_PATH = ROOT / "asset-inventory.json"
USER_AGENT = "MidnightDistrictPhase1B/1.0"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=180) as response:
        return response.read()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolution(path: Path) -> str | None:
    suffix = path.suffix.lower()
    try:
        if suffix == ".png":
            data = path.read_bytes()[:32]
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                return f"{struct.unpack('>I', data[16:20])[0]}x{struct.unpack('>I', data[20:24])[0]}"
        if suffix in {".jpg", ".jpeg"}:
            data = path.read_bytes()
            cursor = 2
            while cursor < len(data) - 9:
                if data[cursor] != 0xFF:
                    cursor += 1
                    continue
                marker = data[cursor + 1]
                cursor += 2
                if marker in {0xD8, 0xD9}:
                    continue
                segment_length = int.from_bytes(data[cursor:cursor + 2], "big")
                if marker in range(0xC0, 0xC4):
                    height = int.from_bytes(data[cursor + 3:cursor + 5], "big")
                    width = int.from_bytes(data[cursor + 5:cursor + 7], "big")
                    return f"{width}x{height}"
                cursor += segment_length
    except Exception:
        return None
    return None


def main() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text())
    additions = []
    existing = {item.get("filename") for item in inventory}

    gltf_entries = [
        item for item in inventory
        if item.get("asset_type") == "model-file"
        and item.get("filename", "").lower().endswith(".gltf")
    ]

    for item in gltf_entries:
        gltf_path = ROOT / item["filename"]
        model = json.loads(gltf_path.read_text())
        references = []
        references.extend(buffer.get("uri") for buffer in model.get("buffers", []) if buffer.get("uri"))
        references.extend(image.get("uri") for image in model.get("images", []) if image.get("uri"))

        for relative_uri in sorted(set(references)):
            if relative_uri.startswith("data:"):
                continue
            destination = gltf_path.parent / relative_uri
            inventory_name = str(destination.relative_to(ROOT))
            if inventory_name in existing:
                continue
            source_url = urljoin(item["source_url"], relative_uri)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(fetch(source_url))
            additions.append(
                {
                    "asset_id": item["asset_id"],
                    "asset_type": "model-resource",
                    "filename": inventory_name,
                    "source_page": item["source_page"],
                    "source_url": source_url,
                    "license": item["license"],
                    "attribution_required": item["attribution_required"],
                    "resolution": resolution(destination) or "binary geometry buffer",
                    "bytes": destination.stat().st_size,
                    "size_mib": round(destination.stat().st_size / 1048576, 3),
                    "sha256": sha256(destination),
                    "notes": "Dependency referenced directly by the approved glTF model.",
                }
            )
            existing.add(inventory_name)

    inventory.extend(additions)
    inventory.sort(key=lambda entry: (entry["asset_id"], entry.get("filename") or ""))
    INVENTORY_PATH.write_text(json.dumps(inventory, indent=2))

    unresolved = []
    for item in gltf_entries:
        gltf_path = ROOT / item["filename"]
        model = json.loads(gltf_path.read_text())
        references = []
        references.extend(buffer.get("uri") for buffer in model.get("buffers", []) if buffer.get("uri"))
        references.extend(image.get("uri") for image in model.get("images", []) if image.get("uri"))
        for relative_uri in references:
            if not relative_uri.startswith("data:") and not (gltf_path.parent / relative_uri).is_file():
                unresolved.append(f"{item['asset_id']}: {relative_uri}")
    if unresolved:
        raise RuntimeError("Missing glTF dependencies:\n" + "\n".join(unresolved))

    print(json.dumps({"downloaded_dependencies": len(additions), "unresolved": unresolved}, indent=2))


if __name__ == "__main__":
    main()
