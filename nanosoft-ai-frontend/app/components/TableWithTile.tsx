"use client";

import { useState } from "react";
import { IconList, IconLayoutGrid } from "@tabler/icons-react";
import { useTheme } from "@/app/components/useTheme";
import { useResponsive, getResponsiveTable, getResponsiveTileDisplay, getSmartVisibleColumns } from "@/app/hooks/useResponsive";

export type TableWithTileRow = Record<string, string>;

interface TableWithTileProps {
  rows: TableWithTileRow[];
  columns?: string[];
  title?: string;
  htmlTableContent?: string; // Old HTML table format
}

export default function TableWithTile({
  rows,
  columns,
  title = "Data",
  htmlTableContent,
}: TableWithTileProps) {
  const responsive = useResponsive();
  const tableConfig = getResponsiveTable(responsive.screen);
  const tileConfig = getResponsiveTileDisplay(responsive.screen);
  const { theme } = useTheme();
  const isDark = theme === "dark";
  // Use CSS variables set by root theme in globals.css
  const tileBackground = "var(--tile-card-bg, #ffffff)";
  const tileBorder = "var(--tile-card-border, 1px solid rgba(0, 0, 0, 0.08))";
  const tileText = "var(--tile-card-text, #0f172a)";
  const tileTextMuted = "var(--tile-card-text-muted, rgba(31, 41, 55, 0.7))";
  const tileFieldBackground = "var(--tile-field-bg, rgba(255, 255, 255, 0.9))";
  const tileFieldBorder = "var(--tile-field-border, 1px solid rgba(148, 163, 184, 0.25))";
  const tileFieldLabelColor = "var(--tile-field-label, #0f172a)";
  const tileFieldValueColor = "var(--tile-field-value, #1f2937)";
  const [viewMode, setViewMode] = useState<"table" | "tile">("table");

  // Automatically detect columns from rows
  const detectedColumns = columns || (() => {
    const cols = new Set<string>();
    rows.forEach((row) => {
      Object.keys(row).forEach((key) => cols.add(key));
    });
    return Array.from(cols);
  })();

  // Toggle container style: absolute on larger screens, inline/static on mobile
  const toggleContainerStyle = {
    position: responsive.isMobile ? 'static' as const : 'absolute' as const,
    top: responsive.isMobile ? undefined : 12,
    right: responsive.isMobile ? undefined : 12,
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    gap: responsive.isMobile ? 6 : 2,
    zIndex: 1000,
    marginBottom: responsive.isMobile ? 8 : 0,
  };

  return (
    <div style={{ width: '100%' }}>
      {/* Table content with buttons inside */}
      <div className="table-with-tile" style={{ marginTop: 0, position: 'relative' }}>
        {/* Toggle buttons positioned at top - right corner INSIDE the border */}
        <div style={toggleContainerStyle}>
          {/* Table View Button (Left) - Toggle to Table */}
          <button
            onClick={() => setViewMode("table")}
            title="Switch to Table View"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '4px 8px',
              borderRadius: '6px',
              background: viewMode === "table" 
                ? 'linear-gradient(180deg, #ae8625 0%, #f7ef8a 35%, #d2ac47 65%, #edc967 100%)'
                : 'rgba(174, 134, 37, 0.3)',
              color: '#1f2937',
              border: '1px solid #d4af37',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 600,
              transition: 'all 0.2s ease-in-out',
              backdropFilter: 'blur(8px)',
              transform: 'scale(1)',
              opacity: viewMode === "table" ? 1 : 0.6,
              boxShadow: viewMode === "table" 
                ? '0 0 12px rgba(212, 175, 55, 0.6), inset 0 0 8px rgba(255, 255, 255, 0.3)'
                : 'none',
            }}
            onMouseDown={e => {
              (e.target as HTMLElement).style.transform = 'scale(0.95)';
            }}
            onMouseUp={e => {
              (e.target as HTMLElement).style.transform = 'scale(1)';
            }}
          >
            <span style={{
              display: 'flex',
              alignItems: 'center',
              textShadow: viewMode === "table" ? '0 0 8px rgba(255, 255, 255, 0.8)' : 'none',
            }}>
              <IconList size={14} />
            </span>
          </button>

          {/* Tile View Button (Right) - Toggle to Tile */}
          <button
            onClick={() => setViewMode("tile")}
            title="Switch to Tile View"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '4px 8px',
              borderRadius: '6px',
              background: viewMode === "tile" 
                ? 'linear-gradient(180deg, #ae8625 0%, #f7ef8a 35%, #d2ac47 65%, #edc967 100%)'
                : 'rgba(174, 134, 37, 0.3)',
              color: '#1f2937',
              border: '1px solid #d4af37',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 600,
              transition: 'all 0.2s ease-in-out',
              backdropFilter: 'blur(8px)',
              transform: 'scale(1)',
              opacity: viewMode === "tile" ? 1 : 0.6,
              boxShadow: viewMode === "tile" 
                ? '0 0 12px rgba(212, 175, 55, 0.6), inset 0 0 8px rgba(255, 255, 255, 0.3)'
                : 'none',
            }}
            onMouseDown={e => {
              (e.target as HTMLElement).style.transform = 'scale(0.95)';
            }}
            onMouseUp={e => {
              (e.target as HTMLElement).style.transform = 'scale(1)';
            }}
          >
            <span style={{
              display: 'flex',
              alignItems: 'center',
              textShadow: viewMode === "tile" ? '0 0 8px rgba(255, 255, 255, 0.8)' : 'none',
            }}>
              <IconLayoutGrid size={14} />
            </span>
          </button>
        </div>

        <div className="content-shell" style={{ paddingTop: 0 }}>
        <div className="data-view-shell" style={{ 
          transition: 'all 0.2s ease-in-out',
          opacity: 1
        }}>
          {/* Table View - Old HTML format */}
          {viewMode === "table" && (
            <div className="data-view-panel is-active" style={{
              animation: 'fadeIn 0.2s ease-in-out'
            }}>
              {htmlTableContent ? (
                <div dangerouslySetInnerHTML={{ __html: htmlTableContent }} />
              ) : (
                <div className="table-scroll" style={{
                  fontSize: tableConfig.fontSize,
                  overflowX: 'auto',
                }}>
                  <table className="table-with-tile" style={{
                    fontSize: tableConfig.fontSize,
                    minWidth: responsive.isMobile ? '100%' : 'auto',
                  }}>
                    <thead>
                      <tr>
                        {detectedColumns.slice(0, tableConfig.columnsVisible).map((col) => (
                          <th key={col} style={{
                            padding: tableConfig.padding,
                            fontSize: tableConfig.fontSize,
                          }}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, rowIdx) => (
                        <tr key={rowIdx} style={{
                          height: tableConfig.compactMode ? 'auto' : 'auto',
                        }}>
                          {detectedColumns.slice(0, tableConfig.columnsVisible).map((col) => (
                            <td key={`${rowIdx}-${col}`} style={{
                              padding: tableConfig.padding,
                              fontSize: tableConfig.fontSize,
                            }}>{row[col] || "—"}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tile View */}
          {viewMode === "tile" && (
            <div className="data-view-panel is-active" style={{
              animation: 'fadeIn 0.2s ease-in-out'
            }}>
              <div className="tile-cards-grid" style={{
                gridTemplateColumns: responsive.isMobile 
                  ? 'repeat(5, 1fr)' 
                  : responsive.isTablet 
                  ? 'repeat(2, 1fr)' 
                  : 'repeat(3, 1fr)',
                gap: responsive.isMobile ? '4px' : responsive.isTablet ? '20px' : '24px',
                padding: responsive.isMobile ? '8px' : responsive.isTablet ? '20px' : '24px',
              }}>
                {rows.map((row, rowIdx) => {
                  // Detect status from row data for status dot color
                  const statusValue = row.status || row.STATUS || row.condition || row.CONDITION || "neutral";
                  const isActive = ["active", "online", "good", "operational"].some(s => statusValue.toLowerCase().includes(s));
                  const statusColor = isActive ? "#10b981" : "#6b7280";

                  return (
                    <div key={rowIdx} className="tile-card" style={{
                      padding: responsive.isMobile ? '8px' : responsive.isTablet ? tileConfig.cardPadding : '12px',
                      minHeight: responsive.isMobile ? '120px' : responsive.isTablet ? tileConfig.cardHeight : '280px',
                      backgroundColor: tileBackground,
                      border: tileBorder,
                      color: tileText,
                      boxShadow: isDark ? '0 8px 20px rgba(0,0,0,0.35)' : '0 8px 20px rgba(0,0,0,0.07)',
                      transition: 'border 0.2s ease, box-shadow 0.2s ease, color 0.2s ease',
                    }}>
                      {/* Top colored strip */}
                      <div className="tile-card-header" />
                      
                      {/* Status dot + card content */}
                      <div style={{ 
                        display: 'flex', 
                        gap: responsive.isMobile ? '4px' : '16px', 
                        padding: responsive.isMobile ? '4px' : tileConfig.cardPadding,
                        flexDirection: responsive.isMobile ? 'row' : 'row',
                      }}>
                        {/* Status Dot */}
                        <div
                          className="tile-status-dot"
                          style={{
                            width: '12px',
                            height: '12px',
                            borderRadius: '50%',
                            backgroundColor: statusColor,
                            flexShrink: 0,
                            marginTop: responsive.isMobile ? '0px' : '4px',
                            boxShadow: `0 0 12px ${statusColor}99`
                          }}
                          title={isActive ? 'Active' : 'Inactive'}
                        />

                        {/* Card Content - Grid Layout */}
                        <div style={{ 
                          flex: 1, 
                          display: 'grid', 
                          gridTemplateColumns: responsive.isMobile 
                            ? '1fr' 
                            : responsive.isTablet
                            ? 'repeat(2, 1fr)'
                            : 'repeat(3, 1fr)',
                          gap: responsive.isMobile ? '2px' : responsive.isTablet ? '16px' : '12px'
                        }}>
                          {(responsive.isDesktop ? detectedColumns : detectedColumns.slice(0, tileConfig.fieldsPerTile)).map((col) => (
                            <div 
                              key={`${rowIdx}-${col}`} 
                              className="tile-field"
                              title={row[col]}
                              style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: responsive.isMobile ? '4px' : '6px',
                                backgroundColor: tileFieldBackground,
                                border: tileFieldBorder,
                              }}
                            >
                              <div className="tile-field-label" style={{
                                fontSize: responsive.isMobile ? '11px' : responsive.isTablet ? '12px' : '11px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                letterSpacing: '0.5px',
                                wordBreak: 'break-word',
                              }}>{col}</div>
                              <div className="tile-field-value" style={{
                                fontSize: responsive.isMobile ? '13px' : responsive.isTablet ? '14px' : '12px',
                                fontWeight: 400,
                                wordBreak: 'break-word',
                                lineHeight: 1.4,
                              }}>{row[col] || "—"}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
