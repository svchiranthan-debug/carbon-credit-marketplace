"""
Live Sentinel-2 NDVI check against Microsoft Planetary Computer.

Runs every stage of the real pipeline and prints PASS/FAIL for each one, so a failure points
at the exact stage (catalogue search, token, band download, masking, NDVI):

    cd backend
    python scripts/check_live_ndvi.py                     # demo 1-acre areca plot (seed_data.py)
    python scripts/check_live_ndvi.py --lat 12.759 --lon 75.201 --area 0.4047
    python scripts/check_live_ndvi.py --plantation-id 3   # use a plot (and its drawn boundary) from the DB
    python scripts/check_live_ndvi.py --plantation-id 3 --persist
        # also runs the real verification for that plot and saves it (adds one verification
        # record; nothing is deleted). The plot needs a photo and SOC for a scored decision.

Exit code 0 only if real Sentinel-2 band pixels were read and NDVI was computed from them.
A 200 from the catalogue or token endpoint alone is NOT reported as success.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.services.ai import satellite_client as sc  # noqa: E402

DEMO = {"lat": 12.7590, "lon": 75.2010, "area": 0.4047}


def stage(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--area", type=float, help="hectares (used when there is no drawn boundary)")
    ap.add_argument("--plantation-id", type=int)
    ap.add_argument("--persist", action="store_true", help="run and save a real verification for --plantation-id")
    args = ap.parse_args()

    settings.ENABLE_REAL_SATELLITE_QUERIES = True
    boundary = None
    plantation = db = None
    if args.plantation_id:
        from app.database import SessionLocal, init_db
        from app.models.plantation import Plantation
        from app.services.geometry import lonlat_ring
        init_db()
        db = SessionLocal()
        plantation = db.get(Plantation, args.plantation_id)
        if plantation is None:
            print(f"No plantation with id {args.plantation_id}.")
            return 2
        lat, lon, area = plantation.latitude, plantation.longitude, plantation.area_hectares
        boundary = lonlat_ring(plantation.boundary_geojson) or None
        print(f"Plot #{plantation.id} '{plantation.name}'")
    else:
        lat = args.lat if args.lat is not None else DEMO["lat"]
        lon = args.lon if args.lon is not None else DEMO["lon"]
        area = args.area if args.area is not None else DEMO["area"]

    fp = sc.make_footprint(lat, lon, area, boundary)
    print(f"Footprint: {fp.kind}, bbox {[round(v, 5) for v in fp.bbox]}")
    print(f"Search: last {settings.SATELLITE_LOOKBACK_DAYS} days, scene cloud < {settings.SATELLITE_MAX_SCENE_CLOUD_PCT}%\n")

    # 1. catalogue search
    t = time.time()
    try:
        scenes = sc.SatelliteClient.search_scenes(fp, settings.SATELLITE_MAX_SCENE_CLOUD_PCT, settings.SATELLITE_LOOKBACK_DAYS)
    except sc.SatelliteAccessError as exc:
        stage("1. STAC search", False, str(exc))
        return 1
    if not stage("1. STAC search", bool(scenes), f"{len(scenes)} scene(s) in {time.time() - t:.1f}s"):
        print("   No scene matched. Try a larger --lookback via SATELLITE_LOOKBACK_DAYS or a higher cloud limit.")
        return 1
    for s in scenes[:3]:
        p = s.get("properties", {})
        print(f"   {s.get('id')}  {str(p.get('datetime'))[:10]}  cloud {p.get('eo:cloud_cover')}%")

    # 2. token
    try:
        token = sc.SatelliteClient.get_sas_token()
        stage("2. SAS token", True, f"expires {sc.SatelliteClient._token_expiry:%Y-%m-%d %H:%M} UTC (token not printed)")
    except sc.SatelliteAccessError as exc:
        stage("2. SAS token", False, str(exc))
        return 1

    # 3-5. per scene: band download, masking, NDVI
    for scene in scenes[: settings.SATELLITE_MAX_SCENES_TRIED]:
        sid = scene.get("id")
        assets = scene.get("assets", {})
        try:
            hrefs = {b: sc.SatelliteClient._sign_href(assets[b]["href"]) for b in ("B04", "B08", "SCL")}
        except KeyError as exc:
            stage(f"3. Band assets ({sid})", False, f"missing {exc}")
            continue
        try:
            t = time.time()
            red, transform, crs = sc.SatelliteClient._read_window(hrefs["B04"], fp)
            stage(f"3a. Read B04 window ({sid})", True, f"{red.shape[1]}x{red.shape[0]} px, CRS {crs}, {time.time() - t:.1f}s")
            nir, _, _ = sc.SatelliteClient._read_window(hrefs["B08"], fp)
            stage("3b. Read B08 window", True, f"{nir.shape[1]}x{nir.shape[0]} px")
            scl, _, _ = sc.SatelliteClient._read_window(hrefs["SCL"], fp, out_shape=red.shape)
            stage("3c. Read SCL window", True, "resampled to the 10 m grid")
        except Exception as exc:  # noqa: BLE001
            stage(f"3. Band download ({sid})", False, f"{exc.__class__.__name__}: {sc.sanitize(exc)}")
            continue

        result, reason = sc.SatelliteClient._ndvi_from_scene(scene, fp)
        if result is None:
            stage(f"4. Mask + NDVI ({sid})", False, reason)
            continue
        stage("4. Polygon + cloud mask", True,
              f"{result['footprint_pixel_count']} plot pixels, {result['clear_pixel_pct']}% cloud-free")
        stage("5. NDVI from real pixels", True,
              f"mean {result['mean_ndvi']}  min {result['min_ndvi']}  max {result['max_ndvi']}  "
              f"canopy>=0.40 {result['vegetation_coverage_pct']}%  ({result['valid_pixel_count']} px)")
        print(f"\n   Scene ID:         {result['scene_id']}")
        print(f"   Acquisition date: {result['acquisition_date']}")
        print(f"   Scene cloud:      {result['cloud_cover_pct']}%")
        print(f"   STAC item:        {result['stac_item_url']}")

        if args.persist and plantation is not None:
            from app.models.user import User
            from app.routers.verification import _execute_verification
            actor = db.query(User).filter(User.role == "ADMIN").first() or db.get(User, plantation.farmer_id)
            v = _execute_verification(plantation, actor, db)
            snap = (v.evidence_snapshot or {}).get("ndvi_measurement", {})
            ok = v.ndvi_provenance == "SENTINEL2_COMPUTED"
            stage("6. Verification saved", ok,
                  f"id {v.id}, decision {v.decision}, provenance {v.ndvi_provenance}, scene {snap.get('scene_id')}")
            if not ok:
                return 1
        print("\nLIVE CHECK PASSED: real Sentinel-2 pixels were read and NDVI computed from them.")
        return 0

    print("\nLIVE CHECK FAILED: no scene could be read and processed (see the FAIL lines above).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
