"use client";

import React, { useState, useEffect } from "react";
import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { useUsageStats } from "@/app/hooks/useUsageStats";

interface UsageProps {
  externalUserId: string;  // ← ADD
  subUserName: string;
}

export default function Usage({ externalUserId, subUserName }: UsageProps) {
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [animated, setAnimated] = useState(false);

  // ── Fetch real data from backend ──────────────────────────
  const { stats, loading, error, refetch } = useUsageStats(externalUserId, subUserName);  

  useEffect(() => {
    setAnimated(true);
  }, []);

  const styles = `
    @keyframes slideInUp {
      from { opacity: 0; transform: translateY(30px); }
      to   { opacity: 1; transform: translateY(0);    }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to   { opacity: 1; }
    }
    @keyframes pulse-dot {
      0%, 100% { opacity: 0.8; transform: scale(1);   }
      50%       { opacity: 0.4; transform: scale(1.2); }
    }
  `;

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return (num / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (num >= 1_000)     return (num / 1_000).toFixed(1).replace(/\.0$/, "")     + "K";
    return num.toLocaleString();
  };

  const isDark    = theme === "dark";
  const textMuted = isDark ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.55)";
  const textFaint = isDark ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.40)";

  // ── Loading state ─────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 0" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ display: "flex", gap: 6, justifyContent: "center", marginBottom: 8 }}>
            {[0, 1, 2].map(i => (
              <span key={i} style={{
                display: "inline-block", width: 8, height: 8,
                borderRadius: "50%", background: "#d4af37",
                animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
          <span style={{ fontSize: 13, color: "#A0AEC0" }}>Loading usage stats…</span>
        </div>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────
  if (error || !stats) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 14 }}>
          {error || "No usage data available"}
        </p>
        <button
          onClick={refetch}
          style={{
            marginTop: 12,
            padding: "8px 20px",
            borderRadius: 8,
            border: "1px solid var(--color-primary)",
            background: "transparent",
            color: "var(--color-primary)",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  // ── Build chart data from history ─────────────────────────
  // history is array of { date, credits_used, audio_seconds, graph_count, request_count }
  const history = stats.history || [];

  // Format date label: "2026-03-20" → "Mar 20"
  const formatDateLabel = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return dateStr;
    }
  };

  const creditsChartData  = history.map(h => ({ date: formatDateLabel(h.date), value: h.credits_used  }));
  const audioChartData    = history.map(h => ({ date: formatDateLabel(h.date), value: h.audio_seconds }));
  const graphChartData    = history.map(h => ({ date: formatDateLabel(h.date), value: h.graph_count   }));
  const requestChartData  = history.map(h => ({ date: formatDateLabel(h.date), value: h.request_count }));
  const tokensChartData   = history.map(h => ({ date: formatDateLabel(h.date), value: h.tokens_used   }));

  // ── KPI cards ─────────────────────────────────────────────
  const kpiMetrics = [
    {
      id:         "credits",
      label:      "Credits Used",
      value:      formatNumber(stats.credits_used),
      unit:       "credits",
      subtext:    `${stats.credits_remaining} remaining`,
      chartColor: "#6496ff",
      data:       creditsChartData,
    },
    {
      id:         "audio",
      label:      "Audio Usage",
      value:      formatNumber(stats.audio_seconds),
      unit:       "seconds",
      subtext:    `of ${formatNumber(stats.audio_limit)} limit`,
      chartColor: "#ff9664",
      data:       audioChartData,
    },
    {
      id:         "graph",
      label:      "Graph Operations",
      value:      formatNumber(stats.graph_count),
      unit:       "operations",
      subtext:    `of ${formatNumber(stats.graph_limit)} limit`,
      chartColor: "#ffc864",
      data:       graphChartData,
    },
    {
  id:         "tokens",
  label:      "Tokens Used",
  value:      formatNumber(stats.tokens_used),   
  unit:       "tokens",
  subtext:    `of ${formatNumber(stats.token_limit)} limit`,
  chartColor: "#64c896",
  data:       tokensChartData,
  },
  ];

  // Trend charts — credits and audio
  const trendMetrics = [
    { ...kpiMetrics[0], trendLabel: "Credits Usage Trend"  },
    { ...kpiMetrics[1], trendLabel: "Audio Usage Trend"    },
  ];

  // Breakdown metrics for day-by-day table
  const breakdownMetrics = kpiMetrics;

  return (
    <>
      <style>{styles}</style>
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "32px",
        background: "transparent",
        color: "var(--manageaccount-text)",
        border: "1px solid var(--manageaccount-border)",
        minHeight: 0,
        width: "100%",
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

          {/* ── KPI Strip ────────────────────────────────────── */}
          <div style={{
            display: "grid",
            gridTemplateColumns: responsive.isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
            gap: "12px",
          }}>
            {kpiMetrics.map((metric, index) => (
              <div
                key={metric.id}
                style={{
                  background: `linear-gradient(135deg, rgba(212,175,55,${isDark ? 0.12 : 0.22}) 0%, rgba(255,255,255,0.02) 100%)`,
                  border: `1.5px solid rgba(212,175,55,${isDark ? 0.35 : 0.30})`,
                  borderRadius: "18px",
                  padding: "16px 16px 14px",
                  position: "relative",
                  overflow: "hidden",
                  backdropFilter: "blur(10px)",
                  boxShadow: `0 10px 36px rgba(0,0,0,${isDark ? 0.35 : 0.18})`,
                  animation: animated ? `slideInUp 0.55s ease-out ${index * 0.08}s both` : "none",
                }}
              >
                <div style={{
                  position: "absolute", inset: 0,
                  background: `radial-gradient(circle at 30% 10%, ${metric.chartColor}18 0%, transparent 55%)`,
                  pointerEvents: "none",
                }} />

                <div style={{ position: "relative", zIndex: 1, display: "flex", gap: "12px", alignItems: "flex-start" }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{
                      fontSize: "11px", color: textMuted, margin: 0,
                      fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.6px",
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    }}>
                      {metric.label}
                    </p>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "8px" }}>
                      <p style={{
                        fontSize: "26px", fontWeight: 900, margin: 0,
                        color: isDark ? "#ffffff" : "#0f172a",
                      }}>
                        {metric.value}
                      </p>
                      <p style={{ fontSize: "12px", fontWeight: 800, margin: 0, color: metric.chartColor, opacity: 0.95 }}>
                        {metric.unit}
                      </p>
                    </div>
                    <p style={{ fontSize: "11px", color: textFaint, margin: "6px 0 0", fontWeight: 600 }}>
                      {metric.subtext}
                    </p>
                  </div>

                  {/* Mini sparkline chart */}
                  {metric.data.length > 0 && (
                    <div style={{ width: "96px", height: "46px", flexShrink: 0 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metric.data}>
                          <XAxis dataKey="date" hide />
                          <YAxis hide />
                          <Line
                            type="monotone" dataKey="value"
                            stroke={metric.chartColor} strokeWidth={2.5}
                            dot={false} isAnimationActive={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* ── Trend Charts ──────────────────────────────────── */}
          <div style={{
            display: "grid",
            gridTemplateColumns: responsive.isDesktop ? "repeat(2, 1fr)" : "1fr",
            gap: "16px",
          }}>
            {trendMetrics.map((metric, index) => (
              <div
                key={metric.id + "-trend"}
                style={{
                  background: `linear-gradient(135deg, rgba(212,175,55,${isDark ? 0.10 : 0.20}) 0%, rgba(255,255,255,0.02) 100%)`,
                  border: `1.5px solid rgba(212,175,55,${isDark ? 0.35 : 0.30})`,
                  borderRadius: "18px",
                  padding: "16px",
                  backdropFilter: "blur(10px)",
                  animation: animated ? `slideInUp 0.6s ease-out ${0.15 + index * 0.12}s both` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                  <div>
                    <p style={{ margin: 0, fontSize: 12, fontWeight: 800, color: textMuted, textTransform: "uppercase", letterSpacing: "0.6px" }}>
                      Trend
                    </p>
                    <p style={{ margin: 0, fontSize: 18, fontWeight: 900, color: isDark ? "#ffffff" : "#0f172a" }}>
                      {metric.trendLabel}
                    </p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 9, height: 9, borderRadius: 999, background: metric.chartColor, boxShadow: `0 0 18px ${metric.chartColor}aa` }} />
                    <p style={{ margin: 0, fontSize: 11, fontWeight: 800, color: textMuted, textTransform: "uppercase" }}>
                      Active
                    </p>
                  </div>
                </div>

                {metric.data.length === 0 ? (
                  <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <p style={{ color: textFaint, fontSize: 13 }}>No history data yet</p>
                  </div>
                ) : (
                  <div style={{ height: 260 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={metric.data}>
                        <CartesianGrid
                          strokeDasharray="4 4"
                          stroke={isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}
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
                          axisLine={false} tickLine={false} width={42}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: isDark ? "rgba(20,20,25,0.95)" : "rgba(240,240,245,0.95)",
                            border: `1px solid rgba(212,175,55,${isDark ? 0.40 : 0.35})`,
                            borderRadius: "10px",
                            color: isDark ? "#ffffff" : "#000000",
                          }}
                          formatter={(val: unknown) => [formatNumber(Number(val)), metric.unit]}
                        />
                        <Line
                          type="monotone" dataKey="value"
                          stroke={metric.chartColor} strokeWidth={2.8}
                          dot={{ r: 3, fill: metric.chartColor }}
                          activeDot={{ r: 6 }}
                          isAnimationActive={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* ── Day-by-day Breakdown ──────────────────────────── */}
          <div style={{
            background: `linear-gradient(135deg, rgba(212,175,55,${isDark ? 0.08 : 0.18}) 0%, rgba(255,255,255,0.02) 100%)`,
            border: `1.5px solid rgba(212,175,55,${isDark ? 0.35 : 0.30})`,
            borderRadius: "18px",
            padding: "16px",
            backdropFilter: "blur(10px)",
          }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
              <div>
                <p style={{ margin: 0, fontSize: 12, fontWeight: 900, color: textMuted, textTransform: "uppercase", letterSpacing: "0.6px" }}>
                  Last {history.length} Days
                </p>
                <p style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 900, color: isDark ? "#ffffff" : "#0f172a" }}>
                  Day-by-day breakdown
                </p>
              </div>
            </div>

            {history.length === 0 ? (
              <p style={{ color: textFaint, fontSize: 13, textAlign: "center", padding: "20px 0" }}>
                No history data yet — will populate as you use the app
              </p>
            ) : (
              <div style={{
                display: "grid",
                gridTemplateColumns: responsive.isDesktop ? "repeat(4, 1fr)" : "repeat(2, 1fr)",
                gap: 12,
              }}>
                {breakdownMetrics.map((metric) => (
                  <div
                    key={metric.id + "-breakdown"}
                    style={{
                      borderRadius: 14,
                      padding: 12,
                      border: `1.5px solid rgba(212,175,55,${isDark ? 0.22 : 0.18})`,
                      background: `linear-gradient(180deg, rgba(0,0,0,${isDark ? 0.08 : 0.04}) 0%, rgba(255,255,255,0.01) 100%)`,
                    }}
                  >
                    <p style={{ margin: 0, fontSize: 12, fontWeight: 900, color: textMuted, textTransform: "uppercase", letterSpacing: "0.55px" }}>
                      {metric.label}
                    </p>
                    <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                      {metric.data.map((row) => (
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
            )}
          </div>

        </div>
      </div>
    </>
  );
}