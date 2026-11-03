// Camp listings: which school break a camp belongs to, who runs it, and who it's for.
// Shared by the server pages and the browser filters, so no snapshot imports here.
import { getDateKey, type EventData } from "./utils";

export type CampSeason = "winter-break" | "pro-d-days" | "spring-break" | "summer";

export interface CampSeasonInfo {
  slug: CampSeason;
  // Short label for tabs and headings ("Winter break").
  label: string;
  // What people type: "winter break camps victoria".
  searchName: string;
  blurb: string;
}

export const CAMP_SEASONS: CampSeasonInfo[] = [
  {
    slug: "winter-break",
    label: "Winter break",
    searchName: "Winter break camps",
    blurb: "Holiday day camps, LEGO robotics, sports and arts camps over the school winter break.",
  },
  {
    slug: "pro-d-days",
    label: "Pro-D & school year",
    searchName: "Pro-D day camps",
    blurb: "Single-day camps for school professional development days and early dismissals, plus school-year camps.",
  },
  {
    slug: "spring-break",
    label: "Spring break",
    searchName: "Spring break camps",
    blurb: "Week-long and daily camps over the March school break.",
  },
  {
    slug: "summer",
    label: "Summer",
    searchName: "Summer camps",
    blurb: "Weekly summer day camps from July through the end of August.",
  },
];

export function getCampSeason(slug: string): CampSeasonInfo | undefined {
  return CAMP_SEASONS.find((season) => season.slug === slug);
}

// By the camp's first day, with the title as a tiebreak for camps that straddle a break.
export function campSeason(event: Pick<EventData, "title" | "start_time">): CampSeason {
  const day = getDateKey(event.start_time);
  const month = Number(day.slice(5, 7));
  const date = Number(day.slice(8, 10));
  const title = event.title.toLowerCase();
  if (/winter|holiday|christmas|festive|polar express/.test(title)) return "winter-break";
  if (/spring break/.test(title)) return "spring-break";
  if (/summer/.test(title)) return "summer";
  if ((month === 12 && date >= 15) || (month === 1 && date <= 8)) return "winter-break";
  if (month === 3 && date >= 8) return "spring-break";
  if (month === 7 || month === 8 || (month === 6 && date >= 20) || (month === 9 && date <= 5)) return "summer";
  return "pro-d-days";
}

// The day a camp listing stops being upcoming: its last day, or its only day.
export function campLastDay(event: Pick<EventData, "start_time" | "end_date">): string {
  return event.end_date || getDateKey(event.start_time);
}

// Inclusive age bounds from "5-11", "5½-11", "13+", "Grades 1-5", "Kindergarten".
export function campAgeBounds(ages?: string): [number, number] | null {
  if (!ages) return null;
  const text = ages.replace(/½/g, ".5");
  let match = /^(\d+(?:\.5)?)\s*-\s*(\d+)/.exec(text);
  if (match) return [Number(match[1]), Number(match[2])];
  match = /^(\d+)\+/.exec(text);
  if (match) return [Number(match[1]), 18];
  match = /^Up to (\d+)/i.exec(text);
  if (match) return [0, Number(match[1])];
  match = /^Grades? (\d+)(?:\s*-\s*(\d+))?/i.exec(text);
  if (match) return [Number(match[1]) + 5, Number(match[2] || match[1]) + 6];
  match = /^K-Grade (\d+)/i.exec(text);
  if (match) return [5, Number(match[1]) + 6];
  if (/kindergarten/i.test(text)) return [5, 6];
  match = /^(\d+)$/.exec(text);
  if (match) return [Number(match[1]), Number(match[1])];
  return null;
}

export const AGE_FILTERS: { key: string; label: string; range: [number, number] }[] = [
  { key: "preschool", label: "Ages 3–5", range: [3, 5] },
  { key: "6-8", label: "Ages 6–8", range: [6, 8] },
  { key: "9-12", label: "Ages 9–12", range: [9, 12] },
  { key: "teen", label: "Teens 13+", range: [13, 18] },
];

export function campFitsAge(event: Pick<EventData, "ages">, filterKey: string): boolean {
  const filter = AGE_FILTERS.find((item) => item.key === filterKey);
  if (!filter) return true;
  const bounds = campAgeBounds(event.ages);
  // No age listed: keep it rather than hide a camp that may fit.
  if (!bounds) return true;
  return bounds[0] <= filter.range[1] && bounds[1] >= filter.range[0];
}

export function campIsFull(event: Pick<EventData, "availability">): boolean {
  return /full/i.test(event.availability || "");
}

// Who runs a camp, by the scraper source it came from.
const CAMP_PROVIDERS: [RegExp, string][] = [
  [/^saanich_camps/, "Saanich Recreation"],
  [/^pm_camps_oakbayrec/, "Oak Bay Recreation"],
  [/^pm_camps_panoramarec/, "Panorama Recreation"],
  [/^pm_camps_seaparcrecreation/, "SEAPARC"],
  [/^pm_camps_esquimalt/, "Esquimalt Recreation"],
  [/^wspr_camps/, "West Shore Parks & Recreation"],
  [/^braefoot_camps/, "Braefoot Community Association"],
];

export function campProvider(event: Pick<EventData, "source" | "venue_name">): string {
  for (const [pattern, name] of CAMP_PROVIDERS) if (pattern.test(event.source || "")) return name;
  return event.venue_name;
}

// "$224.00" -> "$224"
export function campPrice(price?: string): string {
  return (price || "").replace(/\.00\b/g, "").trim();
}

export function sortCamps<T extends Pick<EventData, "start_time" | "title">>(camps: T[]): T[] {
  return [...camps].sort((a, b) => a.start_time.localeCompare(b.start_time) || a.title.localeCompare(b.title));
}
