"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { IconCheck, IconX, IconSettings, IconCreditCard, IconShield, IconBell, IconArrowLeft, IconChartBar } from "@tabler/icons-react";
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
}

type NavSection = "dashboard" | "settings";
type DashboardView = "usage" | "rate-limit";

export default function ManageAccount({ currentPlan = "Pro", profileName = "My Account" }: ManageAccountProps) {
  const router = useRouter();
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [activeSection, setActiveSection] = useState<NavSection>("dashboard");
  const [dashboardView, setDashboardView] = useState<DashboardView>("usage");
  const [expandDashboard, setExpandDashboard] = useState(false);
  const [accounts, setAccounts] = useState<Account[]>([
    {
      id: "1",
      name: profileName,
      email: "user@example.com",
      plan: currentPlan,
      createdAt: "2026-01-15",
    },
  ]);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newAccountName, setNewAccountName] = useState("");

  const handleEdit = (account: Account) => {
    setEditingId(account.id);
    setEditName(account.name);
  };

  const handleSaveEdit = (accountId: string) => {
    if (editName.trim()) {
      setAccounts(accounts.map(acc => 
        acc.id === accountId ? { ...acc, name: editName } : acc
      ));
      setEditingId(null);
      setEditName("");
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName("");
  };

  const handleAddAccount = () => {
    if (newAccountName.trim()) {
      const newAccount: Account = {
        id: String(Date.now()),
        name: newAccountName,
        email: `${newAccountName.toLowerCase().replace(/\s+/g, '.')}@nanosoft.com`,
        plan: "Free",
        createdAt: new Date().toISOString().split('T')[0],
      };
      setAccounts([...accounts, newAccount]);
      setNewAccountName("");
      setIsAddingNew(false);
    }
  };

  const handleDeleteAccount = (accountId: string) => {
    if (accounts.length > 1) {
      setAccounts(accounts.filter(acc => acc.id !== accountId));
    }
  };

  const navItems = [
    { id: "dashboard" as NavSection, label: "Dashboard", icon: IconChartBar },
    { id: "settings" as NavSection, label: "Settings", icon: IconSettings },
  ];

  const dashboardMenuItems = [
    { id: "usage" as DashboardView, label: "Usage" },
    { id: "rate-limit" as DashboardView, label: "Rate Limit" },
  ];

  return (
    <div style={{
      display: "flex",
      width: "100%",
      height: "100%",
      minHeight: 0,
      background: "var(--color-bg)",
      color: "var(--color-text)",
    }}>
      {/* Left Sidebar Navigation */}
      {!responsive.isMobile && (
        <div style={{
          width: responsive.isTablet ? "200px" : "240px",
          minWidth: responsive.isTablet ? "200px" : "240px",
          height: "100%",
          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
          overflowY: "auto",
          background: "linear-gradient(180deg, rgba(30, 30, 35, 0.6) 0%, rgba(20, 20, 25, 0.8) 100%)",
          padding: "24px 0",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}>
          {navItems.map(({ id, label, icon: Icon }) => (
            <div key={id}>
              <button
                onClick={() => {
                  setActiveSection(id);
                  if (id === "dashboard") {
                    setExpandDashboard(!expandDashboard);
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
                    ? "linear-gradient(135deg, var(--color-primary) 0%, rgba(var(--color-primary-rgb), 0.8) 100%)"
                    : "transparent",
                  color: activeSection === id ? "#ffffff" : "var(--color-text-muted)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
                  fontWeight: activeSection === id ? 600 : 500,
                  fontSize: "14px",
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  borderRadius: "10px",
                  boxShadow: activeSection === id ? "0 8px 24px rgba(var(--color-primary-rgb), 0.25)" : "none",
                }}
                onMouseEnter={(e) => {
                  if (activeSection !== id) {
                    const btn = e.currentTarget as HTMLElement;
                    btn.style.background = "rgba(var(--color-primary-rgb), 0.12)";
                    btn.style.color = "var(--color-primary)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeSection !== id) {
                    const btn = e.currentTarget as HTMLElement;
                    btn.style.background = "transparent";
                    btn.style.color = "var(--color-text-muted)";
                  }
                }}
              >
                <Icon size={20} strokeWidth={1.5} />
                <span>{label}</span>
              </button>

              {/* Dashboard Submenu */}
              {id === "dashboard" && activeSection === "dashboard" && expandDashboard && (
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
                      onClick={() => setDashboardView(item.id)}
                      style={{
                        padding: "10px 14px",
                        borderRadius: "8px",
                        background: dashboardView === item.id 
                          ? "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.2) 0%, rgba(var(--color-primary-rgb), 0.1) 100%)"
                          : "transparent",
                        border: dashboardView === item.id 
                          ? "1.5px solid var(--color-primary)"
                          : "1px solid transparent",
                        color: dashboardView === item.id ? "var(--color-primary)" : "rgba(255, 255, 255, 0.7)",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: dashboardView === item.id ? 600 : 500,
                        textAlign: "left",
                        transition: "all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
                        width: "100%",
                      }}
                      onMouseEnter={(e) => {
                        if (dashboardView !== item.id) {
                          const btn = e.currentTarget as HTMLElement;
                          btn.style.background = "rgba(var(--color-primary-rgb), 0.08)";
                          btn.style.color = "var(--color-primary)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (dashboardView !== item.id) {
                          const btn = e.currentTarget as HTMLElement;
                          btn.style.background = "transparent";
                          btn.style.color = "rgba(255, 255, 255, 0.7)";
                        }
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
          paddingTop: responsive.isMobile ? "20px" : responsive.isTablet ? "28px" : "36px",
          paddingRight: responsive.isMobile ? "16px" : responsive.isTablet ? "24px" : "32px",
          paddingBottom: responsive.isMobile ? "16px" : "20px",
          paddingLeft: responsive.isMobile ? "16px" : responsive.isTablet ? "24px" : "32px",
          boxSizing: "border-box",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          flexShrink: 0,
          background: "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.08) 0%, rgba(var(--color-primary-rgb), 0.02) 100%)",
        }}>
          <div style={{ maxWidth: "900px" }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginBottom: "12px",
            }}>
              {!responsive.isDesktop && (
                <button
                  onClick={() => router.back()}
                  style={{
                    background: "rgba(255, 255, 255, 0.1)",
                    border: "1px solid rgba(255, 255, 255, 0.2)",
                    borderRadius: "8px",
                    padding: "8px 8px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ffffff",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(255, 255, 255, 0.15)";
                    e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.3)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(255, 255, 255, 0.1)";
                    e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.2)";
                  }}
                  aria-label="Go back"
                >
                  <IconArrowLeft size={20} strokeWidth={2} />
                </button>
              )}
            </div>
            <h1 style={{
              fontSize: responsive.isMobile ? "24px" : responsive.isTablet ? "32px" : "40px",
              fontWeight: 700,
              color: "#ffffff",
              margin: 0,
              marginBottom: "12px",
              letterSpacing: "-0.5px",
              textShadow: "0 2px 8px rgba(0, 0, 0, 0.2)",
            }}>
              {activeSection === "dashboard" && dashboardView === "usage" && "Usage Statistics"}
              {activeSection === "dashboard" && dashboardView === "rate-limit" && "Rate Limit"}
              {activeSection === "settings" && "Account Settings"}
            </h1>
            <p style={{
              fontSize: responsive.isMobile ? "13px" : responsive.isTablet ? "14px" : "15px",
              color: "rgba(255, 255, 255, 0.6)",
              margin: 0,
              fontWeight: 400,
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
          WebkitOverflowScrolling: "touch",
          scrollBehavior: "smooth",
          padding: responsive.isMobile ? "20px 16px" : responsive.isTablet ? "28px 24px" : "32px 32px",
          boxSizing: "border-box",
        }}>
          {/* Dashboard Section */}
          {activeSection === "dashboard" && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: "20px",
              maxWidth: "900px",
            }}>
              {dashboardView === "usage" && (
                <Usage />
              )}

              {dashboardView === "rate-limit" && (
                <RateLimit />
              )}
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
              {/* Account Card */}
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.1) 0%, rgba(var(--color-primary-rgb), 0.05) 100%)",
                  border: "1.5px solid rgba(var(--color-primary-rgb), 0.3)",
                  borderRadius: "14px",
                  padding: responsive.isMobile ? "20px" : "28px",
                  transition: "all 0.3s ease",
                }}
              >
                <div style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "16px",
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      marginBottom: "16px",
                    }}>
                      <h2 style={{
                        fontSize: responsive.isMobile ? "20px" : "24px",
                        fontWeight: 700,
                        color: "#ffffff",
                        margin: 0,
                      }}>
                        {accounts[0]?.name || "My Account"}
                      </h2>
                      <span style={{
                        fontSize: "11px",
                        background: "var(--color-primary)",
                        color: "#ffffff",
                        padding: "6px 12px",
                        borderRadius: "6px",
                        fontWeight: 700,
                        boxShadow: "0 4px 12px rgba(var(--color-primary-rgb), 0.3)",
                        letterSpacing: "0.5px",
                      }}>
                        {accounts[0]?.plan || "Free"}
                      </span>
                    </div>
                    <div style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}>
                      <p style={{
                        fontSize: "14px",
                        color: "rgba(255, 255, 255, 0.8)",
                        margin: 0,
                      }}>
                        {accounts[0]?.email || "user@example.com"}
                      </p>
                      <p style={{
                        fontSize: "13px",
                        color: "rgba(255, 255, 255, 0.6)",
                        margin: 0,
                      }}>
                        Created on {accounts[0]?.createdAt || "2008-01-15"}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Account Info Grid */}
              <div style={{
                display: "grid",
                gridTemplateColumns: responsive.isMobile ? "1fr" : "repeat(2, 1fr)",
                gap: "16px",
              }}>
                <div style={{
                  background: "rgba(var(--color-primary-rgb), 0.08)",
                  border: "1px solid rgba(var(--color-primary-rgb), 0.2)",
                  borderRadius: "12px",
                  padding: "18px",
                }}>
                  <p style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.6)",
                    margin: 0,
                    marginBottom: "8px",
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}>
                    Email Address
                  </p>
                  <p style={{
                    fontSize: "14px",
                    color: "#ffffff",
                    margin: 0,
                    fontWeight: 600,
                  }}>
                    {accounts[0]?.email || "user@example.com"}
                  </p>
                </div>

                <div style={{
                  background: "rgba(var(--color-primary-rgb), 0.08)",
                  border: "1px solid rgba(var(--color-primary-rgb), 0.2)",
                  borderRadius: "12px",
                  padding: "18px",
                }}>
                  <p style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.6)",
                    margin: 0,
                    marginBottom: "8px",
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}>
                    Plan Type
                  </p>
                  <p style={{
                    fontSize: "14px",
                    color: "#ffffff",
                    margin: 0,
                    fontWeight: 600,
                  }}>
                    {accounts[0]?.plan || "Free"}
                  </p>
                </div>

                <div style={{
                  background: "rgba(var(--color-primary-rgb), 0.08)",
                  border: "1px solid rgba(var(--color-primary-rgb), 0.2)",
                  borderRadius: "12px",
                  padding: "18px",
                }}>
                  <p style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.6)",
                    margin: 0,
                    marginBottom: "8px",
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}>
                    Member Since
                  </p>
                  <p style={{
                    fontSize: "14px",
                    color: "#ffffff",
                    margin: 0,
                    fontWeight: 600,
                  }}>
                    {accounts[0]?.createdAt || "2008-01-15"}
                  </p>
                </div>

                <div style={{
                  background: "rgba(var(--color-primary-rgb), 0.08)",
                  border: "1px solid rgba(var(--color-primary-rgb), 0.2)",
                  borderRadius: "12px",
                  padding: "18px",
                }}>
                  <p style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.6)",
                    margin: 0,
                    marginBottom: "8px",
                    fontWeight: 500,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}>
                    Account ID
                  </p>
                  <p style={{
                    fontSize: "13px",
                    color: "#ffffff",
                    margin: 0,
                    fontFamily: "monospace",
                    fontWeight: 500,
                  }}>
                    {accounts[0]?.id || "—"}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Info */}
        <div style={{
          width: "100%",
          padding: responsive.isMobile ? "16px" : "20px",
          boxSizing: "border-box",
          borderTop: "1px solid rgba(255, 255, 255, 0.1)",
          flexShrink: 0,
          background: "linear-gradient(180deg, transparent 0%, rgba(var(--color-primary-rgb), 0.05) 100%)",
        }}>
          <p style={{
            fontSize: "12px",
            color: "rgba(255, 255, 255, 0.5)",
            margin: 0,
            textAlign: "center",
            lineHeight: "1.5",
          }}>
            You can manage up to 5 accounts on your plan. Each account operates independently with its own dedicated settings.
          </p>
        </div>
      </div>
    </div>
  );
}
