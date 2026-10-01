import { venueSlug } from "./utils";

export interface VenueClosure {
  venueName: string;
  municipality: string;
  closedOn: string;
  reopensLabel: string;
  summary: string;
  alternative?: {
    name: string;
    address: string;
    opensLabel: string;
  };
  infoUrl: string;
}

// Venues that are closed upstream, so they have no events but are still searched for.
export const VENUE_CLOSURES: VenueClosure[] = [
  {
    venueName: "Crystal Pool and Fitness Centre",
    municipality: "Victoria",
    closedOn: "Sept. 25, 2026",
    reopensLabel: "early 2027",
    summary:
      "Crystal Pool closed permanently on Sept. 25, 2026 for construction of the City's new health and wellness facility. City of Victoria recreation moves to the interim Victoria Recreation Centre, opening early 2027, with fitness, a gym, squash courts, and limited swimming.",
    alternative: {
      name: "Victoria Recreation Centre",
      address: "851 Broughton St.",
      opensLabel: "early 2027",
    },
    infoUrl: "https://www.victoria.ca/parks-recreation/recreation/crystal-pool-fitness-centre",
  },
];

export function getVenueClosure(slug: string): VenueClosure | undefined {
  return VENUE_CLOSURES.find((closure) => venueSlug(closure.venueName) === slug);
}

export function closureHeadline(closure: VenueClosure): string {
  return `Closed until ${closure.reopensLabel}`;
}
