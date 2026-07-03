import snapshot from "../../data/demo-snapshot.json";
import { getSportMeta, venueSlug } from "./utils";

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
};

const events = (snapshot.events || []) as SnapshotEvent[];

export function titleFromSlug(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function getVenueSnapshot(slug: string) {
  const venueEvents = events.filter((event) => venueSlug(event.venue_name) === slug);
  const venueName = venueEvents[0]?.venue_name || titleFromSlug(slug);
  const municipality = venueEvents[0]?.municipality || "Greater Victoria";
  const sportLabels = Array.from(
    new Set(venueEvents.map((event) => getSportMeta(event.sport_type).label))
  ).slice(0, 4);

  return {
    venueName,
    municipality,
    eventCount: venueEvents.length,
    sportLabels,
  };
}

export function getSportSnapshot(sport: string) {
  const sportEvents = events.filter((event) => event.sport_type === sport);
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
