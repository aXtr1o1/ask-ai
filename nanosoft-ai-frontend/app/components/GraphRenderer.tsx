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
import { useResponsive, getResponsivePieChartSize } from "@/app/hooks/useResponsive";

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
  const [isButtonHovered, setIsButtonHovered] = useState(false);
  const [hoveredChartType, setHoveredChartType] = useState<ChartType | null>(null);

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

  // ─── Theme-aware button styles (inherits from page theme) ───────────
  const buttonBaseStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 10px',
    background: isButtonHovered || isOpen ? 'var(--color-bg-active)' : 'var(--color-bg-alt)',
    border: isButtonHovered || isOpen ? '1px solid var(--color-primary)' : '1px solid var(--color-border)',
    borderRadius: '6px',
    color: 'var(--color-text)',
    fontSize: '12px',
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    zIndex: 9998,
  } as const;

  // ─── Theme-aware dropdown menu styles (inherits from page theme) ────
  const dropdownMenuStyle = {
    background: 'var(--color-bg-alt)',
    border: '1px solid var(--color-border)'
  };

  const menuItemTextColor = 'var(--color-text)';
  const menuItemActiveText = 'var(--color-primary)';
  const menuItemActiveBackground = 'var(--color-bg-active)';
  const menuItemHoverBackground = 'var(--color-bg-active)';

  return (
    <div style={{ position: 'relative', overflow: 'visible' }}>
      {/* Dropdown Button — Styling updated reactively from state & theme */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        onMouseEnter={() => setIsButtonHovered(true)}
        onMouseLeave={() => setIsButtonHovered(false)}
        style={buttonBaseStyle}
        title="Chart Type Selector"
      >
        {selectedChart.icon}
        <span>{selectedChart.label}</span>
        <IconChevronDown size={14} style={{ marginLeft: '2px', transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }} />
      </button>

      {/* Dropdown Menu — Opens Upward with page theme styling */}
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
                background: 
                  hoveredChartType === chart.type 
                    ? menuItemHoverBackground
                    : currentType === chart.type 
                      ? menuItemActiveBackground 
                      : 'transparent',
                border: 'none',
                color: currentType === chart.type ? menuItemActiveText : menuItemTextColor,
                fontSize: '12px',
                fontWeight: currentType === chart.type ? '600' : '500',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textAlign: 'left',
              }}
              onMouseEnter={() => setHoveredChartType(chart.type)}
              onMouseLeave={() => setHoveredChartType(null)}
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
  const tooltipStyle = { 
    background: 'var(--color-bg-alt)', 
    border: '1px solid var(--color-border)', 
    color: 'var(--color-text)' 
  };
  
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
  const tooltipStyle = { 
    background: 'var(--color-bg-alt)', 
    border: '1px solid var(--color-border)', 
    color: 'var(--color-text)' 
  };
  
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
              margin={{ top: 15, right: 20, left: 20, bottom: 5 }}
              barCategoryGap="15%"
              layout="vertical"
            >
              {/* Subtle grid lines matching dark theme */}
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.12)" vertical={false} />

              {/* Y Axis — labels hidden to move chart left */}
              <YAxis
                dataKey={graphData.label_key}
                type="category"
                tick={false}
                width={0}
                interval={1}
              />

              {/* X Axis — value_key column */}
              <XAxis 
                type="number"
                tick={{ fill: "#9CA3AF", fontSize: 9 }}
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

              {/* Bars — alternating gold colors with uniform height */}
              <Bar dataKey={graphData.value_key} radius={[0, 6, 6, 0]} barSize={18} strokeWidth={3} stroke="#8b6914">
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
export function LineChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) {
  const tooltipStyle = { 
    background: 'var(--color-bg-alt)', 
    border: '1px solid var(--color-border)', 
    color: 'var(--color-text)' 
  };
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
export function PieChartRenderer({ graphData, currentChartType, onChartTypeChange }: { graphData: GraphData; currentChartType?: ChartType; onChartTypeChange?: (type: ChartType) => void }) { 
    const [activeIndex, setActiveIndex] = useState<number | null>(null);
    const responsive = useResponsive();
    const chartSize = getResponsivePieChartSize(responsive.screen);
    const tooltipStyle = { 
    background: 'var(--color-bg-alt)', 
    border: '1px solid var(--color-border)', 
    color: 'var(--color-text)' 
  };
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

      {/* Pie chart container — responsive size based on screen */}
      <div className="graph-chart-container" style={{ position: 'relative', maxWidth: chartSize.containerMaxWidth, margin: '0 auto', border: 'none', boxShadow: 'none', overflow: 'hidden' }}>
        <div style={{ width: chartSize.chartWidth, minWidth: chartSize.containerMinWidth, height: chartSize.height, display: 'flex', justifyContent: 'center', alignItems: 'center', border: 'none' }}>
          <ResponsiveContainer width="100%" height={chartSize.chartHeight}>
            <PieChart margin={{ top: 10, right: 80, bottom: 10, left: 80 }}>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={false}
                outerRadius={responsive.isMobile ? 80 : responsive.isTablet ? 100 : 120}
                fill="#8884d8"
                dataKey="value"
                onMouseEnter={(_, index) => setActiveIndex(index)}
                onMouseLeave={() => setActiveIndex(null)}
              >
                {pieData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={COLORS[index % COLORS.length]}
                    opacity={activeIndex === null || activeIndex === index ? 1 : 0.5}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  ...tooltipStyle,
                  borderRadius: 8,
                  fontSize: 13,
                  padding: "8px 12px"
                }}
                content={({ active, payload }: any) => {
                  if (active && payload && payload.length > 0) {
                    const data = payload[0];
                    return (
                      <div
                        style={{
                          ...tooltipStyle,
                          borderRadius: "8px",
                          fontSize: "13px",
                          padding: "8px 12px"
                        }}
                      >
                        <div>{`${graphData.label_key}: ${data.name}`}</div>
                        <div>{`${graphData.value_key}: ${typeof data.value === 'number' ? data.value.toLocaleString() : data.value}`}</div>
                      </div>
                    );
                  }
                  return null;
                }}
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