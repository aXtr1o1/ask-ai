"use client";

import React, { useState, useEffect, useMemo } from "react";
import { IconList, IconLayoutGrid } from "@tabler/icons-react";
import { useTheme } from "@/app/components/useTheme";
import { useResponsive, getResponsiveTable, getResponsiveTileDisplay, getSmartVisibleColumns } from "@/app/hooks/useResponsive";

export type TableWithTileRow = Record<string, any>;

interface TableWithTileProps {
  rows: TableWithTileRow[];
  columns?: string[];
  title?: string;
  htmlTableContent?: string; // Old HTML table format
}

const TableWithTile = React.memo(function TableWithTile({
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

  // Set default view mode based on device on initial load
  useEffect(() => {
    if (responsive.isMobile) {
      setViewMode("tile");
    }
  }, [responsive.isMobile]);

  // Extract non-table content from htmlTableContent to show as a header/summary
  const summaryContent = useMemo(() => {
    if (!htmlTableContent) return null;
    // Remove the table part to keep only the summary/context
    const summary = htmlTableContent.replace(/<div class="large-dataset-wrapper">[\s\S]*?<\/div>/i, "")
      .replace(/<div class="table-wrapper">[\s\S]*?<\/div>/i, "")
      .trim();
    return summary || null;
  }, [htmlTableContent]);

  const [page, setPage] = useState(0);
  const LIMIT = 100;

  // Automatically detect columns from rows (scan first 100 for performance)
  const detectedColumns = useMemo(() => {
    if (columns) return columns;
    if (rows.length === 0) return [];
    const cols = new Set<string>();
    const sampleRows = rows.slice(0, 100);
    sampleRows.forEach((row) => {
      Object.keys(row).forEach((key) => cols.add(key));
    });
    return Array.from(cols);
  }, [columns, rows]);

  // Pagination: compute the slice of rows to display
  const totalPages = Math.max(1, Math.ceil(rows.length / LIMIT));
  // Reset to first page when data set changes
  useEffect(() => {
    setPage(0);
  }, [rows.length]);
  // Clamp page if totalPages shrinks
  useEffect(() => {
    if (page > totalPages - 1) setPage(Math.max(0, totalPages - 1));
  }, [totalPages, page]);
  const startIdx = page * LIMIT;
  const pagedRows = rows.slice(startIdx, startIdx + LIMIT);

  // Format cell values safely for JSONB / object values
  const formatCellValue = (val: any) => {
    if (val === null || val === undefined) return "—";
    if (typeof val === 'boolean') return val ? '✓' : '✗';
    if (typeof val === 'number') return String(val);
    if (Array.isArray(val)) return val.length === 0 ? '—' : val.map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(', ');
    if (typeof val === 'object') {
      try {
        const s = JSON.stringify(val);
        return s.length > 120 ? s.slice(0, 120) + '…' : s;
      } catch {
        return String(val);
      }
    }
    return String(val);
  };

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
                    overflowY: 'auto',
                    maxHeight: '60vh',
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
                        {pagedRows.map((row, rowIdx) => (
                          <tr key={startIdx + rowIdx} style={{
                            height: tableConfig.compactMode ? 'auto' : 'auto',
                          }}>
                            {detectedColumns.slice(0, tableConfig.columnsVisible).map((col) => (
                              <td key={`${startIdx + rowIdx}-${col}`} style={{
                                padding: tableConfig.padding,
                                fontSize: tableConfig.fontSize,
                              }}>{formatCellValue(row[col])}</td>
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
                {/* Summary / Context for Tile View */}
                {summaryContent && (
                  <div
                    className="large-dataset-context"
                    dangerouslySetInnerHTML={{ __html: summaryContent }}
                    style={{ marginBottom: '8px' }}
                  />
                )}

                <div className="tile-scroll" style={{ overflow: 'auto', maxHeight: '60vh' }}>
                  <div className="tile-cards-grid" style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr',
                    gap: responsive.isMobile ? '12px' : '24px',
                    padding: responsive.isMobile ? '8px' : '20px 24px',
                  }}>
                    {pagedRows.map((row, rowIdx) => {
                      // Detect status from row data for status dot color
                      const statusValue = row.status || row.STATUS || row.condition || row.CONDITION || "neutral";
                      const isActive = ["active", "online", "good", "operational"].some(s => statusValue.toLowerCase().includes(s));
                      const statusColor = isActive ? "#10b981" : "#6b7280";
                      const allCols = detectedColumns;
                      let tileCols: string[];
                      if (responsive.isDesktop) {
                        tileCols = allCols;
                      } else {
                        const maxFields = tileConfig.fieldsPerTile ?? Math.max(3, allCols.length);
                        tileCols = allCols.slice(0, maxFields);
                        const fixedIndex = allCols.findIndex(c => {
                          const v = (row[c] ?? "").toString().toLowerCase();
                          return v.includes("fixed");
                        });
                        if (fixedIndex !== -1) {
                          const fixedCol = allCols[fixedIndex];
                          if (!tileCols.includes(fixedCol)) {
                            tileCols = [...tileCols.slice(0, Math.max(0, tileCols.length - 1)), fixedCol];
                          }
                        }
                      }
                      return (
                        <div key={startIdx + rowIdx} className="tile-card" style={{
                          padding: responsive.isMobile ? '8px' : '16px',
                          minHeight: 'auto',
                          display: 'flex',
                          flexDirection: 'column',
                          backgroundColor: tileBackground,
                          border: tileBorder,
                          color: tileText,
                          boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.4)' : '0 8px 24px rgba(0,0,0,0.08)',
                          borderRadius: '12px',
                          transition: 'all 0.3s ease',
                          minWidth: 0,
                          overflow: 'hidden'
                        }}>
                          {/* Top colored strip */}
                          <div className="tile-card-header" style={{ height: '4px', width: '100%', background: 'linear-gradient(90deg, #d4af37 0%, #ffd700 100%)', borderRadius: '12px 12px 0 0', opacity: 0.8 }} />

                          {/* Status dot + card content */}
                          <div style={{
                            display: 'flex',
                            gap: '16px',
                            padding: '12px',
                            flexDirection: 'row',
                            minWidth: 0,
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
                                marginTop: '4px',
                                boxShadow: `0 0 12px ${statusColor}99`
                              }}
                              title={isActive ? 'Active' : 'Inactive'}
                            />

                            {/* Card Content - Horizontal Spread Layout */}
                            <div style={{
                              flex: 1,
                              display: 'grid',
                              gridTemplateColumns: responsive.isMobile
                                ? 'repeat(2, 1fr)'
                                : 'repeat(5, 1fr)',
                              gap: '16px 12px',
                              minWidth: 0,
                            }}>
                              {(responsive.isDesktop ? detectedColumns : tileCols).map((col) => (
                                <div
                                  key={`${startIdx + rowIdx}-${col}`}
                                  className="tile-field"
                                  title={row[col]}
                                  style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '4px',
                                    backgroundColor: tileFieldBackground,
                                    border: tileFieldBorder,
                                    padding: '8px 10px',
                                    borderRadius: '8px',
                                    minWidth: 0,
                                    overflow: 'hidden',
                                  }}
                                >
                                  <div className="tile-field-label" style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.5px',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    color: tileTextMuted,
                                    opacity: 0.8
                                  }}>{col}</div>
                                  <div className="tile-field-value" style={{
                                    fontSize: '13px',
                                    fontWeight: 500,
                                    color: tileFieldValueColor,
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}>{formatCellValue(row[col])}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
          {/* Pagination Controls (table view only) */}
          {viewMode === "table" && (
            <div style={{ display: 'flex', gap: responsive.isMobile ? 6 : 8, justifyContent: 'center', alignItems: 'center', marginTop: responsive.isMobile ? 6 : 8 }}>
              {(() => {
                const disabledPrev = page <= 0;
                const disabledNext = page >= totalPages - 1;
                const navButtonStyle = (disabled: boolean) => ({
                  padding: responsive.isMobile ? '4px 8px' : responsive.isTablet ? '5px 10px' : '6px 12px',
                  borderRadius: responsive.isMobile ? 6 : 8,
                  border: disabled ? '1px solid rgba(212,175,55,0.28)' : '1px solid rgba(212,175,55,0.9)',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  background: disabled
                    ? 'linear-gradient(180deg, rgba(212,175,55,0.14) 0%, rgba(212,175,55,0.08) 100%)'
                    : 'linear-gradient(180deg, #ae8625 0%, #f7ef8a 35%, #d2ac47 65%, #edc967 100%)',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: responsive.isMobile ? 12 : 13,
                  boxShadow: disabled ? 'none' : (isDark ? '0 6px 20px rgba(212,175,55,0.22)' : '0 6px 14px rgba(212,175,55,0.12)'),
                  transition: 'transform 0.08s ease, box-shadow 0.12s ease, opacity 0.12s ease',
                  minWidth: responsive.isMobile ? 56 : undefined,
                } as React.CSSProperties);

                return (
                  <>
                    <button
                      onClick={() => setPage(Math.max(0, page - 1))}
                      disabled={disabledPrev}
                      style={navButtonStyle(disabledPrev)}
                      onMouseDown={e => (e.currentTarget.style.transform = 'scale(0.98)')}
                      onMouseUp={e => (e.currentTarget.style.transform = 'scale(1)')}
                    >
                      Prev
                    </button>

                    <div style={{ fontSize: responsive.isMobile ? 11 : 12, color: tileTextMuted, padding: responsive.isMobile ? '0 6px' : undefined }}>
                      Page {page + 1} / {totalPages} — Showing {Math.min((page + 1) * LIMIT, rows.length)} of {rows.length}
                    </div>

                    <button
                      onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                      disabled={disabledNext}
                      style={navButtonStyle(disabledNext)}
                      onMouseDown={e => (e.currentTarget.style.transform = 'scale(0.98)')}
                      onMouseUp={e => (e.currentTarget.style.transform = 'scale(1)')}
                    >
                      Next
                    </button>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default TableWithTile;
