import React, { useState, useRef, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  Image,
  StyleSheet,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  Alert,
  Platform
} from "react-native";
import { CameraView, useCameraPermissions, CameraType, FlashMode } from "expo-camera";

interface CameraCaptureModalProps {
  visible: boolean;
  onClose: () => void;
  onPhotoCaptured: (uri: string) => void;
  title?: string;
}

export default function CameraCaptureModal({
  visible,
  onClose,
  onPhotoCaptured,
  title = "Plantation Ground Evidence"
}: CameraCaptureModalProps) {
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState<CameraType>("back");
  const [flash, setFlash] = useState<FlashMode>("off");
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [cameraAvailable, setCameraAvailable] = useState(true);
  const [cameraReady, setCameraReady] = useState(false);
  const cameraRef = useRef<any>(null);

  useEffect(() => {
    if (visible) {
      setCapturedUri(null);
      setCapturing(false);
      setCameraReady(false);
      checkAvailability();
    }
  }, [visible]);

  const checkAvailability = async () => {
    try {
      if (CameraView && typeof CameraView.isAvailableAsync === "function") {
        const avail = await CameraView.isAvailableAsync();
        setCameraAvailable(avail);
      }
    } catch {
      // Default to true on native platforms
      setCameraAvailable(Platform.OS !== "web");
    }
  };

  const handleTakePicture = async () => {
    if (!cameraRef.current || capturing) return;
    setCapturing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.85,
        skipProcessing: false
      });
      if (photo && photo.uri) {
        setCapturedUri(photo.uri);
      } else {
        Alert.alert("Capture Error", "Failed to capture photo. Please try again.");
      }
    } catch (err: any) {
      console.warn("Camera capture error:", err);
      Alert.alert("Camera Error", err.message || "Could not take photo. Please retry.");
    } finally {
      setCapturing(false);
    }
  };

  const handleRetake = () => {
    setCapturedUri(null);
  };

  const handleUsePhoto = () => {
    if (capturedUri) {
      const uri = capturedUri;
      setCapturedUri(null);
      onPhotoCaptured(uri);
    }
  };

  const toggleFacing = () => {
    setFacing((prev) => (prev === "back" ? "front" : "back"));
  };

  const toggleFlash = () => {
    setFlash((prev) => (prev === "off" ? "on" : "off"));
  };

  if (!visible) {
    return null;
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor="#000000" />

        {/* 1. Permission Loading State */}
        {!permission && (
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color="#4ADE80" />
            <Text style={styles.infoText}>Checking camera permissions...</Text>
          </View>
        )}

        {/* 2. Permission Denied State */}
        {permission && !permission.granted && (
          <View style={styles.centerContainer}>
            <View style={styles.iconCircle}>
              <Text style={styles.iconSymbol}>📷</Text>
            </View>
            <Text style={styles.permissionTitle}>Camera Access Required</Text>
            <Text style={styles.permissionMessage}>
              Camera access is required to capture ground evidence.
            </Text>
            <Text style={styles.permissionSubMessage}>
              Live on-site canopy photographs verify tree density and prevent fraud in multi-modal carbon MRV.
            </Text>
            <TouchableOpacity style={styles.primaryBtn} onPress={requestPermission}>
              <Text style={styles.primaryBtnText}>Grant Camera Permission</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryBtn} onPress={onClose}>
              <Text style={styles.secondaryBtnText}>Cancel / Return</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* 3. Camera Hardware Unavailable */}
        {permission && permission.granted && !cameraAvailable && (
          <View style={styles.centerContainer}>
            <Text style={styles.iconSymbol}>⚠️</Text>
            <Text style={styles.permissionTitle}>Camera Unavailable</Text>
            <Text style={styles.permissionMessage}>
              Native camera hardware is not available on this device or simulator.
            </Text>
            <TouchableOpacity style={styles.secondaryBtn} onPress={onClose}>
              <Text style={styles.secondaryBtnText}>Return</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* 4. Live Camera Preview or Captured Image Preview */}
        {permission && permission.granted && cameraAvailable && (
          <View style={styles.fullScreen}>
            {capturedUri ? (
              // Captured Photo Preview
              <View style={styles.previewContainer}>
                <Image source={{ uri: capturedUri }} style={styles.previewImage} resizeMode="cover" />
                
                {/* Header Badge */}
                <View style={styles.previewHeader}>
                  <View style={styles.statusPill}>
                    <Text style={styles.statusPillText}>✓ PHOTO CAPTURED</Text>
                  </View>
                  <Text style={styles.previewSub}>Review image clarity before uploading</Text>
                </View>

                {/* Bottom Action Bar */}
                <View style={styles.previewActionRow}>
                  <TouchableOpacity style={styles.retakeBtn} onPress={handleRetake}>
                    <Text style={styles.retakeBtnText}>↺ RETAKE</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.usePhotoBtn} onPress={handleUsePhoto}>
                    <Text style={styles.usePhotoBtnText}>USE PHOTO →</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              // Live Camera Viewfinder
              <View style={styles.cameraWrapper}>
                <CameraView
                  ref={cameraRef}
                  style={styles.camera}
                  facing={facing}
                  flash={flash}
                  onCameraReady={() => setCameraReady(true)}
                >
                  {/* Top Bar */}
                  <View style={styles.topBar}>
                    <TouchableOpacity style={styles.topBarBtn} onPress={onClose}>
                      <Text style={styles.topBarBtnText}>✕ Close</Text>
                    </TouchableOpacity>
                    <Text style={styles.topBarTitle} numberOfLines={1}>{title}</Text>
                    <TouchableOpacity style={styles.topBarBtn} onPress={toggleFlash}>
                      <Text style={styles.topBarBtnText}>
                        {flash === "on" ? "⚡ On" : "⚡ Off"}
                      </Text>
                    </TouchableOpacity>
                  </View>

                  {/* Viewfinder Target / Canopy Alignment Guide */}
                  <View style={styles.viewfinderCenter}>
                    <View style={styles.viewfinderFrame}>
                      <View style={[styles.corner, styles.topLeft]} />
                      <View style={[styles.corner, styles.topRight]} />
                      <View style={[styles.corner, styles.bottomLeft]} />
                      <View style={[styles.corner, styles.bottomRight]} />
                      <Text style={styles.guideText}>
                        Align plantation canopy & ground trees within frame
                      </Text>
                    </View>
                  </View>

                  {/* Bottom Controls */}
                  <View style={styles.bottomControls}>
                    <TouchableOpacity style={styles.auxBtn} onPress={toggleFacing}>
                      <Text style={styles.auxBtnText}>🔄 Flip</Text>
                    </TouchableOpacity>

                    {/* Shutter Button */}
                    <TouchableOpacity
                      style={[styles.shutterOuter, capturing && styles.shutterDisabled]}
                      onPress={handleTakePicture}
                      disabled={capturing}
                    >
                      <View style={styles.shutterInner}>
                        {capturing ? (
                          <ActivityIndicator size="small" color="#166534" />
                        ) : (
                          <View style={styles.shutterDot} />
                        )}
                      </View>
                    </TouchableOpacity>

                    <TouchableOpacity style={styles.auxBtn} onPress={onClose}>
                      <Text style={styles.auxBtnText}>Cancel</Text>
                    </TouchableOpacity>
                  </View>
                </CameraView>
              </View>
            )}
          </View>
        )}
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000000"
  },
  fullScreen: {
    flex: 1,
    backgroundColor: "#000000"
  },
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#0F172A"
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#1E293B",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16
  },
  iconSymbol: {
    fontSize: 28
  },
  infoText: {
    color: "#E2E8F0",
    marginTop: 12,
    fontSize: 14
  },
  permissionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#FFFFFF",
    marginBottom: 8,
    textAlign: "center"
  },
  permissionMessage: {
    fontSize: 14,
    color: "#E2E8F0",
    textAlign: "center",
    marginBottom: 6,
    fontWeight: "600"
  },
  permissionSubMessage: {
    fontSize: 12,
    color: "#94A3B8",
    textAlign: "center",
    marginBottom: 24,
    lineHeight: 18
  },
  primaryBtn: {
    backgroundColor: "#166534",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    width: "100%",
    alignItems: "center",
    marginBottom: 10
  },
  primaryBtnText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 0.5
  },
  secondaryBtn: {
    backgroundColor: "transparent",
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#334155",
    width: "100%",
    alignItems: "center"
  },
  secondaryBtnText: {
    color: "#94A3B8",
    fontSize: 13,
    fontWeight: "600"
  },
  cameraWrapper: {
    flex: 1
  },
  camera: {
    flex: 1,
    justifyContent: "space-between"
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "rgba(0,0,0,0.5)"
  },
  topBarTitle: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
    flex: 1,
    textAlign: "center",
    marginHorizontal: 8
  },
  topBarBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: "rgba(255,255,255,0.15)"
  },
  topBarBtnText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700"
  },
  viewfinderCenter: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24
  },
  viewfinderFrame: {
    width: "90%",
    height: "70%",
    position: "relative",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
    borderRadius: 12
  },
  corner: {
    position: "absolute",
    width: 24,
    height: 24,
    borderColor: "#4ADE80",
    borderWidth: 3
  },
  topLeft: {
    top: -2,
    left: -2,
    borderBottomWidth: 0,
    borderRightWidth: 0,
    borderTopLeftRadius: 10
  },
  topRight: {
    top: -2,
    right: -2,
    borderBottomWidth: 0,
    borderLeftWidth: 0,
    borderTopRightRadius: 10
  },
  bottomLeft: {
    bottom: -2,
    left: -2,
    borderTopWidth: 0,
    borderRightWidth: 0,
    borderBottomLeftRadius: 10
  },
  bottomRight: {
    bottom: -2,
    right: -2,
    borderTopWidth: 0,
    borderLeftWidth: 0,
    borderBottomRightRadius: 10
  },
  guideText: {
    color: "rgba(255,255,255,0.85)",
    fontSize: 11,
    fontWeight: "700",
    textAlign: "center",
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    overflow: "hidden"
  },
  bottomControls: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    paddingVertical: 24,
    paddingHorizontal: 20,
    backgroundColor: "rgba(0,0,0,0.6)"
  },
  shutterOuter: {
    width: 76,
    height: 76,
    borderRadius: 38,
    borderWidth: 4,
    borderColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "transparent"
  },
  shutterDisabled: {
    opacity: 0.5
  },
  shutterInner: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#FFFFFF",
    justifyContent: "center",
    alignItems: "center"
  },
  shutterDot: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#166534"
  },
  auxBtn: {
    width: 64,
    alignItems: "center",
    paddingVertical: 8
  },
  auxBtnText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700"
  },
  previewContainer: {
    flex: 1,
    position: "relative",
    justifyContent: "space-between"
  },
  previewImage: {
    ...StyleSheet.absoluteFill
  },
  previewHeader: {
    paddingTop: 16,
    paddingHorizontal: 16,
    alignItems: "center"
  },
  statusPill: {
    backgroundColor: "rgba(22, 101, 52, 0.9)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16
  },
  statusPillText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.5
  },
  previewSub: {
    color: "#FFFFFF",
    fontSize: 11,
    marginTop: 6,
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4
  },
  previewActionRow: {
    flexDirection: "row",
    padding: 20,
    gap: 12,
    backgroundColor: "rgba(0,0,0,0.7)"
  },
  retakeBtn: {
    flex: 1,
    backgroundColor: "#334155",
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: "center"
  },
  retakeBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.5
  },
  usePhotoBtn: {
    flex: 1,
    backgroundColor: "#166534",
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: "center"
  },
  usePhotoBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.5
  }
});
