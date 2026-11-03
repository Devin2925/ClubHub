// Server-only data for /camps and the season pages.
import { getDemoCampSources, getDemoSnapshot } from "./snapshot.server";
import {
  CAMP_SEASONS,
  campLastDay,
  campPrice,
  campProvider,
  campSeason,
  sortCamps,
  type CampSeason,
} from "./camps";
import { getDateKey, getTodayKey, nowScheduleKey, venueSlug, type EventData } from "./utils";

export interface CampListing extends EventData {
  season: CampSeason;
  provider: string;
  // Venue page link, when the venue has a schedule of its own (not just this camp).
  venueHref?: string;
}

export interface CampProviderRow {
  key: string;
  name: string;
  area: string;
  places: string[];
  tags: string[];
  infoUrl: string;
  registerUrl: string;
  campCount: number;
}

function trimNote(text: string, limit = 220): string {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  const sentence = clean.slice(0, limit).lastIndexOf(". ");
  return sentence > 80 ? clean.slice(0, sentence + 1) : `${clean.slice(0, limit).replace(/\s+\S*$/, "")}…`;
}

// Camps stay listed until their last day ends, unlike sessions, which drop off after they finish.
export function getUpcomingCamps(): CampListing[] {
  const today = getTodayKey();
  const now = nowScheduleKey();
  const events = getDemoSnapshot().events || [];
  const scheduleVenues = new Set(
    events.filter((event) => event.offering_type !== "camp").map((event) => venueSlug(event.venue_name))
  );
  const camps = events.filter((event) => {
    if (event.offering_type !== "camp") return false;
    const last = campLastDay(event);
    if (last < today) return false;
    // A one-day camp that has already finished today.
    return Boolean(event.end_date) || (event.end_time || event.start_time).replace("T", " ") > now;
  });
  return sortCamps(camps).map((event) => {
    const slug = venueSlug(event.venue_name);
    return {
      ...event,
      description: trimNote(event.description),
      last_fetched: "",
      season: campSeason(event),
      provider: campProvider(event),
      venueHref: scheduleVenues.has(slug) ? `/venues/${slug}` : undefined,
    };
  });
}

export function campProviders(camps: CampListing[]): CampProviderRow[] {
  return getDemoCampSources().map((source) => {
    const prefixes = (source as { event_sources?: string[] }).event_sources || [];
    const campCount = prefixes.length
      ? camps.filter((camp) => prefixes.some((prefix) => (camp.source || "").startsWith(prefix))).length
      : 0;
    return {
      key: source.source_key,
      name: source.name,
      area: source.municipality,
      places: source.venue_names,
      tags: source.tags,
      infoUrl: source.primary_url,
      registerUrl: source.registration_url,
      campCount,
    };
  });
}

function dollars(price: string): number | null {
  const match = /\$\s*(\d+(?:\.\d+)?)/.exec(price || "");
  return match ? Number(match[1]) : null;
}

export interface SeasonSummary {
  slug: CampSeason;
  count: number;
  open: number;
  firstDay?: string;
  lastDay?: string;
  // "Dec 21 – Dec 31"
  span?: string;
  dates: string[];
  // Days with a one-day camp (Pro-D days), for "when is the next Pro-D day".
  singleDays: string[];
  minPrice?: number;
  maxPrice?: number;
  areas: string[];
  providers: string[];
  // The year the next run of this break falls in, for titles ("Spring Break Camps 2027").
  year: number;
}

function rankBy(values: string[]): string[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value]) => value);
}

const MONTH = new Intl.DateTimeFormat("en-CA", { month: "short", timeZone: "UTC" });

// "Dec 21–31", "Nov 27", "Nov 5 – May 21, 2027"
export function daySpan(first: string, last?: string): string {
  const parse = (day: string) => new Date(`${day}T00:00:00Z`);
  const label = (day: string) => `${MONTH.format(parse(day))} ${Number(day.slice(8, 10))}`;
  if (!last || last === first) return label(first);
  const yearSuffix = last.slice(0, 4) !== first.slice(0, 4) ? `, ${last.slice(0, 4)}` : "";
  if (first.slice(0, 7) === last.slice(0, 7)) return `${label(first)}–${Number(last.slice(8, 10))}`;
  return `${label(first)} – ${label(last)}${yearSuffix}`;
}

// The calendar year of the next occurrence of a break, counted from today.
function seasonYear(slug: CampSeason, today: string): number {
  const year = Number(today.slice(0, 4));
  const month = Number(today.slice(5, 7));
  if (slug === "winter-break") return month === 1 ? year - 1 : year;
  if (slug === "spring-break") return month > 3 ? year + 1 : year;
  if (slug === "summer") return month > 8 ? year + 1 : year;
  return year;
}

export function seasonSummaries(camps: CampListing[]): SeasonSummary[] {
  const today = getTodayKey();
  return CAMP_SEASONS.map(({ slug }) => {
    const list = camps.filter((camp) => camp.season === slug);
    const firstDays = list.map((camp) => getDateKey(camp.start_time)).sort();
    const lastDays = list.map((camp) => campLastDay(camp)).sort();
    const prices = list.map((camp) => dollars(camp.price)).filter((value): value is number => value !== null);
    const firstDay = firstDays[0];
    const lastDay = lastDays[lastDays.length - 1];
    return {
      slug,
      count: list.length,
      open: list.filter((camp) => !/full/i.test(camp.availability || "")).length,
      firstDay,
      lastDay,
      span: firstDay ? daySpan(firstDay, lastDay) : undefined,
      dates: Array.from(new Set(firstDays)),
      singleDays: Array.from(new Set(list.filter((camp) => !camp.end_date).map((camp) => getDateKey(camp.start_time)))).sort(),
      minPrice: prices.length ? Math.min(...prices) : undefined,
      maxPrice: prices.length ? Math.max(...prices) : undefined,
      // Most camps first, so a shortened list names the busiest areas.
      areas: rankBy(list.map((camp) => camp.municipality)),
      providers: rankBy(list.map((camp) => camp.provider)),
      year: firstDay ? Number(firstDay.slice(0, 4)) : seasonYear(slug, today),
    };
  });
}

export function priceRangeLabel(summary: SeasonSummary): string {
  if (summary.minPrice === undefined || summary.maxPrice === undefined) return "";
  if (summary.minPrice === summary.maxPrice) return campPrice(`$${summary.minPrice}`);
  return `${campPrice(`$${summary.minPrice.toFixed(2)}`)} to ${campPrice(`$${summary.maxPrice.toFixed(2)}`)}`;
}

// Areas named the way people search them ("Panorama" is the Saanich Peninsula).
export function areaLabel(municipality: string): string {
  if (municipality === "Panorama") return "Saanich Peninsula";
  return municipality;
}
