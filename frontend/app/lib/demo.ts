import type { EventData } from "./utils";

export type DemoSourceRow = {
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

export type DemoVenueRow = {
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

export type DemoSourceAlertRow = {
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

export type DemoVenueAlertRow = {
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

export type DemoCampSourceRow = {
  source_key: string;
  name: string;
  municipality: string;
  venue_names: string[];
  primary_url: string;
  registration_url: string;
  automation_status: "active" | "partial" | "planned";
  scrape_strategy: string;
  sync_source_key: string;
  tags: string[];
};

export type DemoSnapshot = {
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
  camp_sources?: DemoCampSourceRow[];
  sources: DemoSourceRow[];
  venues: DemoVenueRow[];
};

const explicitDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const hasHostedApi = Boolean(process.env.NEXT_PUBLIC_API_URL);
const isVercelRuntime = process.env.VERCEL === "1";

export const DEMO_MODE = explicitDemoMode || (isVercelRuntime && !hasHostedApi);

// Upcoming events travel to the browser as a compact table (see packEvents in
// snapshot.server.ts): repeated strings are sent once and referenced by index.
export type PackedEvents = {
  v: [string, string][]; // [venue_name, municipality]
  u: string[]; // booking URLs
  t: string[]; // titles
  e: [number, number, string, string, number, string, string, number, string, string][];
};

export function unpackEvents(packed: PackedEvents): EventData[] {
  return packed.e.map(([id, title, sport, offering, venue, start, end, url, price, facility]) => {
    const [venueName, municipality] = packed.v[venue];
    const day = start.slice(0, 10);
    return {
      id,
      source_id: "",
      title: packed.t[title],
      sport_type: sport,
      offering_type: offering,
      venue_name: venueName,
      facility_name: facility,
      center_id: 0,
      start_time: `${start}:00`,
      end_time: end ? `${day} ${end}:00` : "",
      price,
      description: "",
      booking_url: packed.u[url],
      source: "",
      municipality,
      last_fetched: "",
    };
  });
}

export async function fetchDemoEvents(): Promise<EventData[]> {
  const response = await fetch("/events.json");
  if (!response.ok) throw new Error(`Could not load schedules (${response.status})`);
  return unpackEvents((await response.json()) as PackedEvents);
}
