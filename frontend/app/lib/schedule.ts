import { formatDate, getDateKey, type EventData } from "./utils";

// One place with upcoming sessions, for the municipality -> rec centre picker.
export interface CatalogVenue {
  municipality: string;
  venue: string;
  sessions: number; // upcoming sessions, biggest places first in the picker
  recCentre: boolean; // runs drop-ins/classes/pickup, not only one-off events or camps
}

export function buildCatalog(events: EventData[]): CatalogVenue[] {
  const places = new Map<string, CatalogVenue>();
  for (const event of events) {
    const key = `${event.municipality}|${event.venue_name}`;
    const place = places.get(key) ?? {
      municipality: event.municipality,
      venue: event.venue_name,
      sessions: 0,
      recCentre: false,
    };
    place.sessions += 1;
    if (event.offering_type !== "event" && event.offering_type !== "camp") place.recCentre = true;
    places.set(key, place);
  }
  return Array.from(places.values());
}

// Filter state that lives in the URL, so a shared link or a search result opens
// on the same day and activity. date: null = default (today or the next day with
// activities), "" = all dates.
export interface ScheduleQuery {
  municipality?: string;
  venue?: string;
  date?: string | null;
  sport?: string;
  type?: string;
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// "YYYY-MM-DD HH:MM:SS", comparable with nowScheduleKey() and snapshot times.
export function timeKey(value: string): string {
  return (value || "").replace("T", " ").slice(0, 19);
}

export function hasEnded(event: EventData, now: string): boolean {
  return timeKey(event.end_time || event.start_time) <= now;
}

export function isHappeningNow(event: EventData, now: string): boolean {
  return timeKey(event.start_time) <= now && !hasEnded(event, now);
}

export function readDateParam(value: string | null | undefined): string | null {
  if (value === "all") return "";
  if (value === WEEKEND) return WEEKEND;
  return value && DATE_RE.test(value) ? value : null;
}

// The "Weekend" date chip: ?date=weekend means the coming Saturday and Sunday (on a
// Saturday, today and tomorrow; on a Sunday, just today).
export const WEEKEND = "weekend";

function shiftDay(dateKey: string, days: number): string {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

export function weekendDates(todayKey: string): string[] {
  const [year, month, day] = todayKey.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay(); // 0 = Sunday
  if (weekday === 0) return [todayKey];
  const saturday = shiftDay(todayKey, 6 - weekday);
  return [saturday, shiftDay(saturday, 1)];
}

// Does a session on dateKey fall in the selected date ("" = all dates)?
export function matchesDate(selection: string, dateKey: string, todayKey: string): boolean {
  if (!selection) return true;
  if (selection === WEEKEND) return weekendDates(todayKey).includes(dateKey);
  return dateKey === selection;
}

// For an empty day: the first later day that has a matching session, and how many it has.
export function nextDateWith(events: EventData[], selection: string, todayKey: string) {
  if (!selection) return null;
  const after = selection === WEEKEND ? weekendDates(todayKey).slice(-1)[0] : selection;
  const counts = new Map<string, number>();
  for (const event of events) {
    const key = getDateKey(event.start_time);
    if (key > after) counts.set(key, (counts.get(key) || 0) + 1);
  }
  const date = Array.from(counts.keys()).sort()[0];
  return date ? { date, count: counts.get(date) || 0 } : null;
}

export function readParam(value: string | string[] | null | undefined): string {
  return (Array.isArray(value) ? value[0] : value || "").slice(0, 120);
}

export function scheduleDates(events: EventData[], limit = 21): string[] {
  return Array.from(new Set(events.map((event) => getDateKey(event.start_time)))).sort().slice(0, limit);
}

export function pickDefaultDate(dates: string[], todayKey: string): string {
  return dates.includes(todayKey) ? todayKey : dates.find((date) => date >= todayKey) || dates[0] || "";
}

export function scheduleSearch(query: ScheduleQuery): string {
  const params = new URLSearchParams();
  if (query.municipality) params.set("municipality", query.municipality);
  if (query.venue) params.set("venue", query.venue);
  if (query.date === "") params.set("date", "all");
  else if (query.date) params.set("date", query.date);
  if (query.sport) params.set("sport", query.sport);
  if (query.type) params.set("type", query.type);
  const search = params.toString();
  return search ? `?${search}` : "";
}

// The inverse of scheduleSearch: read the filter state back out of a URL search string.
// Static pages (force-static) render with empty searchParams on the server, so their clients
// call this on mount to restore the filters a link carried (?date=, ?sport=, ?venue=, ...).
// `date` is set only when the URL names it, so callers can tell "no date in the link" apart
// from "date=all".
export function readScheduleSearch(search: string): ScheduleQuery {
  const params = new URLSearchParams(search);
  const query: ScheduleQuery = {};
  const municipality = readParam(params.get("municipality"));
  if (municipality) query.municipality = municipality;
  const venue = readParam(params.get("venue"));
  if (venue) query.venue = venue;
  if (params.has("date")) query.date = readDateParam(readParam(params.get("date")));
  const sport = readParam(params.get("sport"));
  if (sport) query.sport = sport;
  const type = readParam(params.get("type"));
  if (type) query.type = type;
  return query;
}

// Keep the address bar in step with the filters without adding history entries.
export function replaceSearch(query: ScheduleQuery) {
  const url = `${window.location.pathname}${scheduleSearch(query)}${window.location.hash}`;
  if (url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState(window.history.state, "", url);
  }
}

// Short enough for a phone-width chip: "Today", "Tomorrow", "Fri, Oct 30".
export function dayChipLabel(date: string, todayKey: string): string {
  if (date === WEEKEND) return weekendDates(todayKey).length === 1 ? "Today" : "This weekend";
  if (date === todayKey) return "Today";
  if (date === shiftDay(todayKey, 1)) return "Tomorrow";
  return formatDate(`${date}T00:00:00`);
}

// Which sessions a landing page covers ("Saanich", "swimming", "lane swims"); the
// server uses it for the first day and the browser for the full schedule.
export interface EventFilter {
  venue?: string;
  municipality?: string;
  sports?: string[];
  // Case-insensitive regex source matched against the session title.
  pattern?: string;
}

export function eventMatcher(filter: EventFilter): (event: EventData) => boolean {
  const pattern = filter.pattern ? new RegExp(filter.pattern, "i") : null;
  return (event) =>
    (!filter.venue || event.venue_name === filter.venue) &&
    (!filter.municipality || event.municipality === filter.municipality) &&
    (!filter.sports?.length || filter.sports.includes(event.sport_type)) &&
    (!pattern || pattern.test(event.title));
}
