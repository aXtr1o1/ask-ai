"use client";

import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function Usage() {
  const responsive = useResponsive();
  const { theme } = useTheme();

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
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "24px",
    }}>
      {/* Usage Metrics Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: responsive.isMobile ? "1fr" : responsive.isTablet ? "1fr" : "repeat(2, 1fr)",
        gap: "12px",
      }}>
        {usageMetrics.map((metric) => (
          <div
            key={metric.id}
            style={{
              background: `linear-gradient(135deg, ${metric.color} 0%, rgba(255, 255, 255, 0.02) 100%)`,
              border: `1.5px solid ${metric.borderColor}`,
              borderRadius: "12px",
              padding: "20px",
              transition: "all 0.3s ease",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              const div = e.currentTarget as HTMLElement;
              div.style.transform = "translateY(-4px)";
              div.style.boxShadow = `0 12px 32px ${metric.borderColor}`;
            }}
            onMouseLeave={(e) => {
              const div = e.currentTarget as HTMLElement;
              div.style.transform = "translateY(0)";
              div.style.boxShadow = "none";
            }}
          >
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              marginBottom: "16px",
            }}>
              <div>
                <p style={{
                  fontSize: "12px",
                  color: "rgba(255, 255, 255, 0.6)",
                  margin: 0,
                  marginBottom: "12px",
                  fontWeight: 500,
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}>
                  {metric.label}
                </p>
                <div style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: "8px",
                }}>
                  <p style={{
                    fontSize: "32px",
                    fontWeight: 700,
                    color: "#ffffff",
                    margin: 0,
                  }}>
                    {metric.value}
                  </p>
                  <p style={{
                    fontSize: "13px",
                    color: metric.borderColor,
                    margin: 0,
                    fontWeight: 600,
                  }}>
                    {metric.unit}
                  </p>
                </div>
                <p style={{
                  fontSize: "12px",
                  color: "rgba(255, 255, 255, 0.5)",
                  margin: "12px 0 0 0",
                }}>
                  {metric.subtext}
                </p>
              </div>
            </div>

            {/* Chart */}
            <div style={{
              marginTop: "20px",
              marginLeft: "-20px",
              marginRight: "-20px",
              marginBottom: "-20px",
              borderTop: `1px solid ${metric.borderColor}`,
              paddingTop: "16px",
              paddingLeft: "20px",
              paddingRight: "20px",
              paddingBottom: "0",
            }}>
              <ResponsiveContainer width="100%" height={350}>
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
  );
}
