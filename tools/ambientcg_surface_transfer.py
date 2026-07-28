from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("ambientcg-transfer")
ZIP_ROOT = ROOT / "source-zips"
TEXTURE_ROOT = ROOT / "assets" / "textures"

ASSETS = [
    {
        "asset_id": "Asphalt031",
        "role": "road_asphalt",
        "title": "Asphalt 031",
        "resolution": "2K-JPG",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=Asphalt031",
    },
    {
        "asset_id": "PavingStones107",
        "role": "sidewalk_pavers",
        "title": "Paving Stones 107",
        "resolution": "2K-JPG",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=PavingStones107",
    },
    {
        "asset_id": "Bricks091",
        "role": "weathered_brick",
        "title": "Bricks 091",
        "resolution": "2K-JPG",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=Bricks091",
    },
    {
        "asset_id": "Concrete010",
        "role": "architectural_concrete",
        "title": "Concrete 010",
        "resolution": "2K-JPG",
        "technique": "Procedural PBR",
        "source_page": "https://ambientcg.com/view?id=Concrete010",
    },
    {
        "asset_id": "Metal022",
        "role": "rusted_metal",
        "title": "Metal 022",
        "resolution": "2K-JPG",
        "technique": "Procedural PBR",
        "source_page": "https://ambientcg.com/view?id=Metal022",
    },
    {
        "asset_id": "Planks021",
        "role": "weathered_wood",
        "title": "Planks 021",
        "resolution": "2K-JPG",
        "technique": "Surface Photogrammetry",
        "source_page": "https://ambientcg.com/view?id=Planks021",
    },
    {
        "asset_id": "Rubber002",
        "role": "tire_rubber",
        "title": "Rubber 002",
        "resolution": "2K-JPG",
        "technique": "Procedural PBR",
        "source_page": "https://ambientcg.com/view?id=Rubber002",
    },
    {
        "asset_id": "Plastic006",
        "role": "black_plastic",
        "title": "Plastic 006",
        "resolution": "2K-JPG",
        "technique": "Procedural PBR",
        "source_page": "https://ambientcg.com/view?id=Plastic006",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "MidnightDistrictPhase1B/2.0",
            "Accept": "application/zip,application/octet-stream,*/*",
        },
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=300) as response:
        final_url = response.geturl()
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    return final_url


def classify(filename: str) -> str | None:
    lower = filename.lower()
    if "_color" in lower or "_basecolor" in lower:
        return "diffuse"
    if "_normalgl" in lower or "_normal_gl" in lower:
        return "normal"
    if "_roughness" in lower:
        return "roughness"
    if "_ambientocclusion" in lower or "_ao" in lower:
        return "ao"
    if "_displacement" in lower or "_height" in lower:
        return "displacement"
    if "_metalness" in lower or "_metallic" in lower:
        return "metalness"
    return None


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ZIP_ROOT.mkdir(parents=True)
    TEXTURE_ROOT.mkdir(parents=True)

    inventory: list[dict] = []
    manifest: dict[str, dict] = {}

    for asset in ASSETS:
        asset_id = asset["asset_id"]
        resolution = asset["resolution"]
        request_url = f"https://ambientcg.com/get?file={asset_id}_{resolution}.zip"
        zip_path = ZIP_ROOT / f"{asset_id}_{resolution}.zip"
        final_url = download(request_url, zip_path)

        if not zipfile.is_zipfile(zip_path):
            raise RuntimeError(f"Downloaded file is not a ZIP: {zip_path}")

        role_dir = TEXTURE_ROOT / asset["role"]
        role_dir.mkdir(parents=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(role_dir)

        maps: dict[str, str] = {}
        for path in sorted(role_dir.rglob("*")):
            if not path.is_file():
                continue
            map_type = classify(path.name)
            if map_type and map_type not in maps:
                maps[map_type] = str(path.relative_to(ROOT))
            inventory.append(
                {
                    "asset_id": asset_id,
                    "role": asset["role"],
                    "asset_type": "texture-map",
                    "filename": str(path.relative_to(ROOT)),
                    "source_page": asset["source_page"],
                    "request_url": request_url,
                    "source_url": final_url,
                    "resolution": "2048x2048",
                    "technique": asset["technique"],
                    "license": "CC0 1.0 Universal",
                    "attribution_required": False,
                    "bytes": path.stat().st_size,
                    "size_mib": round(path.stat().st_size / 1048576, 3),
                    "sha256": sha256(path),
                }
            )

        required = {"diffuse", "normal", "roughness", "displacement"}
        missing = sorted(required - set(maps))
        if missing:
            raise RuntimeError(f"{asset_id} missing required PBR maps: {missing}; found {sorted(maps)}")

        manifest[asset["role"]] = {
            **asset,
            "request_url": request_url,
            "source_url": final_url,
            "zip_filename": str(zip_path.relative_to(ROOT)),
            "zip_bytes": zip_path.stat().st_size,
            "zip_size_mib": round(zip_path.stat().st_size / 1048576, 3),
            "zip_sha256": sha256(zip_path),
            "maps": maps,
            "license": "CC0 1.0 Universal",
            "attribution_required": False,
        }

    inventory.sort(key=lambda item: (item["role"], item["filename"]))
    (ROOT / "ambientcg-material-manifest.json").write_text(json.dumps(manifest, indent=2))
    (ROOT / "ambientcg-asset-inventory.json").write_text(json.dumps(inventory, indent=2))
    (ROOT / "AMBIENTCG_LICENSE.md").write_text(
        "# AmbientCG material license\n\n"
        "All selected materials are distributed by ambientCG under CC0 1.0 Universal. "
        "Commercial use, modification, and redistribution inside the game are permitted. "
        "Attribution is not required.\n"
    )

    print(json.dumps({
        "materials": len(manifest),
        "texture_files": len(inventory),
        "total_zip_mib": round(sum(item["zip_bytes"] for item in manifest.values()) / 1048576, 3),
        "roles": sorted(manifest),
    }, indent=2))


if __name__ == "__main__":
    main()
