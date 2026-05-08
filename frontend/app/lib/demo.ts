import snapshot from "../../data/demo-snapshot.json";
import type { EventData } from "./utils";

type DemoSourceRow = {
  source_key: string;
  display_name: string;
  municipality: string;
  status: string;
  last_started_at: string | null;
  last_succeeded_at: string | null;
  last_failed_at: string | null;
  last_completed_at: string | null;
  last_error: string | null;
  last_event_count: number;
  previous_event_count: number;
  last_event_delta: number;
  last_duration_ms: number;
  freshness: string;
  age_hours: number | null;
  is_stale: boolean;
};

type DemoVenueRow = {
  venue_key: string;
  municipality: string;
  venue_name: string;
  status: string;
  last_succeeded_at: string | null;
  previous_event_count: number;
  last_event_count: number;
  last_event_delta: number;
  last_error: string | null;
};

type DemoSourceAlertRow = {
  source_key: string;
  display_name: string;
  municipality: string;
  severity: string;
  reasons: string[];
  last_error: string | null;
  last_event_count: number;
  previous_event_count: number;
  last_event_delta: number;
  freshness: string;
  last_succeeded_at: string | null;
};

type DemoVenueAlertRow = {
  venue_key: string;
  municipality: string;
  venue_name: string;
  severity: string;
  reasons: string[];
  last_error: string | null;
  last_event_count: number;
  previous_event_count: number;
  last_event_delta: number;
  last_succeeded_at: string | null;
};

type DemoSnapshot = {
  generated_at: string;
  counts: {
    events: number;
    sources: number;
    venues: number;
  };
  source_summary: {
    total: number;
    healthy: number;
    warning: number;
    stale: number;
    error: number;
    running: number;
  };
  venue_summary: {
    total: number;
    alerts: number;
  };
  source_alerts: DemoSourceAlertRow[];
  venue_alerts: DemoVenueAlertRow[];
  events: EventData[];
  sources: DemoSourceRow[];
  venues: DemoVenueRow[];
};

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export function getDemoSnapshot(): DemoSnapshot {
  return snapshot as DemoSnapshot;
}

export function getDemoEvents(): EventData[] {
  return getDemoSnapshot().events || [];
}

export function getDemoSourceAlerts(): DemoSourceAlertRow[] {
  return getDemoSnapshot().source_alerts || [];
}

export function getDemoVenueAlerts(): DemoVenueAlertRow[] {
  return getDemoSnapshot().venue_alerts || [];
}

export function getDemoSports() {
  const counts = new Map<string, number>();
  for (const event of getDemoEvents()) {
    counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([sport, count]) => ({ sport, count }))
    .sort((a, b) => b.count - a.count);
}

export function getDemoStatus() {
  const data = getDemoSnapshot();
  return {
    admin_access: false,
    status: "demo",
    last_fetched: data.generated_at,
    latest_sync_completed_at: data.generated_at,
    total_events: data.counts.events,
    source_summary: data.source_summary,
    venue_summary: data.venue_summary,
    rerun_summary: {
      changed_sources: data.sources.filter((row) => (row.last_event_delta || 0) !== 0).length,
      source_alerts: data.source_alerts.length,
      venue_alerts: data.venue_alerts.length,
      latest_completed_at: data.generated_at,
    },
  };
}
