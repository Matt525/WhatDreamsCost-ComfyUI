from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path("transfer")
ASSETS = ROOT / "assets"
INVENTORY: list[dict] = []
USER_AGENT = "MidnightDistrictPhase1B/1.0"


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(request, timeout=180) as response:
        return response.read()


def write_bytes(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(fetch(url))
    return destination


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
        if suffix == ".hdr":
            header = path.read_bytes()[:8192].decode("ascii", "ignore")
            match = re.search(r"[-+]Y\s+(\d+)\s+[-+]X\s+(\d+)", header)
            if match:
                return f"{match.group(2)}x{match.group(1)}"
    except Exception:
        return None
    return None


def add_inventory(
    path: Path,
    *,
    asset_id: str,
    asset_type: str,
    source_page: str,
    source_url: str,
    license_name: str = "CC0 1.0 Universal",
    attribution_required: bool = False,
    declared_resolution: str | None = None,
    notes: str | None = None,
) -> None:
    INVENTORY.append(
        {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "filename": str(path.relative_to(ROOT)),
            "source_page": source_page,
            "source_url": source_url,
            "license": license_name,
            "attribution_required": attribution_required,
            "resolution": resolution(path) or declared_resolution,
            "bytes": path.stat().st_size,
            "size_mib": round(path.stat().st_size / 1048576, 3),
            "sha256": sha256(path),
            "notes": notes,
        }
    )


def flatten_urls(value, path=()):
    results = []
    if isinstance(value, str) and value.startswith("http"):
        results.append(("/".join(path).lower(), value))
    elif isinstance(value, dict):
        for key, item in value.items():
            results.extend(flatten_urls(item, path + (str(key),)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            results.extend(flatten_urls(item, path + (str(index),)))
    return results


def polyhaven_files(asset_id: str) -> tuple[dict, str]:
    api_url = f"https://api.polyhaven.com/files/{asset_id}"
    return json.loads(fetch(api_url)), api_url


def select_model_package(asset_id: str) -> str:
    metadata, _ = polyhaven_files(asset_id)
    candidates = []
    for key_path, url in flatten_urls(metadata):
        value = f"{key_path} {url}".lower()
        if "gltf" not in value:
            continue
        if not url.lower().endswith((".zip", ".glb", ".gltf")):
            continue
        score = 0
        if "1k" in value:
            score += 100
        elif "2k" in value:
            score += 40
        if url.lower().endswith(".zip"):
            score += 50
        if url.lower().endswith(".glb"):
            score += 25
        if "blend" in value or "fbx" in value or "usd" in value:
            score -= 100
        candidates.append((score, url, key_path))
    if not candidates:
        raise RuntimeError(f"No 1K/2K glTF package exposed by Poly Haven for {asset_id}")
    candidates.sort(reverse=True)
    return candidates[0][1]


def download_polyhaven_model(asset_id: str) -> None:
    source_page = f"https://polyhaven.com/a/{asset_id}"
    package_url = select_model_package(asset_id)
    package_name = Path(urlparse(package_url).path).name or f"{asset_id}.package"
    package_path = write_bytes(package_url, ASSETS / "models" / "packages" / package_name)
    add_inventory(
        package_path,
        asset_id=asset_id,
        asset_type="model-package",
        source_page=source_page,
        source_url=package_url,
        declared_resolution="1K glTF package preferred",
    )

    extract_root = ASSETS / "models" / asset_id
    extract_root.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(package_path):
        with zipfile.ZipFile(package_path) as archive:
            archive.extractall(extract_root)
    else:
        shutil.copy2(package_path, extract_root / package_name)

    model_files = list(extract_root.rglob("*.glb")) + list(extract_root.rglob("*.gltf"))
    if not model_files:
        raise RuntimeError(f"The downloaded {asset_id} package contained no GLB/glTF model")

    for path in sorted(extract_root.rglob("*")):
        if not path.is_file():
            continue
        add_inventory(
            path,
            asset_id=asset_id,
            asset_type="model-file" if path.suffix.lower() in {".glb", ".gltf"} else "model-resource",
            source_page=source_page,
            source_url=package_url,
            declared_resolution="1K package resource",
        )

    primary = min(model_files, key=lambda item: (0 if item.suffix.lower() == ".glb" else 1, len(str(item))))
    PRIMARY_MODELS[asset_id] = str(primary.relative_to(ASSETS))


def select_texture_map(asset_id: str, map_name: str) -> str:
    metadata, _ = polyhaven_files(asset_id)
    patterns = {
        "diffuse": ["diff", "albedo", "basecolor", "base_color"],
        "normal": ["nor_gl", "normal_gl", "normal"],
        "roughness": ["rough"],
        "ao": ["ao", "ambient_occlusion"],
        "displacement": ["disp", "height"],
    }[map_name]
    candidates = []
    for key_path, url in flatten_urls(metadata):
        value = f"{key_path} {url}".lower()
        if "2k" not in value:
            continue
        if not url.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if not any(pattern in value for pattern in patterns):
            continue
        if map_name == "normal" and ("nor_dx" in value or "directx" in value):
            continue
        if map_name == "ao" and ("arm" in value or "ao_rough" in value):
            continue
        score = 0
        if url.lower().endswith((".jpg", ".jpeg")):
            score += 10
        if patterns[0] in value:
            score += 20
        candidates.append((score, url, key_path))
    if not candidates:
        raise RuntimeError(f"No 2K {map_name} map found for {asset_id}")
    candidates.sort(reverse=True)
    return candidates[0][1]


def download_texture_set(asset_id: str, local_name: str) -> None:
    source_page = f"https://polyhaven.com/a/{asset_id}"
    for map_name in ("diffuse", "normal", "roughness", "ao", "displacement"):
        url = select_texture_map(asset_id, map_name)
        extension = Path(urlparse(url).path).suffix or ".jpg"
        path = write_bytes(url, ASSETS / "textures" / local_name / f"{map_name}{extension}")
        add_inventory(
            path,
            asset_id=asset_id,
            asset_type=f"texture-{map_name}",
            source_page=source_page,
            source_url=url,
            declared_resolution="2048x2048",
        )
        if resolution(path) != "2048x2048":
            raise RuntimeError(f"{asset_id}/{map_name} is not 2048x2048: {resolution(path)}")


def download_hdri() -> None:
    asset_id = "urban_street_03"
    metadata, _ = polyhaven_files(asset_id)
    candidates = []
    for key_path, url in flatten_urls(metadata):
        value = f"{key_path} {url}".lower()
        if "2k" in value and url.lower().endswith(".hdr"):
            candidates.append(url)
    if not candidates:
        raise RuntimeError("No 2K HDR file found for urban_street_03")
    url = sorted(candidates)[0]
    path = write_bytes(url, ASSETS / "hdri" / "urban_street_03_2k.hdr")
    actual_resolution = resolution(path)
    if actual_resolution != "2048x1024":
        raise RuntimeError(f"HDRI resolution is {actual_resolution}, expected 2048x1024")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise RuntimeError(f"HDRI exceeds the 10 MiB limit: {path.stat().st_size} bytes")
    add_inventory(
        path,
        asset_id=asset_id,
        asset_type="hdri",
        source_page=f"https://polyhaven.com/a/{asset_id}",
        source_url=url,
        declared_resolution="2048x1024",
        notes="Hard limit: 2K and <=10 MiB",
    )


PRIMARY_MODELS: dict[str, str] = {}


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ASSETS.mkdir(parents=True, exist_ok=True)

    for model_id in (
        "covered_car",
        "modular_urban_apartments_facade",
        "modular_factory_facade",
    ):
        download_polyhaven_model(model_id)

    for texture_id, local_name in (
        ("worn_asphalt", "worn_asphalt"),
        ("concrete_tiles_02", "concrete_tiles_02"),
        ("concrete_layers", "concrete_layers"),
        ("rectangular_facade_tiles_02", "rectangular_facade_tiles_02"),
    ):
        download_texture_set(texture_id, local_name)

    download_hdri()

    INVENTORY.append(
        {
            "asset_id": "fab_generic_sedan_v1",
            "asset_type": "purchase-gated-model",
            "filename": None,
            "source_page": "https://www.fab.com/listings/1f87a166-d522-4869-ab74-c12e0f3f7f45",
            "source_url": None,
            "license": "Fab Standard License after purchase",
            "attribution_required": False,
            "resolution": "2K PBR maps advertised",
            "bytes": None,
            "size_mib": None,
            "sha256": None,
            "notes": "Not downloaded: paid Fab asset requires the user's licensed purchase. No substitute or fallback is permitted.",
        }
    )

    INVENTORY.sort(key=lambda item: (item["asset_id"], item.get("filename") or ""))
    (ROOT / "asset-inventory.json").write_text(json.dumps(INVENTORY, indent=2))
    (ROOT / "model-primary-paths.json").write_text(json.dumps(PRIMARY_MODELS, indent=2))
    (ROOT / "ASSET_LICENSES.md").write_text(
        "# Phase 1B asset licensing\n\n"
        "- Poly Haven assets in this bundle: CC0 1.0 Universal; attribution not required.\n"
        "- Sketchfab assets used: none.\n"
        "- Kenney assets used: none in the approved Phase 1B bundle.\n"
        "- Fab V1 Generic Sedan: not bundled; purchase-gated under the Fab Standard License. Attribution is not required after purchase, but standalone redistribution is prohibited.\n"
        "- No procedural or generated replacement is authorized for any missing approved asset.\n"
    )
    print(json.dumps({"files": len(INVENTORY), "primary_models": PRIMARY_MODELS}, indent=2))


if __name__ == "__main__":
    main()
