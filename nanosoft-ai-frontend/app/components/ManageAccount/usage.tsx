"use client";

import React, { useState, useEffect } from "react";
import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function Usage() {
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    setAnimated(true);
  }, []);

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

    @keyframes glow {
      0%, 100% {
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 currentColor;
      }
      50% {
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6), inset 0 1px 0 currentColor;
      }
    }

    @keyframes shimmer {
      0% {
        background-position: -1000px 0;
      }
      100% {
        background-position: 1000px 0;
      }
    }

    @keyframes pulse-dot {
      0%, 100% { opacity: 0.8; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(1.2); }
    }

    @keyframes float-up {
      0% {
        transform: translateY(0px);
        opacity: 0;
      }
      50% {
        opacity: 1;
      }
      100% {
        transform: translateY(-20px);
        opacity: 0;
      }
    }
  `;

  // Chart data for metrics
  const textRequestsData = [
    { date: "Day 1", value: 249 },
    { date: "Day 2", value: 498 },
    { date: "Day 3", value: 872 },
    { date: "Day 4", value: 1245 },
  ];

  const textUsageData = [
    { date: "Day 1", value: 575000 },
    { date: "Day 2", value: 1150000 },
    { date: "Day 3", value: 1725000 },
    { date: "Day 4", value: 2300000 },
  ];

  const audioRequestsData = [
    { date: "Day 1", value: 31 },
    { date: "Day 2", value: 62 },
    { date: "Day 3", value: 109 },
    { date: "Day 4", value: 156 },
  ];

  const audioUsageData = [
    { date: "Day 1", value: 39 },
    { date: "Day 2", value: 78 },
    { date: "Day 3", value: 117 },
    { date: "Day 4", value: 156 },
  ];

  const graphOperationsData = [
    { date: "Day 1", value: 8 },
    { date: "Day 2", value: 16 },
    { date: "Day 3", value: 28 },
    { date: "Day 4", value: 42 },
  ];

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

  const usageMetrics = [
    {
      id: "text-requests",
      label: "Text API Requests",
      value: "1.2K",
      unit: "requests",
      subtext: "This month",
      color: "rgba(100, 150, 255, 0.3)",
      borderColor: "rgba(100, 150, 255, 0.5)",
      chartColor: "#6496ff",
      data: textRequestsData,
    },
    {
      id: "text-usage",
      label: "Text Usage",
      value: "2.3M",
      unit: "tokens",
      subtext: "65% of limit",
      color: "rgba(100, 200, 150, 0.3)",
      borderColor: "rgba(100, 200, 150, 0.5)",
      chartColor: "#64c896",
      data: textUsageData,
    },
    {
      id: "audio-requests",
      label: "Audio API Requests",
      value: "342",
      unit: "requests",
      subtext: "This month",
      color: "rgba(255, 150, 100, 0.3)",
      borderColor: "rgba(255, 150, 100, 0.5)",
      chartColor: "#ff9664",
      data: audioRequestsData,
    },
    {
      id: "audio-usage",
      label: "Audio Usage",
      value: "156",
      unit: "minutes",
      subtext: "42% of limit",
      color: "rgba(200, 100, 255, 0.3)",
      borderColor: "rgba(200, 100, 255, 0.5)",
      chartColor: "#c864ff",
      data: audioUsageData,
    },
    {
      id: "graph-operations",
      label: "Graph Operations",
      value: "42",
      unit: "operations",
      subtext: "This month",
      color: "rgba(255, 200, 100, 0.3)",
      borderColor: "rgba(255, 200, 100, 0.5)",
      chartColor: "#ffc864",
      data: graphOperationsData,
    },
  ];

  return (
    <>
      <style>{styles}</style>
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "32px",
        background: "var(--manageaccount-bg)",
        color: "var(--manageaccount-text)",
        border: `1px solid var(--manageaccount-border)`,
        minHeight: "100vh",
        width: "100%",
      }}>
        {/* Usage Metrics Grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr",
          gap: "16px",
        }}>
          {usageMetrics.map((metric, index) => (
            <div
              key={metric.id}
              style={{
                background: `linear-gradient(135deg, ${metric.color} 0%, rgba(255, 255, 255, 0.01) 100%)`,
                border: `1.5px solid ${metric.borderColor}`,
                borderRadius: "18px",
                padding: "28px",
                transition: "all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)",
                cursor: "pointer",
                backdropFilter: "blur(10px)",
                boxShadow: `0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 ${metric.borderColor}`,
                animation: animated ? `slideInUp 0.6s ease-out ${index * 0.1}s both` : "none",
                position: "relative",
                overflow: "hidden",
              }}
              onMouseEnter={(e) => {
                const div = e.currentTarget as HTMLElement;
                div.style.transform = "translateY(-8px) scale(1.01)";
                div.style.boxShadow = `0 24px 56px ${metric.chartColor}30, inset 0 1px 0 ${metric.borderColor}`;
                div.style.borderColor = metric.borderColor.replace('0.5', '0.9');
              }}
              onMouseLeave={(e) => {
                const div = e.currentTarget as HTMLElement;
                div.style.transform = "translateY(0) scale(1)";
                div.style.boxShadow = `0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 ${metric.borderColor}`;
                div.style.borderColor = metric.borderColor;
              }}
            >
              {/* Animated Background Glow */}
              <div style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: `radial-gradient(circle at center, ${metric.chartColor}10 0%, transparent 70%)`,
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
                      color: "rgba(255, 255, 255, 0.6)",
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
                      background: metric.chartColor,
                      opacity: 0.8,
                      boxShadow: `0 0 12px ${metric.chartColor}`,
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
                      fontSize: "42px",
                      fontWeight: 800,
                      color: "#ffffff",
                      margin: 0,
                      letterSpacing: "-0.5px",
                      background: `linear-gradient(135deg, ${metric.chartColor}, #ffffff)`,
                      backgroundClip: "text",
                      WebkitBackgroundClip: "text",
                      WebkitTextFillColor: "transparent",
                      animation: `fadeIn 1s ease-out ${index * 0.15}s both`,
                    }}>
                      {metric.value}
                    </p>
                    <p style={{
                      fontSize: "14px",
                      color: metric.borderColor,
                      margin: 0,
                      fontWeight: 700,
                      opacity: 0.8,
                    }}>
                      {metric.unit}
                    </p>
                  </div>
                  <p style={{
                    fontSize: "12px",
                    color: "rgba(255, 255, 255, 0.5)",
                    margin: 0,
                    fontWeight: 500,
                  }}>
                    {metric.subtext}
                  </p>
                </div>
                <div style={{
                  background: metric.borderColor.replace('0.5', '0.15'),
                  border: `1.5px solid ${metric.borderColor}`,
                  borderRadius: "14px",
                  padding: "10px 14px",
                  marginLeft: "16px",
                  backdropFilter: "blur(8px)",
                  boxShadow: `inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 0 16px ${metric.chartColor}20`,
                  transition: "all 0.3s ease",
                  animation: `fadeIn 1.1s ease-out ${index * 0.15}s both`,
                }}>
                  <p style={{
                    color: metric.chartColor,
                    margin: 0,
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.4px",
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                  }}>
                    <span style={{
                      display: "inline-block",
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: metric.chartColor,
                      boxShadow: `0 0 8px ${metric.chartColor}`,
                    }} />
                    Active
                  </p>
                </div>
              </div>

            {/* Chart */}
            <div style={{
              marginTop: "28px",
              marginLeft: "-28px",
              marginRight: "-80px",
              marginBottom: "-28px",
              borderTop: `1.5px solid ${metric.borderColor.replace('0.5', '0.2')}`,
              paddingTop: "24px",
              paddingLeft: "28px",
              paddingRight: "10px",
              paddingBottom: "0",
              background: `linear-gradient(180deg, rgba(0,0,0,0) 0%, ${metric.color.replace('0.3', '0.1')} 100%)`,
            }}>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={metric.data}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke={theme === "dark" ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)"}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="date"
                    tick={{
                      fontSize: 11,
                      fill: theme === "dark" ? "rgba(255, 255, 255, 0.5)" : "rgba(0, 0, 0, 0.5)",
                    }}
                    axisLine={{
                      stroke: theme === "dark" ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)",
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 11,
                      fill: theme === "dark" ? "rgba(255, 255, 255, 0.5)" : "rgba(0, 0, 0, 0.5)",
                    }}
                    axisLine={{
                      stroke: theme === "dark" ? "rgba(255, 255, 255, 0.1)" : "rgba(0, 0, 0, 0.1)",
                    }}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: theme === "dark" ? "rgba(20, 20, 25, 0.95)" : "rgba(240, 240, 245, 0.95)",
                      border: `1px solid ${metric.borderColor}`,
                      borderRadius: "8px",
                      color: theme === "dark" ? "#ffffff" : "#000000",
                    }}
                    cursor={{
                      stroke: metric.chartColor,
                      strokeOpacity: 0.3,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={metric.chartColor}
                    strokeWidth={2.5}
                    dot={{
                      fill: metric.chartColor,
                      r: 4,
                    }}
                    activeDot={{
                      r: 6,
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>
    </div>
    </>
  );
}