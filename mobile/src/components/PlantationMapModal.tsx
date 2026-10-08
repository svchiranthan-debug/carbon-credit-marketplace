import React, { useState, useEffect, useRef } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  SafeAreaView,
  StatusBar,
  ActivityIndicator,
  Alert
} from "react-native";
import MapView, { Marker, Region } from "react-native-maps";
import * as Location from "expo-location";

interface PlantationMapModalProps {
  visible: boolean;
  initialLat?: number;
  initialLon?: number;
  onClose: () => void;
  onLocationSelected: (lat: number, lon: number, locationName?: string) => void;
}

const PRESET_LOCATIONS: { name: string; lat: number; lon: number }[] = [
  { name: "Mandya (Agroforest)", lat: 12.5218, lon: 76.8951 },
  { name: "Coorg (Coffee/Canopy)", lat: 12.3375, lon: 75.8069 },
  { name: "Shimoga (Teak)", lat: 13.9299, lon: 75.5681 },
  { name: "Chikkamagaluru", lat: 13.3161, lon: 75.7720 },
  { name: "Udupi (Coastal)", lat: 13.3409, lon: 74.7421 }
];

export default function PlantationMapModal({
  visible,
  initialLat,
  initialLon,
  onClose,
  onLocationSelected
}: PlantationMapModalProps) {
  const [selectedCoord, setSelectedCoord] = useState<{ latitude: number; longitude: number }>({
    latitude: initialLat || 12.5218,
    longitude: initialLon || 76.8951
  });
  const [locating, setLocating] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationName, setLocationName] = useState<string>("");
  const mapRef = useRef<MapView | null>(null);

  useEffect(() => {
    if (visible) {
      const lat = initialLat || 12.5218;
      const lon = initialLon || 76.8951;
      setSelectedCoord({ latitude: lat, longitude: lon });
      setTimeout(() => {
        animateTo(lat, lon);
      }, 200);
    }
  }, [visible, initialLat, initialLon]);

  const animateTo = (lat: number, lon: number) => {
    mapRef.current?.animateToRegion({
      latitude: lat,
      longitude: lon,
      latitudeDelta: 0.04,
      longitudeDelta: 0.04
    }, 600);
  };

  const handleUseLiveGPS = async () => {
    setLocating(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        Alert.alert(
          "Location Permission Required",
          "Please enable location permission in iPhone Settings to locate your plantation on the map."
        );
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const lat = loc.coords.latitude;
      const lon = loc.coords.longitude;
      setSelectedCoord({ latitude: lat, longitude: lon });
      animateTo(lat, lon);
      setLocationName(`GPS Verified (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
    } catch (err: any) {
      Alert.alert("GPS Error", err.message || "Could not retrieve live GPS coordinates.");
    } finally {
      setLocating(false);
    }
  };

  const handleSelectPreset = (preset: { name: string; lat: number; lon: number }) => {
    setSelectedCoord({ latitude: preset.lat, longitude: preset.lon });
    setLocationName(preset.name);
    animateTo(preset.lat, preset.lon);
  };

  const handleSearchSubmit = async () => {
    const q = searchQuery.trim();
    if (!q) return;

    // 1. Check presets first
    const presetMatch = PRESET_LOCATIONS.find(
      (p) => p.name.toLowerCase().includes(q.toLowerCase())
    );
    if (presetMatch) {
      handleSelectPreset(presetMatch);
      return;
    }

    // 2. Genuine native geocoding via expo-location (Apple Maps / CLGeocoder on iOS)
    try {
      const results = await Location.geocodeAsync(q);
      if (results && results.length > 0) {
        const first = results[0];
        const lat = first.latitude;
        const lon = first.longitude;
        setSelectedCoord({ latitude: lat, longitude: lon });
        setLocationName(q);
        animateTo(lat, lon);
      } else {
        Alert.alert(
          "Location Not Found",
          `Could not locate "${q}". Tap any location preset below or tap directly on the map to place your pin.`
        );
      }
    } catch (err: any) {
      Alert.alert(
        "Search Error",
        `Geocoding query failed: ${err.message || "Unknown error"}. You can tap directly on the map to place your pin.`
      );
    }
  };

  const handleConfirmLocation = () => {
    onLocationSelected(
      selectedCoord.latitude,
      selectedCoord.longitude,
      locationName || `Karnataka (${selectedCoord.latitude.toFixed(4)}, ${selectedCoord.longitude.toFixed(4)})`
    );
    onClose();
  };

  if (!visible) return null;

  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor="#FFFFFF" />

        {/* Top Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
            <Text style={styles.closeBtnText}>✕ Close</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Select Plantation Location</Text>
          <TouchableOpacity onPress={handleUseLiveGPS} style={styles.gpsBtn} disabled={locating}>
            {locating ? (
              <ActivityIndicator size="small" color="#166534" />
            ) : (
              <Text style={styles.gpsBtnText}>📍 Live GPS</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Search & Preset Bar */}
        <View style={styles.searchBar}>
          <TextInput
            style={styles.searchInput}
            placeholder="Search regions (e.g. Mandya, Coorg, Shimoga)..."
            value={searchQuery}
            onChangeText={setSearchQuery}
            onSubmitEditing={handleSearchSubmit}
            returnKeyType="search"
          />
          <TouchableOpacity style={styles.searchBtn} onPress={handleSearchSubmit}>
            <Text style={styles.searchBtnText}>Go</Text>
          </TouchableOpacity>
        </View>

        {/* Presets Horizontal Chips */}
        <View style={styles.chipsRow}>
          {PRESET_LOCATIONS.map((preset) => (
            <TouchableOpacity
              key={preset.name}
              style={[
                styles.chip,
                Math.abs(selectedCoord.latitude - preset.lat) < 0.01 &&
                Math.abs(selectedCoord.longitude - preset.lon) < 0.01 &&
                styles.chipActive
              ]}
              onPress={() => handleSelectPreset(preset)}
            >
              <Text
                style={[
                  styles.chipText,
                  Math.abs(selectedCoord.latitude - preset.lat) < 0.01 &&
                  Math.abs(selectedCoord.longitude - preset.lon) < 0.01 &&
                  styles.chipTextActive
                ]}
              >
                {preset.name}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Native MapView */}
        <View style={styles.mapWrapper}>
          <MapView
            ref={mapRef}
            style={styles.map}
            initialRegion={{
              latitude: selectedCoord.latitude,
              longitude: selectedCoord.longitude,
              latitudeDelta: 0.04,
              longitudeDelta: 0.04
            }}
            showsUserLocation={true}
            showsMyLocationButton={true}
            onPress={(e) => {
              const coord = e.nativeEvent.coordinate;
              setSelectedCoord(coord);
              setLocationName(`Geotagged (${coord.latitude.toFixed(4)}, ${coord.longitude.toFixed(4)})`);
            }}
          >
            <Marker
              coordinate={selectedCoord}
              draggable
              onDragEnd={(e) => {
                const coord = e.nativeEvent.coordinate;
                setSelectedCoord(coord);
                setLocationName(`Pin (${coord.latitude.toFixed(4)}, ${coord.longitude.toFixed(4)})`);
              }}
              title="Plantation Geotag"
              description="Farm center coordinates for Sentinel-2 satellite MRV"
            />
          </MapView>

          {/* Floating Instructions Pill */}
          <View style={styles.floatingGuide}>
            <Text style={styles.floatingGuideText}>
              👆 Tap anywhere on the map or drag the pin to position plantation center
            </Text>
          </View>
        </View>

        {/* Footer with Selected Coordinates and Confirmation */}
        <View style={styles.footer}>
          <View style={styles.coordsRow}>
            <View>
              <Text style={styles.coordsLabel}>SELECTED GEOTAG</Text>
              <Text style={styles.coordsValue}>
                Lat: {selectedCoord.latitude.toFixed(5)} • Lon: {selectedCoord.longitude.toFixed(5)}
              </Text>
              {locationName ? <Text style={styles.locationNameSub}>{locationName}</Text> : null}
            </View>
          </View>

          <Text style={styles.boundaryNote}>
            ℹ️ Mobile pin geotagging sets the farm center. Multi-vertex polygon boundary drawing is available in the Web Portal GIS editor.
          </Text>

          <TouchableOpacity style={styles.confirmBtn} onPress={handleConfirmLocation}>
            <Text style={styles.confirmBtnText}>✓ SAVE LOCATION COORDINATES</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF"
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderColor: "#E2E8F0"
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#0F172A"
  },
  closeBtn: {
    paddingVertical: 6,
    paddingHorizontal: 8
  },
  closeBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#64748B"
  },
  gpsBtn: {
    backgroundColor: "#F0FDF4",
    borderColor: "#BBF7D0",
    borderWidth: 1,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 6
  },
  gpsBtnText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#166534"
  },
  searchBar: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
    backgroundColor: "#F8FAFC",
    borderBottomWidth: 1,
    borderColor: "#E2E8F0"
  },
  searchInput: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    fontSize: 12,
    color: "#0F172A"
  },
  searchBtn: {
    backgroundColor: "#1B3B2B",
    paddingHorizontal: 14,
    justifyContent: "center",
    borderRadius: 6
  },
  searchBtnText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700"
  },
  chipsRow: {
    flexDirection: "row",
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 6,
    backgroundColor: "#F1F5F9",
    flexWrap: "wrap"
  },
  chip: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12
  },
  chipActive: {
    backgroundColor: "#1B3B2B",
    borderColor: "#1B3B2B"
  },
  chipText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#475569"
  },
  chipTextActive: {
    color: "#FFFFFF"
  },
  mapWrapper: {
    flex: 1,
    position: "relative"
  },
  map: {
    ...StyleSheet.absoluteFill
  },
  floatingGuide: {
    position: "absolute",
    top: 10,
    left: 16,
    right: 16,
    backgroundColor: "rgba(15, 23, 42, 0.85)",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    alignItems: "center"
  },
  floatingGuideText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
    textAlign: "center"
  },
  footer: {
    padding: 16,
    backgroundColor: "#FFFFFF",
    borderTopWidth: 1,
    borderColor: "#E2E8F0"
  },
  coordsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6
  },
  coordsLabel: {
    fontSize: 9,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.6
  },
  coordsValue: {
    fontSize: 13,
    fontWeight: "800",
    color: "#0F172A",
    fontFamily: "monospace",
    marginTop: 2
  },
  locationNameSub: {
    fontSize: 11,
    color: "#166534",
    fontWeight: "600",
    marginTop: 2
  },
  boundaryNote: {
    fontSize: 10,
    color: "#64748B",
    lineHeight: 14,
    marginBottom: 10
  },
  confirmBtn: {
    backgroundColor: "#1B3B2B",
    paddingVertical: 12,
    borderRadius: 6,
    alignItems: "center"
  },
  confirmBtnText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.5
  }
});
