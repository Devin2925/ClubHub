import snapshot from "../../data/demo-snapshot.json";
import { getDateKey, getSportMeta, getTodayKey, venueSlug } from "./utils";
import { getVenueClosure } from "./closures";

export const SITE_URL = "https://clubhubvictoria.ca";
export const SITE_NAME = "ClubHub Victoria";
export const SITE_DESCRIPTION =
  "Find drop-in sports, swims, skates, fitness classes, and recreation schedules across Victoria, BC and Greater Victoria in one place.";

export type SnapshotEvent = {
  sport_type: string;
  venue_name: string;
  municipality: string;
  offering_type?: string;
  start_time: string;
  end_time?: string;
};

function upcomingEvents(): SnapshotEvent[] {
  const todayKey = getTodayKey();
  return ((snapshot.events || []) as SnapshotEvent[]).filter(
    (event) => getDateKey(event.end_time || event.start_time) >= todayKey
  );
}

interface VenueSeo {
  // What people search for when it differs from the official venue name (from Search Console).
  searchName?: string;
  // Only addresses confirmed on the operator's own site.
  address?: string;
  summary: string;
}

// Venues behind the site's top Google queries get hand-written copy.
const VENUE_SEO: Record<string, VenueSeo> = {
  "henderson-recreation-centre": {
    address: "2291 Cedar Hill X Road, Victoria, BC V8P 5H9",
    summary:
      "Pickleball, badminton and table tennis drop-ins, court rentals, group fitness classes and fitness centre hours at Oak Bay's Henderson Recreation Centre.",
  },
  "saanich-commonwealth-place": {
    searchName: "Commonwealth Pool",
    address: "4636 Elk Lake Drive, Victoria, BC",
    summary:
      "Leisure, fun and open swims, water slide times and 25m/50m lane swimming with lane counts at Saanich Commonwealth Place, plus fitness and court drop-ins.",
  },
  "carsa-vikes-recreation": {
    searchName: "UVic CARSA",
    summary:
      "Drop-in basketball, volleyball, badminton, soccer and pickleball, plus group fitness and yoga, at UVic's CARSA (Vikes Recreation).",
  },
  "g-r-pearkes-recreation-centre": {
    summary:
      "Everyone Welcome skates, adult and figure skating, stick & puck and adult scrimmage times at the G. R. Pearkes arena, plus fitness and pickleball drop-ins.",
  },
  "fairfield-community-place": {
    searchName: "Fairfield Community Centre",
    summary:
      "Community programs, fitness classes, badminton and basketball drop-ins at Fairfield Community Place, run by the Fairfield Gonzales Community Association.",
  },
};

export function getVenueSeo(slug: string): VenueSeo | undefined {
  return VENUE_SEO[slug];
}

export function getVenueSearchName(slug: string): string | undefined {
  return VENUE_SEO[slug]?.searchName;
}

export function snapshotUpdatedLabel(): string {
  return new Date(`${snapshot.generated_at}Z`).toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "America/Vancouver",
  });
}

export function titleFromSlug(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function getVenueSnapshot(slug: string) {
  const venueEvents = upcomingEvents().filter((event) => venueSlug(event.venue_name) === slug);
  const closure = getVenueClosure(slug);
  const venueName = venueEvents[0]?.venue_name || closure?.venueName || titleFromSlug(slug);
  const municipality = venueEvents[0]?.municipality || closure?.municipality || "Greater Victoria";
  const sportCounts = new Map<string, number>();
  for (const event of venueEvents) {
    sportCounts.set(event.sport_type, (sportCounts.get(event.sport_type) || 0) + 1);
  }
  const sportLabels = Array.from(sportCounts.entries())
    .filter(([sport]) => sport !== "other")
    .sort((a, b) => b[1] - a[1])
    .map(([sport]) => getSportMeta(sport).label)
    .slice(0, 4);

  return {
    venueName,
    municipality,
    eventCount: venueEvents.length,
    sportLabels,
  };
}

export function getSportSnapshot(sport: string) {
  const sportEvents = upcomingEvents().filter((event) => event.sport_type === sport);
  const sportMeta = getSportMeta(sport);
  const municipalities = Array.from(new Set(sportEvents.map((event) => event.municipality)));
  const venues = Array.from(new Set(sportEvents.map((event) => event.venue_name)));

  return {
    label: sportMeta.label,
    eventCount: sportEvents.length,
    municipalityCount: municipalities.length,
    venueCount: venues.length,
  };
}
