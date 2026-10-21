// Sport metadata: icons, colors, display names
export const SPORT_META: Record<string, { color: string; label: string }> = {
  hockey:        { color: "#ff5252", label: "Hockey" },
  pickleball:    { color: "#2dd4bf", label: "Pickleball" },
  basketball:    { color: "#fb923c", label: "Basketball" },
  badminton:     { color: "#38bdf8", label: "Badminton" },
  volleyball:    { color: "#a78bfa", label: "Volleyball" },
  "table-tennis":{ color: "#f472b6", label: "Table Tennis" },
  skating:       { color: "#818cf8", label: "Skating" },
  swimming:      { color: "#22d3ee", label: "Swimming" },
  fitness:       { color: "#fbbf24", label: "Fitness" },
  archery:       { color: "#a3e635", label: "Archery" },
  arts:          { color: "#e879f9", label: "Arts" },
  kids:          { color: "#fcd34d", label: "Kids" },
  soccer:        { color: "#22c55e", label: "Soccer" },
  tennis:        { color: "#eab308", label: "Tennis" },
  squash:        { color: "#a855f7", label: "Squash" },
  curling:       { color: "#38bdf8", label: "Curling" },
  other:         { color: "#94a3b8", label: "Community" },
};

export const OFFERING_META: Record<string, { label: string }> = {
  "drop-in": { label: "Drop-In" },
  pickup: { label: "Pickup" },
  class: { label: "Class" },
  camp: { label: "Camp" },
};

export function getSportMeta(sportType: string) {
  return SPORT_META[sportType] || SPORT_META.other;
}

export function getOfferingMeta(offeringType: string) {
  return OFFERING_META[offeringType] || { label: "Activity" };
}

export const DISPLAY_TIME_ZONE = "America/Vancouver";

const OFFSET_RE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;
const WALL_CLOCK_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/;

// Schedule times are Victoria wall-clock times with no offset ("2026-10-21 05:30:00").
// Read them as-is, so the server (UTC on Vercel) and every browser show the same
// time; only values that carry an offset are converted to Victoria time.
function scheduleDate(value: string): { date: Date; timeZone: string } {
  const match = WALL_CLOCK_RE.exec(value);
  if (match && !OFFSET_RE.test(value.trim())) {
    const [, year, month, day, hour = "0", minute = "0", second = "0"] = match;
    return {
      date: new Date(Date.UTC(+year, +month - 1, +day, +hour, +minute, +second)),
      timeZone: "UTC",
    };
  }
  return { date: new Date(value), timeZone: DISPLAY_TIME_ZONE };
}

// ISO 8601 with Victoria's UTC offset, for structured data ("2026-10-21T05:30:00-07:00").
export function toScheduleIso(value: string): string {
  const match = WALL_CLOCK_RE.exec(value || "");
  if (!match || OFFSET_RE.test(value.trim())) return value;
  const [, year, month, day, hour = "00", minute = "00", second = "00"] = match;
  const guess = new Date(Date.UTC(+year, +month - 1, +day, +hour, +minute, +second));
  const offset =
    new Intl.DateTimeFormat("en-US", { timeZone: DISPLAY_TIME_ZONE, timeZoneName: "longOffset" })
      .formatToParts(guess)
      .find((part) => part.type === "timeZoneName")
      ?.value.replace("GMT", "") || "-08:00";
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${offset || "+00:00"}`;
}

// Format time from ISO string
export function formatTime(isoString: string): string {
  const { date, timeZone } = scheduleDate(isoString);
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
  });
}

// Format date from ISO string
export function formatDate(isoString: string): string {
  const { date, timeZone } = scheduleDate(isoString);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone,
  });
}

// Format full date
export function formatFullDate(isoString: string): string {
  const { date, timeZone } = scheduleDate(isoString);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone,
  });
}

export function formatMonthDay(isoString: string): string {
  const { date, timeZone } = scheduleDate(isoString);
  return date.toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    timeZone,
  });
}

// Sync timestamps are UTC instants; the backend writes them without an offset.
export function formatDateTime(isoString: string): string {
  const date = new Date(OFFSET_RE.test(isoString.trim()) ? isoString : `${isoString.replace(" ", "T")}Z`);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: DISPLAY_TIME_ZONE,
    timeZoneName: "short",
  });
}

// Get date key for grouping (YYYY-MM-DD)
export function getDateKey(isoString: string): string {
  if (!isoString) return "";
  return isoString.includes("T") ? isoString.split("T")[0] : isoString.split(" ")[0];
}

// Today's date key (YYYY-MM-DD) in the display time zone
export function getTodayKey(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
  }).format(new Date());
}

// Current Victoria wall-clock time, comparable with schedule start_time strings.
export function nowScheduleKey(): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: DISPLAY_TIME_ZONE,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date())
      .map((part) => [part.type, part.value])
  );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

// Check if date is today
export function isToday(dateKey: string): boolean {
  return dateKey === getTodayKey();
}

export function formatFreshnessLabel(freshness: string): string {
  switch (freshness) {
    case "fresh":
      return "Fresh";
    case "warning":
      return "Warning";
    case "stale":
      return "Stale";
    case "error":
      return "Error";
    case "running":
      return "Running";
    default:
      return "Never";
  }
}

// API base URL
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5001";

// Venue slug helper
export function venueSlug(venueName: string): string {
  return venueName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

// Event type
export interface EventData {
  id: number;
  source_id: string;
  title: string;
  sport_type: string;
  offering_type: string;
  venue_name: string;
  facility_name: string;
  center_id: number;
  start_time: string;
  end_time: string;
  price: string;
  description: string;
  booking_url: string;
  source: string;
  municipality: string;
  last_fetched: string;
}
