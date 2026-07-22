"use client";

import React, { useState, useCallback, useRef } from "react";
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from "recharts";

const CHART_COLORS = {
  gold: "#d4af37",
  green: "#22c55e",
  blue: "#3b82f6",
  purple: "#8b5cf6",
  red: "#ef4444",
  orange: "#f59e0b",
  gray: "#9ca3af"
};

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={{ background: "rgba(10,10,10,0.9)", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 8, padding: "8px 12px", boxShadow: "0 4px 12px rgba(0,0,0,0.5)" }}>
        <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.7)", marginBottom: 4 }}>{data.name}</p>
        <p style={{ margin: 0, fontSize: 14, fontWeight: 800, color: data.color || "#d4af37" }}>
          {data.isCurrency ? `\u20B9 ${data.value.toLocaleString("en-IN")}` : data.value}
        </p>
      </div>
    );
  }
  return null;
};

// --- Types ---

interface AssetDetail {
  AssetName: string | null;
  AssetTagNo: string | null;
  ASDivision: string | null;
  ASDiscipline: string | null;
  EquipmentRefNo: string | null;
  LocationSite: string | null;
  BuildingName: string | null;
  SpotName: string | null;
  AssetPurcaseDate: string | null;
  AssetInstalledDate: string | null;
  TotalPPMPlanned: number | null;
  TotalNoofBreakdowns: number | null;
  TotalMaintenanceCost: number | null;
  TotalMaterialUtilizedCost: number | null;
  PlannedAsonDate: number | null;
  CompletedWo: number | null;
  PendingWo: number | null;
  PPMCompletedPerc: number | null;
  Registered: number | null;
  Completed: number | null;
  Pending: number | null;
  CCMCompletedPerc: number | null;
  AssetCalibrated: number | null;
  Active: number | null;
  Expired: number | null;
  TotalManHourUtilized: string | null;
  TotalDowntime: string | null;
  LastCalibtrationOn: string | null;
  CalibTotalDowntime: string | null;
  RemainingDays: number | null;
  Nextcalibrationon: string | null;
  TotalCost: number | null;
  PPMCost: number | null;
  PPMGeneralCost: number | null;
  PPMMaterialCost: number | null;
  PPMLabourCost: number | null;
  PPMVendorCost: number | null;
  BDMCost: number | null;
  BDMGeneralCost: number | null;
  BDMMaterialCost: number | null;
  BDMLabourCost: number | null;
  BDMVendorCost: number | null;
  CalibrationCost: number | null;
  ManhourUtilized: string | null;
  AvgMaintenanceHrs: string | null;
  MaterialQtyusedinPPM: number | null;
  MaterialQtyusedinBDM: number | null;
  ManhourUtilizedBDM: string | null;
  TotalDowntimeBDM: string | null;
  TotalMaterialQtyUtilized: number | null;
}

interface PPMFrequencyRow {
  ContractID: number;
  LocalityID: number;
  Name: string;
  Total: number;
  HOURLY: number;
  DAILY: number;
  WEEKLY: number;
  MONTHLY: number;
  QUARTERLY: number;
  HALFYEARLY: number;
  ANNUAL: number;
  BIMONTHLY: number;
  BIDAILY: number;
  TRIMESTER: number;
  BIWEEKLY: number;
  LastBDMTechRemarks: string | null;
  LastPPMTechRemarks: string | null;
}

interface PPMScheduleRow {
  FirstPPMDate: string | null;
  LastPPMDate: string | null;
  NextPPMDate: string | null;
  WorkOrderNo: string | null;
  FrequencyName: string | null;
  PMTechRemarks: string | null;
}

interface HistoryApiResponse {
  Output?: {
    status?: { code: string; message: string };
    data?: [AssetDetail[], PPMFrequencyRow[], unknown[], PPMScheduleRow[], unknown[]];
  };
  error?: string;
}

interface LifecycleDetail {
  AgedInMonths: number | null;
  AssetEOL: number | null;
  AssetPurchaseDate: string | null;
  AssetInstalledDate: string | null;
  PurchaseCost: number | null;
  InstallationCost: number | null;
  TrainingCost: number | null;
  AssetBookValue: number | null;
  LifeInMonths: number | null;
  LifeInYear: number | null;
  YearOfManuf: number | null;
  TotalBreakdown: number | null;
  BDMYearPerc: number | null;
  DepreciationPeriod: string | null;
  DepStartDate: string | null;
  DepEndDate: string | null;
  SalvageCost: number | null;
  SalvagePercentage: number | null;
  DepTotalAmount: number | null;
  AfterDepricationValue: number | null;
  ExpiryDate: string | null;
  RemainingPeriod: string | null;
  WarrActive: string | null;
  InsuranceTotalValue: number | null;
  InsuranceFrmDate: string | null;
  InsuranceToDate: string | null;
  TotalMaintenanceCost: number | null;
  UpcomingMaintenanceCost: number | null;
  MaterialCost: number | null;
  ManPowerCost: number | null;
  VendorCost: number | null;
  GeneralCost: number | null;
  MTTR: number | null;
  MTBF: number | null;
}

interface UpcomingWorkorderRow {
  Frequency: string;
  UpcomingWorkorders: number;
  ExpectedCost: number;
  AverageCost: number;
}

interface YearlyExpenseRow {
  WoYear: number;
  TotalExpenses: number;
  Analysis: number;
}

interface WorkOrderSummaryRow {
  WorkOrders: string;
  Total: number;
  OpenWo: number;
  Closed: number;
}

interface LifecycleApiResponse {
  Output?: {
    status?: { code: string; message: string };
    data?: [LifecycleDetail[], UpcomingWorkorderRow[], YearlyExpenseRow[], WorkOrderSummaryRow[], unknown[]];
  };
  error?: string;
}

interface AnalyticsData {
  history: HistoryApiResponse;
  lifecycle: LifecycleApiResponse;
}

interface AssetAnalyticsDashboardProps {
  loggedInUser: string;
  baseUrl: string;
}

// --- Helpers ---

const fmt = (val: string | number | null | undefined, fallback = "N/A"): string => {
  if (val === null || val === undefined || val === "" || val === "null") return fallback;
  return String(val);
};

const fmtNum = (val: number | null | undefined, decimals = 0): string => {
  if (val === null || val === undefined) return "N/A";
  return val.toLocaleString("en-IN", { maximumFractionDigits: decimals });
};

const fmtCurrency = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return "N/A";
  return "\u20B9 " + val.toLocaleString("en-IN");
};

const fmtPerc = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return "N/A";
  return val.toFixed(1) + "%";
};

const isValidBarcode = (val: string): boolean => {
  const trimmed = val.trim();
  if (!trimmed) return false;
  return /^\d+$/.test(trimmed);
};

// --- Sub-components ---

const StatCard = ({
  label, value, accent = false, color, small = false,
}: {
  label: string; value: string; accent?: boolean; color?: string; small?: boolean;
}) => (
  <div
    className="al-stat-card"
    style={{
      background: accent
        ? "linear-gradient(135deg, rgba(212,175,55,0.12) 0%, rgba(247,239,138,0.06) 100%)"
        : "rgba(255,255,255,0.04)",
      border: accent ? "1px solid rgba(212,175,55,0.3)" : "1px solid rgba(255,255,255,0.07)",
      borderRadius: 10,
      padding: small ? "10px 12px" : "14px 16px",
      display: "flex",
      flexDirection: "column",
      gap: 6,
      cursor: "default",
      transition: "transform 0.2s ease, box-shadow 0.2s ease",
    }}
  >
    <span style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
      {label}
    </span>
    <span style={{ fontSize: small ? 13 : 15, fontWeight: 700, color: color || (accent ? "#d4af37" : "var(--color-text, #fff)"), lineHeight: 1.2 }}>
      {value}
    </span>
  </div>
);

const InfoRow = ({ label, value }: { label: string; value: string }) => (
  <div style={{
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 0",
    borderBottom: "1px solid rgba(255,255,255,0.05)",
    gap: 12,
  }}>
    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", fontWeight: 500, flexShrink: 0 }}>{label}</span>
    <span style={{ fontSize: 13, color: "var(--color-text, #fff)", fontWeight: 600, textAlign: "right" }}>{value}</span>
  </div>
);

const SectionTitle = ({ title, subtitle }: { title: string; subtitle?: string }) => (
  <div style={{ marginBottom: 14 }}>
    <h3 style={{ margin: 0, fontSize: 12, fontWeight: 800, color: "#d4af37", textTransform: "uppercase", letterSpacing: "0.1em" }}>{title}</h3>
    {subtitle && <p style={{ margin: "3px 0 0", fontSize: 11, color: "rgba(255,255,255,0.35)" }}>{subtitle}</p>}
  </div>
);

const Card = ({ children, style, delay = 0 }: { children: React.ReactNode; style?: React.CSSProperties; delay?: number }) => (
  <div className="al-animate" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "16px 18px", animationDelay: `${delay}s`, ...style }}>
    {children}
  </div>
);

// --- Charts ---

const CostBreakdownChart = ({ data }: { data: any[] }) => {
  const filtered = data.filter(d => d.value > 0);
  if (!filtered.length) return <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "rgba(255,255,255,0.3)" }}>No cost data</div>;
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={filtered} innerRadius={60} outerRadius={80} paddingAngle={4} dataKey="value" stroke="none">
            {filtered.map((entry, index) => <Cell key={index} fill={entry.color} />)}
          </Pie>
          <RechartsTooltip content={<CustomTooltip />} isAnimationActive={false} />
          <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: 11, color: "rgba(255,255,255,0.6)" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

const ProactiveReactiveChart = ({ ppm, bdm }: { ppm: number; bdm: number }) => {
  const data = [
    { name: "Proactive (PPM)", value: ppm, color: "#10b981", isCurrency: true },
    { name: "Reactive (BDM)", value: bdm, color: CHART_COLORS.red, isCurrency: true }
  ].filter(d => d.value > 0);
  if (!data.length) return <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "rgba(255,255,255,0.3)" }}>No cost data</div>;
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} innerRadius={60} outerRadius={80} paddingAngle={4} dataKey="value" stroke="none">
            {data.map((entry, index) => <Cell key={index} fill={entry.color} />)}
          </Pie>
          <RechartsTooltip content={<CustomTooltip />} isAnimationActive={false} />
          <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: 11, color: "rgba(255,255,255,0.6)" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

const WorkOrderChart = ({ completed, pending }: { completed: number; pending: number }) => {
  const data = [
    { name: "Completed", value: completed, color: CHART_COLORS.green },
    { name: "Pending", value: pending, color: CHART_COLORS.orange }
  ].filter(d => d.value > 0);
  if (!data.length) return <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "rgba(255,255,255,0.3)" }}>No work orders</div>;
  return (
    <div style={{ width: "100%", height: 180, position: "relative" }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} innerRadius={55} outerRadius={70} paddingAngle={4} dataKey="value" stroke="none">
            {data.map((entry, index) => <Cell key={index} fill={entry.color} />)}
          </Pie>
          <RechartsTooltip content={<CustomTooltip />} isAnimationActive={false} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: "#fff", lineHeight: 1 }}>{completed + pending}</span>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 2 }}>Total WOs</span>
      </div>
    </div>
  );
};

const AssetLifeChart = ({ consumed, total }: { consumed: number; total: number }) => {
  const remaining = Math.max(total - consumed, 0);
  const data = [
    { name: "Consumed", value: consumed, color: consumed / total > 0.8 ? CHART_COLORS.red : CHART_COLORS.gold },
    { name: "Remaining", value: remaining, color: "rgba(255,255,255,0.05)" }
  ];
  return (
    <div style={{ width: "100%", height: 140, position: "relative", marginTop: 10 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} cx="50%" cy="100%" startAngle={180} endAngle={0} innerRadius={70} outerRadius={90} dataKey="value" stroke="none">
            {data.map((entry, index) => <Cell key={index} fill={entry.color} />)}
          </Pie>
          <RechartsTooltip content={<CustomTooltip />} isAnimationActive={false} />
        </PieChart>
      </ResponsiveContainer>
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", pointerEvents: "none" }}>
        <span style={{ fontSize: 24, fontWeight: 800, color: "#fff", lineHeight: 1 }}>{Math.round((consumed / total) * 100)}%</span>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 4 }}>Life Consumed</span>
      </div>
    </div>
  );
};

const ProgressBar = ({ value, max, color = "#d4af37" }: { value: number; max: number; color?: string }) => {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ background: "rgba(255,255,255,0.08)", borderRadius: 4, height: 6, overflow: "hidden" }}>
      <div style={{ width: pct + "%", height: "100%", background: "linear-gradient(90deg, " + color + "99, " + color + ")", borderRadius: 4, transition: "width 1s ease" }} />
    </div>
  );
};

const DashHeader = ({
  title, subtitle, leftBtn, rightBtn,
}: {
  title: string; subtitle?: string;
  leftBtn?: { label: string; onClick: () => void };
  rightBtn: { label: string; onClick: () => void };
}) => (
  <div style={{ padding: "16px 24px 14px", borderBottom: "1px solid rgba(212,175,55,0.15)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, flexShrink: 0 }}>
    <div>
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: "#d4af37" }}>{title}</h2>
      {subtitle && <p style={{ margin: "2px 0 0", fontSize: 12, color: "rgba(255,255,255,0.4)" }}>{subtitle}</p>}
    </div>
    <div style={{ display: "flex", gap: 8 }}>
      {leftBtn && (
        <button className="al-btn-gold" onClick={leftBtn.onClick}>{leftBtn.label}</button>
      )}
      <button className="al-btn-muted" onClick={rightBtn.onClick}>{rightBtn.label}</button>
    </div>
  </div>
);

// --- History Dashboard ---

function HistoryDashboard({ data, barcode, onViewLifecycle, onNewSearch }: {
  data: AnalyticsData; barcode: string; onViewLifecycle: () => void; onNewSearch: () => void;
}) {
  const assetDetail: AssetDetail | null = data.history?.Output?.data?.[0]?.[0] ?? null;
  const ppmFreq: PPMFrequencyRow[] = data.history?.Output?.data?.[1] ?? [];
  const ppmSchedule: PPMScheduleRow[] = data.history?.Output?.data?.[3] ?? [];

  const generated = ppmFreq.find(r => r.Name === "Generated")?.Total ?? 0;
  const carriedOut = ppmFreq.find(r => r.Name === "CarriedOut")?.Total ?? 0;
  const completedWo = assetDetail?.CompletedWo ?? 0;
  const pendingWo = assetDetail?.PendingWo ?? 0;
  const totalPlanned = assetDetail?.TotalPPMPlanned ?? 0;
  const totalWo = completedWo + pendingWo;

  const freqKeys = [
    { label: "Daily", key: "DAILY" }, { label: "Weekly", key: "WEEKLY" },
    { label: "Monthly", key: "MONTHLY" }, { label: "Quarterly", key: "QUARTERLY" },
    { label: "Half-Yearly", key: "HALFYEARLY" }, { label: "Annual", key: "ANNUAL" },
    { label: "Bi-Monthly", key: "BIMONTHLY" }, { label: "Bi-Weekly", key: "BIWEEKLY" },
  ];

  const genRow = ppmFreq.find(r => r.Name === "Generated");

  return (
    <div style={{ flex: 1, overflow: "hidden auto", padding: "0 0 24px", display: "flex", flexDirection: "column" }}>
      <DashHeader
        title="Asset History"
        subtitle={"Barcode: " + barcode + (assetDetail?.AssetTagNo ? " \u2014 " + assetDetail.AssetTagNo : "")}
        rightBtn={{ label: "New Search", onClick: onNewSearch }}
      />
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18, flex: 1 }}>

        <Card delay={0.1}>
          <SectionTitle title="Asset Overview" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
            <StatCard label="Asset Name" value={fmt(assetDetail?.AssetName)} accent />
            <StatCard label="Asset Tag No" value={fmt(assetDetail?.AssetTagNo)} accent />
            <StatCard label="Equipment Ref" value={fmt(assetDetail?.EquipmentRefNo)} />
            <StatCard label="Division" value={fmt(assetDetail?.ASDivision)} />
            <StatCard label="Discipline" value={fmt(assetDetail?.ASDiscipline)} />
            <StatCard label="Site" value={fmt(assetDetail?.LocationSite)} />
            <StatCard label="Building" value={fmt(assetDetail?.BuildingName)} />
            <StatCard label="Location" value={fmt(assetDetail?.SpotName)} />
            <StatCard label="Purchase Date" value={fmt(assetDetail?.AssetPurcaseDate)} />
            <StatCard label="Installation Date" value={fmt(assetDetail?.AssetInstalledDate)} />
          </div>
        </Card>

        <Card delay={0.2}>
          <SectionTitle title="Maintenance Summary" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10, marginBottom: 14 }}>
            <StatCard label="Total Planned PPM" value={fmtNum(totalPlanned)} accent color="#3b82f6" />
            <StatCard label="Planned As-Of Today" value={fmtNum(assetDetail?.PlannedAsonDate)} color="#8b5cf6" />
            <StatCard label="Completed Work Orders" value={fmtNum(completedWo)} color="#22c55e" />
            <StatCard label="Pending Work Orders" value={fmtNum(pendingWo)} color="#f59e0b" />
            <StatCard label="Breakdown Count" value={fmtNum(assetDetail?.TotalNoofBreakdowns)} color="#ef4444" />
            <StatCard label="Calibration Status" value={assetDetail?.AssetCalibrated ? "Calibrated" : "Not Calibrated"} color={assetDetail?.AssetCalibrated ? "#22c55e" : "#ef4444"} />
          </div>
          {totalWo > 0 && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>Work Order Completion</span>
                <span style={{ fontSize: 11, color: "#22c55e", fontWeight: 700 }}>{Math.round((completedWo / totalWo) * 100)}%</span>
              </div>
              <ProgressBar value={completedWo} max={totalWo} color="#22c55e" />
            </div>
          )}
        </Card>

        <Card delay={0.3}>
          <SectionTitle title="Cost Analysis" />
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
              <StatCard label="Total Cost" value={fmtCurrency(assetDetail?.TotalCost)} accent color="#d4af37" />
              <StatCard label="PPM Cost" value={fmtCurrency(assetDetail?.PPMCost)} color="#3b82f6" />
              <StatCard label="BDM Cost" value={fmtCurrency(assetDetail?.BDMCost)} color="#8b5cf6" />
              <StatCard label="Vendor Cost" value={fmtCurrency((assetDetail?.PPMVendorCost ?? 0) + (assetDetail?.BDMVendorCost ?? 0))} />
              <StatCard label="Labour Cost" value={fmtCurrency((assetDetail?.PPMLabourCost ?? 0) + (assetDetail?.BDMLabourCost ?? 0))} />
              <StatCard label="Material Cost" value={fmtCurrency((assetDetail?.PPMMaterialCost ?? 0) + (assetDetail?.BDMMaterialCost ?? 0))} />
              <StatCard label="General Cost" value={fmtCurrency((assetDetail?.PPMGeneralCost ?? 0) + (assetDetail?.BDMGeneralCost ?? 0))} />
              <StatCard label="Calibration Cost" value={fmtCurrency(assetDetail?.CalibrationCost)} />
            </div>
            <div className="al-grid-2">
              <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: "12px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", textAlign: "center" }}>Cost Breakdown</p>
                <CostBreakdownChart data={[
                  { name: "Vendor Cost", value: (assetDetail?.PPMVendorCost ?? 0) + (assetDetail?.BDMVendorCost ?? 0), color: CHART_COLORS.purple, isCurrency: true },
                  { name: "Labour Cost", value: (assetDetail?.PPMLabourCost ?? 0) + (assetDetail?.BDMLabourCost ?? 0), color: CHART_COLORS.blue, isCurrency: true },
                  { name: "Material Cost", value: (assetDetail?.PPMMaterialCost ?? 0) + (assetDetail?.BDMMaterialCost ?? 0), color: CHART_COLORS.gold, isCurrency: true },
                  { name: "General Cost", value: (assetDetail?.PPMGeneralCost ?? 0) + (assetDetail?.BDMGeneralCost ?? 0), color: CHART_COLORS.gray, isCurrency: true },
                  { name: "Calibration Cost", value: assetDetail?.CalibrationCost || 0, color: CHART_COLORS.orange, isCurrency: true }
                ]} />
              </div>
              <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: "12px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", textAlign: "center" }}>Proactive vs Reactive</p>
                <ProactiveReactiveChart ppm={assetDetail?.PPMCost || 0} bdm={assetDetail?.BDMCost || 0} />
              </div>
            </div>
          </div>
        </Card>

        <Card delay={0.4}>
          <SectionTitle title="Maintenance Status" />
          <div className="al-grid-2">
            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "14px" }}>
              <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Planned vs Completed</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <WorkOrderChart completed={completedWo} pending={totalPlanned - completedWo} />
              </div>
            </div>
            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "14px" }}>
              <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Generated vs Carried Out</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.6)" }}>Generated</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#3b82f6" }}>{fmtNum(generated)}</span>
                  </div>
                  <ProgressBar value={generated} max={generated || 1} color="#3b82f6" />
                </div>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.6)" }}>Carried Out</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#22c55e" }}>{fmtNum(carriedOut)}</span>
                  </div>
                  <ProgressBar value={carriedOut} max={generated || 1} color="#22c55e" />
                </div>
              </div>
            </div>
          </div>

          {genRow && (
            <div style={{ marginTop: 14 }}>
              <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Maintenance Frequency Distribution</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(90px, 1fr))", gap: 8 }}>
                {freqKeys.map(({ label, key }) => {
                  const val = (genRow as unknown as Record<string, number>)[key] ?? 0;
                  if (!val) return null;
                  return (
                    <div key={key} style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.15)", borderRadius: 8, padding: "8px 10px", textAlign: "center" }}>
                      <div style={{ fontSize: 16, fontWeight: 800, color: "#d4af37" }}>{val}</div>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", marginTop: 2 }}>{label}</div>
                    </div>
                  );
                }).filter(Boolean)}
              </div>
            </div>
          )}
        </Card>

        {ppmSchedule.length > 0 && (
          <Card delay={0.5}>
            <SectionTitle title="Upcoming Maintenance" />
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(212,175,55,0.2)" }}>
                    {["Work Order No", "Frequency", "Last PPM Date", "Next PPM Date", "Technician Remarks"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "#d4af37", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ppmSchedule.map((row, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td style={{ padding: "9px 10px", color: "var(--color-text, #fff)", fontWeight: 600 }}>{fmt(row.WorkOrderNo)}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.7)" }}>{fmt(row.FrequencyName)}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.7)" }}>{fmt(row.LastPPMDate)}</td>
                      <td style={{ padding: "9px 10px", color: "#22c55e", fontWeight: 600 }}>{fmt(row.NextPPMDate)}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.5)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{fmt(row.PMTechRemarks)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <Card delay={0.6}>
          <SectionTitle title="Asset Health Summary" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
            <StatCard label="Total Downtime (PPM)" value={fmt(assetDetail?.TotalDowntime)} />
            <StatCard label="Total Downtime (BDM)" value={fmt(assetDetail?.TotalDowntimeBDM)} />
            <StatCard label="Total Man Hours" value={fmt(assetDetail?.TotalManHourUtilized)} accent />
            <StatCard label="Avg Maint. Hrs" value={fmt(assetDetail?.AvgMaintenanceHrs)} />
            <StatCard label="Man Hours (PPM)" value={fmt(assetDetail?.ManhourUtilized)} />
            <StatCard label="Man Hours (BDM)" value={fmt(assetDetail?.ManhourUtilizedBDM)} />
            <StatCard label="Material Used (PPM)" value={fmtNum(assetDetail?.MaterialQtyusedinPPM)} />
            <StatCard label="Material Used (BDM)" value={fmtNum(assetDetail?.MaterialQtyusedinBDM)} />
            <StatCard label="Last Calibration" value={fmt(assetDetail?.LastCalibtrationOn)} />
            <StatCard label="Next Calibration" value={fmt(assetDetail?.Nextcalibrationon)} />
            <StatCard label="Calib. Downtime" value={fmt(assetDetail?.CalibTotalDowntime)} />
            <StatCard label="CCM Complete %" value={assetDetail?.CCMCompletedPerc != null ? assetDetail.CCMCompletedPerc + "%" : "N/A"} color="#3b82f6" />
            <StatCard label="Remaining Days" value={assetDetail?.RemainingDays !== null && assetDetail?.RemainingDays !== undefined ? assetDetail.RemainingDays + " days" : "N/A"} color="#f59e0b" />
            <StatCard label="PPM Complete %" value={fmtPerc(assetDetail?.PPMCompletedPerc)} accent />
          </div>
          {ppmFreq.length > 0 && (ppmFreq[0]?.LastPPMTechRemarks || ppmFreq[0]?.LastBDMTechRemarks) && (
            <div style={{ marginTop: 14, background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "12px 14px" }}>
              <p style={{ margin: "0 0 6px", fontSize: 10, fontWeight: 700, color: "#d4af37", textTransform: "uppercase", letterSpacing: "0.08em" }}>Last Technician Remarks</p>
              {ppmFreq[0]?.LastPPMTechRemarks && <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)", marginBottom: 4 }}><span style={{ color: "rgba(255,255,255,0.35)", fontSize: 10 }}>PPM: </span>{ppmFreq[0].LastPPMTechRemarks}</div>}
              {ppmFreq[0]?.LastBDMTechRemarks && <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)" }}><span style={{ color: "rgba(255,255,255,0.35)", fontSize: 10 }}>BDM: </span>{ppmFreq[0].LastBDMTechRemarks}</div>}
            </div>
          )}
        </Card>

        {/* 9.7 Navigation CTA */}
        <button className="al-cta-btn" onClick={onViewLifecycle}>
          View Asset Lifecycle &nbsp; &#8594;
        </button>
      </div>
    </div>
  );
}

// --- Lifecycle Dashboard ---

function LifecycleDashboard({ data, barcode, onBackToHistory, onNewSearch }: {
  data: AnalyticsData; barcode: string; onBackToHistory: () => void; onNewSearch: () => void;
}) {
  const lc: LifecycleDetail | null = data.lifecycle?.Output?.data?.[0]?.[0] ?? null;
  const upcoming: UpcomingWorkorderRow[] = data.lifecycle?.Output?.data?.[1] ?? [];
  const yearlyExpense: YearlyExpenseRow[] = data.lifecycle?.Output?.data?.[2] ?? [];
  const woSummary: WorkOrderSummaryRow[] = data.lifecycle?.Output?.data?.[3] ?? [];

  const woRow = woSummary.find(r => r.WorkOrders === "No. of PPM Till Date");
  const totalWo = woRow?.Total ?? 0;
  const openWo = woRow?.OpenWo ?? 0;
  const closedWo = woRow?.Closed ?? 0;

  const remainingLife = (lc?.LifeInMonths !== null && lc?.LifeInMonths !== undefined && lc?.AgedInMonths !== null && lc?.AgedInMonths !== undefined)
    ? Math.max(lc.LifeInMonths - lc.AgedInMonths, 0)
    : null;
  const showLifeChart = (lc?.LifeInMonths ?? 0) > 0 && lc?.AgedInMonths != null;

  return (
    <div style={{ flex: 1, overflow: "hidden auto", display: "flex", flexDirection: "column", padding: "0 0 24px" }}>
      <DashHeader
        title="Asset Lifecycle"
        subtitle={"Barcode: " + barcode}
        leftBtn={{ label: "\u2190 Asset History", onClick: onBackToHistory }}
        rightBtn={{ label: "New Search", onClick: onNewSearch }}
      />
      <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18, flex: 1 }}>

        <Card delay={0.1}>
          <SectionTitle title="Lifecycle Overview" />
          <div className={showLifeChart ? "al-grid-2" : ""}>
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10, marginBottom: 14 }}>
                <StatCard label="Asset Age" value={lc?.AgedInMonths !== null && lc?.AgedInMonths !== undefined ? lc.AgedInMonths + " months" : "N/A"} accent />
                <StatCard label="Expected Life" value={lc?.LifeInYear !== null && lc?.LifeInYear !== undefined ? lc.LifeInYear + " years" : "N/A"} accent />
                <StatCard label="Remaining Life" value={remainingLife !== null ? remainingLife + " months" : "N/A"} color="#22c55e" />
                <StatCard label="Purchase Date" value={fmt(lc?.AssetPurchaseDate)} />
                <StatCard label="Installation Date" value={fmt(lc?.AssetInstalledDate)} />
                <StatCard label="Book Value" value={fmtCurrency(lc?.AssetBookValue)} color="#d4af37" />
                <StatCard label="Purchase Cost" value={fmtCurrency(lc?.PurchaseCost)} />
                <StatCard label="Installation Cost" value={fmtCurrency(lc?.InstallationCost)} />
                <StatCard label="Training Cost" value={fmtCurrency(lc?.TrainingCost)} />
                <StatCard label="Year of Manufacture" value={lc?.YearOfManuf ? String(lc.YearOfManuf) : "N/A"} />
              </div>
            </div>
            {showLifeChart && (
              <div>
                <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: "12px", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <AssetLifeChart consumed={lc!.AgedInMonths!} total={lc!.LifeInMonths!} />
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card delay={0.2}>
          <SectionTitle title="Depreciation" />
          <div className="al-grid-2">
            <div>
              <InfoRow label="Depreciation Period" value={fmt(lc?.DepreciationPeriod)} />
              <InfoRow label="Start Date" value={fmt(lc?.DepStartDate)} />
              <InfoRow label="End Date" value={fmt(lc?.DepEndDate)} />
              <InfoRow label="Salvage %" value={lc?.SalvagePercentage !== null && lc?.SalvagePercentage !== undefined ? lc.SalvagePercentage + "%" : "N/A"} />
            </div>
            <div className="al-grid-2" style={{ gap: 8, alignContent: "start" }}>
              <StatCard label="Total Depreciation" value={fmtCurrency(lc?.DepTotalAmount)} accent small />
              <StatCard label="Salvage Value" value={fmtCurrency(lc?.SalvageCost)} small />
              <StatCard label="After Depreciation" value={fmtCurrency(lc?.AfterDepricationValue)} color="#22c55e" small />
              <StatCard label="Asset EOL (Yr)" value={lc?.AssetEOL !== null && lc?.AssetEOL !== undefined ? String(lc.AssetEOL) : "N/A"} color="#f59e0b" small />
            </div>
          </div>
        </Card>

        <Card delay={0.3}>
          <SectionTitle title="Warranty & Insurance" />
          <div className="al-grid-2">
            <div>
              <p style={{ margin: "0 0 6px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Warranty</p>
              <InfoRow label="Status" value={fmt(lc?.WarrActive)} />
              <InfoRow label="Expiry Date" value={fmt(lc?.ExpiryDate)} />
              <InfoRow label="Remaining Period" value={fmt(lc?.RemainingPeriod)} />
            </div>
            <div>
              <p style={{ margin: "0 0 6px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Insurance</p>
              <InfoRow label="Total Coverage" value={fmtCurrency(lc?.InsuranceTotalValue)} />
              <InfoRow label="From Date" value={fmt(lc?.InsuranceFrmDate)} />
              <InfoRow label="To Date" value={fmt(lc?.InsuranceToDate)} />
            </div>
          </div>
        </Card>

        <Card delay={0.4}>
          <SectionTitle title="Maintenance Cost Analysis" />
          <div className="al-grid-2">
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
                <StatCard label="Total Maintenance" value={fmtCurrency(lc?.TotalMaintenanceCost)} accent color="#d4af37" />
                <StatCard label="Upcoming Maintenance" value={fmtCurrency(lc?.UpcomingMaintenanceCost)} color="#f59e0b" />
                <StatCard label="General Cost" value={fmtCurrency(lc?.GeneralCost)} />
                <StatCard label="Vendor Cost" value={fmtCurrency(lc?.VendorCost)} />
                <StatCard label="Material Cost" value={fmtCurrency(lc?.MaterialCost)} />
                <StatCard label="Labour Cost" value={fmtCurrency(lc?.ManPowerCost)} />
              </div>
            </div>
            <div>
              <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: "12px", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <p style={{ margin: "0 0 10px", fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.08em", textAlign: "center" }}>Maintenance Cost Breakdown</p>
                <CostBreakdownChart data={[
                  { name: "Vendor Cost", value: lc?.VendorCost || 0, color: CHART_COLORS.purple, isCurrency: true },
                  { name: "Labour Cost", value: lc?.ManPowerCost || 0, color: CHART_COLORS.blue, isCurrency: true },
                  { name: "Material Cost", value: lc?.MaterialCost || 0, color: CHART_COLORS.gold, isCurrency: true },
                  { name: "General Cost", value: lc?.GeneralCost || 0, color: CHART_COLORS.gray, isCurrency: true }
                ]} />
              </div>
            </div>
          </div>
        </Card>

        <Card delay={0.5}>
          <SectionTitle title="Reliability Metrics" />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
            <StatCard label="MTTR" value={lc?.MTTR !== null && lc?.MTTR !== undefined ? lc.MTTR + " hrs" : "N/A"} accent color="#3b82f6" />
            <StatCard label="MTBF" value={lc?.MTBF !== null && lc?.MTBF !== undefined ? lc.MTBF + " hrs" : "N/A"} accent color="#22c55e" />
            <StatCard label="Breakdown %" value={fmtPerc(lc?.BDMYearPerc)} color="#ef4444" />
            <StatCard label="Total Breakdowns" value={fmtNum(lc?.TotalBreakdown)} />
          </div>
        </Card>

        {upcoming.length > 0 && (
          <Card delay={0.5}>
            <SectionTitle title="Upcoming Maintenance Forecast" />
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(212,175,55,0.2)" }}>
                    {["Frequency", "Upcoming Work Orders", "Expected Cost", "Average Cost"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "#d4af37", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {upcoming.map((row, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td style={{ padding: "9px 10px", color: "var(--color-text, #fff)", fontWeight: 600 }}>{fmt(row.Frequency)}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.7)" }}>{fmtNum(row.UpcomingWorkorders)}</td>
                      <td style={{ padding: "9px 10px", color: "#f59e0b", fontWeight: 600 }}>{fmtCurrency(row.ExpectedCost)}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.7)" }}>{fmtCurrency(row.AverageCost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {yearlyExpense.length > 0 && (
          <Card delay={0.6}>
            <SectionTitle title="Yearly Cost Analysis" />
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(212,175,55,0.2)" }}>
                    {["Year", "Total Expenses", "Analysis (Variance)"].map(h => (
                      <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: "#d4af37", textTransform: "uppercase", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {yearlyExpense.map((yr, idx) => (
                    <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <td style={{ padding: "9px 10px", color: "var(--color-text, #fff)", fontWeight: 600 }}>{yr.WoYear}</td>
                      <td style={{ padding: "9px 10px", color: "rgba(255,255,255,0.9)", fontWeight: 500 }}>{fmtCurrency(yr.TotalExpenses)}</td>
                      <td style={{ padding: "9px 10px", color: yr.Analysis < 0 ? "#ef4444" : "#22c55e", fontWeight: 600 }}>{fmtCurrency(yr.Analysis)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {(totalWo > 0 || openWo > 0 || closedWo > 0) && (
          <Card delay={0.5}>
            <SectionTitle title="Work Order Summary" />
            <div className="al-grid-2">
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <StatCard label="Total Work Orders" value={fmtNum(totalWo)} accent />
                <StatCard label="Open" value={fmtNum(openWo)} color="#f59e0b" />
                <StatCard label="Closed" value={fmtNum(closedWo)} color="#22c55e" />
              </div>
              {totalWo > 0 && (
                <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, padding: "12px", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <WorkOrderChart completed={closedWo} pending={openWo} />
                </div>
              )}
            </div>
          </Card>
        )}

      </div>
    </div>
  );
}

// --- Main ---

type View = "welcome" | "loading" | "history" | "lifecycle";

export default function AssetAnalyticsDashboard({ loggedInUser, baseUrl, onExit }: AssetAnalyticsDashboardProps & { onExit?: () => void }) {
  const [view, setView] = useState<View>("welcome");
  const [barcode, setBarcode] = useState("");
  const [inputError, setInputError] = useState("");
  const [fetchError, setFetchError] = useState("");
  const [data, setData] = useState<AnalyticsData | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleAnalyze = useCallback(async () => {
    const trimmed = barcode.trim();
    if (!trimmed) { setInputError("Please enter an Asset Barcode number."); return; }
    if (!isValidBarcode(trimmed)) { setInputError("Invalid format. Enter only the numeric barcode (e.g. 4109211108)."); return; }
    setInputError("");
    setFetchError("");
    setView("loading");
    try {
      const res = await fetch(baseUrl + "/api/asset-analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ barcode: trimmed, userName: loggedInUser }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.detail || "HTTP " + res.status);
      }
      const result = await res.json();
      if (result.error) throw new Error(result.error);
      setData(result as AnalyticsData);
      setView("history");
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Failed to fetch asset data. Please try again.");
      setView("welcome");
    }
  }, [barcode, baseUrl, loggedInUser]);

  const handleReset = () => {
    setView("welcome");
    setData(null);
    setBarcode("");
    setFetchError("");
    setInputError("");
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  if (view === "loading") {
    return (
      <div style={rootStyle}>
        <style>{STYLES}</style>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {[0, 1, 2].map(i => (
              <span key={i} style={{ width: 10, height: 10, borderRadius: "50%", background: "#d4af37", animation: "al-bounce 1.2s ease-in-out " + (i * 0.2) + "s infinite", display: "inline-block" }} />
            ))}
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "rgba(255,255,255,0.4)", fontWeight: 500 }}>Fetching asset data...</p>
          {onExit && (
            <button onClick={onExit} style={{ marginTop: 20, background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.6)", padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>
              Cancel
            </button>
          )}
        </div>
      </div>
    );
  }

  if (view === "history" && data) {
    return (
      <div style={rootStyle}>
        <style>{STYLES}</style>
        <HistoryDashboard data={data} barcode={barcode} onViewLifecycle={() => setView("lifecycle")} onNewSearch={handleReset} />
      </div>
    );
  }

  if (view === "lifecycle" && data) {
    return (
      <div style={rootStyle}>
        <style>{STYLES}</style>
        <LifecycleDashboard data={data} barcode={barcode} onBackToHistory={() => setView("history")} onNewSearch={handleReset} />
      </div>
    );
  }

  return (
    <div style={rootStyle}>
      <style>{STYLES}</style>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "32px 24px" }}>
        <div style={{ width: 54, height: 54, borderRadius: 16, background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.3)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20, boxShadow: "0 0 32px rgba(212,175,55,0.12)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#d4af37" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>
        <h1 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 800, background: "linear-gradient(135deg, #AE8625 0%, #F7EF8A 50%, #D2AC47 100%)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", textAlign: "center" }}>
          Asset Lens
        </h1>
        <p style={{ margin: "0 0 30px", fontSize: 13, color: "rgba(255,255,255,0.45)", textAlign: "center", lineHeight: 1.65, maxWidth: 380 }}>
          I am Asset Lens, designed to retrieve asset history and lifecycle information. Enter a barcode to begin.
        </p>

        <div style={{ width: "100%", maxWidth: 400 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, background: "rgba(255,255,255,0.05)", border: inputError ? "1px solid rgba(239,68,68,0.55)" : "1px solid rgba(255,255,255,0.12)", borderRadius: 12, padding: "4px 14px", transition: "border-color 0.2s" }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              inputMode="numeric"
              value={barcode}
              onChange={e => { setBarcode(e.target.value); if (inputError) setInputError(""); }}
              onKeyDown={e => e.key === "Enter" && handleAnalyze()}
              placeholder="Enter asset barcode (e.g. 4109211108)"
              autoFocus
              autoComplete="off"
              spellCheck={false}
              style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--color-text, #fff)", fontSize: 14, padding: "12px 0", fontFamily: "inherit", fontWeight: 500 }}
            />
            {barcode && (
              <button onClick={() => { setBarcode(""); setInputError(""); inputRef.current?.focus(); }} style={{ background: "transparent", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", fontSize: 16, padding: "2px 4px", lineHeight: "1" }}>&#10005;</button>
            )}
          </div>
          {inputError && <p style={{ margin: "7px 0 0 2px", fontSize: 12, color: "#ef4444" }}>{inputError}</p>}
          {fetchError && (
            <div style={{ margin: "10px 0 0", padding: "10px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 8, fontSize: 12, color: "#ef4444" }}>{fetchError}</div>
          )}
          <button
            onClick={handleAnalyze}
            disabled={!barcode.trim()}
            style={{ marginTop: 12, width: "100%", padding: "13px 20px", background: barcode.trim() ? "linear-gradient(135deg, rgba(212,175,55,0.22) 0%, rgba(247,239,138,0.1) 100%)" : "rgba(255,255,255,0.04)", border: barcode.trim() ? "1px solid rgba(212,175,55,0.45)" : "1px solid rgba(255,255,255,0.08)", borderRadius: 10, color: barcode.trim() ? "#d4af37" : "rgba(255,255,255,0.25)", fontSize: 14, fontWeight: 700, cursor: barcode.trim() ? "pointer" : "default", letterSpacing: "0.03em", transition: "all 0.2s ease", fontFamily: "inherit" }}
          >
            Analyze Asset
          </button>
          {onExit && (
            <button
              onClick={onExit}
              style={{ marginTop: 12, width: "100%", padding: "12px 20px", background: "transparent", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 10, color: "rgba(255,255,255,0.6)", fontSize: 14, fontWeight: 600, cursor: "pointer", transition: "all 0.2s ease", fontFamily: "inherit" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.4)"; e.currentTarget.style.color = "#fff"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)"; e.currentTarget.style.color = "rgba(255,255,255,0.6)"; }}
            >
              Exit Asset Lens
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const rootStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  width: "100%",
  height: "100%",
  overflow: "hidden",
  color: "var(--color-text, #fff)",
  fontFamily: "var(--font-sometype-mono), system-ui, sans-serif",
  background: "transparent",
};

const STYLES = `
  @keyframes al-bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
  }
  @keyframes fade-in-up {
    from { opacity: 0; transform: translateY(15px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .al-animate {
    opacity: 0;
    animation: fade-in-up 0.5s ease-out forwards;
  }
  .al-stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.2);
  }
  .al-btn-gold {
    background: transparent;
    border: 1px solid rgba(212,175,55,0.4);
    color: #d4af37;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
  }
  .al-btn-gold:hover { background: rgba(212,175,55,0.1); }
  .al-btn-muted {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.15);
    color: rgba(255,255,255,0.55);
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
  }
  .al-btn-muted:hover { border-color: #d4af37; color: #d4af37; }
  .al-cta-btn {
    width: 100%;
    padding: 15px 24px;
    background: linear-gradient(135deg, rgba(212,175,55,0.2) 0%, rgba(247,239,138,0.1) 100%);
    border: 1px solid rgba(212,175,55,0.5);
    border-radius: 12px;
    color: #d4af37;
    font-size: 15px;
    font-weight: 800;
    cursor: pointer;
    letter-spacing: 0.04em;
    transition: all 0.25s ease;
    font-family: inherit;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }
  .al-cta-btn:hover {
    background: linear-gradient(135deg, rgba(212,175,55,0.32) 0%, rgba(247,239,138,0.16) 100%);
    box-shadow: 0 0 24px rgba(212,175,55,0.22);
    transform: translateY(-1px);
  }
  .al-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .al-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  @media (max-width: 600px) {
    .al-grid-2, .al-grid-3 {
      grid-template-columns: 1fr !important;
    }
    .al-stat-card {
      padding: 12px !important;
    }
  }
`;
