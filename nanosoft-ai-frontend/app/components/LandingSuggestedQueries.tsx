"use client";

import { useMemo, useState } from "react";
import { IconNumbers, IconTable, IconFileDescription } from "@tabler/icons-react";

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
    ],
  },
];

type LandingSuggestedQueriesProps = {
  onSelect: (text: string) => void;
  disabled?: boolean;
};

export default function LandingSuggestedQueries({
  onSelect,
  disabled = false,
}: LandingSuggestedQueriesProps) {
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);

  const activeGroup = useMemo(
    () =>
      activeGroupId
        ? LANDING_SUGGESTED_QUERY_GROUPS.find((g) => g.id === activeGroupId) ??
          null
        : null,
    [activeGroupId]
  );

  const isPanelOpen = !!activeGroup;

  return (
    <div className="landing-suggested-queries" aria-label="Suggested questions">
      <div className="landing-suggested-row">
        {LANDING_SUGGESTED_QUERY_GROUPS.map((group) => {
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
