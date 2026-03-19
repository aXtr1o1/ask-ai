"use client";

import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";

export default function RateLimit() {
  const responsive = useResponsive();
  const { theme } = useTheme();

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

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "24px",
    }}>
      {/* Rate Limit Cards Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: responsive.isMobile ? "1fr" : responsive.isTablet ? "1fr" : "repeat(2, 1fr)",
        gap: "12px",
      }}>
        {rateLimitMetrics.map((metric) => (
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
              marginBottom: "16px",
            }}>
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
                gap: "6px",
                marginBottom: "12px",
              }}>
                <p style={{
                  fontSize: "24px",
                  fontWeight: 700,
                  color: "#ffffff",
                  margin: 0,
                }}>
                  {metric.current}
                </p>
                <p style={{
                  fontSize: "13px",
                  color: "rgba(255, 255, 255, 0.5)",
                  margin: 0,
                  fontWeight: 500,
                }}>
                  / {metric.limit}
                </p>
              </div>
              <p style={{
                fontSize: "11px",
                color: "rgba(255, 255, 255, 0.5)",
                margin: 0,
              }}>
                {metric.unit}
              </p>
            </div>

            {/* Progress Bar */}
            <div style={{
              width: "100%",
              height: "12px",
              background: "rgba(255, 255, 255, 0.1)",
              borderRadius: "6px",
              overflow: "hidden",
              marginBottom: "12px",
              marginTop: "24px",
            }}>
              <div
                style={{
                  height: "100%",
                  width: `${metric.percentage}%`,
                  background: metric.progressColor,
                  borderRadius: "4px",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <p style={{
              fontSize: "11px",
              color: "rgba(255, 255, 255, 0.5)",
              margin: 0,
              textAlign: "right",
            }}>
              {metric.percentage}% used
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
