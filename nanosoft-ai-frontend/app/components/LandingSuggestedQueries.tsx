"use client";

import { useMemo, useState } from "react";
import { IconNumbers, IconTable, IconFileDescription, IconChartBar, IconLayoutGrid, IconBulb } from "@tabler/icons-react";

export type SuggestedQueryGroup = {
  id: string;
  label: string;
  icon: React.ReactNode;
  queries: string[];
};

/** Mock prompts per group — replace with API/config later */
export const LANDING_SUGGESTED_QUERY_GROUPS: SuggestedQueryGroup[] = [
  {
    id: "count",
    label: "COUNT",
    icon: <IconNumbers size={16} stroke={1.5} />,
    queries: [
      "How many assets are registered in the system?",
      "Count assets grouped by building or location",
      "What is the total number of active equipment records?",
    ],
  },
  {
    id: "large-dataset",
    label: "LARGE DATASET",
    icon: <IconTable size={16} stroke={1.5} />,
    queries: [
      "Show all assets in a detailed table with tags, barcodes, and status",
      "List the full equipment inventory with every available column",
      "Return a large dataset of maintenance and asset records",
    ],
  },
  {
    id: "summary",
    label: "SUMMARY",
    icon: <IconFileDescription size={16} stroke={1.5} />,
    queries: [
      "Summarize asset distribution across all sites and floors",
      "Give me a high-level overview of HVAC and electrical assets",
      "Brief summary of compliance and operational status for equipment",
      "Provide a concise summary of asset conditions and maintenance needs",
      "Summarize the key insights about our asset inventory and maintenance backlog",
      "Give me a quick summary of asset health and upcoming maintenance tasks",
      "Provide a brief overview of our asset management status and priorities",
      "Summarize the current state of our asset inventory and maintenance schedule",
      "Give me a high-level summary of our asset portfolio and maintenance needs",
      "Provide a concise summary of our asset management status and upcoming maintenance tasks",
      "Summarize the key insights about our asset inventory, maintenance backlog, and compliance status",
      "Give me a quick summary of our asset health, maintenance needs, and compliance status",
      "Provide a brief overview of our asset management status, including inventory, maintenance schedule, and compliance status",
      "Summarize the current state of our asset inventory, maintenance schedule, and compliance status in a concise overview",
    ],
  },
];

export const ADVANCE_SUGGESTED_QUERY_GROUPS: SuggestedQueryGroup[] = [
  {
    id: "business-analysis",
    label: "BUSINESS ANALYSIS",
    icon: <IconChartBar size={16} stroke={1.5} />,
    queries: [
      "Top five localities by total asset count",
      "Top five equipment types by asset count",
      "BDM complaint types by occurrence and percentage",
      "Monthly maintenance workload trends for BDM and PPM",
      "Asset priority distribution by count and percentage",
    ],
  },
  {
    id: "employee-details",
    label: "EMPLOYEE DETAILS",
    icon: <IconTable size={16} stroke={1.5} />,
    queries: [
      "Which employees handle the highest number of work orders?",
      "Across buildings, which employees have the widest assignment coverage?",
      "By maintenance type, which employees handle the most work?",
      "Among open orders, which employees have the largest backlog?",
      "Based on completed orders, which employees have the highest volume?",
    ],
  },
  {
    id: "building-information",
    label: "BUILDING INFORMATION",
    icon: <IconLayoutGrid size={16} stroke={1.5} />,
    queries: [
      "Which buildings contain the highest number of assets?",
      "Across maintenance activities, which buildings have the highest workload?",
      "By complaint frequency, which buildings experience the most recurring issues?",
      "Among aging assets, which buildings have the greatest concentration?",
      "Based on overall risk, which buildings require the highest priority?",
    ],
  },
  {
    id: "technician-analysis",
    label: "TECHNICIAN ANALYSIS",
    icon: <IconBulb size={16} stroke={1.5} />,
    queries: [
      "Which technicians handle the highest overall maintenance workload?",
      "Across equipment types, which technicians have the strongest experience?",
      "By complaint category, which technicians handle the most cases?",
      "Among repeat repairs, which technicians receive the most assignments?",
      "Based on maintenance tasks, which technicians show the strongest specialization?",
    ],
  },
];

type LandingSuggestedQueriesProps = {
  onSelect: (text: string) => void;
  disabled?: boolean;
  isAdvanceAskAI?: boolean;
};

export default function LandingSuggestedQueries({
  onSelect,
  disabled = false,
  isAdvanceAskAI = false,
}: LandingSuggestedQueriesProps) {
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  const activeGroups = isAdvanceAskAI ? ADVANCE_SUGGESTED_QUERY_GROUPS : LANDING_SUGGESTED_QUERY_GROUPS;

  const activeGroup = useMemo(
    () =>
      activeGroupId
        ? activeGroups.find((g) => g.id === activeGroupId) ??
        null
        : null,
    [activeGroupId, activeGroups]
  );

  const isPanelOpen = !!activeGroup;

  return (
    <div className="landing-suggested-queries" aria-label="Suggested questions">
      <div className="landing-suggested-row">
        {activeGroups.map((group) => {
          const isActive = activeGroupId === group.id;

          return (
            <button
              key={group.id}
              type="button"
              className={
                "landing-suggested-group-toggle" +
                (isActive ? " landing-suggested-group-toggle--active" : "")
              }
              disabled={disabled}
              aria-pressed={isActive}
              onClick={() => setActiveGroupId(isActive ? null : group.id)}
              title={`Show ${group.label} suggestions`}
            >
              <span className="landing-suggested-group-icon" aria-hidden>
                {group.icon}
              </span>
              {group.label}
            </button>
          );
        })}
      </div>

      <div
        className={
          "landing-suggested-panel" + (isPanelOpen ? " landing-suggested-panel--open" : "")
        }
        role="region"
        aria-label="Suggestions list"
        aria-hidden={!isPanelOpen}
      >
        <div className="landing-suggested-panel-header">
          <div className="landing-suggested-panel-title">
            <span className="landing-suggested-group-icon" aria-hidden>
              {activeGroup?.icon}
            </span>
            <span>{activeGroup?.label ?? ""}</span>
          </div>

          <button
            type="button"
            className="landing-suggested-panel-close"
            onClick={() => setActiveGroupId(null)}
            aria-label="Close suggestions"
            tabIndex={isPanelOpen ? 0 : -1}
          >
            X
          </button>
        </div>

        <div className="landing-suggested-panel-list">
          {(activeGroup?.queries ?? []).map((q) => (
            <button
              key={q}
              type="button"
              className="landing-suggested-panel-item"
              disabled={disabled}
              title={q}
              onClick={() => {
                onSelect(q);
                setActiveGroupId(null);
              }}
            >
              {q.length > 74 ? `${q.slice(0, 72)}...` : q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
