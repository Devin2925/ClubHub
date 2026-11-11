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
  yoga:          { color: "#fb7185", label: "Yoga" },
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
  event: { label: "Event" },
};

// Community calendars store all-day events as 00:00-23:59.
export function isAllDay(event: Pick<EventData, "start_time" | "end_time">): boolean {
  return /[ T]00:00/.test(event.start_time) && /[ T]23:59/.test(event.end_time || "");
}

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

// "Mon, Dec 21 – Thu, Dec 24" for a multi-day camp, "Fri, Nov 27" for one day.
export function formatDateRange(start: string, endDate?: string): string {
  const first = formatDate(start);
  if (!endDate || endDate <= getDateKey(start)) return first;
  return `${first} – ${formatDate(`${endDate}T00:00:00`)}`;
}

// Weekdays a camp runs, counting the first and last day: 4 for Mon-Thu.
export function campDayCount(start: string, endDate?: string): number {
  if (!endDate) return 1;
  const from = Date.parse(`${getDateKey(start)}T00:00:00Z`);
  const to = Date.parse(`${endDate}T00:00:00Z`);
  let days = 0;
  for (let time = from; time <= to; time += 86400000) {
    const weekday = new Date(time).getUTCDay();
    if (weekday !== 0 && weekday !== 6) days += 1;
  }
  return Math.max(days, 1);
}

// "Ages 5-11", "Grades 1-5", "Kindergarten"
export function formatAges(ages?: string): string {
  if (!ages) return "";
  const text = ages.replace(/-/g, "–");
  return /^\d/.test(text) || /^Up to/.test(text) ? `Ages ${text}` : text;
}

// Sync timestamps are UTC instants; the backend writes them without an offset.
// The zone is a fixed "PT": B.C. has been on UTC-7 all year since Nov 2026, and tz data
// versions label that differently ("PDT" on Vercel's build, "MST" on current phones), which
// made the server and browser text disagree.
export function formatDateTime(isoString: string): string {
  const date = new Date(OFFSET_RE.test(isoString.trim()) ? isoString : `${isoString.replace(" ", "T")}Z`);
  const local = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: DISPLAY_TIME_ZONE,
  });
  return `${local} PT`;
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
  // Camps: the last day of a multi-day run (start/end_time hold the first day's
  // hours), spots left as the provider words it, and the age range ("5-11").
  end_date?: string;
  availability?: string;
  ages?: string;
  // Community events that run several days are listed on each day; this keeps
  // the first day so the card can still say "Dec 1 – Dec 14".
  run_start?: string;
}
