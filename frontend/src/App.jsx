import React, { Suspense, lazy, useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import DisclaimerBanner from "./components/DisclaimerBanner";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import ErrorBoundary from "./components/ErrorBoundary";
import { getRoleDashboardView, isRouteAllowed } from "./utils/roleRouting";

// Pages are code-split: each loads on first visit, keeping the initial bundle small.
const LandingPage = lazy(() => import("./pages/LandingPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const FarmerDashboard = lazy(() => import("./pages/FarmerDashboard"));
const CreatePlantationPage = lazy(() => import("./pages/CreatePlantationPage"));
const VerificationReportPage = lazy(() => import("./pages/VerificationReportPage"));
const MarketplacePage = lazy(() => import("./pages/MarketplacePage"));
const CreditDetailsPage = lazy(() => import("./pages/CreditDetailsPage"));
const BuyerDashboard = lazy(() => import("./pages/BuyerDashboard"));
const TransactionHistoryPage = lazy(() => import("./pages/TransactionHistoryPage"));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard"));
const FarmerPlantationsPage = lazy(() => import("./pages/FarmerPlantationsPage"));
const FarmerCarbonAssetsPage = lazy(() => import("./pages/FarmerCarbonAssetsPage"));
const AuditorQueuePage = lazy(() => import("./pages/AuditorQueuePage"));

function AppContent() {
  const { isAuthenticated, role, loading } = useAuth();
  const [currentView, setCurrentView] = useState("landing");
  const [portalRole, setPortalRole] = useState(null);
  const [selectedPlantationId, setSelectedPlantationId] = useState(null);
  const [selectedCreditId, setSelectedCreditId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Check if current view is public or authenticated portal view
  const isPublicView = ["landing", "login", "register"].includes(currentView);
  const showSidebar = isAuthenticated && !isPublicView;

  // Enforce role authorization for the active view
  const isAllowed = isRouteAllowed(currentView, role, isAuthenticated);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FAF9F6] flex items-center justify-center text-xs text-slate-500 font-sans">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-[#1B3B2B] border-t-transparent rounded-full animate-spin"></div>
          <span>Loading session...</span>
        </div>
      </div>
    );
  }

  // Render view router
  const renderView = () => {
    // If not allowed, redirect unauthorized requests to their authorized dashboard or login
    if (!isAllowed) {
      if (!isAuthenticated) {
        return (
          <LoginPage
            setCurrentView={setCurrentView}
            portalRole={portalRole}
            setPortalRole={setPortalRole}
          />
        );
      }
      // If authenticated user attempts to access an unauthorized route, redirect to their role dashboard
      const authorizedDashboard = getRoleDashboardView(role);
      if (authorizedDashboard === "admin_dashboard") {
        return (
          <AdminDashboard
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      } else if (authorizedDashboard === "buyer_dashboard") {
        return (
          <BuyerDashboard
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
          />
        );
      } else if (authorizedDashboard === "farmer_dashboard") {
        return (
          <FarmerDashboard
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      }
      return <LandingPage setCurrentView={setCurrentView} setPortalRole={setPortalRole} />;
    }

    switch (currentView) {
      case "landing":
        return (
          <LandingPage
            setCurrentView={setCurrentView}
            setPortalRole={setPortalRole}
          />
        );
      case "login":
        return (
          <LoginPage
            setCurrentView={setCurrentView}
            portalRole={portalRole}
            setPortalRole={setPortalRole}
          />
        );
      case "register":
        return (
          <RegisterPage
            setCurrentView={setCurrentView}
            portalRole={portalRole}
            setPortalRole={setPortalRole}
          />
        );
      case "farmer_dashboard":
        return (
          <FarmerDashboard
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "farmer_plantations":
        return (
          <FarmerPlantationsPage
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "farmer_carbon_assets":
        return (
          <FarmerCarbonAssetsPage
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "create_plantation":
        return (
          <CreatePlantationPage
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "verification_report":
        return (
          <VerificationReportPage
            plantationId={selectedPlantationId}
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
          />
        );
      case "marketplace":
        return (
          <MarketplacePage
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
          />
        );
      case "credit_details":
        return (
          <CreditDetailsPage
            creditId={selectedCreditId}
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "buyer_dashboard":
        return (
          <BuyerDashboard
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
          />
        );
      case "transactions":
        return (
          <TransactionHistoryPage
            setCurrentView={setCurrentView}
            setSelectedCreditId={setSelectedCreditId}
          />
        );
      case "admin_dashboard":
        return (
          <AdminDashboard
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      case "auditor_queue":
        return (
          <AuditorQueuePage
            setCurrentView={setCurrentView}
            setSelectedPlantationId={setSelectedPlantationId}
          />
        );
      default:
        return (
          <LandingPage
            setCurrentView={setCurrentView}
            setPortalRole={setPortalRole}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF9F6] text-slate-900 flex flex-col font-sans selection:bg-forest-100 selection:text-forest-900">
      {/* Header (offset on desktop so the fixed sidebar does not cover it) */}
      <div className={showSidebar ? "lg:pl-56" : ""}>
        {/* Top Academic Prototype Disclaimer */}
        <DisclaimerBanner />

        {/* Main Top Header Navbar */}
        <Navbar
          currentView={currentView}
          setCurrentView={setCurrentView}
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          setPortalRole={setPortalRole}
        />
      </div>

      {/* Optional Authenticated Sidebar */}
      {showSidebar && (
        <Sidebar
          currentView={currentView}
          setCurrentView={setCurrentView}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      {/* Main View Container (offset by sidebar width on desktop when authenticated) */}
      <main className={`flex-1 pb-16 transition-all duration-200 ${showSidebar ? "lg:pl-64" : ""}`}>
        <ErrorBoundary onReset={() => setCurrentView(getRoleDashboardView(role))}>
          <Suspense fallback={<div className="py-20 text-center text-xs text-slate-500">Loading…</div>}>
            {renderView()}
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
