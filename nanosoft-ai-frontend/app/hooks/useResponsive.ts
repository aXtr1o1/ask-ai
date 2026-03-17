'use client';

import { useState, useEffect } from 'react';

export type ScreenType = 'mobile' | 'tablet' | 'desktop';

interface ResponsiveInfo {
  isMobile: boolean;      // width ≤ 640px — narrow phones, single column layout
  isTablet: boolean;      // 641px ≤ width ≤ 1024px — tablets, two-column layout
  isDesktop: boolean;     // width > 1024px — desktop/laptop, full layout
  screen: ScreenType;     // Current screen type for conditional rendering
  width: number;          // Actual window.innerWidth for custom calculations
  height: number;         // Actual window.innerHeight for custom calculations
}


export function useResponsive(): ResponsiveInfo {
  // Calculate initial state based on actual window width
  const getInitialState = (): ResponsiveInfo => {
    if (typeof window === 'undefined') {
      // SSR: default to desktop for initial render
      return {
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        screen: 'desktop',
        width: 1024,
        height: 768,
      };
    }

    const width = window.innerWidth;
    const height = window.innerHeight;
    
    if (width <= 640) {
      return {
        isMobile: true,
        isTablet: false,
        isDesktop: false,
        screen: 'mobile',
        width,
        height,
      };
    } else if (width <= 1024) {
      return {
        isMobile: false,
        isTablet: true,
        isDesktop: false,
        screen: 'tablet',
        width,
        height,
      };
    } else {
      return {
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        screen: 'desktop',
        width,
        height,
      };
    }
  };

  const [responsive, setResponsive] = useState<ResponsiveInfo>(getInitialState());

  useEffect(() => {
    let debounceTimer: NodeJS.Timeout;

    const handleResize = () => {
      // Debounce: wait 150ms after resize stops before updating
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const width = window.innerWidth;
        const height = window.innerHeight;

        let screen: ScreenType;
        let isMobile: boolean;
        let isTablet: boolean;
        let isDesktop: boolean;

        // Determine screen type based on width
        if (width <= 640) {  // Changed from < 640 to <= 640 to match CSS @media (max-width: 640px)
          screen = 'mobile';
          isMobile = true;
          isTablet = false;
          isDesktop = false;
        } else if (width <= 1024) {  // Changed to match @media (max-width: 1024px)
          screen = 'tablet';
          isMobile = false;
          isTablet = true;
          isDesktop = false;
        } else {
          screen = 'desktop';
          isMobile = false;
          isTablet = false;
          isDesktop = true;
        }

        setResponsive({
          isMobile,
          isTablet,
          isDesktop,
          screen,
          width,
          height,
        });
      }, 150);
    };

    // Set initial size immediately
    handleResize();

    // Add resize listener
    window.addEventListener('resize', handleResize);
    
    // Add orientationchange listener for mobile devices (crucial for rotation detection!)
    window.addEventListener('orientationchange', handleResize);

    // Cleanup
    return () => {
      clearTimeout(debounceTimer);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleResize);
    };
  }, []);

  return responsive;
}

/**
 * Alternative: Media Query matcher hook
 * Use this if you want CSS-based media queries with React
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    
    // Set initial state
    if (media.matches !== matches) {
      setMatches(media.matches);
    }

    // Create listener
    const listener = (e: MediaQueryListEvent) => {
      setMatches(e.matches);
    };

    // Add listener
    media.addEventListener('change', listener);

    // Cleanup
    return () => media.removeEventListener('change', listener);
  }, [matches, query]);

  return matches;
}

/**
 * Get auto-adjusted responsive sizes for typography
 * Returns font sizes that scale based on screen resolution
 */
export function getResponsiveFontSizes(screen: ScreenType): {
  heading: string;
  subheading: string;
  body: string;
  small: string;
  caption: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        heading: '20px',
        subheading: '16px',
        body: '13px',
        small: '12px',
        caption: '11px',
      };
    case 'tablet':
      return {
        heading: '24px',
        subheading: '18px',
        body: '14px',
        small: '13px',
        caption: '12px',
      };
    case 'desktop':
      return {
        heading: '28px',
        subheading: '20px',
        body: '16px',
        small: '14px',
        caption: '13px',
      };
  }
}

/**
 * Get auto-adjusted responsive spacing (padding, margin, gap)
 * Returns consistent spacing values based on screen size
 */
export function getResponsiveSpacing(screen: ScreenType): {
  xs: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        xs: '4px',
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '20px',
      };
    case 'tablet':
      return {
        xs: '6px',
        sm: '12px',
        md: '16px',
        lg: '20px',
        xl: '24px',
      };
    case 'desktop':
      return {
        xs: '8px',
        sm: '16px',
        md: '20px',
        lg: '24px',
        xl: '32px',
      };
  }
}

/**
 * Get auto-adjusted responsive tile grid configuration
 * Returns grid-template-columns for tile cards
 */
export function getResponsiveTileGrid(screen: ScreenType): {
  columns: string;
  gap: string;
  minWidth: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        columns: 'repeat(auto-fit, minmax(100px, 1fr))',
        gap: '10px',
        minWidth: '100px',
      };
    case 'tablet':
      return {
        columns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '16px',
        minWidth: '120px',
      };
    case 'desktop':
      return {
        columns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '20px',
        minWidth: '140px',
      };
  }
}

/**
 * Get auto-adjusted responsive message bubble sizing
 * Returns dimensions for chat message bubbles
 */
export function getResponsiveMessageBubble(screen: ScreenType): {
  fontSize: string;
  padding: string;
  borderRadius: string;
  maxWidth: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        fontSize: '13px',
        padding: '8px 12px',
        borderRadius: '12px',
        maxWidth: '90%',
      };
    case 'tablet':
      return {
        fontSize: '14px',
        padding: '10px 14px',
        borderRadius: '14px',
        maxWidth: '85%',
      };
    case 'desktop':
      return {
        fontSize: '15px',
        padding: '12px 16px',
        borderRadius: '16px',
        maxWidth: '75%',
      };
  }
}

/**
 * Get auto-adjusted responsive chart/graph configuration
 * Returns dimensions for charts based on screen size
 */
export function getResponsiveChart(screen: ScreenType): {
  maxWidth: string;
  height: string;
  overflowX: string;
  titleSize: string;
  showLegend: boolean;
} {
  switch (screen) {
    case 'mobile':
      return {
        maxWidth: '100%',
        height: '350px',
        overflowX: 'auto',
        titleSize: '14px',
        showLegend: false,
      };
    case 'tablet':
      return {
        maxWidth: '500px',
        height: '420px',
        overflowX: 'hidden',
        titleSize: '16px',
        showLegend: true,
      };
    case 'desktop':
      return {
        maxWidth: '600px',
        height: '520px',
        overflowX: 'hidden',
        titleSize: '18px',
        showLegend: true,
      };
  }
}

/**
 * Get auto-adjusted responsive container dimensions
 * Returns width and padding based on sidebar configuration
 */
export function getResponsiveContainer(screen: ScreenType): {
  maxWidth: string;
  padding: string;
  borderRadius: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        maxWidth: '100%',
        padding: '12px',
        borderRadius: '8px',
      };
    case 'tablet':
      return {
        maxWidth: 'calc(100vw - 180px)',
        padding: '16px',
        borderRadius: '12px',
      };
    case 'desktop':
      return {
        maxWidth: 'calc(100vw - 260px)',
        padding: '20px',
        borderRadius: '16px',
      };
  }
}

/**
 * Get auto-adjusted responsive table configuration
 * Returns table sizing based on screen resolution
 */
export function getResponsiveTable(screen: ScreenType): {
  fontSize: string;
  padding: string;
  compactMode: boolean;
  columnsVisible: number;
} {
  switch (screen) {
    case 'mobile':
      return {
        fontSize: '12px',
        padding: '6px 10px',
        compactMode: true,
        columnsVisible: 2,
      };
    case 'tablet':
      return {
        fontSize: '13px',
        padding: '8px 12px',
        compactMode: false,
        columnsVisible: 3,
      };
    case 'desktop':
      return {
        fontSize: '14px',
        padding: '10px 14px',
        compactMode: false,
        columnsVisible: 5,
      };
  }
}

/**
 * Get auto-adjusted responsive sidebar configuration
 * Returns sidebar dimensions and behavior
 */
export function getResponsiveSidebar(screen: ScreenType): {
  width: string;
  isVisible: boolean;
  isOverlay: boolean;
  position: 'fixed' | 'relative';
} {
  switch (screen) {
    case 'mobile':
      return {
        width: '240px',
        isVisible: false,
        isOverlay: true,
        position: 'fixed',
      };
    case 'tablet':
      return {
        width: '180px',
        isVisible: true,
        isOverlay: false,
        position: 'relative',
      };
    case 'desktop':
      return {
        width: '260px',
        isVisible: true,
        isOverlay: false,
        position: 'relative',
      };
  }
}

/**
 * Get auto-adjusted tile data visibility
 * Returns which data fields and how many to show on tiles based on screen size
 * This makes tiles display different amounts of data - not just sizing
 */
export function getResponsiveTileDataConfig(screen: ScreenType): {
  showFields: string[];      // Which data fields to display on tile
  maxFields: number;         // Maximum fields to show per tile
  showLabelOnly: boolean;    // Show key name only on mobile
  compact: boolean;          // Compact value display (abbreviated on mobile)
  truncateLength: number;    // Max characters for values
} {
  switch (screen) {
    case 'mobile':
      return {
        showFields: ['label', 'value', 'status'],  // Show only essential fields
        maxFields: 2,                               // Max 2 data fields per tile
        showLabelOnly: false,
        compact: true,                              // Abbreviate values (e.g., "1.2K" instead of "1234")
        truncateLength: 15,                         // Truncate long values to 15 chars
      };
    case 'tablet':
      return {
        showFields: ['label', 'value', 'status', 'unit'],
        maxFields: 3,
        showLabelOnly: false,
        compact: false,
        truncateLength: 25,
      };
    case 'desktop':
      return {
        showFields: ['label', 'value', 'status', 'unit', 'change', 'date'],
        maxFields: 6,                               // Show all possible fields
        showLabelOnly: false,
        compact: false,
        truncateLength: 50,
      };
  }
}

/**
 * Get auto-adjusted table column visibility
 * Returns which columns to show/hide based on screen resolution
 * Makes table show different columns - not just resizing them
 */
export function getResponsiveTableColumns(screen: ScreenType): {
  visibleColumns: string[];        // Column names to show
  maxColumns: number;               // Maximum columns to display
  hideSecondaryData: boolean;      // Hide secondary/detail columns on mobile
  rowHeight: string;
  cellPadding: string;
  fontSize: string;
  abbreviateHeaders: boolean;      // Use short column names
} {
  switch (screen) {
    case 'mobile':
      return {
        visibleColumns: ['name', 'value', 'status'],  // Show only essential columns
        maxColumns: 3,
        hideSecondaryData: true,                       // Hide date, description, etc
        rowHeight: '36px',
        cellPadding: '6px 8px',
        fontSize: '12px',
        abbreviateHeaders: true,                       // Use "Val" instead of "Value"
      };
    case 'tablet':
      return {
        visibleColumns: ['name', 'status', 'value', 'unit', 'date'],
        maxColumns: 5,
        hideSecondaryData: false,
        rowHeight: '40px',
        cellPadding: '8px 12px',
        fontSize: '13px',
        abbreviateHeaders: false,
      };
    case 'desktop':
      return {
        visibleColumns: ['name', 'status', 'value', 'unit', 'change', 'date', 'description'],
        maxColumns: 7,                                // Show all available columns
        hideSecondaryData: false,
        rowHeight: '44px',
        cellPadding: '10px 14px',
        fontSize: '14px',
        abbreviateHeaders: false,
      };
  }
}

export function getResponsiveChartDisplay(screen: ScreenType): {
  alignment: 'flex-start' | 'center' | 'flex-end';  // Where chart is positioned
  marginX: string;                                   // Horizontal margin auto-center
  marginY: string;                                   // Vertical margin
  legendPosition: 'bottom' | 'right' | 'hidden';    // Where legend appears
  showGrid: boolean;                                 // Show background grid
  showTooltip: boolean;                             // Show value tooltips
  animationEnabled: boolean;                        // Enable chart animations
  responsiveWidth: string;                          // Chart container width
  containerJustify: 'center' | 'flex-start' | 'space-between';
} {
  switch (screen) {
    case 'mobile':
      return {
        alignment: 'flex-start',                     // Align to left on mobile
        marginX: '0px',                              // No auto margin - full left side
        marginY: '0px',
        legendPosition: 'hidden',                    // Hide legend to save space
        showGrid: false,                             // Hide grid lines for clarity
        showTooltip: true,
        animationEnabled: false,                     // Disable animations on mobile for performance
        responsiveWidth: '100%',
        containerJustify: 'flex-start',              // Left-align container on mobile
      };
    case 'tablet':
      return {
        alignment: 'center',
        marginX: 'auto',
        marginY: '12px',
        legendPosition: 'bottom',                    // Legend below chart
        showGrid: true,
        showTooltip: true,
        animationEnabled: true,
        responsiveWidth: '90%',
        containerJustify: 'center',
      };
    case 'desktop':
      return {
        alignment: 'center',
        marginX: 'auto',
        marginY: '16px',
        legendPosition: 'right',                     // Legend to the side
        showGrid: true,
        showTooltip: true,
        animationEnabled: true,
        responsiveWidth: '100%',
        containerJustify: 'center',
      };
  }
}

/**
 * Get responsive pie chart sizing
 * Ensures pie charts don't overflow on mobile with fixed minWidth
 */
export function getResponsivePieChartSize(screen: ScreenType): {
  containerMaxWidth: string;
  containerMinWidth: string;
  height: string;
  chartWidth: string;
  chartHeight: number;
} {
  switch (screen) {
    case 'mobile':
      return {
        containerMaxWidth: '100%',
        containerMinWidth: '0px',           // No minimum - allows full mobile width
        height: '300px',
        chartWidth: '100%',
        chartHeight: 300,
      };
    case 'tablet':
      return {
        containerMaxWidth: '500px',
        containerMinWidth: '500px',
        height: '350px',
        chartWidth: '100%',
        chartHeight: 350,
      };
    case 'desktop':
      return {
        containerMaxWidth: '600px',
        containerMinWidth: '600px',
        height: '400px',
        chartWidth: '100%',
        chartHeight: 400,
      };
  }
}

/**
 * Get auto-adjusted data formatting for responses
 * Returns how to format numbers, dates, and values based on screen size
 * Compact numbers on mobile (1.2K instead of 1234), full on desktop
 */
export function getResponsiveDataFormat(screen: ScreenType): {
  numberFormat: 'compact' | 'full';          // 1.2K vs 1234
  dateFormat: 'short' | 'full';              // 3/17 vs March 17, 2026
  decimalPlaces: number;                     // How many decimal places to show
  abbreviateUnits: boolean;                  // "hrs" vs "hours"
  showFullLabels: boolean;                   // Full text vs abbreviations
} {
  switch (screen) {
    case 'mobile':
      return {
        numberFormat: 'compact',              // 1.2K, 3.5M, etc
        dateFormat: 'short',                  // 3/17 or Mar 17
        decimalPlaces: 1,                     // 1.2 not 1.234
        abbreviateUnits: true,                // hrs, min, sec
        showFullLabels: false,                // Use short text
      };
    case 'tablet':
      return {
        numberFormat: 'full',
        dateFormat: 'short',                  // March 17
        decimalPlaces: 2,                     // 1.23
        abbreviateUnits: false,               // hours, minutes
        showFullLabels: true,
      };
    case 'desktop':
      return {
        numberFormat: 'full',                 // Full numbers with commas
        dateFormat: 'full',                   // March 17, 2026
        decimalPlaces: 2,                     // 1.23 with full precision
        abbreviateUnits: false,               // Complete unit names
        showFullLabels: true,                 // Show everything
      };
  }
}

/**
 * Get auto-adjusted tile card display configuration
 * Returns how to display tile VALUES and FIELDS - not just grid sizing
 * Controls what data appears on each tile card
 */
export function getResponsiveTileDisplay(screen: ScreenType): {
  fieldsPerTile: number;                    // How many data fields per tile
  fontSizeLabel: string;
  fontSizeValue: string;
  fontSizeUnit: string;
  valueFormat: 'compact' | 'full';         // 1.2K vs 1234.56
  showStatusDot: boolean;                  // Show green/red status indicator
  showUnit: boolean;                       // Show measurement unit
  showChange: boolean;                     // Show % change indicator
  cardHeight: string;
  cardPadding: string;
} {
  switch (screen) {
    case 'mobile':
      return {
        fieldsPerTile: 2,                              // Label + Value only
        fontSizeLabel: '10px',
        fontSizeValue: '14px',
        fontSizeUnit: '9px',
        valueFormat: 'compact',                        // 1.2K
        showStatusDot: true,                           // Show status indicator
        showUnit: false,                               // Hide units to save space
        showChange: false,                             // Don't show % change
        cardHeight: '100px',
        cardPadding: '12px',
      };
    case 'tablet':
      return {
        fieldsPerTile: 3,                              // Label + Value + Unit
        fontSizeLabel: '11px',
        fontSizeValue: '16px',
        fontSizeUnit: '10px',
        valueFormat: 'full',
        showStatusDot: true,
        showUnit: true,                                // Show units
        showChange: false,
        cardHeight: '110px',
        cardPadding: '14px',
      };
    case 'desktop':
      return {
        fieldsPerTile: 4,                              // Label + Value + Unit + Change
        fontSizeLabel: '12px',
        fontSizeValue: '18px',
        fontSizeUnit: '11px',
        valueFormat: 'full',
        showStatusDot: true,
        showUnit: true,
        showChange: true,                              // Show % change (↑/↓)
        cardHeight: '120px',
        cardPadding: '16px',
      };
  }
}

/**
 * Format number based on screen size responsiveness
 * Converts 1234567 to "1.2M" on mobile, "1,234,567" on desktop
 */
export function formatResponsiveNumber(
  value: number,
  screen: ScreenType,
  decimals?: number
): string {
  const config = getResponsiveDataFormat(screen);
  
  if (config.numberFormat === 'compact') {
    if (value >= 1000000) {
      return (value / 1000000).toFixed(decimals || 1) + 'M';
    } else if (value >= 1000) {
      return (value / 1000).toFixed(decimals || 1) + 'K';
    }
    return value.toString();
  }
  
  // Full format with commas
  return value.toLocaleString('en-US', { maximumFractionDigits: decimals || 2 });
}

/**
 * Filter tile fields based on screen size
 * Returns only the fields that should be visible on this screen
 * Usage: const visibleFields = getVisibleTileFields(tileData, responsive.screen);
 */
export function getVisibleTileFields(
  tileData: Record<string, any>,
  screen: ScreenType
): Record<string, any> {
  const config = getResponsiveTileDataConfig(screen);
  const result: Record<string, any> = {};
  
  // Only include fields that should be shown
  config.showFields.forEach(field => {
    if (tileData.hasOwnProperty(field)) {
      result[field] = tileData[field];
    }
  });
  
  return result;
}

/**
 * Filter table columns based on screen size
 * Returns only the columns that should be visible on this screen
 * Usage: const visibleCols = getVisibleTableColumns(tableData, responsive.screen);
 */
export function getVisibleTableColumns(
  columnNames: string[],
  screen: ScreenType
): string[] {
  const config = getResponsiveTableColumns(screen);
  
  // Return only columns that exist in both list and config
  return columnNames.filter(col => 
    config.visibleColumns.includes(col) && 
    columnNames.indexOf(col) < config.maxColumns
  );
}

/**
 * SMART WRAPPER: Only filter columns on mobile/tablet, keep desktop full
 * Desktop always shows ALL columns (original behavior)
 * Mobile/Tablet shows reduced columns only
 */
export function getSmartVisibleColumns(
  columnNames: string[],
  screen: ScreenType
): string[] {
  // Desktop: show all columns
  if (screen === 'desktop') {
    return columnNames;
  }
  
  // Mobile/Tablet: apply responsive filtering
  return getVisibleTableColumns(columnNames, screen);
}

/**
 * SMART WRAPPER: Only filter tile fields on mobile/tablet, keep desktop full
 * Desktop always shows ALL fields (original behavior)
 * Mobile/Tablet shows reduced fields only
 */
export function getSmartVisibleTileFields(
  tileData: Record<string, any>,
  screen: ScreenType
): Record<string, any> {
  // Desktop: show all fields
  if (screen === 'desktop') {
    return tileData;
  }
  
  // Mobile/Tablet: apply responsive filtering
  return getVisibleTileFields(tileData, screen);
}

/**
 * SMART WRAPPER: Get tile display config that only reduces on mobile/tablet
 * Desktop gets full display settings, mobile/tablet get compact settings
 */
export function getSmartTileDisplay(screen: ScreenType) {
  // Desktop: show everything
  if (screen === 'desktop') {
    return {
      fieldsPerTile: 999,                          // Show all fields
      fontSizeLabel: '12px',
      fontSizeValue: '18px',
      fontSizeUnit: '11px',
      valueFormat: 'full' as const,               // Full numbers
      showStatusDot: true,
      showUnit: true,                             // Show units
      showChange: true,                           // Show change %
      cardHeight: 'auto',                         // Auto height
      cardPadding: '16px',                        // Full padding
    };
  }
  
  // Mobile/Tablet: apply responsive reduction
  return getResponsiveTileDisplay(screen);
}

/**
 * SMART WRAPPER: Get table config that only reduces on mobile/tablet
 * Desktop keeps full display, mobile/tablet get compact display
 */
export function getSmartTableConfig(screen: ScreenType) {
  // Desktop: show everything at normal size
  if (screen === 'desktop') {
    return {
      fontSize: '14px',
      padding: '10px 14px',
      compactMode: false,
      columnsVisible: 999,                        // Show all
    };
  }
  
  // Mobile/Tablet: apply responsive reduction
  return getResponsiveTable(screen);
}

/**
 * SMART WRAPPER: Get data format that only compacts on mobile/tablet
 * Desktop shows full format, mobile/tablet show compact format
 */
export function getSmartDataFormat(screen: ScreenType) {
  // Desktop: full format always
  if (screen === 'desktop') {
    return {
      numberFormat: 'full' as const,              // Full numbers with commas
      dateFormat: 'full' as const,                // Full dates
      decimalPlaces: 2,                           // Full precision
      abbreviateUnits: false,                     // Full unit names
      showFullLabels: true,                       // Show everything
    };
  }
  
  // Mobile/Tablet: apply responsive compacting
  return getResponsiveDataFormat(screen);
}

/**
 * SMART WRAPPER: Format number - only compact on mobile, full on desktop
 * Shows "1.2K" on mobile, "1234" on desktop
 */
export function getSmartFormattedNumber(
  value: number,
  screen: ScreenType,
  decimals?: number
): string {
  const config = getSmartDataFormat(screen);
  
  if (config.numberFormat === 'compact') {
    if (value >= 1000000) {
      return (value / 1000000).toFixed(decimals || 1) + 'M';
    } else if (value >= 1000) {
      return (value / 1000).toFixed(decimals || 1) + 'K';
    }
    return value.toString();
  }
  
  // Full format with commas
  return value.toLocaleString('en-US', { maximumFractionDigits: decimals || 2 });
}
