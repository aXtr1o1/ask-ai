"use client";

import { useState } from "react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Cell,
  LineChart,
  Line,
  PieChart,
  Pie
} from "recharts";
import { IconChartBar, IconChartArea, IconChartPie, IconChartLine, IconChevronDown } from "@tabler/icons-react";
import { useTheme } from "./useTheme";

// ─── Graph Response Interface ────────────────────────────────────────────────
export interface GraphData {
  type: "graph";              // ← backend sets this to "graph"
  chart_type: "bar";          // ← always "bar" — backend doesn't vary by chart type
  context_summary: string;    // ← shown above the chart as title/summary
  label_key: string;          // ← X axis column name (e.g. "DivisionName")
  value_key: string;          // ← Y axis column name (e.g. "result")
  records: Record<string, number | string>[];  // ← raw grouped data for all chart types
}

// ─── Parse Graph Response ────────────────────────────────────────────────────
/**
 * Attempts to parse text as GraphData
 * Returns GraphData if type === "graph", null otherwise
 * Called BEFORE renderLargeDataset() so no confusion between types
 */
export function parseGraphData(text: string): GraphData | null {
  try {
    // Try parsing the text as JSON
    const parsed = JSON.parse(text);

    // Handle session_id wrapper — extract inner response if present
    const inner = (parsed.session_id && parsed.response)
      ? JSON.parse(parsed.response)
      : parsed;

    // DEBUG: Log what we're checking
    console.log("🔍 parseGraphData debug:", {
      hasParsed: !!parsed,
      type: inner?.type,
      isGraph: inner?.type === "graph",
      keys: Object.keys(inner || {}).slice(0, 5),
    });

    // Only return GraphData if type === "graph" — prevents confusion with large_dataset
    if (inner?.type !== "graph") {
      console.warn("❌ Not a graph response. Type:", inner?.type);
      return null;
    }

    console.log("✅ Graph detected! Rendering chart...");
    return inner as GraphData;
  } catch (error) {
    // Not JSON or not a graph response — return null, fall through to next handler
    console.warn("⚠️ parseGraphData parse error:", error instanceof Error ? error.message : error);
    return null;
  }
}

// ─── Chart Type Dropdown Component ──────────────────────────────────────────
export type ChartType = 'vertical-bar' | 'horizontal-bar' | 'pie' | 'line';

interface ChartTypeDropdownProps {
  currentType: ChartType;
  onTypeChange: (type: ChartType) => void;
}

function ChartTypeDropdown({ currentType, onTypeChange }: ChartTypeDropdownProps) {
  const { theme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);

  const chartTypes = [
    { type: 'vertical-bar' as ChartType, label: 'Bar Chart', icon: <IconChartBar size={16} /> },
    { type: 'horizontal-bar' as ChartType, label: 'Horizontal Bar', icon: <IconChartArea size={16} /> },
    { type: 'pie' as ChartType, label: 'Pie Chart', icon: <IconChartPie size={16} /> },
    { type: 'line' as ChartType, label: 'Line Chart', icon: <IconChartLine size={16} /> },
  ];

  const selectedChart = chartTypes.find(c => c.type === currentType) || chartTypes[0];

  const handleSelect = (type: ChartType) => {
    onTypeChange(type);
    setIsOpen(false);
  };

  // Theme-aware dropdown styles
  const dropdownMenuStyle = theme === "light"
    ? { background: "#ffffff", border: "1px solid #e8e4dc" }
    : { background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.5)" };

  const menuItemTextColor = theme === "light" ? "#1f2937" : "#9CA3AF";
  const menuItemActiveText = theme === "light" ? "#1f2937" : "#d4af37";
  const menuItemActiveBackground = theme === "light" ? "rgba(212,175,55,0.1)" : "rgba(212,175,55,0.2)";
  const menuItemHoverBackground = theme === "light" ? "rgba(212,175,55,0.08)" : "rgba(212,175,55,0.15)";

  return (
    <div style={{ position: 'relative', overflow: 'visible' }}>
      {/* Dropdown Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 10px',
          background: 'rgba(212,175,55,0.15)',
          border: '1px solid rgba(212,175,55,0.5)',
          borderRadius: '6px',
          color: '#d4af37',
          fontSize: '12px',
          fontWeight: '500',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          zIndex: 9998,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(212,175,55,0.25)';
          e.currentTarget.style.borderColor = '#d4af37';
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = 'rgba(212,175,55,0.15)';
            e.currentTarget.style.borderColor = 'rgba(212,175,55,0.5)';
          }
        }}
        title="Chart Type Selector"
      >
        {selectedChart.icon}
        <span>{selectedChart.label}</span>
        <IconChevronDown size={14} style={{ marginLeft: '2px', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
      </button>

      {/* Dropdown Menu — Opens Upward */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: '6px',
            ...dropdownMenuStyle,
            borderRadius: '6px',
            boxShadow: theme === "light" 
              ? '0 4px 12px rgba(0,0,0,0.1)' 
              : '0 4px 12px rgba(0,0,0,0.6)',
            zIndex: 9999,
            minWidth: '160px',
          }}
          onMouseLeave={() => setIsOpen(false)}
        >
          {chartTypes.map((chart) => (
            <button
              key={chart.type}
              onClick={() => handleSelect(chart.type)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                width: '100%',
                padding: '10px 12px',
                background: currentType === chart.type ? menuItemActiveBackground : 'transparent',
                border: 'none',
                color: currentType === chart.type ? menuItemActiveText : menuItemTextColor,
                fontSize: '12px',
                fontWeight: currentType === chart.type ? '600' : '500',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textAlign: 'left',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = menuItemHoverBackground;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = currentType === chart.type ? menuItemActiveBackground : 'transparent';
              }}
            >
              {chart.icon}
              <span>{chart.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Vertical Bar Chart Component ────────────────────────────────────────────
export function BarChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) {
  const { theme } = useTheme();
  
  const tooltipStyle = theme === "light" 
    ? { background: "#ffffff", border: "1px solid #e8e4dc", color: "#1f2937" }
    : { background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.4)", color: "#F3F4F6" };
  
  return (
    <div className="ai-bubble" style={{ overflow: 'visible' }}>
      {/* Context summary shown above chart — from backend */}
      <div className="graph-context-summary">
        {graphData.context_summary}
      </div>

      {/* Bar chart container — enlarged & optimized */}
      <div className="graph-chart-container" style={{ position: 'relative' }}>
        <div style={{ width: "100%", minWidth: "900px", height: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={graphData.records.slice(0, 50)}
              margin={{ top: 15, right: 20, left: 30, bottom: 5 }}
              barCategoryGap="15%"
            >
              {/* Subtle grid lines matching dark theme */}
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.12)" vertical={true} />

              {/* X Axis — labels hidden (shown in tooltip on hover) */}
              <XAxis
                dataKey={graphData.label_key}
                tick={false}
                height={0}
              />

              {/* Y Axis — value_key column e.g. result / count */}
              <YAxis 
                tick={{ fill: "#9CA3AF", fontSize: 11 }} 
                width={55}
                domain={[0, "dataMax + 100"]}
                label={{ value: graphData.value_key, angle: -90, position: "insideLeft", offset: -10, style: { fill: "#9CA3AF", fontSize: 11 } }}
              />

              {/* Tooltip on hover — shows label + value */}
              <Tooltip
                contentStyle={{
                  ...tooltipStyle,
                  borderRadius: 8,
                  fontSize: 13,
                  padding: "8px 12px"
                }}
                cursor={{ fill: "rgba(212,175,55,0.08)" }}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(value: any) => {
                  if (typeof value === 'number') return [value.toLocaleString(), graphData.value_key];
                  if (typeof value === 'string') return [value, graphData.value_key];
                  return ["0", graphData.value_key];
                }}
                labelFormatter={(label) => `${graphData.label_key}: ${label}`}
              />

              {/* Bars — alternating gold colors matching your theme */}
              <Bar dataKey={graphData.value_key} radius={[6, 6, 0, 0]} barSize="75%" maxBarSize={40} strokeWidth={3} stroke="#8b6914">
                {graphData.records.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={index % 2 === 0 ? "#d4af37" : "#f5c249"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Footer Control Row — Dropdown Left + Group Count Right */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px' }}>
        {/* Chart Type Dropdown — Left Side */}
        {currentChartType && onChartTypeChange && (
          <ChartTypeDropdown currentType={currentChartType} onTypeChange={onChartTypeChange} />
        )}
        {/* Group Count — Right Side */}
        <div className="graph-footer">
          {graphData.records.length} group{graphData.records.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}

// ─── Horizontal Bar Chart Component ──────────────────────────────────────────
export function HorizontalBarChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) {
  const { theme } = useTheme();
  
  const tooltipStyle = theme === "light" 
    ? { background: "#ffffff", border: "1px solid #e8e4dc", color: "#1f2937" }
    : { background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.4)", color: "#F3F4F6" };
  
  return (
    <div className="ai-bubble" style={{ overflow: 'visible' }}>
      {/* Context summary shown above chart — from backend */}
      <div className="graph-context-summary">
        {graphData.context_summary}
      </div>

      {/* Bar chart container — enlarged & optimized */}
      <div className="graph-chart-container" style={{ position: 'relative' }}>
        <div style={{ width: "100%", minWidth: "900px", height: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={graphData.records.slice(0, 50)}
              margin={{ top: 15, right: 20, left: 180, bottom: 5 }}
              barCategoryGap="20%"
              layout="vertical"
            >
              {/* Subtle grid lines matching dark theme */}
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.12)" vertical={false} />

              {/* Y Axis — now shows labels for categories (reversed from vertical) */}
              <YAxis
                dataKey={graphData.label_key}
                type="category"
                tick={{ fill: "#9CA3AF", fontSize: 11 }}
                width={160}
              />

              {/* X Axis — value_key column */}
              <XAxis 
                type="number"
                tick={{ fill: "#9CA3AF", fontSize: 11 }}
                domain={[0, "dataMax + 100"]}
              />

              {/* Tooltip on hover — shows label + value */}
              <Tooltip
                contentStyle={{
                  ...tooltipStyle,
                  borderRadius: 8,
                  fontSize: 13,
                  padding: "8px 12px"
                }}
                cursor={{ fill: "rgba(212,175,55,0.08)" }}
                formatter={(value: any) => {
                  if (typeof value === 'number') return [value.toLocaleString(), graphData.value_key];
                  if (typeof value === 'string') return [value, graphData.value_key];
                  return ["0", graphData.value_key];
                }}
                labelFormatter={(label) => `${graphData.label_key}: ${label}`}
              />

              {/* Bars — alternating gold colors */}
              <Bar dataKey={graphData.value_key} radius={[0, 6, 6, 0]} barSize="60%" maxBarSize={25} strokeWidth={3} stroke="#8b6914">
                {graphData.records.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={index % 2 === 0 ? "#d4af37" : "#f5c249"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Footer Control Row — Dropdown Left + Group Count Right */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px' }}>
        {/* Chart Type Dropdown — Left Side */}
        {currentChartType && onChartTypeChange && (
          <ChartTypeDropdown currentType={currentChartType} onTypeChange={onChartTypeChange} />
        )}
        {/* Group Count — Right Side */}
        <div className="graph-footer">
          {graphData.records.length} group{graphData.records.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}

// ─── Line Chart Component ───────────────────────────────────────────────────
export function LineChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) {  const { theme } = useTheme();
  
  const tooltipStyle = theme === "light" 
    ? { background: "#ffffff", border: "1px solid #e8e4dc", color: "#1f2937" }
    : { background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.4)", color: "#F3F4F6" };
    return (
    <div className="ai-bubble" style={{ overflow: 'visible' }}>
      {/* Context summary shown above chart — from backend */}
      <div className="graph-context-summary">
        {graphData.context_summary}
      </div>

      {/* Line chart container — enlarged & optimized */}
      <div className="graph-chart-container" style={{ position: 'relative' }}>
        <div style={{ width: "100%", minWidth: "900px", height: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={graphData.records.slice(0, 50)}
              margin={{ top: 15, right: 20, left: 30, bottom: 5 }}
            >
              {/* Subtle grid lines matching dark theme */}
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.12)" />

              {/* X Axis — labels hidden (shown in tooltip on hover) */}
              <XAxis
                dataKey={graphData.label_key}
                tick={false}
                height={0}
              />

              {/* Y Axis — value_key column */}
              <YAxis 
                tick={{ fill: "#9CA3AF", fontSize: 11 }} 
                width={55}
                domain={[0, "dataMax + 100"]}
                label={{ value: graphData.value_key, angle: -90, position: "insideLeft", offset: -10, style: { fill: "#9CA3AF", fontSize: 11 } }}
              />

              {/* Tooltip on hover — shows label + value */}
              <Tooltip
                contentStyle={{
                  ...tooltipStyle,
                  borderRadius: 8,
                  fontSize: 13,
                  padding: "8px 12px"
                }}
                cursor={{ fill: "rgba(212,175,55,0.08)" }}
                formatter={(value: any) => {
                  if (typeof value === 'number') return [value.toLocaleString(), graphData.value_key];
                  if (typeof value === 'string') return [value, graphData.value_key];
                  return ["0", graphData.value_key];
                }}
                labelFormatter={(label) => `${graphData.label_key}: ${label}`}
              />

              {/* Line — gold stroke */}
              <Line 
                type="monotone" 
                dataKey={graphData.value_key} 
                stroke="#d4af37" 
                dot={{ fill: "#f5c249", r: 4, strokeWidth: 2, stroke: "#8b6914" }}
                activeDot={{ r: 6 }}
                strokeWidth={3}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Footer Control Row — Dropdown Left + Group Count Right */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px' }}>
        {/* Chart Type Dropdown — Left Side */}
        {currentChartType && onChartTypeChange && (
          <ChartTypeDropdown currentType={currentChartType} onTypeChange={onChartTypeChange} />
        )}
        {/* Group Count — Right Side */}
        <div className="graph-footer">
          {graphData.records.length} group{graphData.records.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}

// ─── Pie Chart Component ────────────────────────────────────────────────────
export function PieChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) {  const { theme } = useTheme();
  
  const tooltipStyle = theme === "light" 
    ? { background: "#ffffff", border: "1px solid #e8e4dc", color: "#1f2937" }
    : { background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.4)", color: "#F3F4F6" };
    // Prepare pie chart data — limit to top 8 slices for readability
  const pieData = graphData.records.slice(0, 8).map((record) => ({
    name: record[graphData.label_key],
    value: record[graphData.value_key] || 0,
  }));

  const COLORS = [
    "#d4af37", "#f5c249", "#c9a227", "#ffd700",
    "#daa520", "#b8961a", "#e6c200", "#cc9900"
  ];

  return (
    <div className="ai-bubble" style={{ overflow: 'visible' }}>
      {/* Context summary shown above chart — from backend */}
      <div className="graph-context-summary">
        {graphData.context_summary}
      </div>

      {/* Pie chart container */}
      <div className="graph-chart-container" style={{ position: 'relative' }}>
        <div style={{ width: "100%", minWidth: "900px", height: "100%", display: 'flex', justifyContent: 'flex-start', alignItems: 'center', paddingLeft: '20px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <Pie
                data={pieData}
                cx="20%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value?.toLocaleString() || 0}`}
                outerRadius={120}
                fill="#8884d8"
                dataKey="value"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  ...tooltipStyle,
                  borderRadius: 8,
                  fontSize: 13,
                  padding: "8px 12px"
                }}
                formatter={(value: any) => {
                  if (typeof value === 'number') return [value.toLocaleString(), graphData.value_key];
                  if (typeof value === 'string') return [value, graphData.value_key];
                  return ["0", graphData.value_key];
                }}
                labelFormatter={(label) => `${graphData.label_key}: ${label}`}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Footer Control Row — Dropdown Left + Group Count Right */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px' }}>
        {/* Chart Type Dropdown — Left Side */}
        {currentChartType && onChartTypeChange && (
          <ChartTypeDropdown currentType={currentChartType} onTypeChange={onChartTypeChange} />
        )}
        {/* Group Count — Right Side */}
        <div className="graph-footer">
          {graphData.records.length} group{graphData.records.length !== 1 ? "s" : ""} (showing top {Math.min(8, graphData.records.length)})
        </div>
      </div>
    </div>
  );
}
 
