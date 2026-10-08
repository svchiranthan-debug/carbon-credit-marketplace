import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  ActivityIndicator,
  Alert,
  StyleSheet
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import { api, API_BASE_URL } from "../services/api";
import { useAuth } from "../context/AuthContext";
import CameraCaptureModal from "../components/CameraCaptureModal";
import PlantationMapModal from "../components/PlantationMapModal";

export default function FarmerScreen() {
  const { user } = useAuth();
  const submittingRef = useRef(false);
  const [plantations, setPlantations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [selectedPlantation, setSelectedPlantation] = useState<any | null>(null);
  const [verification, setVerification] = useState<any | null>(null);

  // Camera Modal State
  const [cameraVisible, setCameraVisible] = useState(false);
  const [cameraTargetPlotId, setCameraTargetPlotId] = useState<number | null>(null);

  // Map Modal State
  const [mapVisible, setMapVisible] = useState(false);
  const [locationLabel, setLocationLabel] = useState("Mandya (Agroforest), Karnataka");

  // Form State
  const [name, setName] = useState("");
  const [species, setSpecies] = useState("Teak, Silver Oak & Coffee");
  const [treeCount, setTreeCount] = useState("450");
  const [areaHectares, setAreaHectares] = useState("1.8");
  const [soilSoc, setSoilSoc] = useState("1.85");
  const [latitude, setLatitude] = useState("12.5218");
  const [longitude, setLongitude] = useState("76.8951");
  const [imageUri, setImageUri] = useState<string | null>(null);

  const fetchPlantations = async () => {
    setLoading(true);
    try {
      const data = await api.getPlantations();
      setPlantations(data || []);
      if (data && data.length > 0 && !selectedPlantation) {
        loadVerification(data[0]);
      }
    } catch (err: any) {
      console.warn("Error fetching plantations:", err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadVerification = async (p: any) => {
    setSelectedPlantation(p);
    setVerification(null);
    try {
      const ver = await api.getVerification(p.id);
      setVerification(ver);
    } catch {
      setVerification(null);
    }
  };

  useEffect(() => {
    fetchPlantations();
  }, []);

  // Quick Live GPS Button
  const handleGetLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        Alert.alert(
          "Location Permission Required",
          "Location permission is needed to geotag your plantation. Please enable in iPhone Settings."
        );
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const lat = loc.coords.latitude.toFixed(4);
      const lon = loc.coords.longitude.toFixed(4);
      setLatitude(lat);
      setLongitude(lon);
      setLocationLabel(`GPS Verified (${lat}, ${lon})`);
      Alert.alert("GPS Acquired", `Coordinates: ${lat}, ${lon}`);
    } catch (err: any) {
      Alert.alert(
        "GPS Unavailable",
        err.message || "Could not retrieve live GPS coordinates. Please use Open Map or enter coordinates manually."
      );
    }
  };

  // Open Native Camera Modal
  const handleOpenCamera = (targetPlotId: number | null = null) => {
    setCameraTargetPlotId(targetPlotId);
    setCameraVisible(true);
  };

  // Handle Photo Accepted from Native Camera
  const handlePhotoAccepted = async (uri: string) => {
    setCameraVisible(false);
    if (cameraTargetPlotId) {
      await handleUploadForPlantation(cameraTargetPlotId, uri);
    } else {
      setImageUri(uri);
      Alert.alert(
        "GROUND EVIDENCE CAPTURED",
        "Photo stored and ready to submit with plantation registration."
      );
    }
  };

  // Upload Evidence for Existing Plantation
  const handleUploadForPlantation = async (plotId: number, uri: string) => {
    setUploadingImage(true);
    console.log(`[Mobile MRV] Uploading ground photo for plot #${plotId}...`);
    try {
      const res = await api.uploadPlantationImage(plotId, uri);
      console.log(`[Mobile MRV] Upload complete: ${res.image_url}`);
      Alert.alert(
        "GROUND EVIDENCE CAPTURED",
        "Ground photo successfully uploaded to backend. You can now execute multi-modal verification."
      );
      const data = await api.getPlantations();
      setPlantations(data || []);
      const updated = data.find((p: any) => p.id === plotId);
      if (updated) {
        setSelectedPlantation(updated);
        await loadVerification(updated);
      }
    } catch (err: any) {
      console.error(`[Mobile MRV] Upload failure: ${err.message}`);
      Alert.alert("Upload Failed", err.message || "Network error uploading ground evidence. Please retry.");
    } finally {
      setUploadingImage(false);
    }
  };

  // Pick from Photo Gallery (Secondary / Testing option)
  const handlePickExistingPhoto = async (targetPlotId: number | null = null) => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: true,
        quality: 0.85
      });
      if (!result.canceled && result.assets && result.assets.length > 0) {
        const uri = result.assets[0].uri;
        if (targetPlotId) {
          await handleUploadForPlantation(targetPlotId, uri);
        } else {
          setImageUri(uri);
          Alert.alert("Photo Selected", "Gallery photo loaded as ground evidence.");
        }
      }
    } catch (err: any) {
      Alert.alert("Gallery Error", err.message || "Could not open photo library.");
    }
  };

  // Run Multi-Modal Verification
  const handleRunVerification = async (plotId: number) => {
    setLoading(true);
    console.log(`[Mobile MRV] Running verification for plot #${plotId}...`);
    try {
      const ver = await api.runVerification(plotId);
      console.log(`[Mobile MRV] Verification success: Decision=${ver.decision}, Score=${ver.overall_score}`);
      setVerification(ver);
      Alert.alert(
        "Verification Complete",
        `Multi-modal status: ${ver.decision}\nScore: ${ver.overall_score !== null ? `${ver.overall_score}/100` : "PENDING (Auditor Review)"}`
      );
      const data = await api.getPlantations();
      setPlantations(data || []);
    } catch (err: any) {
      console.error(`[Mobile MRV] Verification error: ${err.message}`);
      Alert.alert("Verification Error", err.message || "Failed to execute multi-modal verification.");
    } finally {
      setLoading(false);
    }
  };

  // Submit New Plantation and Run Verification
  const handleSubmitPlantation = async () => {
    if (!name.trim()) {
      Alert.alert("Missing Field", "Please enter plantation name.");
      return;
    }

    if (!api.getToken()) {
      Alert.alert(
        "Session Required",
        "No active login session detected. Please exit and log in to connect to the backend server."
      );
      return;
    }

    const latNum = parseFloat(latitude);
    const lonNum = parseFloat(longitude);
    if (isNaN(latNum) || isNaN(lonNum) || latNum < -90 || latNum > 90 || lonNum < -180 || lonNum > 180) {
      Alert.alert("Invalid Coordinates", "Please enter valid latitude (-90 to 90) and longitude (-180 to 180), or select via Open Map.");
      return;
    }

    const parsedTrees = parseInt(treeCount, 10);
    if (isNaN(parsedTrees) || parsedTrees <= 0) {
      Alert.alert("Invalid Tree Count", "Please enter a valid positive number of trees.");
      return;
    }

    const parsedArea = parseFloat(areaHectares);
    if (isNaN(parsedArea) || parsedArea <= 0) {
      Alert.alert("Invalid Area", "Please enter a valid positive area in hectares.");
      return;
    }

    let parsedSoc: number | undefined = undefined;
    if (soilSoc.trim()) {
      const val = parseFloat(soilSoc.trim());
      if (isNaN(val) || val < 0 || val > 10) {
        Alert.alert(
          "Invalid SOC Value",
          "Soil Organic Carbon (SOC) must be a numeric percentage between 0.0% and 10.0%, or left blank if awaiting lab test."
        );
        return;
      }
      parsedSoc = val;
    }

    if (submittingRef.current || submitting) {
      console.log("[Mobile MRV] Submission already in flight. Ignoring duplicate tap.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    console.log(`[Mobile MRV] Submit pressed: "${name.trim()}" (Trees: ${parsedTrees}, Area: ${parsedArea}ha, SOC: ${parsedSoc ?? "None"})`);

    try {
      // 1. Create plantation
      console.log(`[Mobile MRV] Creating plantation record at ${API_BASE_URL}/plantations`);
      const newPlot = await api.createPlantation({
        name: name.trim(),
        farmer_name: user?.full_name || "Ramesh Gowda",
        location: locationLabel || `Karnataka (${latNum.toFixed(4)}, ${lonNum.toFixed(4)})`,
        latitude: latNum,
        longitude: lonNum,
        area_hectares: parsedArea,
        plantation_age_years: 3.5,
        tree_count: parsedTrees,
        tree_species: species,
        soil_soc_pct: parsedSoc,
        soil_depth_cm: 45.0,
        soil_type: "Red Sandy Loam",
        plantation_type: "Agroforestry",
        sustainable_practice: "Organic Mulching"
      });

      console.log(`[Mobile MRV] Plantation created: Plot #${newPlot.id}`);

      // 2. Upload ground evidence photo if captured
      let uploadedImagePath: string | undefined = undefined;
      if (imageUri) {
        console.log(`[Mobile MRV] Uploading ground photo for plot #${newPlot.id}...`);
        try {
          const uploadRes = await api.uploadPlantationImage(newPlot.id, imageUri);
          uploadedImagePath = uploadRes.image_url;
          console.log(`[Mobile MRV] Image uploaded for plot #${newPlot.id}: ${uploadedImagePath}`);
        } catch (imgErr: any) {
          console.error(`[Mobile MRV] Image upload failed: ${imgErr.message}`);
          Alert.alert(
            "Evidence Upload Failed",
            `Plantation #${newPlot.id} was created, but photo upload failed (${imgErr.message}). Verification was not executed. Please use 'RE-CAPTURE PHOTO' or 'UPLOAD EXISTING PHOTO' below to retry.`
          );
          setName("");
          setImageUri(null);
          await fetchPlantations();
          setSelectedPlantation(newPlot);
          setVerification(null);
          return;
        }
      } else {
        console.log(`[Mobile MRV] Notice: Plot #${newPlot.id} submitted without ground photo.`);
      }

      // 3. Trigger multi-modal verification
      console.log(`[Mobile MRV] Running verification for plot #${newPlot.id}...`);
      try {
        const ver = await api.runVerification(newPlot.id, uploadedImagePath, parsedSoc);
        console.log(`[Mobile MRV] Verification response: Decision=${ver.decision}, Score=${ver.overall_score}`);
        setVerification(ver);

        const scoreText = ver.overall_score !== null ? `${ver.overall_score} / 100` : "PENDING (Evidence required)";
        Alert.alert(
          "Verification Complete",
          `Plot #${newPlot.id} Multi-Modal Result:\n\nStatus: ${ver.decision}\nScore: ${scoreText}\nRisk Level: ${ver.risk_level || "LOW"}`
        );
      } catch (verErr: any) {
        console.error(`[Mobile MRV] Verification error: ${verErr.message}`);
        setVerification(null);
        Alert.alert(
          "Verification Alert",
          `Plot #${newPlot.id} registered, but verification returned: ${verErr.message}`
        );
      }

      setName("");
      setImageUri(null);
      await fetchPlantations();
      setSelectedPlantation(newPlot);
    } catch (err: any) {
      console.error(`[Mobile MRV] Submit plantation failed: ${err.message}`);
      Alert.alert("Submission Error", err.message || "Failed to submit plantation for verification.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Native Camera Modal */}
      <CameraCaptureModal
        visible={cameraVisible}
        onClose={() => setCameraVisible(false)}
        onPhotoCaptured={handlePhotoAccepted}
        title={cameraTargetPlotId ? `Capture Plot #${cameraTargetPlotId} Evidence` : "Capture Plantation Photo"}
      />

      {/* Interactive Map Picker Modal */}
      <PlantationMapModal
        visible={mapVisible}
        initialLat={parseFloat(latitude) || 12.5218}
        initialLon={parseFloat(longitude) || 76.8951}
        onClose={() => setMapVisible(false)}
        onLocationSelected={(lat, lon, locName) => {
          setLatitude(lat.toFixed(4));
          setLongitude(lon.toFixed(4));
          if (locName) setLocationLabel(locName);
        }}
      />

      {/* Network Server Indicator */}
      <View style={styles.networkBanner}>
        <Text style={styles.networkBannerText}>📡 Backend Server: {API_BASE_URL}</Text>
      </View>

      {/* Header */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionSubtitle}>FARMER REGISTRATION & MRV EVIDENCE</Text>
        <Text style={styles.sectionTitle}>Plantation Onboarding</Text>
      </View>

      {/* Registration Form Card */}
      <View style={styles.card}>
        <Text style={styles.label}>Plantation Plot Name *</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g., Coorg Shade-Grown Agroforest"
          value={name}
          onChangeText={setName}
        />

        <View style={styles.row}>
          <View style={styles.halfCol}>
            <Text style={styles.label}>Tree Count</Text>
            <TextInput
              style={styles.input}
              keyboardType="numeric"
              value={treeCount}
              onChangeText={setTreeCount}
            />
          </View>
          <View style={styles.halfCol}>
            <Text style={styles.label}>Area (Hectares)</Text>
            <TextInput
              style={styles.input}
              keyboardType="numeric"
              value={areaHectares}
              onChangeText={setAreaHectares}
            />
          </View>
        </View>

        <Text style={styles.label}>Tree Species & Agroforestry Mix</Text>
        <TextInput
          style={styles.input}
          value={species}
          onChangeText={setSpecies}
        />

        {/* Plantation Location & Map Geotagging Box */}
        <View style={styles.locationBox}>
          <View style={styles.locationHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.locationLabel}>Plantation Location & Geotag</Text>
              <Text style={styles.locationSubLabel} numberOfLines={1}>{locationLabel}</Text>
            </View>
            <View style={styles.locationBtnRow}>
              {/* Button to Open Native Map */}
              <TouchableOpacity onPress={() => setMapVisible(true)} style={styles.mapBtn}>
                <Text style={styles.mapBtnText}>🗺️ Open Map</Text>
              </TouchableOpacity>
              {/* Quick GPS Geotag */}
              <TouchableOpacity onPress={handleGetLocation} style={styles.smallBtn}>
                <Text style={styles.smallBtnText}>📍 GPS</Text>
              </TouchableOpacity>
            </View>
          </View>
          <Text style={styles.coordText}>Lat: {latitude} • Lon: {longitude}</Text>
        </View>

        {/* Soil Organic Carbon */}
        <View style={styles.row}>
          <View style={styles.halfCol}>
            <Text style={styles.label}>Soil Organic Carbon (SOC %)</Text>
            <TextInput
              style={styles.input}
              keyboardType="numeric"
              value={soilSoc}
              onChangeText={setSoilSoc}
            />
          </View>
          <View style={styles.halfCol}>
            <Text style={styles.label}>Soil Depth</Text>
            <TextInput style={[styles.input, styles.disabledInput]} value="0 - 30 cm" editable={false} />
          </View>
        </View>

        {/* Ground Canopy Photo Evidence Section */}
        <Text style={styles.label}>Ground Canopy Photo Evidence (AI Vision)</Text>
        <View style={styles.photoContainer}>
          {imageUri ? (
            <View style={styles.capturedEvidenceBox}>
              <Image source={{ uri: imageUri }} style={styles.previewImage} resizeMode="cover" />
              <View style={styles.capturedBadgeRow}>
                <View style={styles.evidenceSuccessBadge}>
                  <Text style={styles.evidenceSuccessText}>✓ GROUND EVIDENCE CAPTURED</Text>
                </View>
                <TouchableOpacity onPress={() => setImageUri(null)} style={styles.clearBtn}>
                  <Text style={styles.clearBtnText}>✕ Remove</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.capturedHint}>Image will be uploaded & attached to plot upon submission.</Text>
            </View>
          ) : (
            <View style={styles.photoPlaceholder}>
              <Text style={styles.placeholderIcon}>📷</Text>
              <Text style={styles.placeholderText}>No photo captured yet</Text>
              <Text style={styles.placeholderSub}>Required for Deep Learning AI computer vision verification</Text>
            </View>
          )}

          <View style={styles.photoBtnRow}>
            {/* Primary Button: Directly Opens Native Camera */}
            <TouchableOpacity
              onPress={() => handleOpenCamera(null)}
              style={styles.primaryCameraBtn}
            >
              <Text style={styles.primaryCameraBtnText}>📷 CAPTURE PLANTATION PHOTO</Text>
            </TouchableOpacity>

            {/* Secondary Button: Gallery Picker */}
            <TouchableOpacity
              onPress={() => handlePickExistingPhoto(null)}
              style={styles.secondaryPickerBtn}
            >
              <Text style={styles.secondaryPickerBtnText}>🖼️ UPLOAD EXISTING PHOTO</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Submit for Verification Button */}
        <TouchableOpacity
          style={[styles.submitBtn, submitting && styles.btnDisabled]}
          onPress={handleSubmitPlantation}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitBtnText}>Submit for Verification</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Selected Plantation MRV Evidence & Verification Card */}
      {selectedPlantation && (
        <View style={styles.card}>
          <View style={styles.verHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.verTitle}>Plot #{selectedPlantation.id} • {selectedPlantation.name}</Text>
              <Text style={styles.plotMeta}>{selectedPlantation.location}</Text>
            </View>
            <View style={[
              styles.statusBadge,
              selectedPlantation.status === "VERIFIED" ? styles.badgeApproved :
              selectedPlantation.status === "REVIEW" ? styles.badgeReview : styles.badgePending
            ]}>
              <Text style={styles.statusText}>{selectedPlantation.status}</Text>
            </View>
          </View>

          {/* Ground Evidence Status for this Plot */}
          <View style={styles.evidenceSection}>
            <Text style={styles.evidenceSectionTitle}>GROUND EVIDENCE STATUS</Text>
            {selectedPlantation.image_url ? (
              <View style={styles.evidencePresentCard}>
                <Image
                  source={{
                    uri: selectedPlantation.image_url.startsWith("http")
                      ? selectedPlantation.image_url
                      : `${API_BASE_URL.replace("/api", "")}${selectedPlantation.image_url}`
                  }}
                  style={styles.evidenceDisplayImage}
                  resizeMode="cover"
                />
                <View style={styles.evidenceInfoRow}>
                  <View style={styles.evidenceSuccessBadge}>
                    <Text style={styles.evidenceSuccessText}>✓ GROUND EVIDENCE CAPTURED</Text>
                  </View>
                  <Text style={styles.evidenceTimestamp}>Stored on MRV server</Text>
                </View>
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={styles.reCaptureBtn}
                    onPress={() => handleOpenCamera(selectedPlantation.id)}
                    disabled={uploadingImage}
                  >
                    <Text style={styles.reCaptureBtnText}>📷 RE-CAPTURE PHOTO</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.verifyBtn}
                    onPress={() => handleRunVerification(selectedPlantation.id)}
                    disabled={loading}
                  >
                    <Text style={styles.verifyBtnText}>⚡ RUN VERIFICATION</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <View style={styles.evidenceMissingCard}>
                <View style={styles.missingBadge}>
                  <Text style={styles.missingBadgeText}>⚠️ GROUND EVIDENCE MISSING</Text>
                </View>
                <Text style={styles.missingExplanation}>
                  Multi-modal verification requires on-site canopy photographic evidence before carbon credits can be issued.
                </Text>

                {uploadingImage ? (
                  <View style={styles.uploadingBox}>
                    <ActivityIndicator size="small" color="#166534" />
                    <Text style={styles.uploadingText}>Uploading ground evidence to backend...</Text>
                  </View>
                ) : (
                  <View style={styles.photoBtnRow}>
                    <TouchableOpacity
                      style={styles.primaryCameraBtn}
                      onPress={() => handleOpenCamera(selectedPlantation.id)}
                    >
                      <Text style={styles.primaryCameraBtnText}>📷 CAPTURE PLANTATION PHOTO</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.secondaryPickerBtn}
                      onPress={() => handlePickExistingPhoto(selectedPlantation.id)}
                    >
                      <Text style={styles.secondaryPickerBtnText}>🖼️ UPLOAD EXISTING PHOTO</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            )}
          </View>

          {/* Verification Results Breakdown (if verified) */}
          {verification && (
            <View style={styles.verificationBlock}>
              <View style={styles.scoreRow}>
                <Text style={styles.scoreLabel}>Weighted Verification Score:</Text>
                <Text style={styles.scoreValue}>
                  {verification.overall_score !== null ? `${verification.overall_score} / 100` : "PENDING"}
                </Text>
              </View>

              <View style={styles.pillarsGrid}>
                <View style={styles.pillarCard}>
                  <Text style={styles.pillarTag}>SATELLITE (40%)</Text>
                  <Text style={styles.pillarVal}>{verification.ndvi_score || "—"}</Text>
                  <Text style={styles.pillarSub}>
                    {verification.is_real_satellite ? "Sentinel-2 Real" : "Simulator"}
                  </Text>
                </View>

                <View style={styles.pillarCard}>
                  <Text style={styles.pillarTag}>AI VISION (35%)</Text>
                  <Text style={styles.pillarVal}>{verification.cv_score || "—"}</Text>
                  <Text style={styles.pillarSub}>
                    {verification.ai_confidence_pct ? `${verification.ai_confidence_pct}% Conf` : "Pending"}
                  </Text>
                </View>

                <View style={styles.pillarCard}>
                  <Text style={styles.pillarTag}>SOIL SOC (25%)</Text>
                  <Text style={styles.pillarVal}>{verification.soc_score || "—"}</Text>
                  <Text style={styles.pillarSub}>{verification.soc_pct ? `${verification.soc_pct}%` : "—"}</Text>
                </View>
              </View>

              <View style={[
                styles.riskBox,
                verification.risk_level === "HIGH" ? styles.riskHigh :
                verification.risk_level === "MEDIUM" ? styles.riskMed : styles.riskLow
              ]}>
                <Text style={styles.riskTitle}>
                  Fraud & Risk Score: {verification.risk_score || 0}/100 • {verification.risk_level || "LOW"} RISK
                </Text>
                {verification.risk_factors && verification.risk_factors.length > 0 ? (
                  <Text style={styles.riskDetail}>⚠️ {verification.risk_factors[0]}</Text>
                ) : (
                  <Text style={styles.riskDetail}>✓ All signals consistent. pHash verified unique.</Text>
                )}
              </View>
            </View>
          )}
        </View>
      )}

      {/* Existing Plantations List */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionSubtitle}>MY REGISTERED PLANTATIONS</Text>
      </View>
      {loading ? (
        <ActivityIndicator size="small" color="#1B3B2B" />
      ) : (
        plantations.map((p) => (
          <TouchableOpacity
            key={p.id}
            style={[styles.plotItem, selectedPlantation?.id === p.id && styles.plotItemSelected]}
            onPress={() => loadVerification(p)}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.plotName}>Plot #{p.id} • {p.name}</Text>
              <Text style={styles.plotMeta}>{p.area_hectares} ha • {p.tree_count} trees • {p.tree_species}</Text>
              <Text style={styles.evidenceIndicator}>
                {p.image_url ? "✓ Ground Photo Attached" : "⚠️ Ground Photo Missing"}
              </Text>
            </View>
            <View style={[
              styles.smallBadge,
              p.status === "VERIFIED" ? styles.badgeApproved : styles.badgeReview
            ]}>
              <Text style={styles.smallBadgeText}>{p.status}</Text>
            </View>
          </TouchableOpacity>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F8FAFC" },
  content: { padding: 16, paddingBottom: 40 },
  networkBanner: { backgroundColor: "#F1F5F9", paddingVertical: 4, paddingHorizontal: 8, borderRadius: 4, marginBottom: 8, alignItems: "center" },
  networkBannerText: { fontSize: 10, color: "#64748B", fontFamily: "monospace" },
  sectionHeader: { marginBottom: 10, marginTop: 6 },
  sectionSubtitle: { fontSize: 10, fontWeight: "700", color: "#64748B", letterSpacing: 0.8 },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  card: { backgroundColor: "#FFFFFF", borderRadius: 8, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: "#E2E8F0" },
  label: { fontSize: 11, fontWeight: "700", color: "#475569", marginBottom: 4, marginTop: 8 },
  input: { borderWidth: 1, borderColor: "#CBD5E1", borderRadius: 6, paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, backgroundColor: "#FFFFFF", color: "#0F172A" },
  disabledInput: { backgroundColor: "#F1F5F9", color: "#64748B" },
  row: { flexDirection: "row", gap: 10 },
  halfCol: { flex: 1 },
  locationBox: { backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 6, padding: 10, marginVertical: 8 },
  locationHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 8 },
  locationLabel: { fontSize: 11, fontWeight: "700", color: "#334155" },
  locationSubLabel: { fontSize: 10, color: "#166534", fontWeight: "600", marginTop: 2 },
  locationBtnRow: { flexDirection: "row", gap: 6 },
  mapBtn: { backgroundColor: "#1B3B2B", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 4 },
  mapBtnText: { color: "#FFFFFF", fontSize: 10, fontWeight: "700" },
  smallBtn: { backgroundColor: "#E2E8F0", paddingHorizontal: 8, paddingVertical: 5, borderRadius: 4 },
  smallBtnText: { color: "#334155", fontSize: 10, fontWeight: "700" },
  coordText: { fontSize: 11, color: "#64748B", fontFamily: "monospace", marginTop: 4 },
  photoContainer: { marginTop: 6, marginBottom: 12 },
  capturedEvidenceBox: { marginBottom: 8 },
  previewImage: { width: "100%", height: 160, borderRadius: 6 },
  capturedBadgeRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 6 },
  evidenceSuccessBadge: { backgroundColor: "#DCFCE7", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, borderWidth: 1, borderColor: "#86EFAC" },
  evidenceSuccessText: { color: "#166534", fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  clearBtn: { paddingHorizontal: 8, paddingVertical: 2 },
  clearBtnText: { color: "#EF4444", fontSize: 11, fontWeight: "600" },
  capturedHint: { fontSize: 10, color: "#64748B", marginTop: 3 },
  photoPlaceholder: { height: 110, backgroundColor: "#F1F5F9", borderRadius: 6, justifyContent: "center", alignItems: "center", borderWidth: 1, borderColor: "#CBD5E1", borderStyle: "dashed", marginBottom: 8 },
  placeholderIcon: { fontSize: 24, marginBottom: 4 },
  placeholderText: { fontSize: 12, fontWeight: "700", color: "#64748B" },
  placeholderSub: { fontSize: 10, color: "#94A3B8", marginTop: 2, textAlign: "center", paddingHorizontal: 16 },
  photoBtnRow: { flexDirection: "column", gap: 8, marginTop: 4 },
  primaryCameraBtn: { backgroundColor: "#1B3B2B", paddingVertical: 11, borderRadius: 6, alignItems: "center", shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 2, elevation: 2 },
  primaryCameraBtnText: { color: "#FFFFFF", fontSize: 12, fontWeight: "800", letterSpacing: 0.5 },
  secondaryPickerBtn: { backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#CBD5E1", paddingVertical: 9, borderRadius: 6, alignItems: "center" },
  secondaryPickerBtnText: { color: "#334155", fontSize: 11, fontWeight: "700" },
  submitBtn: { backgroundColor: "#1B3B2B", paddingVertical: 12, borderRadius: 6, alignItems: "center", marginTop: 12 },
  submitBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.5 },
  btnDisabled: { opacity: 0.6 },
  verHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 },
  verTitle: { fontSize: 14, fontWeight: "800", color: "#0F172A" },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  badgeApproved: { backgroundColor: "#DCFCE7" },
  badgeReview: { backgroundColor: "#FEF3C7" },
  badgePending: { backgroundColor: "#F1F5F9" },
  statusText: { fontSize: 10, fontWeight: "800", color: "#166534" },
  evidenceSection: { marginTop: 8, paddingTop: 12, borderTopWidth: 1, borderColor: "#F1F5F9" },
  evidenceSectionTitle: { fontSize: 10, fontWeight: "800", color: "#64748B", letterSpacing: 0.8, marginBottom: 8 },
  evidencePresentCard: { backgroundColor: "#F8FAFC", borderRadius: 6, padding: 10, borderWidth: 1, borderColor: "#E2E8F0" },
  evidenceDisplayImage: { width: "100%", height: 140, borderRadius: 6, marginBottom: 8 },
  evidenceInfoRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  evidenceTimestamp: { fontSize: 10, color: "#94A3B8" },
  actionRow: { flexDirection: "row", gap: 8 },
  reCaptureBtn: { flex: 1, backgroundColor: "#FFFFFF", borderWidth: 1, borderColor: "#CBD5E1", paddingVertical: 8, borderRadius: 6, alignItems: "center" },
  reCaptureBtnText: { color: "#334155", fontSize: 11, fontWeight: "700" },
  verifyBtn: { flex: 1, backgroundColor: "#1B3B2B", paddingVertical: 8, borderRadius: 6, alignItems: "center" },
  verifyBtnText: { color: "#FFFFFF", fontSize: 11, fontWeight: "800" },
  evidenceMissingCard: { backgroundColor: "#FFFBEB", borderRadius: 6, padding: 12, borderWidth: 1, borderColor: "#FDE68A" },
  missingBadge: { alignSelf: "flex-start", backgroundColor: "#FEF3C7", paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, marginBottom: 6 },
  missingBadgeText: { color: "#92400E", fontSize: 10, fontWeight: "800" },
  missingExplanation: { fontSize: 11, color: "#78350F", lineHeight: 16, marginBottom: 10 },
  uploadingBox: { paddingVertical: 12, alignItems: "center", gap: 6 },
  uploadingText: { fontSize: 11, color: "#166534", fontWeight: "600" },
  verificationBlock: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderColor: "#F1F5F9" },
  scoreRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingBottom: 10, borderBottomWidth: 1, borderColor: "#F1F5F9" },
  scoreLabel: { fontSize: 12, color: "#64748B", fontWeight: "600" },
  scoreValue: { fontSize: 16, fontWeight: "800", color: "#0F172A", fontFamily: "monospace" },
  pillarsGrid: { flexDirection: "row", gap: 8, marginVertical: 10 },
  pillarCard: { flex: 1, backgroundColor: "#F8FAFC", borderRadius: 6, padding: 8, alignItems: "center", borderWidth: 1, borderColor: "#E2E8F0" },
  pillarTag: { fontSize: 8, fontWeight: "800", color: "#64748B" },
  pillarVal: { fontSize: 14, fontWeight: "800", color: "#0F172A", marginVertical: 2, fontFamily: "monospace" },
  pillarSub: { fontSize: 8, color: "#64748B", textAlign: "center" },
  riskBox: { padding: 10, borderRadius: 6, marginTop: 6 },
  riskLow: { backgroundColor: "#F0FDF4", borderColor: "#BBF7D0", borderWidth: 1 },
  riskMed: { backgroundColor: "#FFFBEB", borderColor: "#FDE68A", borderWidth: 1 },
  riskHigh: { backgroundColor: "#FEF2F2", borderColor: "#FECACA", borderWidth: 1 },
  riskTitle: { fontSize: 11, fontWeight: "800", color: "#0F172A" },
  riskDetail: { fontSize: 10, color: "#475569", marginTop: 2 },
  plotItem: { backgroundColor: "#FFFFFF", borderRadius: 6, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: "#E2E8F0", flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  plotItemSelected: { borderColor: "#1B3B2B", borderWidth: 2 },
  plotName: { fontSize: 12, fontWeight: "700", color: "#0F172A" },
  plotMeta: { fontSize: 10, color: "#64748B", marginTop: 2 },
  evidenceIndicator: { fontSize: 9, color: "#64748B", marginTop: 3, fontWeight: "600" },
  smallBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  smallBadgeText: { fontSize: 9, fontWeight: "700", color: "#166534" }
});
