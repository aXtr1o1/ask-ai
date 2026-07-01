"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from "recharts";
import {
  IconChartBar,
  IconChartLine,
  IconChartPie,
  IconChartArea,
  IconDownload,
  IconCopy,
  IconCheck,
  IconArrowsSort,
  IconAdjustmentsHorizontal
} from "@tabler/icons-react";
import { useResponsive } from "@/app/hooks/useResponsive";

export interface AdvanceGraphProps {
  text: string;
  isDark: boolean;
  onCopy?: (txt: string) => void;
  copied?: boolean;
  userQuery?: string;
}

interface ParsedGraphData {
  title: string;
  records: Record<string, any>[];
  labelKey: string;
  valueKey: string;
  originalJson?: string;
}

export default function AdvanceGraph({ text, isDark, onCopy, copied: externalCopied, userQuery = "" }: AdvanceGraphProps) {
  const [chartType, setChartType] = useState<"bar" | "horizontal-bar" | "line" | "area" | "pie">("bar");
  const [sortBy, setSortBy] = useState<"none" | "asc" | "desc">("none");
  const [internalCopied, setInternalCopied] = useState(false);
  const responsive = useResponsive();

  // ─── Detect Explicitly Requested Chart Type ───
  const explicitlyRequestedType = useMemo((): "bar" | "horizontal-bar" | "line" | "area" | "pie" | null => {
    const query = (userQuery || "").toLowerCase();
    if (query.includes("horizontal bar")) return "horizontal-bar";
    if (query.includes("pie") || query.includes("donut")) return "pie";
    if (query.includes("line")) return "line";
    if (query.includes("area")) return "area";
    if (query.includes("bar")) return "bar";
    return null;
  }, [userQuery]);

  useEffect(() => {
    if (explicitlyRequestedType) {
      setChartType(explicitlyRequestedType);
    } else {
      setChartType("bar");
    }
  }, [explicitlyRequestedType]);

  const handleCopy = () => {
    if (onCopy) {
      onCopy(text);
    } else {
      navigator.clipboard.writeText(text);
      setInternalCopied(true);
      setTimeout(() => setInternalCopied(false), 2000);
    }
  };

  const isCopySuccess = externalCopied || internalCopied;

  // ─── Parse and Auto-detect Graph Structure ───
  const parsedData = useMemo((): ParsedGraphData | null => {
    if (!text) return null;
    try {
      let raw = text.trim();
      let parsed: any = null;

      // Handle envelope structure
      if (raw.startsWith("{")) {
        try {
          const wrapper = JSON.parse(raw);
          if (wrapper.response !== undefined) {
            raw = String(wrapper.response).trim();
          }
        } catch {}
      }

      if (raw.startsWith("{")) {
        parsed = JSON.parse(raw);
      } else {
        return null;
      }

      let records: Record<string, any>[] = [];
      let title = parsed.context_summary || parsed.title || "Graph Analysis";

      if (Array.isArray(parsed.records)) {
        records = parsed.records;
      } else if (Array.isArray(parsed.data)) {
        records = parsed.data;
      } else if (Array.isArray(parsed)) {
        records = parsed;
        title = "Group Distribution";
      }

      if (!records || records.length === 0) return null;

      // Auto-detect keys if not explicitly provided
      let labelKey = parsed.label_key || "";
      let valueKey = parsed.value_key || "";

      if (!labelKey || !valueKey) {
        const sample = records[0];
        const keys = Object.keys(sample);
        
        // Find numeric key and string key
        for (const k of keys) {
          const val = sample[k];
          if (typeof val === "number" && !valueKey) {
            valueKey = k;
          } else if (typeof val === "string" && !labelKey && k.toLowerCase() !== "id") {
            labelKey = k;
          }
        }
        
        // Fallbacks
        if (!labelKey) labelKey = keys.find(k => k.toLowerCase() !== "id") || keys[0];
        if (!valueKey) valueKey = keys.find(k => k !== labelKey) || keys[0];
      }

      return {
        title,
        records,
        labelKey,
        valueKey,
        originalJson: raw
      };
    } catch (e) {
      console.error("Failed to parse graph data:", e);
      return null;
    }
  }, [text]);

  // ─── Apply Sorting ───
  const displayRecords = useMemo(() => {
    if (!parsedData) return [];
    const { records, valueKey } = parsedData;
    const items = [...records];
    
    if (sortBy === "asc") {
      return items.sort((a, b) => Number(a[valueKey] || 0) - Number(b[valueKey] || 0));
    } else if (sortBy === "desc") {
      return items.sort((a, b) => Number(b[valueKey] || 0) - Number(a[valueKey] || 0));
    }
    return items;
  }, [parsedData, sortBy]);

  if (!parsedData || displayRecords.length === 0) {
    return (
      <div style={{ padding: "16px", color: isDark ? "#94a3b8" : "#64748b", fontSize: "13px" }}>
        No displayable graph data found.
      </div>
    );
  }

  const { title, labelKey, valueKey } = parsedData;

  // ─── Curated Color Palette ───
  const colors = {
    primary: isDark ? "#d4af37" : "#aa7c11",
    primaryLight: isDark ? "#f5c249" : "#d4af37",
    primaryGradientStart: "#D4AF37",
    primaryGradientEnd: "#AA7C11",
    grid: isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)",
    text: isDark ? "#94a3b8" : "#64748b",
    tooltipBg: isDark ? "#1e293b" : "#ffffff",
    tooltipBorder: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
    accentPalette: [
      "#d4af37", "#f5c249", "#aa7c11", "#ffd700",
      "#daa520", "#b8961a", "#e6c200", "#cc9900"
    ]
  };

  // ─── Download Graph Data ───
  const handleDownload = () => {
    const csvContent = [
      [labelKey, valueKey].join(","),
      ...displayRecords.map(r => `"${String(r[labelKey]).replace(/"/g, '""')}",${r[valueKey]}`)
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${title.toLowerCase().replace(/[^a-z0-9]/g, "_")}_data.csv`);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const chartHeight = responsive.isMobile ? 260 : 320;

  return (
    <div
      className="advance-graph-card"
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        padding: "16px",
        borderRadius: "10px",
        background: isDark ? "rgba(15, 23, 42, 0.4)" : "rgba(248, 250, 252, 0.6)",
        border: `1px solid ${isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.05)"}`,
      }}
    >
      {/* Header Info */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px" }}>
        <div style={{ flex: 1 }}>
          <h4
            style={{
              margin: 0,
              fontSize: "14px",
              fontWeight: 600,
              color: isDark ? "#f1f5f9" : "#0f172a",
              lineHeight: "1.4"
            }}
          >
            {title}
          </h4>
          <span style={{ fontSize: "11px", color: colors.text }}>
            Comparing {valueKey} across {displayRecords.length} groups
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {/* Sort Toggle */}
          <button
            onClick={() => setSortBy(prev => prev === "none" ? "desc" : prev === "desc" ? "asc" : "none")}
            title="Sort Data"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "4px",
              color: sortBy !== "none" ? colors.primary : colors.text,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.2s"
            }}
          >
            <IconArrowsSort size={15} />
          </button>

          {/* Copy Raw Data */}
          <button
            onClick={handleCopy}
            title="Copy graph JSON data"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "4px",
              color: colors.text,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.2s"
            }}
          >
            {isCopySuccess ? <IconCheck size={15} style={{ color: "#22c55e" }} /> : <IconCopy size={15} />}
          </button>

          {/* Download CSV */}
          <button
            onClick={handleDownload}
            title="Download CSV"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "4px",
              color: colors.text,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.2s"
            }}
          >
            <IconDownload size={15} />
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div style={{ width: "100%", height: chartHeight, position: "relative" }}>
        <ResponsiveContainer width="100%" height="100%">
          {(() => {
            switch (chartType) {
              case "horizontal-bar":
                return (
                  <BarChart
                    data={displayRecords}
                    layout="vertical"
                    margin={{ top: 5, right: 15, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} horizontal={true} vertical={false} />
                    <XAxis type="number" stroke={colors.text} fontSize={10} />
                    <YAxis dataKey={labelKey} type="category" stroke={colors.text} fontSize={10} width={70} />
                    <Tooltip
                      contentStyle={{ background: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: "8px", fontSize: "12px" }}
                      labelStyle={{ fontWeight: 600, color: colors.primary }}
                    />
                    <Bar dataKey={valueKey} fill={colors.primary} radius={[0, 4, 4, 0]}>
                      {displayRecords.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={colors.accentPalette[index % colors.accentPalette.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                );

              case "line":
                return (
                  <LineChart
                    data={displayRecords}
                    margin={{ top: 5, right: 15, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                    <XAxis dataKey={labelKey} stroke={colors.text} fontSize={10} />
                    <YAxis stroke={colors.text} fontSize={10} />
                    <Tooltip
                      contentStyle={{ background: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: "8px", fontSize: "12px" }}
                      labelStyle={{ fontWeight: 600, color: colors.primary }}
                    />
                    <Line
                      type="monotone"
                      dataKey={valueKey}
                      stroke={colors.primary}
                      strokeWidth={2}
                      dot={{ r: 4, stroke: colors.primary, strokeWidth: 1 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                );

              case "area":
                return (
                  <AreaChart
                    data={displayRecords}
                    margin={{ top: 5, right: 15, left: 0, bottom: 5 }}
                  >
                    <defs>
                      <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={colors.primary} stopOpacity={0.4} />
                        <stop offset="95%" stopColor={colors.primary} stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
                    <XAxis dataKey={labelKey} stroke={colors.text} fontSize={10} />
                    <YAxis stroke={colors.text} fontSize={10} />
                    <Tooltip
                      contentStyle={{ background: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: "8px", fontSize: "12px" }}
                      labelStyle={{ fontWeight: 600, color: colors.primary }}
                    />
                    <Area
                      type="monotone"
                      dataKey={valueKey}
                      stroke={colors.primary}
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#areaGradient)"
                    />
                  </AreaChart>
                );

              case "pie":
                return (
                  <PieChart>
                    <Tooltip
                      contentStyle={{ background: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: "8px", fontSize: "12px" }}
                    />
                    <Pie
                      data={displayRecords}
                      dataKey={valueKey}
                      nameKey={labelKey}
                      cx="50%"
                      cy="50%"
                      innerRadius={responsive.isMobile ? 35 : 45}
                      outerRadius={responsive.isMobile ? 70 : 90}
                      paddingAngle={2}
                      label={!responsive.isMobile}
                    >
                      {displayRecords.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={colors.accentPalette[index % colors.accentPalette.length]} />
                      ))}
                    </Pie>
                  </PieChart>
                );

              case "bar":
              default:
                return (
                  <BarChart
                    data={displayRecords}
                    margin={{ top: 5, right: 15, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
                    <XAxis dataKey={labelKey} stroke={colors.text} fontSize={10} />
                    <YAxis stroke={colors.text} fontSize={10} />
                    <Tooltip
                      contentStyle={{ background: colors.tooltipBg, border: `1px solid ${colors.tooltipBorder}`, borderRadius: "8px", fontSize: "12px" }}
                      labelStyle={{ fontWeight: 600, color: colors.primary }}
                    />
                    <Bar dataKey={valueKey} fill={colors.primary} radius={[4, 4, 0, 0]}>
                      {displayRecords.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={colors.accentPalette[index % colors.accentPalette.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                );
            }
          })()}
        </ResponsiveContainer>
      </div>

      {/* Control Switchers */}
      {!explicitlyRequestedType && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderTop: `1px solid ${isDark ? "rgba(255, 255, 255, 0.05)" : "rgba(15, 23, 42, 0.05)"}`,
            paddingTop: "12px"
          }}
        >
          <div style={{ display: "flex", gap: "6px" }}>
            {(["bar", "horizontal-bar", "line", "area", "pie"] as const).map(type => {
              const isActive = chartType === type;
              return (
                <button
                  key={type}
                  onClick={() => setChartType(type)}
                  style={{
                    padding: "4px 8px",
                    borderRadius: "5px",
                    fontSize: "11px",
                    fontWeight: 500,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    border: "1px solid transparent",
                    background: isActive ? colors.primary : "transparent",
                    color: isActive ? "#ffffff" : colors.text,
                    transition: "all 0.15s ease"
                  }}
                >
                  {type === "bar" && <IconChartBar size={12} />}
                  {type === "horizontal-bar" && <IconChartBar size={12} style={{ transform: "rotate(90deg)" }} />}
                  {type === "line" && <IconChartLine size={12} />}
                  {type === "area" && <IconChartArea size={12} />}
                  {type === "pie" && <IconChartPie size={12} />}
                  <span style={{ textTransform: "capitalize" }}>{type.replace("-", " ")}</span>
                </button>
              );
            })}
          </div>

          <div style={{ fontSize: "10px", color: colors.text, fontStyle: "italic" }}>
            * Interactive View
          </div>
        </div>
      )}
    </div>
  );
}
