"use client";

import { useState, useEffect, useCallback } from "react";

// ── Types ─────────────────────────────────────────────────────
export interface DailyHistory {
  date:          string;
  credits_used:  number;
  audio_seconds: number;
  graph_count:   number;
  request_count: number;
  tokens_used:   number;
}

export interface UsageStats {
  credits_limit:     number;
  credits_used:      number;
  credits_remaining: number;
  audio_seconds:     number;
  audio_limit:       number;
  graph_count:       number;
  graph_limit:       number;
  request_count:     number;
  request_limit:     number;
  tokens_used:       number;
  token_limit:       number;
  tokens_remaining:  number;
  history:           DailyHistory[];
}

interface UseUsageStatsReturn {
  stats:   UsageStats | null;
  loading: boolean;
  error:   string | null;
  refetch: () => void;
}

// ── Hook ──────────────────────────────────────────────────────
export function useUsageStats(
  externalUserId: string | null,   // ← loggedInUser (client_name)
  subUserName:    string | null    // ← userIdFromUrl (sub user)
): UseUsageStatsReturn {

  const [stats,   setStats]   = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error,   setError]   = useState<string | null>(null);

  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

  const fetchStats = useCallback(async () => {

    // Don't fetch if either value is missing
    if (!externalUserId || !externalUserId.trim()) {
      setStats(null);
      return;
    }
    if (!subUserName || !subUserName.trim()) {
      setStats(null);
      return;
    }

    if (!baseUrl) {
      setError("API base URL not configured");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // ✅ Both values in URL
      const res = await fetch(
        `${baseUrl}/api/usage/${encodeURIComponent(externalUserId.trim())}/${encodeURIComponent(subUserName.trim())}`
      );

      if (!res.ok) {
        if (res.status === 404) {
          setError("No usage data found for this user");
        } else {
          setError(`Failed to fetch usage stats (${res.status})`);
        }
        setStats(null);
        return;
      }

      const data: UsageStats = await res.json();
      setStats(data);

    } catch (err) {
      console.error("❌ useUsageStats fetch failed:", err);
      setError("Failed to load usage stats. Please try again.");
      setStats(null);
    } finally {
      setLoading(false);
    }

  }, [externalUserId, subUserName, baseUrl]); // ✅ both in deps

  // Fetch on mount and whenever either value changes
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    loading,
    error,
    refetch: fetchStats,
  };
}