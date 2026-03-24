"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { IconX, IconSettings, IconArrowLeft, IconChartBar } from "@tabler/icons-react";
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
}

type NavSection = "dashboard" | "settings";
type DashboardView = "usage" | "rate-limit";

export default function ManageAccount({
  currentPlan = "Pro",
  profileName = "My Account",
  subUserName, // ← NEW prop received
  externalUserId,           
}: ManageAccountProps) {
  const router = useRouter();
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [activeSection, setActiveSection] = useState<NavSection>("dashboard");
  const [dashboardView, setDashboardView] = useState<DashboardView>("usage");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  const [accounts] = useState<Account[]>([
    {
      id: "1",
      name: profileName,
      email: "user@example.com",
      plan: currentPlan,
      createdAt: "2026-01-15",
    },
  ]);

  const handleBackToDashboard = () => {
    if (responsive.isMobile || responsive.isTablet) {
      setShowMobileSidebar(!showMobileSidebar);
    } else {
      router.back();
    }
  };

  const navItems = [
    { id: "dashboard" as NavSection, label: "Dashboard", icon: IconChartBar },
    { id: "settings"  as NavSection, label: "Settings",  icon: IconSettings  },
  ];

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
          onClick={() => setShowMobileSidebar(false)}
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
          background: "var(--sidebar-bg)",
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
        }}>
          {/* Mobile Close Button */}
          {responsive.isMobile && (
            <div style={{
              display: "flex",
              justifyContent: "flex-end",
              paddingRight: "16px",
              paddingBottom: "8px",
              borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            }}>
              <button
                onClick={() => setShowMobileSidebar(false)}
                style={{
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  borderRadius: "8px",
                  padding: "8px",
                  cursor: "pointer",
                  color: "#ffffff",
                }}
              >
                <IconX size={20} strokeWidth={2} />
              </button>
            </div>
          )}

          {navItems.map(({ id, label, icon: Icon }) => (
            <div key={id}>
              <button
                onClick={() => {
                  setActiveSection(id);
                  if (responsive.isMobile && id === "settings") {
                    setShowMobileSidebar(false);
                  }
                }}
                style={{
                  width: "calc(100% - 16px)",
                  marginLeft: "8px",
                  padding: "12px 16px",
                  border: activeSection === id
                    ? "1.5px solid var(--color-primary)"
                    : "1px solid transparent",
                  background: activeSection === id
                    ? "linear-gradient(135deg, var(--color-primary) 0%, rgba(var(--color-primary-rgb), 0.25) 100%)"
                    : "transparent",
                  color: activeSection === id
                    ? "var(--color-primary-strong)"
                    : "var(--color-text)",
                  cursor: "pointer",
                  textAlign: "left",
                  fontWeight: activeSection === id ? 600 : 500,
                  fontSize: "14px",
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  borderRadius: "10px",
                  transition: "all 0.3s ease",
                }}
              >
                <Icon size={20} strokeWidth={1.5} />
                <span>{label}</span>
              </button>

              {/* Dashboard Submenu */}
              {id === "dashboard" && (
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  marginTop: "8px",
                  paddingLeft: "8px",
                  borderLeft: "2px solid rgba(var(--color-primary-rgb), 0.3)",
                  marginLeft: "16px",
                  paddingTop: "8px",
                }}>
                  {dashboardMenuItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setActiveSection("dashboard");
                        setDashboardView(item.id);
                        if (responsive.isMobile) setShowMobileSidebar(false);
                      }}
                      style={{
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: dashboardView === item.id
                          ? "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.2) 0%, rgba(var(--color-primary-rgb), 0.1) 100%)"
                          : "transparent",
                        border: dashboardView === item.id
                          ? "1.5px solid var(--color-primary)"
                          : "1px solid transparent",
                        color: dashboardView === item.id
                          ? "var(--color-primary)"
                          : "var(--color-text)",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: dashboardView === item.id ? 700 : 500,
                        textAlign: "left",
                        width: "100%",
                        transition: "all 0.3s ease",
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
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
                  background: "rgba(255, 255, 255, 0.1)",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  borderRadius: "8px",
                  padding: "8px",
                  cursor: "pointer",
                  color: "#ffffff",
                  marginBottom: "12px",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                <IconArrowLeft size={20} strokeWidth={2} />
              </button>
            )}
            <h1 style={{
              fontSize: responsive.isMobile ? "24px" : "40px",
              fontWeight: 700,
              color: "#ffffff",
              margin: 0,
              marginBottom: "12px",
            }}>
              {activeSection === "dashboard" && dashboardView === "usage"      && "Usage Statistics"}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "Rate Limit"}
              {activeSection === "settings"                                    && "Account Settings"}
            </h1>
            <p style={{
              fontSize: responsive.isMobile ? "13px" : "15px",
              color: "rgba(255, 255, 255, 0.6)",
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
                  color: "#ffffff",
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
                <p style={{ fontSize: "14px", color: "rgba(255,255,255,0.8)", margin: 0 }}>
                  {accounts[0]?.email}
                </p>
                <p style={{ fontSize: "13px", color: "rgba(255,255,255,0.6)", margin: "8px 0 0" }}>
                  Created on {accounts[0]?.createdAt}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}