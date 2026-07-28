from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("ambientcg-major-v2")
ASSETS = [
    {
        "asset_id": "Asphalt006",
        "role": "road_reference",
        "title": "Asphalt 006 — exact user reference",
        "technique": "Approximation",
        "source_page": "https://ambientcg.com/view?id=Asphalt006",
    },
    {
        "asset_id": "Asphalt030",
        "role": "road_photogrammetry",
        "title": "Asphalt 030 — photogrammetry alternative",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=Asphalt030",
    },
    {
        "asset_id": "PavingStones027",
        "role": "sidewalk_pavers",
        "title": "Paving Stones 027 — urban sidewalk",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=PavingStones027",
    },
    {
        "asset_id": "Bricks097",
        "role": "weathered_brick",
        "title": "Bricks 097 — damaged industrial brick",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=Bricks097",
    },
    {
        "asset_id": "Concrete023",
        "role": "architectural_concrete",
        "title": "Concrete 023 — patched concrete",
        "technique": "Procedural PBR",
        "source_page": "https://ambientcg.com/view?id=Concrete023",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> str:
    request = Request(url, headers={"User-Agent": "MidnightDistrictPhase1B/2.1", "Accept": "*/*"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=300) as response:
        final_url = response.geturl()
        destination.write_bytes(response.read())
    return final_url


def classify(name: str) -> str | None:
    lower = name.lower()
    if "_color" in lower or "_basecolor" in lower: return "diffuse"
    if "_normalgl" in lower or "_normal_gl" in lower: return "normal"
    if "_roughness" in lower: return "roughness"
    if "_ambientocclusion" in lower or "_ao" in lower: return "ao"
    if "_displacement" in lower or "_height" in lower: return "displacement"
    if "_metalness" in lower or "_metallic" in lower: return "metalness"
    return None


def main() -> None:
    if ROOT.exists(): shutil.rmtree(ROOT)
    (ROOT / "assets" / "textures").mkdir(parents=True)
    inventory = []
    manifest = {}

    for asset in ASSETS:
        request_url = f"https://ambientcg.com/get?file={asset['asset_id']}_2K-JPG.zip"
        temporary_zip = ROOT / f".{asset['asset_id']}.zip"
        final_url = download(request_url, temporary_zip)
        if not zipfile.is_zipfile(temporary_zip):
            raise RuntimeError(f"Not a ZIP: {asset['asset_id']}")

        output_dir = ROOT / "assets" / "textures" / asset["role"]
        output_dir.mkdir(parents=True)
        maps = {}
        with zipfile.ZipFile(temporary_zip) as archive:
            for member in archive.infolist():
                map_type = classify(Path(member.filename).name)
                if map_type is None or not member.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                if map_type in maps:
                    continue
                extension = Path(member.filename).suffix.lower()
                destination = output_dir / f"{map_type}{extension}"
                destination.write_bytes(archive.read(member))
                relative = str(destination.relative_to(ROOT))
                maps[map_type] = relative
                inventory.append({
                    "asset_id": asset["asset_id"],
                    "role": asset["role"],
                    "asset_type": "texture-map",
                    "map_type": map_type,
                    "filename": relative,
                    "source_page": asset["source_page"],
                    "request_url": request_url,
                    "source_url": final_url,
                    "resolution": "2048x2048",
                    "technique": asset["technique"],
                    "license": "CC0 1.0 Universal",
                    "attribution_required": False,
                    "bytes": destination.stat().st_size,
                    "size_mib": round(destination.stat().st_size / 1048576, 3),
                    "sha256": sha256(destination),
                })
        zip_bytes = temporary_zip.stat().st_size
        zip_hash = sha256(temporary_zip)
        temporary_zip.unlink()
        required = {"diffuse", "normal", "roughness", "displacement"}
        missing = sorted(required - set(maps))
        if missing: raise RuntimeError(f"{asset['asset_id']} missing {missing}")
        manifest[asset["role"]] = {
            **asset,
            "resolution": "2K-JPG",
            "maps": maps,
            "request_url": request_url,
            "source_url": final_url,
            "source_zip_bytes": zip_bytes,
            "source_zip_size_mib": round(zip_bytes / 1048576, 3),
            "source_zip_sha256": zip_hash,
            "license": "CC0 1.0 Universal",
            "attribution_required": False,
        }

    inventory.sort(key=lambda item: (item["role"], item["map_type"]))
    (ROOT / "major-surface-manifest.json").write_text(json.dumps(manifest, indent=2))
    (ROOT / "major-surface-inventory.json").write_text(json.dumps(inventory, indent=2))
    (ROOT / "LICENSE.md").write_text("All materials in this packet are from ambientCG and licensed CC0 1.0 Universal. Attribution is not required.\n")
    print(json.dumps({"materials": list(manifest), "files": len(inventory), "bytes": sum(x["bytes"] for x in inventory)}, indent=2))


if __name__ == "__main__":
    main()
