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
};

export function getSportMeta(sportType: string) {
  return SPORT_META[sportType] || SPORT_META.other;
}

export function getOfferingMeta(offeringType: string) {
  return OFFERING_META[offeringType] || { label: "Activity" };
}

export const DISPLAY_TIME_ZONE = "America/Vancouver";

// Format time from ISO string
export function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: DISPLAY_TIME_ZONE,
  });
}

// Format date from ISO string
export function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: DISPLAY_TIME_ZONE,
  });
}

// Format full date
export function formatFullDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: DISPLAY_TIME_ZONE,
  });
}

export function formatMonthDay(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    timeZone: DISPLAY_TIME_ZONE,
  });
}

export function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
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

// Check if date is today
export function isToday(dateKey: string): boolean {
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: DISPLAY_TIME_ZONE,
  }).format(new Date());
  return dateKey === today;
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
