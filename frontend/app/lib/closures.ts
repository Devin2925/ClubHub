import { venueSlug } from "./utils";
import { IS_VICTORIA } from "./city";

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
  // Open venues to point people to while this one is closed, nearest first.
  nearby?: {
    sport: string;
    heading: string;
    venues: string[];
  }[];
}

// Venues that are closed upstream, so they have no events but are still searched for.
const VICTORIA_CLOSURES: VenueClosure[] = [
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
    nearby: [
      {
        sport: "swimming",
        heading: "Where to swim while Crystal Pool is closed",
        venues: [
          "Oak Bay Recreation Centre",
          "Esquimalt Recreation Centre",
          "Saanich Commonwealth Place",
          "Gordon Head Recreation Centre",
          "Juan de Fuca Rec Centre",
        ],
      },
      {
        sport: "skating",
        heading: "City public skating continues at the arena",
        venues: ["Save on Foods Memorial Centre"],
      },
    ],
  },
];

// Sources (checked 2026-11-09): City of Vancouver news release "Vancouver Aquatic Centre
// scheduled to close June 28, 2026" and Daily Hive, Oct. 14, 2026 (replacement design and the
// court pause on demolition). Recheck after the Nov. 3, 2026 injunction date.
const VANCOUVER_CLOSURES: VenueClosure[] = [
  {
    venueName: "Vancouver Aquatic Centre",
    municipality: "Vancouver",
    closedOn: "June 28, 2026",
    reopensLabel: "its replacement opens (targeted for 2029)",
    summary:
      "The Vancouver Aquatic Centre on Beach Avenue closed permanently on June 28, 2026 ahead of demolition. A new aquatic centre with an eight-lane 25m lap pool, leisure and diving pools, a hot tub and a fitness gym is planned for the same site, targeted to open in 2029.",
    infoUrl: "https://vancouver.ca/parks-recreation-culture/vancouver-aquatic-centre.aspx",
    nearby: [
      {
        sport: "swimming",
        heading: "Where to swim while the Vancouver Aquatic Centre is closed",
        venues: [
          "Templeton Park Pool",
          "Hillcrest Aquatic Centre",
          "Lord Byng Pool",
          "Kerrisdale Pool",
          "Kensington Pool",
        ],
      },
    ],
  },
];

export const VENUE_CLOSURES: VenueClosure[] = IS_VICTORIA ? VICTORIA_CLOSURES : VANCOUVER_CLOSURES;

export function getVenueClosure(slug: string): VenueClosure | undefined {
  return VENUE_CLOSURES.find((closure) => venueSlug(closure.venueName) === slug);
}

export function closureHeadline(closure: VenueClosure): string {
  return `Closed until ${closure.reopensLabel}`;
}
