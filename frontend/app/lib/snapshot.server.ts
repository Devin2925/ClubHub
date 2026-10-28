// Server-only: importing the snapshot here keeps the multi-megabyte JSON out of
// browser bundles. Client components get data through props or /events.json.
import snapshot from "../../data/demo-snapshot.json";
import type {
  DemoCampSourceRow,
  DemoSnapshot,
  DemoSourceAlertRow,
  DemoVenueAlertRow,
  PackedEvents,
} from "./demo";
import { getDateKey, getTodayKey, nowScheduleKey, type EventData } from "./utils";

export function getDemoSnapshot(): DemoSnapshot {
  return snapshot as unknown as DemoSnapshot;
}

// The snapshot is frozen at export time, so hide anything that has already finished.
export function getDemoEvents(): EventData[] {
  const todayKey = getTodayKey();
  return (getDemoSnapshot().events || []).filter(
    (event) => getDateKey(event.end_time || event.start_time) >= todayKey
  );
}

export function getDemoCampSources(): DemoCampSourceRow[] {
  return getDemoSnapshot().camp_sources || [];
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
  // The export writes naive UTC; mark it so browsers don't read it as local time.
  const generatedAt = /[zZ]|[+-]\d{2}:\d{2}$/.test(data.generated_at) ? data.generated_at : `${data.generated_at}Z`;
  return {
    admin_access: false,
    status: "demo",
    last_fetched: generatedAt,
    latest_sync_completed_at: generatedAt,
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

// Upcoming events that haven't finished yet, in the browser's compact format.
export function packEvents(events: EventData[]): PackedEvents {
  const packed: PackedEvents = { v: [], u: [], t: [], e: [] };
  const venueIndex = new Map<string, number>();
  const urlIndex = new Map<string, number>();
  const titleIndex = new Map<string, number>();
  const indexOf = <T,>(map: Map<string, number>, list: T[], key: string, value: T) => {
    let index = map.get(key);
    if (index === undefined) {
      index = list.length;
      map.set(key, index);
      list.push(value);
    }
    return index;
  };
  const sorted = [...events].sort((a, b) => a.start_time.localeCompare(b.start_time));
  for (const event of sorted) {
    const start = event.start_time.replace("T", " ").slice(0, 16);
    const end = (event.end_time || "").replace("T", " ").slice(11, 16);
    packed.e.push([
      event.id,
      indexOf(titleIndex, packed.t, event.title, event.title),
      event.sport_type,
      event.offering_type || "",
      indexOf(venueIndex, packed.v, `${event.venue_name}|${event.municipality}`, [event.venue_name, event.municipality]),
      start,
      end,
      indexOf(urlIndex, packed.u, event.booking_url || "", event.booking_url || ""),
      event.price || "",
      event.facility_name || "",
    ]);
  }
  return packed;
}

// Drops sessions that have already ended today, not just past days.
export function getUnfinishedEvents(now = nowScheduleKey()): EventData[] {
  return getDemoEvents().filter((event) => (event.end_time || event.start_time).replace("T", " ") > now);
}

// What schedule cards need; drops long descriptions and bookkeeping fields from
// data that gets serialized into the page.
export function slimEvent(event: EventData): EventData {
  return { ...event, description: "", last_fetched: "", source_id: "" };
}

export type DemoCampSource = DemoCampSourceRow;
export type { DemoSourceAlertRow, DemoVenueAlertRow, DemoSnapshot };
