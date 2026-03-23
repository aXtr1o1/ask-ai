"use client";

import React, { useState, useEffect } from "react";
import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";

export default function RateLimit() {
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    setAnimated(true);
  }, []);

  const isDark = theme === "dark";
  const textColor = isDark ? "#ffffff" : "#0f172a";
  const textMuted = isDark ? "rgba(255,255,255,0.7)" : "rgba(15,23,42,0.8)";
  const textFaint = isDark ? "rgba(255,255,255,0.5)" : "rgba(15,23,42,0.6)";

  const styles = `
    @keyframes slideInUp {
      from {
        opacity: 0;
        transform: translateY(30px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes progressFill {
      from {
        width: 0;
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    @keyframes pulse-dot {
      0%, 100% { opacity: 0.8; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(1.2); }
    }

    @keyframes statusGlow {
      0%, 100% { box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 0 12px currentColor; }
      50% { box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 0 20px currentColor; }
    }
  `;

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return ((num / 1000000).toFixed(1)).replace(/\.0$/, "") + "M";
    }
    if (num >= 1000) {
      return ((num / 1000).toFixed(1)).replace(/\.0$/, "") + "K";
    }
    return num.toLocaleString();
  };

  const calculatePercentage = (used: number, limit: number) => {
    if (limit === 0) return 0;
    return Math.round((used / limit) * 100);
  };

  const rateLimitMetrics = [
    {
      id: "text-limit",
      label: "Text API Rate Limit",
      current: "1.2K",
      limit: "5K",
      unit: "requests/day",
      percentage: 25,
      color: "rgba(100, 150, 255, 0.3)",
      borderColor: "rgba(100, 150, 255, 0.5)",
      progressColor: "#6496ff",
    },
    {
      id: "text-tokens-limit",
      label: "Text Tokens Limit",
      current: "2.3M",
      limit: "10M",
      unit: "tokens/day",
      percentage: 23,
      color: "rgba(100, 200, 150, 0.3)",
      borderColor: "rgba(100, 200, 150, 0.5)",
      progressColor: "#64c896",
    },
    {
      id: "audio-limit",
      label: "Audio API Rate Limit",
      current: "342",
      limit: "1K",
      unit: "seconds/day",
      percentage: 34,
      color: "rgba(255, 150, 100, 0.3)",
      borderColor: "rgba(255, 150, 100, 0.5)",
      progressColor: "#ff9664",
    },
    {
      id: "credits-limit",
      label: "Credits Remaining",
      current: "344",
      limit: "500",
      unit: "credits",
      percentage: 31,
      color: "rgba(200, 100, 255, 0.3)",
      borderColor: "rgba(200, 100, 255, 0.5)",
      progressColor: "#c864ff",
    },
    {
      id: "graph-limit",
      label: "Graph Operations Limit",
      current: "42",
      limit: "100",
      unit: "operations/month",
      percentage: 42,
      color: "rgba(255, 200, 100, 0.3)",
      borderColor: "rgba(255, 200, 100, 0.5)",
      progressColor: "#ffc864",
    },
  ];

  // Determine status color and text based on usage percentage
  const getStatusInfo = (percentage: number) => {
    // Keep statuses readable, but aligned with the project's gold/black style.
    if (percentage >= 80)
      return { color: "#f87171", status: "Critical", bgColor: "rgba(248, 113, 113, 0.12)" };
    if (percentage >= 60)
      return { color: "#fbbf24", status: "Warning", bgColor: "rgba(251, 191, 36, 0.12)" };
    return { color: "#d4af37", status: "Healthy", bgColor: "rgba(212, 175, 55, 0.12)" };
  };

  return (
    <>
      <style>{styles}</style>
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "32px",
        background: "transparent",
        color: "var(--manageaccount-text)",
        border: `1px solid var(--manageaccount-border)`,
        minHeight: 0,
        width: "100%",
      }}>
        {/* Rate Limit Cards Grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: responsive.isDesktop ? "repeat(2, 1fr)" : "1fr",
          gap: "16px",
        }}>
          {rateLimitMetrics.map((metric, index) => {
            const status = getStatusInfo(metric.percentage);
            return (
            <div
              key={metric.id}
              style={{
                background: `linear-gradient(135deg, rgba(212, 175, 55, ${theme === "dark" ? 0.12 : 0.22}) 0%, rgba(255, 255, 255, 0.02) 100%)`,
                border: `1.5px solid rgba(212, 175, 55, ${theme === "dark" ? 0.35 : 0.30})`,
                borderRadius: "18px",
                padding: responsive.isMobile ? "18px" : "22px",
                transition: "all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)",
                cursor: "pointer",
                backdropFilter: "blur(10px)",
                boxShadow: `0 12px 44px rgba(0, 0, 0, ${theme === "dark" ? 0.34 : 0.18}), inset 0 1px 0 rgba(212, 175, 55, 0.18)`,
                animation: animated ? `slideInUp 0.6s ease-out ${index * 0.1}s both` : "none",
                position: "relative",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                const div = e.currentTarget as HTMLElement;
                div.style.transform = "translateY(-8px) scale(1.01)";
                div.style.boxShadow = `0 24px 56px rgba(212, 175, 55, 0.18), inset 0 1px 0 rgba(212, 175, 55, 0.35)`;
                div.style.borderColor = theme === "dark" ? "rgba(212, 175, 55, 0.55)" : "rgba(212, 175, 55, 0.45)";
              }}
              onMouseLeave={(e) => {
                const div = e.currentTarget as HTMLElement;
                div.style.transform = "translateY(0) scale(1)";
                div.style.boxShadow = `0 12px 44px rgba(0, 0, 0, ${theme === "dark" ? 0.34 : 0.18}), inset 0 1px 0 rgba(212, 175, 55, 0.18)`;
                div.style.borderColor = theme === "dark" ? "rgba(212, 175, 55, 0.35)" : "rgba(212, 175, 55, 0.30)";
              }}
            >
              {/* Animated Background Glow */}
              <div style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: `radial-gradient(circle at 20% 10%, rgba(212, 175, 55, 0.22) 0%, transparent 55%), radial-gradient(circle at center, ${metric.progressColor}12 0%, transparent 70%)`,
                opacity: 0,
                animation: `fadeIn 1.2s ease-out ${index * 0.15}s forwards`,
                pointerEvents: "none",
              }} />

              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "24px",
                position: "relative",
                zIndex: 1,
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "16px",
                  }}>
                    <p style={{
                      fontSize: "12px",
                      color: textMuted,
                      margin: 0,
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.7px",
                      animation: `fadeIn 0.8s ease-out ${index * 0.1}s backward`,
                    }}>
                      {metric.label}
                    </p>
                    <div style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "50%",
                      background: metric.progressColor,
                      opacity: 0.8,
                      boxShadow: `0 0 12px ${metric.progressColor}`,
                      animation: `pulse-dot 2.5s ease-in-out infinite`,
                    }} />
                  </div>
                  <div style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: "10px",
                    marginBottom: "8px",
                  }}>
                    <p style={{
                      fontSize: "36px",
                      fontWeight: 800,
                      color: isDark ? "transparent" : "#0f172a",
                      margin: 0,
                      letterSpacing: "-0.5px",
                      background: isDark ? `linear-gradient(135deg, ${metric.progressColor}, #ffffff)` : "none",
                      backgroundClip: isDark ? "text" : "unset",
                      WebkitBackgroundClip: isDark ? "text" : "unset",
                      WebkitTextFillColor: isDark ? "transparent" : "initial",
                      animation: `fadeIn 1s ease-out ${index * 0.15}s both`,
                    }}>
                      {metric.current}
                    </p>
                    <p style={{
                      fontSize: "12px",
                      color: textFaint,
                      margin: 0,
                      fontWeight: 500,
                    }}>
                      / {metric.limit}
                    </p>
                  </div>
                  <p style={{
                    fontSize: "11px",
                    color: textFaint,
                    margin: 0,
                    fontWeight: 500,
                  }}>
                    {metric.unit}
                  </p>
                </div>
                <div style={{
                  background: status.bgColor,
                  border: `1.5px solid ${status.color}`,
                  borderRadius: "12px",
                  padding: "8px 14px",
                  marginLeft: "16px",
                  backdropFilter: "blur(8px)",
                  boxShadow: `inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 0 16px ${status.color}20`,
                  animation: `fadeIn 1.1s ease-out ${index * 0.15}s both`,
                }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                  }}>
                    <div style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: status.color,
                      boxShadow: `0 0 8px ${status.color}`,
                      animation: `pulse-dot 2.5s ease-in-out infinite`,
                    }} />
                    <p style={{
                      color: status.color,
                      margin: 0,
                      fontSize: "10px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.3px",
                    }}>
                      {status.status}
                    </p>
                  </div>
                </div>
              </div>

              {/* Progress Bar Container */}
              <div style={{
                display: "flex",
                flexDirection: "column",
                gap: "12px",
                marginTop: "28px",
                paddingTop: "24px",
                borderTop: `1.5px solid rgba(212, 175, 55, ${theme === "dark" ? 0.22 : 0.20})`,
                position: "relative",
                zIndex: 1,
              }}>
                {/* Enhanced Progress Bar */}
                <div style={{
                  width: "100%",
                  height: "18px",
                  background: "rgba(255, 255, 255, 0.06)",
                  borderRadius: "10px",
                  overflow: "hidden",
                  border: `1px solid rgba(212, 175, 55, ${theme === "dark" ? 0.25 : 0.20})`,
                  position: "relative",
                }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${metric.percentage}%`,
                      background: `linear-gradient(90deg, ${metric.progressColor}, ${metric.progressColor}dd)`,
                      borderRadius: "8px",
                      transition: "width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)",
                      boxShadow: `0 0 16px ${metric.progressColor}90, inset 0 1px 0 rgba(255, 255, 255, 0.4)`,
                      position: "relative",
                      animation: animated ? `progressFill 1.2s cubic-bezier(0.34, 1.56, 0.64, 1) ${index * 0.1}s both` : "none",
                    }}
                  />
                </div>
                
                {/* Usage Stats */}
                <div style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}>
                  <p style={{
                    fontSize: "12px",
                    color: textFaint,
                    margin: 0,
                    fontWeight: 500,
                  }}>
                    Usage
                  </p>
                  <p style={{
                    fontSize: "14px",
                    color: status.color,
                    margin: 0,
                    fontWeight: 700,
                    letterSpacing: "0.3px",
                    animation: `fadeIn 1.2s ease-out ${index * 0.15}s both`,
                  }}>
                    {metric.percentage}%
                  </p>
                </div>
              </div>
            </div>
            );
          })}
        </div>
      </div>
    </>
  );
}