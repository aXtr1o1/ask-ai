"use client";

import React, { useState, useEffect, useMemo } from "react";
import { IconList, IconLayoutGrid, IconDownload } from "@tabler/icons-react";
import { useTheme } from "@/app/components/useTheme";
import { useResponsive, getResponsiveTable, getResponsiveTileDisplay, getSmartVisibleColumns } from "@/app/hooks/useResponsive";

export type TableWithTileRow = Record<string, any>;

interface TableWithTileProps {
  rows: TableWithTileRow[];
  columns?: string[];
  title?: string;
  htmlTableContent?: string; // Old HTML table format
  /** When set, pagination shows "Showing X of totalCount" (preview of a larger result set). */
  totalCount?: number;
  showOnlyTiles?: boolean;
  /** Explicit flag: renders space booking bullet-list tiles instead of normal pill grid */
  isSpaceBooking?: boolean;
}

const TableWithTile = React.memo(function TableWithTile({
  rows,
  columns,
  title = "Data",
  htmlTableContent,
  totalCount,
  showOnlyTiles = false,
  isSpaceBooking = false,
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
  const [viewMode, setViewMode] = useState<"table" | "tile">(showOnlyTiles ? "tile" : "table");

  useEffect(() => {
    if (showOnlyTiles) {
      setViewMode("tile");
    }
  }, [showOnlyTiles]);

  const [page, setPage] = useState(0);
  const LIMIT = 100;


  // Extract non-table content from htmlTableContent to show as a header/summary
  const summaryContent = useMemo(() => {
    if (!htmlTableContent) return null;
    // Remove the table part to keep only the summary/context
    const summary = htmlTableContent.replace(/<div class="large-dataset-wrapper">[\s\S]*?<\/div>/i, "")
      .replace(/<div class="table-wrapper">[\s\S]*?<\/div>/i, "")
      .trim();
    return summary || null;
  }, [htmlTableContent]);



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

  // Use explicit prop — falls back to column sniffing if prop not provided
  const isSpaceBookingData = isSpaceBooking;

  // Pagination: compute the slice of rows to display
  const totalPages = Math.max(1, Math.ceil(rows.length / LIMIT));
  const displayTotal =
    totalCount != null && totalCount > rows.length ? totalCount : rows.length;
  const visibleCount = Math.min((page + 1) * LIMIT, rows.length);
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
    if (typeof val === 'boolean') return val ? 'True' : 'False';
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

  // Download handler to export data as Excel with bold headers
  /* changes done by megnathan: Updated handleDownload to show success toast only after file is actually saved or when download starts for fallback. */
  const handleDownload = async () => {
    const headers = detectedColumns;
    const htmlRows = rows.map(row =>
      `<tr>${headers.map(col => {
        const val = row[col];
        const formatted = formatCellValue(val);
        // Escape special HTML characters
        const escaped = ('' + formatted)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
        return `<td>${escaped}</td>`;
      }).join('')}</tr>`
    ).join('');

    const htmlContent = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
      <head>
        <meta charset="utf-8">
        <!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>Sheet1</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->
        <style>
          th { font-weight: bold; background-color: #f3f4f6; text-align: left; padding: 8px; }
          td { padding: 4px; }
        </style>
      </head>
      <body>
        <table>
          <thead>
            <tr>
              ${headers.map(col => `<th>${col}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${htmlRows}
          </tbody>
        </table>
      </body>
      </html>
    `;
    const blob = new Blob([htmlContent], { type: 'application/vnd.ms-excel' });

    let savedName = "Nano data.xls";
    let isFallback = false;

    // Try to use File System Access API (Save As dialog)
    if (typeof window !== "undefined" && "showSaveFilePicker" in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: "Nano data.xls",
          types: [{
            description: 'Excel File',
            accept: { 'application/vnd.ms-excel': ['.xls'] },
          }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        savedName = handle.name;
        isFallback = false;
      } catch (err) {
        // If user cancelled, just return
        if ((err as Error).name === 'AbortError') return;
        console.warn("File picker failed, falling back to default download.", err);
        // Fallback
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "Nano data.xls");
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        isFallback = true;
      }
    } else {
      // Fallback for browsers without File System Access API
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", "Nano data.xls");
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      isFallback = true;
    }

    // Show toast notification
    const isDark = document.documentElement.getAttribute("data-theme") !== "light";
    const bg = isDark ? "rgba(28, 28, 30, 0.97)" : "rgba(255, 255, 255, 0.97)";
    const border = isDark ? "rgba(212, 175, 55, 0.5)" : "rgba(180, 140, 30, 0.4)";
    const textColor = isDark ? "#ffffff" : "#1a1a1a";
    const accent = isDark ? "#D4AF37" : "#9A7B20";
    const shadow = isDark ? "0 8px 32px rgba(0,0,0,0.5)" : "0 8px 32px rgba(0,0,0,0.15)";

    const toast = document.createElement("div");
    toast.style.cssText = `
      position: fixed;
      bottom: 32px;
      left: 50%;
      transform: translateX(-50%) translateY(20px);
      background: ${bg};
      border: 1px solid ${border};
      border-radius: 12px;
      padding: 14px 24px;
      color: ${textColor};
      font-size: 14px;
      font-weight: 500;
      box-shadow: ${shadow};
      z-index: 99999;
      display: flex;
      align-items: center;
      gap: 10px;
      opacity: 0;
      transition: opacity 0.3s ease, transform 0.3s ease;
      pointer-events: none;
      white-space: nowrap;
      backdrop-filter: blur(8px);
    `;

    /* changes done by megnathan: Vary toast message based on whether save is confirmed or just started */
    if (isFallback) {
      toast.innerHTML = `<span style="color:${accent};font-size:18px;">ℹ</span> <span>Download started...</span>`;
    } else {
      toast.innerHTML = `<span style="color:${accent};font-size:18px;">✓</span> <span>Saved as <strong style="color:${accent};">"${savedName}"</strong></span>`;
    }

    document.body.appendChild(toast);
    requestAnimationFrame(() => {
      toast.style.opacity = "1";
      toast.style.transform = "translateX(-50%) translateY(0)";
    });
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(-50%) translateY(20px)";
      setTimeout(() => document.body.removeChild(toast), 350);
    }, 3000);
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
        {!showOnlyTiles && (
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

            {/* Download Button */}
            <button
              onClick={handleDownload}
              title="Download data"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '4px 8px',
                borderRadius: '6px',
                background: 'rgba(174, 134, 37, 0.3)',
                color: '#1f2937',
                border: '1px solid #d4af37',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 600,
                transition: 'all 0.2s ease-in-out',
                backdropFilter: 'blur(8px)',
                transform: 'scale(1)',
                opacity: 0.8,
              }}
              onMouseDown={e => {
                (e.target as HTMLElement).style.transform = 'scale(0.95)';
              }}
              onMouseUp={e => {
                (e.target as HTMLElement).style.transform = 'scale(1)';
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.opacity = '1';
                (e.currentTarget as HTMLElement).style.boxShadow = '0 0 12px rgba(212, 175, 55, 0.6)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.opacity = '0.8';
                (e.currentTarget as HTMLElement).style.boxShadow = 'none';
              }}
            >
              <span style={{
                display: 'flex',
                alignItems: 'center',
              }}>
                <IconDownload size={14} />
              </span>
            </button>
          </div>
        )}

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
                              fontWeight: 600,
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
                      if (isSpaceBookingData) {
                        // ── Space Booking: bullet list layout ──────────────────
                        return (
                          <div key={startIdx + rowIdx} className="tile-card animate-fadeIn" style={{
                            padding: responsive.isMobile ? '12px 16px' : '16px 20px',
                            backgroundColor: tileBackground,
                            border: tileBorder,
                            color: tileText,
                            boxShadow: isDark ? '0 8px 24px rgba(0,0,0,0.4)' : '0 8px 24px rgba(0,0,0,0.08)',
                            borderRadius: '12px',
                            transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
                            minWidth: 0,
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.borderColor = 'var(--color-primary, #d4af37)';
                            e.currentTarget.style.transform = 'translateY(-2px)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.borderColor = '';
                            e.currentTarget.style.transform = 'translateY(0)';
                          }}
                          >
                            <ul style={{
                              listStyle: 'none',
                              margin: 0,
                              padding: 0,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '6px',
                            }}>
                              {detectedColumns.map((col) => {
                                const val = formatCellValue(row[col]);
                                return (
                                  <li key={col} style={{ display: 'flex', alignItems: 'baseline', gap: '8px', minWidth: 0 }}>
                                    <span style={{
                                      width: '5px', height: '5px', borderRadius: '50%',
                                      background: 'rgba(212,175,55,0.7)', flexShrink: 0, marginTop: '5px',
                                    }} />
                                    <span style={{
                                      fontSize: '11px', fontWeight: 700, textTransform: 'uppercase',
                                      letterSpacing: '0.5px', color: tileTextMuted, flexShrink: 0, whiteSpace: 'nowrap',
                                    }}>
                                      {col}:
                                    </span>
                                    <span style={{
                                      fontSize: '13px', fontWeight: 500, color: tileFieldValueColor,
                                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}>
                                      {val}
                                    </span>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        );
                      }

                      // ── Normal Ask AI: original pill grid layout ────────────
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

                            {/* Card Content - Pill grid layout */}
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
                                    opacity: 0.8,
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
                      Page {page + 1} / {totalPages} — Showing {visibleCount} of {displayTotal}
                      {displayTotal > rows.length ? " (preview)" : ""}
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
