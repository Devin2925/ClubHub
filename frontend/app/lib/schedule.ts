import { formatDate, getDateKey, type EventData } from "./utils";

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
  return value && DATE_RE.test(value) ? value : null;
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

// Keep the address bar in step with the filters without adding history entries.
export function replaceSearch(query: ScheduleQuery) {
  const url = `${window.location.pathname}${scheduleSearch(query)}${window.location.hash}`;
  if (url !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
    window.history.replaceState(window.history.state, "", url);
  }
}

// Short enough for a phone-width chip: "Today", "Tomorrow", "Fri, Oct 30".
export function dayChipLabel(date: string, todayKey: string): string {
  if (date === todayKey) return "Today";
  const [year, month, day] = todayKey.split("-").map(Number);
  const tomorrow = new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
  if (date === tomorrow) return "Tomorrow";
  return formatDate(`${date}T00:00:00`);
}
