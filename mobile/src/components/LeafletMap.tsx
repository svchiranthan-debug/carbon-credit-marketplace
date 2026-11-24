import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import { StyleProp, ViewStyle } from "react-native";
import { WebView, WebViewMessageEvent } from "react-native-webview";

/**
 * Leaflet map inside a WebView, using the same free tiles as the web app (Esri World Imagery and
 * OpenStreetMap). react-native-maps needs a Google Maps API key (and a Google Cloud billing
 * account) in a release Android build, so it showed a blank map in the APK; this needs no key.
 *
 * The page posts {type: "tap" | "pinDrag", lat, lon} and {type: "ready"}; the app sends view and
 * overlay updates with injectJavaScript.
 */

export type LatLng = { latitude: number; longitude: number };

export interface LeafletMapHandle {
  flyTo: (lat: number, lon: number, zoom?: number) => void;
}

interface Props {
  style?: StyleProp<ViewStyle>;
  initialCenter: LatLng;
  mode: "PIN" | "BOUNDARY";
  pin: LatLng;
  vertices: LatLng[];
  onTap: (coord: LatLng) => void;
  onPinDrag: (coord: LatLng) => void;
}

const LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist";

function buildHtml(center: LatLng): string {
  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<link rel="stylesheet" href="${LEAFLET}/leaflet.css" />
<script src="${LEAFLET}/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; padding: 0; background: #e2e8f0; }
  .msg { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
         font: 13px sans-serif; color: #475569; padding: 24px; text-align: center; }
</style>
</head>
<body>
<div id="map"></div>
<script>
  function send(m) { if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify(m)); }
  if (typeof L === "undefined") {
    document.body.innerHTML = '<div class="msg">Map could not load. Check the phone\\'s internet connection and reopen the map.</div>';
    send({ type: "error", message: "leaflet-not-loaded" });
  } else {
    var map = L.map("map", { zoomControl: true }).setView([${center.latitude}, ${center.longitude}], 15);
    var satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Tiles &copy; Esri" });
    var street = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" });
    satellite.addTo(map);
    L.control.layers({ "Satellite": satellite, "Street": street }, null, { position: "bottomleft" }).addTo(map);

    var overlay = L.layerGroup().addTo(map);
    var pinMarker = null;

    map.on("click", function (e) { send({ type: "tap", lat: e.latlng.lat, lon: e.latlng.lng }); });

    window.__setState = function (s) {
      overlay.clearLayers();
      pinMarker = null;
      if (s.mode === "PIN") {
        pinMarker = L.marker([s.pin.latitude, s.pin.longitude], { draggable: true }).addTo(overlay);
        pinMarker.on("dragend", function () {
          var p = pinMarker.getLatLng();
          send({ type: "pinDrag", lat: p.lat, lon: p.lng });
        });
      } else {
        var pts = s.vertices.map(function (v) { return [v.latitude, v.longitude]; });
        if (pts.length >= 3) {
          L.polygon(pts, { color: "#166534", weight: 2, fillColor: "#166534", fillOpacity: 0.25 }).addTo(overlay);
        } else if (pts.length === 2) {
          L.polyline(pts, { color: "#166534", weight: 2 }).addTo(overlay);
        }
        pts.forEach(function (p, i) {
          L.circleMarker(p, { radius: 7, color: "#ffffff", weight: 2, fillColor: "#166534", fillOpacity: 1 })
            .bindTooltip("Corner " + (i + 1)).addTo(overlay);
        });
      }
    };
    window.__flyTo = function (lat, lon, zoom) { map.flyTo([lat, lon], zoom || map.getZoom(), { duration: 0.6 }); };
    send({ type: "ready" });
  }
</script>
</body>
</html>`;
}

const LeafletMap = forwardRef<LeafletMapHandle, Props>(function LeafletMap(
  { style, initialCenter, mode, pin, vertices, onTap, onPinDrag },
  ref
) {
  const webRef = useRef<WebView>(null);
  const ready = useRef(false);
  // The page is built once; later moves go through flyTo so the map is not reloaded.
  const html = useRef(buildHtml(initialCenter)).current;

  const run = useCallback((js: string) => {
    if (ready.current) webRef.current?.injectJavaScript(`${js}; true;`);
  }, []);

  const pushState = useCallback(() => {
    run(`window.__setState(${JSON.stringify({ mode, pin, vertices })})`);
  }, [run, mode, pin, vertices]);

  useEffect(() => {
    pushState();
  }, [pushState]);

  useImperativeHandle(ref, () => ({
    flyTo: (lat: number, lon: number, zoom?: number) => run(`window.__flyTo(${lat}, ${lon}, ${zoom ?? "undefined"})`),
  }), [run]);

  const onMessage = (event: WebViewMessageEvent) => {
    let msg: { type: string; lat?: number; lon?: number };
    try {
      msg = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }
    if (msg.type === "ready") {
      ready.current = true;
      pushState();
    } else if (msg.type === "tap" && msg.lat != null && msg.lon != null) {
      onTap({ latitude: msg.lat, longitude: msg.lon });
    } else if (msg.type === "pinDrag" && msg.lat != null && msg.lon != null) {
      onPinDrag({ latitude: msg.lat, longitude: msg.lon });
    }
  };

  return (
    <WebView
      ref={webRef}
      style={style}
      originWhitelist={["*"]}
      // A real site as the base URL so tile servers see a normal Referer (OpenStreetMap's tile
      // policy asks for one); the page itself is inline.
      source={{ html, baseUrl: "https://carbon-credit-marketplace.vercel.app/" }}
      javaScriptEnabled
      domStorageEnabled
      onMessage={onMessage}
      onLoadStart={() => {
        ready.current = false;
      }}
    />
  );
});

export default LeafletMap;
