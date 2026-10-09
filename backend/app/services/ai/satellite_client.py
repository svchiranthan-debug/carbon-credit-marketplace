"""
Sentinel-2 L2A NDVI client.

Queries the Microsoft Planetary Computer STAC API for a recent, low-cloud Sentinel-2 L2A
scene covering the plantation, then reads ONLY the pixels inside the plantation footprint
(the farmer's drawn boundary polygon when available, otherwise a square of the plot's area
around its centre) from the Red (B04) and Near-Infrared (B08) bands. Pixels that the scene
classification layer (SCL) marks as cloud, cloud shadow, cirrus, snow, saturated or no-data
are excluded, and computes

    NDVI = (NIR - Red) / (NIR + Red)

Honesty rules (these are deliberate and covered by tests):
  * NDVI statistics are only ever produced from real band pixels.
  * If the service is disabled, unreachable, finds no scene, or band pixels cannot be
    read, the result is ``available=False`` with a reason. No simulated or "derived"
    values are substituted, and nothing is labelled as real satellite data unless pixels
    were actually read.
"""
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

from ...config import settings

logger = logging.getLogger(__name__)

NDVI_FORMULA = "NDVI = (NIR [B08] - Red [B04]) / (NIR [B08] + Red [B04])"
COLLECTION = "sentinel-2-l2a"
# Sentinel-2 processing baseline 04.00+ (Jan 2022 onward) adds a -1000 DN offset to L2A reflectance.
BOA_ADD_OFFSET = -1000.0
QUANTIFICATION_VALUE = 10000.0


def unavailable(reason: str, bbox: Optional[List[float]] = None) -> Dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "bounding_box": bbox,
        "formula": NDVI_FORMULA,
    }


# Sentinel-2 Scene Classification (SCL) classes that are not usable ground observations.
SCL_EXCLUDED = {0, 1, 3, 8, 9, 10, 11}  # no-data, saturated/defective, cloud shadow, cloud med/high, cirrus, snow
MIN_CLEAR_FRACTION = 0.5  # at least half of the plot's pixels must be cloud-free


class Footprint:
    """The area NDVI is measured over: a boundary polygon (lon/lat ring) or a square approximation."""

    def __init__(self, bbox: List[float], polygon: Optional[List[List[float]]], kind: str):
        self.bbox = bbox
        self.polygon = polygon  # closed ring of [lon, lat], or None
        self.kind = kind        # "POLYGON" | "SQUARE_APPROX"

    def geojson(self) -> Dict[str, Any]:
        if self.polygon:
            return {"type": "Polygon", "coordinates": [self.polygon]}
        b = self.bbox
        return {"type": "Polygon", "coordinates": [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]]}


def footprint_bbox(latitude: float, longitude: float, area_hectares: Optional[float]) -> List[float]:
    """[min_lon, min_lat, max_lon, max_lat] of a square with the plantation's area, centred on it.

    Used when no boundary polygon was stored. A minimum 20 m x 20 m box keeps at least a few
    10 m pixels inside the window for very small plots.
    """
    area_m2 = max((area_hectares or 0.0) * 10_000.0, 400.0)
    half_side_m = math.sqrt(area_m2) / 2.0
    dlat = half_side_m / 111_320.0
    dlon = half_side_m / (111_320.0 * max(math.cos(math.radians(latitude)), 1e-6))
    return [longitude - dlon, latitude - dlat, longitude + dlon, latitude + dlat]


def make_footprint(latitude: float, longitude: float, area_hectares: Optional[float],
                   boundary_lonlat: Optional[List[List[float]]] = None) -> Footprint:
    if boundary_lonlat and len(boundary_lonlat) >= 4:
        lons = [p[0] for p in boundary_lonlat]
        lats = [p[1] for p in boundary_lonlat]
        return Footprint([min(lons), min(lats), max(lons), max(lats)], boundary_lonlat, "POLYGON")
    return Footprint(footprint_bbox(latitude, longitude, area_hectares), None, "SQUARE_APPROX")


def dn_to_reflectance(dn: np.ndarray, processing_baseline: Optional[str]) -> np.ndarray:
    """Convert L2A digital numbers to surface reflectance; DN 0 is no-data (returned as NaN)."""
    arr = dn.astype(np.float64)
    offset = 0.0
    try:
        if processing_baseline and float(processing_baseline) >= 4.0:
            offset = BOA_ADD_OFFSET
    except ValueError:
        pass
    refl = (arr + offset) / QUANTIFICATION_VALUE
    refl[arr == 0] = np.nan
    return refl


def compute_ndvi(red_refl: np.ndarray, nir_refl: np.ndarray) -> np.ndarray:
    """Pixel-wise NDVI; invalid pixels (no-data or zero denominator) become NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = nir_refl + red_refl
        ndvi = (nir_refl - red_refl) / denom
    ndvi[~np.isfinite(ndvi)] = np.nan
    return np.clip(ndvi, -1.0, 1.0)


def summarize_ndvi(ndvi: np.ndarray) -> Optional[Dict[str, float]]:
    valid = ndvi[np.isfinite(ndvi)]
    if valid.size == 0:
        return None
    return {
        "mean_ndvi": round(float(valid.mean()), 3),
        "min_ndvi": round(float(valid.min()), 3),
        "max_ndvi": round(float(valid.max()), 3),
        # Share of footprint pixels with NDVI >= 0.40 (active photosynthetic canopy)
        "vegetation_coverage_pct": round(float((valid >= 0.40).sum()) / valid.size * 100.0, 1),
        "valid_pixel_count": int(valid.size),
    }


RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_S = 10.0
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)
_SAS_QUERY_RE = re.compile(r"\?[^\s'\"]*")


class SatelliteAccessError(Exception):
    """A stage of the satellite pipeline failed; ``str(exc)`` is a sanitised, user-facing reason."""


class SasTokenError(SatelliteAccessError):
    """The token service failed. Not scene-specific, so no further scenes are tried."""


def sanitize(text: str) -> str:
    """Remove query strings (SAS signatures) from URLs inside an error message."""
    return _SAS_QUERY_RE.sub("?<signature removed>", str(text))[:300]


def error_chain(exc: BaseException) -> str:
    """Message of an exception plus its causes (GDAL puts the real HTTP/CURL error in the cause)."""
    parts, seen, cur = [], set(), exc
    while cur is not None and id(cur) not in seen and len(parts) < 4:
        seen.add(id(cur))
        msg = str(cur).strip()
        if msg and msg not in parts and "See previous exception" not in msg:
            parts.append(msg)
        cur = cur.__cause__ or cur.__context__
    return " <- ".join(parts) or exc.__class__.__name__


def _retry_after_s(resp) -> Optional[float]:
    try:
        value = float(resp.headers.get("Retry-After", ""))
        return max(0.0, min(value, MAX_RETRY_AFTER_S))
    except (TypeError, ValueError, AttributeError):
        return None


def http_request(method: str, url: str, stage: str, **kwargs):
    """HTTP call with bounded retries on transient failures only.

    Retries timeouts, connection errors and HTTP 429/500/502/503/504 up to
    SATELLITE_MAX_ATTEMPTS times with exponential backoff (Retry-After honoured, capped).
    Any other status (400/401/403/404 ...) is returned immediately: retrying a permanent
    error only wastes time. Raises SatelliteAccessError when every attempt failed.
    """
    attempts = max(1, int(settings.SATELLITE_MAX_ATTEMPTS))
    kwargs.setdefault("timeout", settings.SATELLITE_REQUEST_TIMEOUT_S)
    last = "no response"
    for attempt in range(1, attempts + 1):
        wait = settings.SATELLITE_RETRY_BACKOFF_S * (2 ** (attempt - 1))
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.Timeout:
            last = f"timed out after {kwargs['timeout']:.0f} s"
        except requests.RequestException as exc:
            last = f"{exc.__class__.__name__}"
        else:
            if resp.status_code not in RETRYABLE_STATUS:
                return resp
            last = f"HTTP {resp.status_code}"
            wait = _retry_after_s(resp) if _retry_after_s(resp) is not None else wait
        if attempt < attempts:
            logger.info("%s: %s (attempt %d/%d), retrying in %.1fs", stage, last, attempt, attempts, wait)
            time.sleep(wait)
    raise SatelliteAccessError(f"{stage}: {last} after {attempts} attempt{'s' if attempts > 1 else ''}.")


def _pc_headers() -> Dict[str, str]:
    if settings.PLANETARY_COMPUTER_API_KEY:
        return {"Ocp-Apim-Subscription-Key": settings.PLANETARY_COMPUTER_API_KEY}
    return {}


class SatelliteClient:
    # One SAS token for the whole collection, reused until shortly before it expires.
    _token: Optional[str] = None
    _token_expiry: Optional[datetime] = None

    @classmethod
    def reset_token_cache(cls) -> None:
        cls._token, cls._token_expiry = None, None

    @classmethod
    def get_sas_token(cls, force_refresh: bool = False) -> str:
        """Returns a Planetary Computer SAS token for sentinel-2-l2a (cached).

        Raises SatelliteAccessError naming the HTTP status if the token service fails.
        """
        now = datetime.now(timezone.utc)
        if (not force_refresh and cls._token and cls._token_expiry
                and cls._token_expiry - TOKEN_REFRESH_MARGIN > now):
            return cls._token
        stage = "Planetary Computer token service"
        try:
            resp = http_request("GET", f"{settings.PLANETARY_COMPUTER_SAS_URL}/{COLLECTION}", stage, headers=_pc_headers())
        except SasTokenError:
            raise
        except SatelliteAccessError as exc:
            raise SasTokenError(str(exc)) from None
        if resp.status_code != 200:
            raise SasTokenError(f"{stage}: HTTP {resp.status_code} (not retried; permanent error).")
        try:
            body = resp.json()
        except ValueError:
            raise SasTokenError(f"{stage}: response was not JSON.")
        token = (body or {}).get("token")
        if not token:
            raise SasTokenError(f"{stage}: response contained no token.")
        expiry = None
        raw = (body or {}).get("msft:expiry")
        if raw:
            try:
                expiry = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
            except ValueError:
                expiry = None
        if expiry is not None and expiry <= now:
            raise SasTokenError(f"{stage}: returned an already-expired token.")
        cls._token, cls._token_expiry = token, expiry or (now + timedelta(minutes=45))
        return token

    @classmethod
    def _sign_href(cls, href: str) -> str:
        """Append the (cached) Planetary Computer SAS token to a blob URL (raises SasTokenError)."""
        token = cls.get_sas_token().lstrip("?")
        sep = "&" if "?" in href else "?"
        return f"{href}{sep}{token}"

    @classmethod
    def search_scenes(cls, footprint: "Footprint", max_cloud_cover: float, lookback_days: int) -> List[Dict[str, Any]]:
        """STAC search for Sentinel-2 L2A items intersecting the plot geometry (least cloudy first)."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)
        payload = {
            "collections": [COLLECTION],
            "intersects": footprint.geojson(),
            "datetime": f"{start:%Y-%m-%dT00:00:00Z}/{end:%Y-%m-%dT23:59:59Z}",
            "limit": 20,
            "query": {"eo:cloud_cover": {"lt": max_cloud_cover}},
        }
        stage = "Satellite catalogue (STAC search)"
        resp = http_request("POST", f"{settings.SENTINEL_STAC_URL}/search", stage, json=payload,
                            headers={"Accept": "application/geo+json", **_pc_headers()})
        if resp.status_code != 200:
            raise SatelliteAccessError(f"{stage}: HTTP {resp.status_code} (not retried; permanent error).")
        try:
            features = resp.json().get("features", [])
        except ValueError:
            raise SatelliteAccessError(f"{stage}: response was not JSON.")
        # least cloudy first; among equally clear scenes, the most recent first (stable sorts)
        features.sort(key=lambda f: f.get("properties", {}).get("datetime", ""), reverse=True)
        features.sort(key=lambda f: f.get("properties", {}).get("eo:cloud_cover", 100.0))
        return features

    @classmethod
    def query_satellite_ndvi(
        cls,
        latitude: float,
        longitude: float,
        area_hectares: Optional[float] = None,
        boundary_lonlat: Optional[List[List[float]]] = None,
        max_cloud_cover: Optional[float] = None,
        lookback_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        footprint = make_footprint(latitude, longitude, area_hectares, boundary_lonlat)
        bbox = footprint.bbox
        max_cloud_cover = settings.SATELLITE_MAX_SCENE_CLOUD_PCT if max_cloud_cover is None else max_cloud_cover
        lookback_days = settings.SATELLITE_LOOKBACK_DAYS if lookback_days is None else lookback_days

        if not settings.ENABLE_REAL_SATELLITE_QUERIES:
            return unavailable("Satellite queries are disabled (ENABLE_REAL_SATELLITE_QUERIES=false).", bbox)

        try:
            features = cls.search_scenes(footprint, max_cloud_cover, lookback_days)
        except SatelliteAccessError as exc:
            return unavailable(f"Satellite catalogue unreachable — {exc}", bbox)

        if not features:
            return unavailable(
                f"No Sentinel-2 L2A scene with <{max_cloud_cover:.0f}% cloud cover in the last {lookback_days} days.",
                bbox,
            )

        reasons = []
        for scene in features[: max(1, settings.SATELLITE_MAX_SCENES_TRIED)]:
            try:
                result, reason = cls._ndvi_from_scene(scene, footprint)
            except SasTokenError as exc:
                return unavailable(
                    f"Scene {scene.get('id', '?')} found, but band files could not be authorised — {exc}", bbox)
            if result is not None:
                result["search"] = {"lookback_days": lookback_days, "max_scene_cloud_pct": max_cloud_cover,
                                    "scenes_found": len(features)}
                return result
            reasons.append(f"{scene.get('id', 'scene')}: {reason}")
        return unavailable("No usable Sentinel-2 observation of the plot. " + " | ".join(reasons), bbox)

    @classmethod
    def _read_window(cls, href: str, footprint: "Footprint", out_shape: Optional[Tuple[int, int]] = None):
        """Reads the footprint's bounding window. Returns (array, window_transform, crs).

        ``out_shape`` resamples (nearest neighbour) onto a given grid, used to put the 20 m SCL
        band on the 10 m B04/B08 grid.
        """
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.warp import transform_bounds
        from rasterio.windows import Window, from_bounds

        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            # Band windows can be slow on home/college connections: allow more time than API calls.
            GDAL_HTTP_TIMEOUT=str(int(max(60, settings.SATELLITE_REQUEST_TIMEOUT_S * 3))),
            GDAL_HTTP_CONNECTTIMEOUT=str(int(max(20, settings.SATELLITE_REQUEST_TIMEOUT_S))),
            # GDAL retries HTTP 429/5xx itself; 403 (bad/expired signature) is not retried
            GDAL_HTTP_MAX_RETRY=str(max(0, int(settings.SATELLITE_MAX_ATTEMPTS) - 1)),
            GDAL_HTTP_RETRY_DELAY=str(settings.SATELLITE_RETRY_BACKOFF_S),
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff",
            VSI_CACHE="TRUE",
        ):
            with rasterio.open(href) as src:
                bounds = transform_bounds("EPSG:4326", src.crs, *footprint.bbox)
                window = from_bounds(*bounds, transform=src.transform)
                window = Window(int(math.floor(window.col_off)), int(math.floor(window.row_off)),
                                max(1, int(math.ceil(window.width))), max(1, int(math.ceil(window.height))))
                kwargs = {"window": window, "boundless": True, "fill_value": 0}
                if out_shape is not None:
                    kwargs.update(out_shape=out_shape, resampling=Resampling.nearest)
                data = src.read(1, **kwargs)
                win_transform = src.window_transform(window)
                if out_shape is not None and out_shape != (window.height, window.width):
                    win_transform = win_transform * win_transform.scale(window.width / out_shape[1], window.height / out_shape[0])
                return data, win_transform, src.crs

    @classmethod
    def _read_band_window(cls, href: str, bbox: List[float]) -> np.ndarray:
        """Backwards-compatible helper: raw window for a bounding box."""
        return cls._read_window(href, Footprint(bbox, None, "SQUARE_APPROX"))[0]

    @staticmethod
    def footprint_mask(footprint: "Footprint", shape: Tuple[int, int], transform, crs) -> np.ndarray:
        """True for pixels inside the footprint polygon (pixel centres; all touched for tiny plots)."""
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom

        geom = transform_geom("EPSG:4326", crs, footprint.geojson())
        inside = geometry_mask([geom], out_shape=shape, transform=transform, invert=True)
        if not inside.any():
            inside = geometry_mask([geom], out_shape=shape, transform=transform, invert=True, all_touched=True)
        return inside

    @classmethod
    def _ndvi_from_scene(cls, scene: Dict[str, Any], footprint: "Footprint") -> Tuple[Optional[Dict[str, Any]], str]:
        try:
            import rasterio  # noqa: F401
        except ImportError:
            return None, "rasterio is not installed on the backend (pip install rasterio)."

        props = scene.get("properties", {})
        assets = scene.get("assets", {})
        red_asset = assets.get("B04") or assets.get("red")
        nir_asset = assets.get("B08") or assets.get("nir")
        scl_asset = assets.get("SCL") or assets.get("scl")
        if not red_asset or not nir_asset:
            return None, "Scene has no B04/B08 assets."
        if not scl_asset:
            return None, "Scene has no SCL (cloud classification) asset."

        raw_hrefs = [a.get("href") for a in (red_asset, nir_asset, scl_asset)]
        if not all(raw_hrefs):
            return None, "Scene band assets have no download URL."

        def read_bands(force_refresh: bool):
            if force_refresh:
                cls.get_sas_token(force_refresh=True)
            hrefs = [cls._sign_href(h) for h in raw_hrefs]
            red, transform, crs = cls._read_window(hrefs[0], footprint)
            nir, _, _ = cls._read_window(hrefs[1], footprint)
            scl_arr, _, _ = cls._read_window(hrefs[2], footprint, out_shape=red.shape)
            return red, nir, scl_arr, transform, crs

        try:
            # Band files are read over HTTP range requests, which fail now and then on slow or
            # busy connections ("RasterioIOError: Read failed"). Retry the whole read a bounded
            # number of times with backoff. A 403 (expired/rejected signature) gets exactly one
            # token refresh; a second 403 is treated as permanent.
            attempts = max(1, int(settings.SATELLITE_MAX_ATTEMPTS))
            refreshed = False
            refresh_next = False
            for attempt in range(1, attempts + 1):
                try:
                    red_dn, nir_dn, scl, transform, crs = read_bands(force_refresh=refresh_next)
                    break
                except SatelliteAccessError:
                    raise
                except Exception as exc:
                    text = error_chain(exc)
                    forbidden = "403" in text or "AuthenticationFailed" in text
                    if forbidden and refreshed:
                        raise
                    if attempt == attempts:
                        raise
                    refresh_next = forbidden
                    refreshed = refreshed or forbidden
                    wait = 0 if forbidden else settings.SATELLITE_RETRY_BACKOFF_S * (2 ** (attempt - 1))
                    logger.info("Band read failed for %s (attempt %d/%d): %s; retrying in %.1fs",
                                scene.get("id"), attempt, attempts, sanitize(text), wait)
                    if wait:
                        time.sleep(wait)
            inside = cls.footprint_mask(footprint, red_dn.shape, transform, crs)
        except SasTokenError:
            raise
        except SatelliteAccessError as exc:
            return None, str(exc)
        except Exception as exc:  # rasterio/GDAL raise a variety of IO errors
            detail = sanitize(error_chain(exc))
            logger.warning("Band read failed for %s: %s", scene.get("id"), detail)
            if "403" in detail:
                detail = "access denied (HTTP 403) even after refreshing the token — " + detail
            n = max(1, int(settings.SATELLITE_MAX_ATTEMPTS))
            return None, f"Band read failed after {n} attempt{'s' if n > 1 else ''} ({exc.__class__.__name__}: {detail})."

        if red_dn.shape != nir_dn.shape:
            return None, "Red and NIR windows have different shapes."

        footprint_pixels = int(inside.sum())
        if footprint_pixels == 0:
            return None, "Plot footprint covers no satellite pixels."
        clear = inside & ~np.isin(scl, list(SCL_EXCLUDED))
        clear_pixels = int(clear.sum())
        clear_fraction = clear_pixels / footprint_pixels
        if clear_fraction < MIN_CLEAR_FRACTION:
            return None, f"Only {clear_fraction:.0%} of the plot is cloud-free in this scene (need {MIN_CLEAR_FRACTION:.0%})."

        baseline = props.get("s2:processing_baseline")
        ndvi = compute_ndvi(dn_to_reflectance(red_dn, baseline), dn_to_reflectance(nir_dn, baseline))
        ndvi[~clear] = np.nan
        stats = summarize_ndvi(ndvi)
        if stats is None:
            return None, "All cloud-free pixels in the plantation footprint are no-data."

        platform = props.get("platform", "Sentinel-2")
        scene_id = scene.get("id", "unknown-scene")
        acquired = (props.get("datetime") or "")[:10] or None
        return {
            "available": True,
            **stats,
            "source_label": f"Sentinel-2 L2A ({platform}) scene {scene_id}",
            "source": "Microsoft Planetary Computer (sentinel-2-l2a)",
            "scene_id": scene_id,
            "stac_item_url": f"{settings.SENTINEL_STAC_URL}/collections/{COLLECTION}/items/{scene_id}",
            "acquisition_date": acquired,
            "cloud_cover_pct": props.get("eo:cloud_cover"),
            "processing_baseline": baseline,
            "footprint_type": footprint.kind,
            "footprint_pixel_count": footprint_pixels,
            "clear_pixel_pct": round(clear_fraction * 100.0, 1),
            "bounding_box": footprint.bbox,
            "formula": NDVI_FORMULA,
        }, ""
