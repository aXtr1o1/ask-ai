"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { IconMenu2 } from "@tabler/icons-react";
import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";
import Usage from "./usage";
import RateLimit from "./rate-limit";

interface Account {
  id: string;
  name: string;
  email: string;
  plan: string;
  createdAt: string;
}

interface ManageAccountProps {
  currentPlan?: string;
  profileName?: string;
  subUserName?: string;
  externalUserId?: string;
  email?: string;
  // When the mobile sidebar (inside ManageAccount) is opened/closed,
  // inform the parent so it can hide unrelated UI (e.g. the overlay close X).
  onMobileSidebarOpenChange?: (open: boolean) => void;
}

type NavSection = "dashboard" | "settings";
type DashboardView = "usage" | "rate-limit";

export default function ManageAccount({
  currentPlan = "Pro",
  profileName = "My Account",
  subUserName, // ← NEW prop received
  externalUserId,
  email,
  onMobileSidebarOpenChange,
}: ManageAccountProps) {
  const router = useRouter();
  const responsive = useResponsive();
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const headerColor = "var(--color-text)";
  const subheaderColor = "var(--color-text-muted)";
  const sidebarText = "var(--sidebar-text)";
  const sidebarTextMuted = "var(--color-text-muted)";
  const sidebarTextActive = "var(--color-text)";
  const bodyText = "var(--color-text)";
  const bodyTextMuted = "var(--color-text-muted)";
  const [activeSection, setActiveSection] = useState<NavSection>("dashboard");
  const [dashboardView, setDashboardView] = useState<DashboardView>("usage");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  const setMobileSidebarOpen = (open: boolean) => {
    setShowMobileSidebar(open);
    onMobileSidebarOpenChange?.(open);
  };

  const [accounts] = useState<Account[]>([
    {
      id: "1",
      name: profileName,
      email: "v4demo@example.com",
      plan: currentPlan,
      createdAt: "2026-01-15",
    },
  ]);

  const handleBackToDashboard = () => {
    if (responsive.isMobile || responsive.isTablet) {
      setMobileSidebarOpen(true);
    } else {
      router.back();
    }
  };

  const dashboardMenuItems = [
    { id: "usage" as DashboardView, label: "Usage" },
    { id: "rate-limit" as DashboardView, label: "Rate Limit" },
  ];

  // ── The actual username to query user_profile
  // prefer subUserName prop, fall back to profileName
  const queryUserName = subUserName || profileName;
  const queryExternalUser = externalUserId || profileName;  // ← ADD

  return (
    <div style={{
      display: "flex",
      width: "100%",
      height: "100%",
      minHeight: 0,
      background: "var(--color-bg)",
      color: "var(--color-text)",
    }}>
      {/* Mobile Backdrop */}
      {responsive.isMobile && showMobileSidebar && (
        <div
          onClick={() => setMobileSidebarOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.6)",
            backdropFilter: "blur(8px)",
            zIndex: 999,
          }}
        />
      )}

      {/* Left Sidebar Navigation */}
      {(!responsive.isMobile || showMobileSidebar) && (
        <div style={{
          width: responsive.isTablet ? "200px" : "240px",
          minWidth: responsive.isTablet ? "200px" : "240px",
          height: "100%",
          background: isDark ? "rgba(0, 0, 0, 0.72)" : "var(--sidebar-bg)",
          color: "var(--color-text)",
          borderRight: "1px solid var(--sidebar-border)",
          overflowY: "auto",
          padding: "24px 0",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          position: responsive.isMobile ? "fixed" : "relative",
          left: responsive.isMobile ? 0 : "auto",
          top: responsive.isMobile ? 0 : "auto",
          zIndex: responsive.isMobile ? 1000 : "auto",
          ...(isDark
            ? {
              backdropFilter: "blur(14px)",
              WebkitBackdropFilter: "blur(14px)",
            }
            : null),
        }}>
          <div style={{ padding: "0 16px 8px" }}>
            <div
              style={{
                fontSize: 20,
                fontWeight: 900,
                letterSpacing: 0.8,
                textTransform: "uppercase",
                color: "var(--color-primary)",
                padding: "10px 12px",
                borderRadius: 10,
                border: "1.5px solid rgba(var(--color-primary-rgb), 0.7)",
                background:
                  "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.28) 0%, rgba(var(--color-primary-rgb), 0.10) 100%)",
                display: "inline-flex",
                alignItems: "center",
                boxShadow: "0 0 0 1px rgba(0,0,0,0.25), 0 10px 24px rgba(0,0,0,0.35)",
              }}
            >
              Dashboard
            </div>
          </div>

          <div style={{ padding: "0 16px", display: "flex", flexDirection: "column", gap: 10 }}>
            {dashboardMenuItems.map((item) => {
              const isActive =
                activeSection === "dashboard" && dashboardView === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveSection("dashboard");
                    setDashboardView(item.id);
                    if (responsive.isMobile) setMobileSidebarOpen(false);
                  }}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "8px",
                    background: isActive
                      ? "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.2) 0%, rgba(var(--color-primary-rgb), 0.1) 100%)"
                      : "transparent",
                    border: isActive
                      ? "1.5px solid var(--color-primary)"
                      : "1px solid transparent",
                    color: isActive ? "var(--color-primary)" : "var(--color-text)",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: isActive ? 700 : 500,
                    textAlign: "left",
                    width: "100%",
                    transition: "all 0.3s ease",
                  }}
                >
                  {item.label}
                </button>
              );
            })}

            <button
              type="button"
              onClick={() => {
                setActiveSection("settings");
                if (responsive.isMobile) setMobileSidebarOpen(false);
              }}
              style={{
                padding: "10px 12px",
                borderRadius: "8px",
                background: activeSection === "settings"
                  ? "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.2) 0%, rgba(var(--color-primary-rgb), 0.1) 100%)"
                  : "transparent",
                border: activeSection === "settings"
                  ? "1.5px solid var(--color-primary)"
                  : "1px solid transparent",
                color: activeSection === "settings" ? "var(--color-primary)" : "var(--color-text)",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: activeSection === "settings" ? 700 : 500,
                textAlign: "left",
                width: "100%",
                transition: "all 0.3s ease",
              }}
            >
              Settings
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        width: "100%",
        minHeight: 0,
      }}>
        {/* Header */}
        <div style={{
          width: "100%",
          paddingTop: responsive.isMobile ? "20px" : "36px",
          paddingRight: responsive.isMobile ? "16px" : "32px",
          paddingBottom: responsive.isMobile ? "16px" : "20px",
          paddingLeft: responsive.isMobile ? "16px" : "32px",
          boxSizing: "border-box",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          flexShrink: 0,
          background: "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.08) 0%, rgba(var(--color-primary-rgb), 0.02) 100%)",
        }}>
          <div style={{ maxWidth: "900px" }}>
            {!responsive.isDesktop && (
              <button
                onClick={handleBackToDashboard}
                style={{
                  background: "rgba(255, 255, 255, 0.08)",
                  border: "1px solid rgba(0,0,0,0.06)",
                  borderRadius: "8px",
                  padding: "8px",
                  cursor: "pointer",
                  color: headerColor,
                  marginBottom: "12px",
                  display: "flex",
                  alignItems: "center",
                }}
                aria-label="Open menu"
              >
                <IconMenu2 size={20} strokeWidth={2} />
              </button>
            )}
            <h1 style={{
              fontSize: responsive.isMobile ? "24px" : "40px",
              fontWeight: 700,
              color: headerColor,
              margin: 0,
              marginBottom: "12px",
            }}>
              {activeSection === "dashboard" && dashboardView === "usage" && "Usage Statistics"}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "Rate Limit"}
              {activeSection === "settings" && "Account Settings"}
            </h1>
            <p style={{
              fontSize: responsive.isMobile ? "13px" : "15px",
              color: subheaderColor,
              margin: 0,
            }}>
              {activeSection === "dashboard" && dashboardView === "usage" && "Monitor your API usage, request counts, and resource consumption over time."}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "View your current rate limits and adjust them based on your subscription plan."}
              {activeSection === "settings" && "Update your account preferences and settings"}
            </p>
          </div>
        </div>

        {/* Content - Scrollable */}
        <div style={{
          flex: 1,
          minHeight: 0,
          overflowY: "scroll",
          overflowX: "hidden",
          padding: responsive.isMobile ? "20px 16px" : "32px 32px",
          boxSizing: "border-box",
        }}>
          {/* Dashboard Section */}
          {activeSection === "dashboard" && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: "20px",
              maxWidth: responsive.isDesktop ? "1400px" : "100%",
            }}>
              {/* ── Pass queryUserName to both Usage and RateLimit ── */}
              {dashboardView === "usage" && <Usage externalUserId={queryExternalUser} subUserName={queryUserName} />}
              {dashboardView === "rate-limit" && <RateLimit externalUserId={queryExternalUser} subUserName={queryUserName} />}
            </div>
          )}

          {/* Settings Section */}
          {activeSection === "settings" && (
            <div style={{
              background: isDark ? "rgba(255,255,255,0.05)" : "#ffffff",
              color: isDark ? "#ffffff" : "#222222",
              borderRadius: "16px",
              padding: responsive.isMobile ? "20px" : "32px",
              boxShadow: isDark ? "none" : "0 4px 20px rgba(0,0,0,0.05)",
              display: "flex",
              flexDirection: "column",
              gap: "24px",
              maxWidth: "700px",
              border: isDark ? "1px solid rgba(255,255,255,0.1)" : "1px solid #e0e0e0",
            }}>
              <h2 style={{ fontSize: "20px", fontWeight: 700, color: isDark ? "#ffffff" : "#222222", margin: 0 }}>Personal Information</h2>

              {/* Gender
              <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", cursor: "pointer", color: isDark ? "#ccc" : "#222" }}>
                  <input type="radio" name="gender" defaultChecked style={{ accentColor: "var(--color-primary)" }} /> Male
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", cursor: "pointer", color: isDark ? "#ccc" : "#222" }}>
                  <input type="radio" name="gender" style={{ accentColor: "var(--color-primary)" }} /> Female
                </label>
              </div> */}

              {/* Name */}
              <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 200px" }}>
                  <label style={{ display: "block", fontSize: "12px", color: isDark ? "#aaa" : "#666", marginBottom: "6px" }}>First Name</label>
                  <input type="text" value={subUserName || ""} readOnly style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #e0e0e0", background: isDark ? "rgba(255,255,255,0.05)" : "#f9f9f9", color: isDark ? "#ffffff" : "#222" }} />
                </div>
                <div style={{ flex: "1 1 200px" }}>
                  <label style={{ display: "block", fontSize: "12px", color: isDark ? "#aaa" : "#666", marginBottom: "6px" }}>Last Name</label>
                  <input type="text" value={profileName || ""} readOnly style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #e0e0e0", background: isDark ? "rgba(255,255,255,0.05)" : "#f9f9f9", color: isDark ? "#ffffff" : "#222" }} />
                </div>
              </div>

              {/* Email */}
              <div>
                <label style={{ display: "block", fontSize: "12px", color: isDark ? "#aaa" : "#666", marginBottom: "6px" }}>Email</label>
                <div style={{ position: "relative" }}>
                  <input type="email" value={email || accounts[0]?.email || "rolandDonald@mail.com"} readOnly style={{ width: "100%", padding: "10px 12px", paddingRight: "80px", borderRadius: "8px", border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #e0e0e0", background: isDark ? "rgba(255,255,255,0.05)" : "#f9f9f9", color: isDark ? "#ffffff" : "#222" }} />
                  {email && (
                    <span style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", fontSize: "12px", color: "#00b074", fontWeight: 700 }}>✓ Verified</span>
                  )}
                </div>
              </div>

              {/* User ID */}
              <div>
                <label style={{ display: "block", fontSize: "12px", color: isDark ? "#aaa" : "#666", marginBottom: "6px" }}>User ID</label>
                <input type="text" value={externalUserId || ""} readOnly style={{ width: "100%", padding: "10px 12px", borderRadius: "8px", border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #e0e0e0", background: isDark ? "rgba(255,255,255,0.05)" : "#f9f9f9", color: isDark ? "#ffffff" : "#222" }} />
              </div>

              {/* current Pack */}
              <div>
                <label style={{ display: "block", fontSize: "12px", color: isDark ? "#aaa" : "#666", marginBottom: "12px" }}>Current Pack</label>
                <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                  {["Free", "Pro", "Max"].map((plan) => {
                    const isActive = currentPlan === plan || (plan === "Pro" && !currentPlan);
                    return (
                      <div key={plan} style={{
                        flex: "1 1 150px",
                        padding: "16px",
                        borderRadius: "12px",
                        border: isActive ? `2px solid var(--color-primary)` : (isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #e0e0e0"),
                        background: isActive ? (isDark ? "rgba(var(--color-primary-rgb), 0.2)" : "rgba(var(--color-primary-rgb), 0.05)") : (isDark ? "rgba(255,255,255,0.05)" : "#f9f9f9"),
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                        position: "relative"
                      }}>
                        {isActive && (
                          <span style={{ position: "absolute", top: "12px", right: "12px", color: "var(--color-primary)", fontSize: "12px", fontWeight: 700 }}>✓ Active</span>
                        )}
                        <h3 style={{ fontSize: "16px", fontWeight: 700, color: isDark ? "#ffffff" : "#222222", margin: 0 }}>{plan}</h3>
                        <p style={{ fontSize: "12px", color: isDark ? "#aaa" : "#666", margin: 0 }}>{plan === "Free" ? "Basic features" : plan === "Pro" ? "Advanced tools" : "Enterprise power"}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
