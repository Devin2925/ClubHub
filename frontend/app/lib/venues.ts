import type { EventData } from "./utils";

export interface VenueSummary {
  venueName: string;
  municipality: string;
  count: number;
  nextTime: string;
}

export function summarizeVenues(events: EventData[]): VenueSummary[] {
  const map = new Map<string, VenueSummary>();
  for (const event of events) {
    const existing = map.get(event.venue_name);
    if (!existing) {
      map.set(event.venue_name, {
        venueName: event.venue_name,
        municipality: event.municipality,
        count: 1,
        nextTime: event.start_time,
      });
    } else {
      existing.count += 1;
      if (event.start_time < existing.nextTime) existing.nextTime = event.start_time;
    }
  }
  return Array.from(map.values());
}
