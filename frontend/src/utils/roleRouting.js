/**
 * Role-Based Routing & Access Authorization
 * Carbon Credit Marketplace with Multi-Modal Verification
 */

export const UserRole = {
  FARMER: "FARMER",
  BUYER: "BUYER",
  AUDITOR: "AUDITOR",
  ADMIN: "ADMIN",
};

/**
 * Returns the default authorized dashboard view for a user's role.
 * NEVER defaults an unknown or missing role to FARMER!
 */
export function getRoleDashboardView(role) {
  if (!role) return "login";
  const normalized = String(role).trim().toUpperCase();

  switch (normalized) {
    case UserRole.FARMER:
      return "farmer_dashboard";
    case UserRole.BUYER:
      return "buyer_dashboard";
    case UserRole.AUDITOR:
    case UserRole.ADMIN:
      return "admin_dashboard";
    default:
      // Unknown or invalid role -> NEVER fallback to FARMER
      return "login";
  }
}

/**
 * Checks whether a given view is allowed for the user's role and authentication status.
 */
export function isRouteAllowed(view, role, isAuthenticated) {
  // 1. Public views always accessible
  const publicViews = ["landing", "login", "register", "marketplace", "credit_details"];
  if (publicViews.includes(view)) {
    return true;
  }

  // 2. Protected views require active authentication and valid role
  if (!isAuthenticated || !role) {
    return false;
  }

  const normalized = String(role).trim().toUpperCase();

  // 3. Farmer Routes
  if (normalized === UserRole.FARMER) {
    const farmerViews = [
      "farmer_dashboard",
      "farmer_plantations",
      "farmer_carbon_assets",
      "create_plantation",
      "verification_report",
      "marketplace",
      "credit_details"
    ];
    return farmerViews.includes(view);
  }

  // 4. Buyer Routes
  if (normalized === UserRole.BUYER) {
    const buyerViews = [
      "buyer_dashboard",
      "marketplace",
      "credit_details",
      "transactions"
    ];
    return buyerViews.includes(view);
  }

  // 5. Auditor & Admin Routes
  if (normalized === UserRole.AUDITOR || normalized === UserRole.ADMIN) {
    const auditorViews = [
      "admin_dashboard",
      "auditor_queue",
      "verification_report",
      "marketplace",
      "credit_details",
      "transactions"
    ];
    return auditorViews.includes(view);
  }

  return false;
}
