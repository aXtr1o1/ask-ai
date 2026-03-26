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
    { id: "usage"      as DashboardView, label: "Usage"      },
    { id: "rate-limit" as DashboardView, label: "Rate Limit" },
  ];

  // ── The actual username to query user_profile
  // prefer subUserName prop, fall back to profileName
const queryUserName     = subUserName || profileName;
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
                fontSize: 20  ,
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
              {activeSection === "dashboard" && dashboardView === "usage"      && "Usage Statistics"}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "Rate Limit"}
              {activeSection === "settings"                                    && "Account Settings"}
            </h1>
            <p style={{
              fontSize: responsive.isMobile ? "13px" : "15px",
              color: subheaderColor,
              margin: 0,
            }}>
              {activeSection === "dashboard" && dashboardView === "usage"      && "Monitor your API usage, request counts, and resource consumption over time."}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "View your current rate limits and adjust them based on your subscription plan."}
              {activeSection === "settings"                                    && "Update your account preferences and settings"}
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
              {dashboardView === "usage"      && <Usage      externalUserId={queryExternalUser} subUserName={queryUserName} />}
              {dashboardView === "rate-limit" && <RateLimit  externalUserId={queryExternalUser} subUserName={queryUserName} />}
            </div>
          )}

          {/* Settings Section */}
          {activeSection === "settings" && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: "24px",
              maxWidth: "700px",
            }}>
              <div style={{
                background: "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.1) 0%, rgba(var(--color-primary-rgb), 0.05) 100%)",
                border: "1.5px solid rgba(var(--color-primary-rgb), 0.3)",
                borderRadius: "14px",
                padding: responsive.isMobile ? "20px" : "28px",
              }}>
                <h2 style={{
                  fontSize: responsive.isMobile ? "20px" : "24px",
                  fontWeight: 700,
                  color: headerColor,
                  margin: 0,
                  marginBottom: "16px",
                }}>
                  {accounts[0]?.name || "My Account"}
                  <span style={{
                    fontSize: "11px",
                    background: "var(--color-primary)",
                    color: "#ffffff",
                    padding: "6px 12px",
                    borderRadius: "6px",
                    fontWeight: 700,
                    marginLeft: "12px",
                  }}>
                    {accounts[0]?.plan || "Free"}
                  </span>
                </h2>
                <p style={{ fontSize: "14px", color: bodyTextMuted, margin: 0 }}>
                  {accounts[0]?.email}
                </p>
                <p style={{ fontSize: "13px", color: bodyTextMuted, margin: "8px 0 0" }}>
                  Created on {accounts[0]?.createdAt}
                </p>
              </div>

              {/* Additional settings details */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 18,
                  // Align details with the content inside the top card
                  paddingLeft: responsive.isMobile ? "20px" : "28px",
                  paddingRight: responsive.isMobile ? "20px" : "28px",
                }}
              >
                {[
                  { label: "EMAIL ADDRESS", value: accounts[0]?.email ?? "-" },
                  { label: "PLAN TYPE", value: accounts[0]?.plan ?? "-" },
                  { label: "MEMBER SINCE", value: accounts[0]?.createdAt ?? "-" },
                  { label: "ACCOUNT ID", value: accounts[0]?.id ?? "-" },
                ].map((row) => (
                  <div key={row.label} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: 0.6, color: bodyTextMuted }}>
                      {row.label}
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: bodyText }}>
                      {row.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}