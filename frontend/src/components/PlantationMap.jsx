import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Search, RotateCcw, Crosshair, MapPin, Info, Undo2, Check, AlertCircle } from "lucide-react";

// Geodesic Polygon Area Calculation in Hectares and Square Meters
export function calculatePolygonArea(coords) {
  if (!coords || coords.length < 3) return { hectares: 0, squareMeters: 0 };
  const R = 6378137; // Earth's radius in meters
  let total = 0;
  const n = coords.length;
  
  const meanLatRad = (coords.reduce((sum, c) => sum + c[0], 0) / n) * (Math.PI / 180);
  const cosMeanLat = Math.cos(meanLatRad);

  for (let i = 0; i < n; i++) {
    const p1 = coords[i];
    const p2 = coords[(i + 1) % n];
    
    const x1 = (p1[1] * Math.PI / 180) * R * cosMeanLat;
    const y1 = (p1[0] * Math.PI / 180) * R;
    const x2 = (p2[1] * Math.PI / 180) * R * cosMeanLat;
    const y2 = (p2[0] * Math.PI / 180) * R;
    
    total += (x1 * y2 - x2 * y1);
  }
  
  const squareMeters = Math.round(Math.abs(total) / 2);
  const hectares = Math.round((squareMeters / 10000) * 100) / 100;
  return { hectares, squareMeters };
}

// Centroid calculation
export function calculateCentroid(coords) {
  if (!coords || coords.length === 0) return [12.9716, 77.5946];
  const sumLat = coords.reduce((sum, c) => sum + c[0], 0);
  const sumLng = coords.reduce((sum, c) => sum + c[1], 0);
  return [
    parseFloat((sumLat / coords.length).toFixed(6)),
    parseFloat((sumLng / coords.length).toFixed(6))
  ];
}

// Calculate target zoom level based on geocoding item precision
export function getZoomForPlace(item) {
  const type = (item.type || "").toLowerCase();
  const cls = (item.class || "").toLowerCase();

  // Building or exact address / landmark: close zoom
  if (cls === "building" || ["house", "building", "address", "isolated_dwelling", "farm", "farmyard", "yes"].includes(type)) {
    return 18;
  }
  // Street / Road / Highway
  if (cls === "highway" || ["road", "street", "residential", "living_street", "tertiary", "secondary", "primary", "unclassified"].includes(type)) {
    return 17;
  }
  // Locality / Suburb / Neighborhood / Quarter
  if (["suburb", "neighbourhood", "quarter", "hamlet", "allotments"].includes(type)) {
    return 15;
  }
  // Village / Town / Postal code
  if (["village", "postcode", "postal_code", "town"].includes(type)) {
    return 14;
  }
  // City
  if (type === "city") {
    return 13;
  }
  // County / District / State
  if (["county", "district", "state", "region", "province"].includes(type)) {
    return 10;
  }
  // Country
  if (type === "country") {
    return 5;
  }
  return 15;
}

// Helper to format clean display address
export function formatAddressLabel(item) {
  const addr = item.address || {};
  const mainPart = item.name || addr.road || addr.suburb || addr.neighbourhood || addr.village || addr.town || addr.city || "Location";
  
  // Format secondary details
  const parts = [];
  if (addr.road && addr.road !== mainPart) parts.push(addr.road);
  if (addr.suburb && addr.suburb !== mainPart) parts.push(addr.suburb);
  if (addr.city && addr.city !== mainPart) parts.push(addr.city);
  else if (addr.town && addr.town !== mainPart) parts.push(addr.town);
  else if (addr.village && addr.village !== mainPart) parts.push(addr.village);
  if (addr.state) parts.push(addr.state);
  if (addr.postcode) parts.push(addr.postcode);
  if (addr.country) parts.push(addr.country);

  return {
    title: mainPart,
    subtitle: parts.slice(0, 4).join(", ") || item.display_name.split(",").slice(1, 4).join(", ")
  };
}

export default function PlantationMap({ 
  initialLatitude = 12.9716, 
  initialLongitude = 77.5946, 
  initialArea = 0,
  initialCoordinates = [],
  onUpdateGeometry,
  onLocationFound
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const polygonLayerRef = useRef(null);
  const markersGroupRef = useRef(null);
  const searchMarkerRef = useRef(null);

  // Satellite view by default
  const [activeLayer, setActiveLayer] = useState("satellite"); // "satellite" | "street"
  const [polygonCoords, setPolygonCoords] = useState(initialCoordinates);
  const [computedArea, setComputedArea] = useState({ 
    hectares: initialArea, 
    squareMeters: Math.round(initialArea * 10000) 
  });
  const [centroid, setCentroid] = useState([initialLatitude, initialLongitude]);

  // Geocoding Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searchStatus, setSearchStatus] = useState(null); // { type: 'loading'|'success'|'error'|'info', text: '' }
  const [selectedAddress, setSelectedAddress] = useState("");

  // Satellite tile provider (Esri World Imagery)
  const satelliteUrl = import.meta.env.VITE_SATELLITE_TILE_URL || 
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
  const streetUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialCenter = centroid;
    const initialZoom = polygonCoords.length > 0 ? 16 : 13;

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: initialZoom,
      zoomControl: false,
      attributionControl: false
    });

    // Custom attribution
    L.control.attribution({ position: "bottomright", prefix: false })
      .addAttribution("&copy; Esri World Imagery &bull; OpenStreetMap")
      .addTo(map);

    // Zoom control on top-left
    L.control.zoom({ position: "topleft" }).addTo(map);

    // Satellite Tile Layer by default
    const tileUrl = activeLayer === "satellite" ? satelliteUrl : streetUrl;
    const tileLayer = L.tileLayer(tileUrl, { maxZoom: 19 }).addTo(map);
    tileLayerRef.current = tileLayer;

    // Feature Groups
    const polygonGroup = L.featureGroup().addTo(map);
    const markersGroup = L.featureGroup().addTo(map);
    polygonLayerRef.current = polygonGroup;
    markersGroupRef.current = markersGroup;

    // Map Click Handler for drawing polygon vertices
    map.on("click", (e) => {
      const newPoint = [parseFloat(e.latlng.lat.toFixed(6)), parseFloat(e.latlng.lng.toFixed(6))];
      setPolygonCoords(prev => [...prev, newPoint]);
    });

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Sync active tile layer
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;
    mapInstanceRef.current.removeLayer(tileLayerRef.current);

    const newUrl = activeLayer === "satellite" ? satelliteUrl : streetUrl;
    const newTileLayer = L.tileLayer(newUrl, { maxZoom: 19 }).addTo(mapInstanceRef.current);
    newTileLayer.bringToBack();
    tileLayerRef.current = newTileLayer;
  }, [activeLayer]);

  // Sync polygon & markers onto map
  useEffect(() => {
    if (!mapInstanceRef.current || !polygonLayerRef.current || !markersGroupRef.current) return;

    polygonLayerRef.current.clearLayers();
    markersGroupRef.current.clearLayers();

    if (polygonCoords.length > 0) {
      // Add vertex marker pins
      polygonCoords.forEach((pt, idx) => {
        const marker = L.circleMarker(pt, {
          radius: 5,
          fillColor: "#1B3B2B",
          color: "#FFFFFF",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9
        });
        marker.bindTooltip(`Point ${idx + 1}`, { permanent: false, direction: "top" });
        markersGroupRef.current.addLayer(marker);
      });

      // Draw polygon if >= 3 vertices
      if (polygonCoords.length >= 3) {
        const polygon = L.polygon(polygonCoords, {
          color: "#1B3B2B",
          weight: 2.5,
          fillColor: "#10b981",
          fillOpacity: 0.28,
          dashArray: "4, 4"
        });
        polygonLayerRef.current.addLayer(polygon);

        const areaResult = calculatePolygonArea(polygonCoords);
        const center = calculateCentroid(polygonCoords);
        setComputedArea(areaResult);
        setCentroid(center);

        if (onUpdateGeometry) {
          onUpdateGeometry({
            latitude: center[0],
            longitude: center[1],
            area_hectares: areaResult.hectares,
            area_sqm: areaResult.squareMeters,
            coordinates: polygonCoords
          });
        }
      } else if (polygonCoords.length === 2) {
        const polyline = L.polyline(polygonCoords, {
          color: "#1B3B2B",
          weight: 2,
          dashArray: "4, 4"
        });
        polygonLayerRef.current.addLayer(polyline);
      }
    } else {
      setComputedArea({ hectares: 0, squareMeters: 0 });
      if (onUpdateGeometry) {
        onUpdateGeometry({
          latitude: centroid[0],
          longitude: centroid[1],
          area_hectares: 0,
          area_sqm: 0,
          coordinates: []
        });
      }
    }
  }, [polygonCoords]);

  // Address-Level Geocoding Search Handler (Sections 8-11)
  const handleSearchLocation = async (e) => {
    if (e) e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    setSearching(true);
    setSearchResults([]);
    setSearchStatus({ type: "loading", text: "Searching locations..." });

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=6&q=${encodeURIComponent(query)}`,
        {
          headers: {
            "Accept-Language": "en"
          }
        }
      );

      const results = await response.json();

      if (results && results.length > 0) {
        setSearchResults(results);
        setSearchStatus({
          type: "info",
          text: `Found ${results.length} matching location${results.length > 1 ? "s" : ""}. Please select from the results below:`
        });
      } else {
        setSearchResults([]);
        setSearchStatus({
          type: "error",
          text: "No matching location found. Try a nearby landmark, street, locality or PIN code."
        });
      }
    } catch (err) {
      console.error("Geocoding error:", err);
      setSearchStatus({
        type: "error",
        text: "Geocoding request failed. Please check your internet connection."
      });
    } finally {
      setSearching(false);
    }
  };

  // User selects an item from the search result dropdown (Section 10 & 12)
  const handleSelectResult = (item) => {
    const lat = parseFloat(item.lat);
    const lon = parseFloat(item.lon);
    const targetZoom = getZoomForPlace(item);
    const { title, subtitle } = formatAddressLabel(item);
    const fullSelectedName = `${title}, ${subtitle}`;

    setSelectedAddress(fullSelectedName);
    setSearchResults([]); // Close dropdown
    setSearchStatus({
      type: "success",
      text: `Location selected: ${title}`
    });

    if (mapInstanceRef.current) {
      // Fly smoothly to the selected exact coordinates with calibrated zoom
      mapInstanceRef.current.flyTo([lat, lon], targetZoom, {
        duration: 1.6,
        easeLinearity: 0.25
      });

      // Place search marker at exact geocoded location
      if (searchMarkerRef.current) {
        mapInstanceRef.current.removeLayer(searchMarkerRef.current);
      }

      const marker = L.circleMarker([lat, lon], {
        radius: 8,
        fillColor: "#0284c7",
        color: "#FFFFFF",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(mapInstanceRef.current);

      marker.bindTooltip(`Searched: ${title}`, { permanent: true, direction: "top" }).openTooltip();
      searchMarkerRef.current = marker;
    }

    // Inform parent form to update the plantation address and default coordinates
    if (onLocationFound) {
      onLocationFound({
        name: title,
        displayName: fullSelectedName,
        latitude: lat,
        longitude: lon,
        type: item.type
      });
    }
  };

  // Undo the last added vertex
  const handleUndoPoint = () => {
    setPolygonCoords(prev => {
      if (prev.length === 0) return prev;
      return prev.slice(0, -1);
    });
  };

  // Clear all points
  const handleClear = () => {
    setPolygonCoords([]);
    setComputedArea({ hectares: 0, squareMeters: 0 });
    if (searchMarkerRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.removeLayer(searchMarkerRef.current);
      searchMarkerRef.current = null;
    }
  };

  // Recenter map on centroid
  const handleCenterOnPlot = () => {
    if (mapInstanceRef.current && centroid) {
      mapInstanceRef.current.setView(centroid, 16);
    }
  };

  return (
    <div className="space-y-3">
      {/* 1. Address-Level Geospatial Search Box & Results Dropdown */}
      <div className="relative space-y-1.5">
        <form onSubmit={handleSearchLocation} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search location, street, village or PIN code"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded border border-slate-200 focus:outline-none focus:border-slate-400 bg-white text-xs text-slate-800"
            />
          </div>
          <button
            type="submit"
            disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 bg-[#1B3B2B] hover:bg-[#142e21] text-white rounded text-xs font-semibold tracking-wide disabled:opacity-50 transition shrink-0 uppercase"
          >
            {searching ? "Searching..." : "Search"}
          </button>
        </form>

        {/* Search Status / Notification */}
        {searchStatus && (
          <div className="flex items-center gap-1.5 text-[11px]">
            {searchStatus.type === "error" && <AlertCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />}
            {searchStatus.type === "success" && <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />}
            <span className={
              searchStatus.type === "success" 
                ? "text-emerald-700 font-medium" 
                : searchStatus.type === "error" 
                  ? "text-rose-600 font-medium" 
                  : "text-slate-500"
            }>
              {searchStatus.text}
            </span>
          </div>
        )}

        {/* LOCATION RESULTS DROPDOWN (Section 10) */}
        {searchResults.length > 0 && (
          <div className="absolute top-11 left-0 right-0 z-30 bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden max-h-60 overflow-y-auto">
            <div className="bg-slate-50 px-3 py-1.5 border-b border-slate-100 flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                Location Results
              </span>
              <span className="text-[10px] text-slate-400">Click to locate on map</span>
            </div>
            <div className="divide-y divide-slate-100">
              {searchResults.map((item, index) => {
                const { title, subtitle } = formatAddressLabel(item);
                const placeType = item.type || item.class || "location";
                return (
                  <button
                    key={`${item.place_id}-${index}`}
                    type="button"
                    onClick={() => handleSelectResult(item)}
                    className="w-full text-left px-3 py-2 hover:bg-emerald-50/50 transition flex items-start justify-between gap-2 group"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3 h-3 text-[#1B3B2B] shrink-0" />
                        <span className="font-semibold text-slate-900 text-xs truncate group-hover:text-[#1B3B2B]">
                          {title}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 truncate pl-4.5">
                        {subtitle}
                      </p>
                    </div>
                    <span className="shrink-0 text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium mt-0.5">
                      {placeType}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 2. Map Controls & Layer Switcher Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleUndoPoint}
            disabled={polygonCoords.length === 0}
            className="px-2.5 py-1 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded text-[11px] font-medium inline-flex items-center gap-1 disabled:opacity-40 transition"
            title="Undo last added vertex"
          >
            <Undo2 className="w-3 h-3 text-slate-500" />
            <span>Undo</span>
          </button>

          <button
            type="button"
            onClick={handleClear}
            disabled={polygonCoords.length === 0}
            className="px-2.5 py-1 bg-white hover:bg-rose-50 border border-slate-200 hover:border-rose-200 text-slate-600 hover:text-rose-700 rounded text-[11px] font-medium inline-flex items-center gap-1 disabled:opacity-40 transition"
            title="Clear and redraw boundary"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Clear Boundary</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Layer switcher: SATELLITE (default) | MAP */}
          <div className="inline-flex rounded border border-slate-200 bg-white p-0.5 shadow-2xs">
            <button
              type="button"
              onClick={() => setActiveLayer("satellite")}
              className={`px-2.5 py-0.5 rounded text-[11px] font-semibold transition ${
                activeLayer === "satellite" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Satellite
            </button>
            <button
              type="button"
              onClick={() => setActiveLayer("street")}
              className={`px-2.5 py-0.5 rounded text-[11px] font-semibold transition ${
                activeLayer === "street" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Map
            </button>
          </div>

          <button
            type="button"
            onClick={handleCenterOnPlot}
            className="px-2.5 py-1 bg-white hover:bg-slate-50 border border-slate-200 rounded text-slate-700 text-[11px] inline-flex items-center gap-1 font-medium"
            title="Recenter view"
          >
            <Crosshair className="w-3 h-3 text-slate-500" />
            <span>Center</span>
          </button>
        </div>
      </div>

      {/* 3. Substantial Interactive Geospatial Map Container */}
      <div className="relative border border-slate-200 rounded overflow-hidden bg-slate-100 shadow-2xs">
        <div 
          ref={mapContainerRef} 
          style={{ height: "500px", width: "100%", zIndex: 1 }} 
        />

        {/* Floating Instruction Banner inside map */}
        <div className="absolute top-2.5 right-2.5 z-10 bg-white/95 backdrop-blur-xs border border-slate-200 rounded px-2.5 py-1.5 text-[11px] text-slate-800 shadow-xs flex items-center gap-1.5 font-medium">
          <MapPin className="w-3.5 h-3.5 text-[#1B3B2B]" />
          <span>Click on satellite view to draw boundary vertices ({polygonCoords.length} points)</span>
        </div>
      </div>

      {/* 4. Real-Time Boundary Metrics & Area in Hectares + Square Meters (Sections 16, 17, 18) */}
      <div className="bg-white p-3.5 rounded border border-slate-200 text-xs">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Plantation Boundary & Area Calculation
          </span>
          <span className="text-[10px] text-slate-400">
            {polygonCoords.length >= 3 
              ? `${polygonCoords.length} Boundary Vertices Defined` 
              : polygonCoords.length > 0 
                ? `${polygonCoords.length} points (need ≥ 3 for polygon)` 
                : "No boundary defined"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <span className="text-[11px] text-slate-500 block mb-0.5">Centroid Latitude</span>
            <p className="font-bold text-slate-900 font-mono text-sm">
              {centroid[0]}
            </p>
          </div>

          <div>
            <span className="text-[11px] text-slate-500 block mb-0.5">Centroid Longitude</span>
            <p className="font-bold text-slate-900 font-mono text-sm">
              {centroid[1]}
            </p>
          </div>

          <div>
            <span className="text-[11px] text-slate-500 block mb-0.5">Calculated Plantation Area</span>
            <p className="font-bold text-[#1B3B2B] font-mono text-sm">
              {computedArea.hectares > 0 ? (
                <>
                  <span>{computedArea.hectares} ha</span>
                  <span className="text-slate-400 font-normal text-xs ml-1.5">
                    ({computedArea.squareMeters.toLocaleString()} m²)
                  </span>
                </>
              ) : (
                <span className="text-slate-400 font-normal text-xs">Draw polygon on satellite map</span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* 5. Clear distinction note: Map Navigation Location vs Plantation Boundary (Section 18) */}
      <div className="flex items-start gap-1.5 p-2.5 bg-slate-50 border border-slate-200 rounded text-[11px] text-slate-600 leading-relaxed">
        <Info className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-700">Geospatial Distinction:</span>{" "}
          <span>The searched address locates and centers the map. The polygon you draw defines the true plantation boundary and carbon sequestration area.</span>
        </div>
      </div>
    </div>
  );
}
