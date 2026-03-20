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

  const kpiMetrics = usageMetrics.filter((m) =>
    ["text-requests", "text-usage", "audio-requests", "audio-usage"].includes(m.id)
  );
  const textUsageMetric = usageMetrics.find((m) => m.id === "text-usage")!;
  const audioUsageMetric = usageMetrics.find((m) => m.id === "audio-usage")!;
  const breakdownMetrics = kpiMetrics;

  const isDark = theme === "dark";
  const textMuted = isDark ? "rgba(255, 255, 255, 0.6)" : "rgba(0, 0, 0, 0.55)";
  const textFaint = isDark ? "rgba(255, 255, 255, 0.45)" : "rgba(0, 0, 0, 0.40)";

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
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: "16px",
        }}>
          {/* KPI strip */}
          <div style={{
            display: "grid",
            gridTemplateColumns: responsive.isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
            gap: "12px",
          }}>
            {kpiMetrics.map((metric, index) => (
              <div
                key={metric.id}
                style={{
                  background: `linear-gradient(135deg, rgba(212, 175, 55, ${isDark ? 0.12 : 0.22}) 0%, rgba(255, 255, 255, 0.02) 100%)`,
                  border: `1.5px solid rgba(212, 175, 55, ${isDark ? 0.35 : 0.30})`,
                  borderRadius: "18px",
                  padding: "16px 16px 14px",
                  position: "relative",
                  overflow: "hidden",
                  backdropFilter: "blur(10px)",
                  boxShadow: `0 10px 36px rgba(0, 0, 0, ${isDark ? 0.35 : 0.18})`,
                  cursor: "default",
                  animation: animated ? `slideInUp 0.55s ease-out ${index * 0.08}s both` : "none",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: `radial-gradient(circle at 30% 10%, ${metric.chartColor}18 0%, transparent 55%)`,
                    pointerEvents: "none",
                  }}
                />

                <div style={{ position: "relative", zIndex: 1, display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{
                      fontSize: "11px",
                      color: textMuted,
                      margin: 0,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.6px",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}>
                      {metric.label}
                    </p>

                    <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "8px" }}>
                      <p style={{
                        fontSize: "26px",
                        fontWeight: 900,
                        margin: 0,
                        letterSpacing: "-0.4px",
                        color: isDark ? "#ffffff" : "#0f172a",
                      }}>
                        {metric.value}
                      </p>
                      <p style={{
                        fontSize: "12px",
                        fontWeight: 800,
                        margin: 0,
                        color: metric.borderColor,
                        opacity: 0.95,
                      }}>
                        {metric.unit}
                      </p>
                    </div>

                    <p style={{
                      fontSize: "11px",
                      color: textFaint,
                      margin: "6px 0 0",
                      fontWeight: 600,
                    }}>
                      {metric.subtext}
                    </p>
                  </div>

                  <div style={{ width: "96px", height: "46px", flexShrink: 0 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={metric.data}>
                        <XAxis dataKey="date" hide />
                        <YAxis hide />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke={metric.chartColor}
                          strokeWidth={2.5}
                          dot={false}
                          isAnimationActive={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Trends */}
          <div style={{
            display: "grid",
            gridTemplateColumns: responsive.isDesktop ? "repeat(2, 1fr)" : "1fr",
            gap: "16px",
          }}>
            {[textUsageMetric, audioUsageMetric].map((metric, index) => (
              <div
                key={metric.id}
                style={{
                  background: `linear-gradient(135deg, rgba(212, 175, 55, ${isDark ? 0.10 : 0.20}) 0%, rgba(255, 255, 255, 0.02) 100%)`,
                  border: `1.5px solid rgba(212, 175, 55, ${isDark ? 0.35 : 0.30})`,
                  borderRadius: "18px",
                  padding: "16px",
                  backdropFilter: "blur(10px)",
                  boxShadow: `0 14px 52px rgba(0, 0, 0, ${isDark ? 0.34 : 0.18})`,
                  overflow: "hidden",
                  animation: animated ? `slideInUp 0.6s ease-out ${0.15 + index * 0.12}s both` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <p style={{ margin: 0, fontSize: 12, fontWeight: 800, color: textMuted, textTransform: "uppercase", letterSpacing: "0.6px" }}>
                      Trend
                    </p>
                    <p style={{ margin: 0, fontSize: 18, fontWeight: 900, color: isDark ? "#ffffff" : "#0f172a" }}>
                      {metric.label}
                    </p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 9, height: 9, borderRadius: 999, background: metric.chartColor, boxShadow: `0 0 18px ${metric.chartColor}aa` }} />
                    <p style={{ margin: 0, fontSize: 11, fontWeight: 800, color: textMuted, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                      Active
                    </p>
                  </div>
                </div>

                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={metric.data}>
                      <CartesianGrid
                        strokeDasharray="4 4"
                        stroke={isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.08)"}
                        vertical={false}
                      />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 11, fill: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.55)" }}
                        axisLine={{ stroke: isDark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.10)" }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 11, fill: isDark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.55)" }}
                        axisLine={false}
                        tickLine={false}
                        width={42}
                        domain={["auto", "auto"]}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: isDark ? "rgba(20, 20, 25, 0.95)" : "rgba(240, 240, 245, 0.95)",
                          border: `1px solid rgba(212, 175, 55, ${isDark ? 0.40 : 0.35})`,
                          borderRadius: "10px",
                          color: isDark ? "#ffffff" : "#000000",
                        }}
                        cursor={{ stroke: metric.chartColor, strokeOpacity: 0.35 }}
                        formatter={(val: unknown) => [formatNumber(Number(val)), metric.unit]}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke={metric.chartColor}
                        strokeWidth={2.8}
                        dot={{ r: 3, fill: metric.chartColor }}
                        activeDot={{ r: 6 }}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ))}
          </div>

          {/* Compact day breakdown */}
          <div style={{
            background: `linear-gradient(135deg, rgba(212, 175, 55, ${isDark ? 0.08 : 0.18}) 0%, rgba(255, 255, 255, 0.02) 100%)`,
            border: `1.5px solid rgba(212, 175, 55, ${isDark ? 0.35 : 0.30})`,
            borderRadius: "18px",
            padding: "16px",
            backdropFilter: "blur(10px)",
            boxShadow: `0 12px 44px rgba(0, 0, 0, ${isDark ? 0.30 : 0.18})`,
            overflow: "hidden",
          }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
              <div>
                <p style={{ margin: 0, fontSize: 12, fontWeight: 900, color: textMuted, textTransform: "uppercase", letterSpacing: "0.6px" }}>
                  Last 4 Days
                </p>
                <p style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 900, color: isDark ? "#ffffff" : "#0f172a" }}>
                  Day-by-day breakdown
                </p>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: textFaint, fontWeight: 700 }}>
                Demo values
              </p>
            </div>

            <div style={{
              display: "grid",
              gridTemplateColumns: responsive.isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
              gap: 12,
            }}>
              {breakdownMetrics.map((metric) => (
                <div
                  key={metric.id}
                  style={{
                    borderRadius: 14,
                    padding: 12,
                    border: `1.5px solid rgba(212, 175, 55, ${isDark ? 0.22 : 0.18})`,
                    background: `linear-gradient(180deg, rgba(0,0,0,${isDark ? 0.08 : 0.04}) 0%, rgba(255,255,255,0.01) 100%)`,
                  }}
                >
                  <p style={{ margin: 0, fontSize: 12, fontWeight: 900, color: textMuted, textTransform: "uppercase", letterSpacing: "0.55px" }}>
                    {metric.label}
                  </p>
                  <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                    {metric.data.map((row: { date: string; value: number }) => (
                      <div key={row.date} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                        <span style={{ fontSize: 11, fontWeight: 800, color: textFaint }}>{row.date}</span>
                        <span style={{ fontSize: 11, fontWeight: 900, color: metric.chartColor }}>
                          {formatNumber(row.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
    </div>
    </>
  );
}