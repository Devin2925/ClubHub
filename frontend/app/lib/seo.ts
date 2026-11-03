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
  // Other common names that help search engines connect branded and official names.
  alternateNames?: string[];
  // Only addresses confirmed on the operator's own site.
  address?: string;
  // Short, query-aligned title. The root layout appends the site name.
  metaTitle?: string;
  // Search-result copy, kept separate from the fuller on-page summary.
  metaDescription?: string;
  // Visible page heading; keep this aligned with the title link we want Google to use.
  heading?: string;
  summary: string;
  answers?: {
    question: string;
    answer: string;
  }[];
}

// Venues behind the site's top Google queries get hand-written copy.
const VENUE_SEO: Record<string, VenueSeo> = {
  "henderson-recreation-centre": {
    searchName: "Henderson Rec Centre",
    alternateNames: ["Henderson Recreation Center", "Henderson Rec Center", "Henderson Centre Oak Bay"],
    address: "2291 Cedar Hill X Road, Victoria, BC V8P 5H9",
    metaTitle: "Henderson Rec Centre Schedule & Drop-Ins",
    metaDescription:
      "Today's Henderson Rec Centre schedule: pickleball, badminton and table tennis drop-ins, cycle and fitness classes, fitness centre hours and kids camps in Oak Bay.",
    heading: "Henderson Rec Centre schedule",
    summary:
      "Pickleball, badminton and table tennis drop-ins, court rentals, group fitness classes and fitness centre hours at Oak Bay's Henderson Recreation Centre.",
    answers: [
      {
        question: "What drop-ins are at Henderson Rec Centre?",
        answer:
          "Current listings include pickleball, badminton and table tennis social play, indoor court rentals, group fitness and fitness centre drop-in times.",
      },
      {
        question: "What does \"Reserved Drop-in\" mean at Henderson?",
        answer:
          "Oak Bay runs its racquet social play as reserved drop-ins: you book a spot ahead through Oak Bay Recreation's online registration rather than just showing up. Tap Book on a session to go to it.",
      },
      {
        question: "Where is Henderson Rec Centre?",
        answer:
          "Henderson Recreation Centre is at 2291 Cedar Hill Cross Road in Oak Bay, in Henderson Park. It is run by Oak Bay Parks, Recreation and Culture.",
      },
      {
        question: "Does this schedule include today's activities?",
        answer:
          "Yes. Use the date buttons below to check today or another upcoming date, then filter by sport or activity type.",
      },
    ],
  },
  "saanich-commonwealth-place": {
    searchName: "Commonwealth Pool",
    alternateNames: ["Saanich Commonwealth Pool", "SCP"],
    address: "4636 Elk Lake Drive, Victoria, BC",
    metaTitle: "Commonwealth Pool Drop-In & Swim Schedule",
    metaDescription:
      "See today's Commonwealth Pool schedule for lane swimming, leisure and open swims, water slide times, aquafit and other Saanich drop-ins.",
    heading: "Saanich Commonwealth Pool drop-in schedule",
    summary:
      "Leisure, fun and open swims, water slide times and 25m/50m lane swimming with lane counts at Saanich Commonwealth Place, plus fitness and court drop-ins.",
    answers: [
      {
        question: "What is on the Commonwealth Pool schedule?",
        answer:
          "The schedule includes 25m and 50m lane swimming, leisure and open swims, fun swims, water slide times, aquafit and water walking when offered.",
      },
      {
        question: "Can I find the Saanich Commonwealth Pool drop-in schedule here?",
        answer:
          "Yes. The listings combine pool sessions with other current drop-ins at Saanich Commonwealth Place and can be filtered by date and activity.",
      },
    ],
  },
  "carsa-vikes-recreation": {
    searchName: "CARSA",
    alternateNames: ["UVic CARSA", "Vikes Recreation", "Vikes Rec", "Centre for Athletics, Recreation and Special Abilities"],
    address: "3964 Gordon Head Road, Victoria, BC",
    metaTitle: "CARSA Drop-In Schedule: Yoga, Basketball & More",
    metaDescription:
      "Today's UVic CARSA schedule: drop-in yoga, basketball, volleyball, badminton, pickleball, squash and group fitness times for UVic students.",
    heading: "CARSA drop-in schedule",
    summary:
      "Drop-in yoga, basketball, volleyball, badminton, soccer, pickleball and squash, plus group fitness and spin classes, at UVic's CARSA (Vikes Recreation).",
    // Membership facts from vikesrec.ca/membership and /yoga (fall 2026).
    answers: [
      {
        question: "Are CARSA drop-ins free for UVic students?",
        answer:
          "Students who pay UVic's Athletics and Recreation fee with tuition get drop-in basketball, volleyball, badminton, ping pong, squash, tennis, pickleball and open recreation as base benefits. Yoga, group fitness and the weight centre need a membership or drop-in pass.",
      },
      {
        question: "How much is CARSA yoga?",
        answer:
          "Yoga classes are $20 per drop-in, or included with a Vikes Yoga membership. Each class has a reserve-a-spot link, so book ahead for busy times.",
      },
      {
        question: "Is this the UVic Vikes Recreation schedule?",
        answer:
          "Yes. CARSA is UVic's Vikes Recreation centre; this page lists its public drop-in, yoga and group fitness schedule by date and activity.",
      },
      {
        question: "Do I need to book CARSA classes?",
        answer:
          "Yoga and group fitness classes have a reserve-a-spot link to UVic's ActiveLiving booking, which Book opens. Pickleball court passes are booked too; drop-in basketball, volleyball, badminton and open play don't need a booking.",
      },
    ],
  },
  "cedar-hill-recreation-centre": {
    searchName: "Cedar Hill Rec Centre",
    metaTitle: "Cedar Hill Rec Centre Services & Schedule",
    metaDescription:
      "See Cedar Hill Recreation Centre services and upcoming times for badminton, table tennis, fitness, yoga, weight training, ceramics and art.",
    heading: "Cedar Hill Recreation Centre schedule and services",
    summary:
      "Badminton court rentals, table tennis, reserved fitness drop-ins, yoga, strength training, ceramics and art programs at Cedar Hill Recreation Centre in Saanich.",
    answers: [
      {
        question: "What services are offered by Cedar Hill Recreation Centre?",
        answer:
          "Current listings include badminton court rentals, table tennis, fitness and yoga drop-ins, weight training, ceramics and art programs, plus selected youth activities.",
      },
      {
        question: "Can I filter the Cedar Hill schedule?",
        answer:
          "Yes. Choose a date, sport or activity type below to narrow the schedule to the sessions you want.",
      },
    ],
  },
  "g-r-pearkes-recreation-centre": {
    summary:
      "Everyone Welcome skates, adult and figure skating, stick & puck and adult scrimmage times at the G. R. Pearkes arena, plus fitness and pickleball drop-ins.",
  },
  "fairfield-community-place": {
    searchName: "Fairfield Community Centre",
    alternateNames: ["Fairfield Place"],
    metaTitle: "Fairfield Community Centre Schedule",
    metaDescription:
      "See upcoming fitness, yoga, badminton, basketball, early-years and community activities at Fairfield Community Centre in Victoria, BC.",
    heading: "Fairfield Community Centre schedule",
    summary:
      "Community programs, fitness classes, badminton and basketball drop-ins at Fairfield Community Place, run by the Fairfield Gonzales Community Association.",
    answers: [
      {
        question: "Is Fairfield Community Place the Fairfield Community Centre?",
        answer:
          "Yes. People commonly search for Fairfield Community Place as Fairfield Community Centre or Fairfield Place; this page covers the same Victoria facility.",
      },
      {
        question: "What activities are listed at Fairfield Place?",
        answer:
          "Listings include fitness and yoga, badminton, basketball, early-years programs, community gatherings and other scheduled neighbourhood activities.",
      },
    ],
  },
  "crystal-pool-and-fitness-centre": {
    searchName: "Crystal Pool",
    alternateNames: ["Crystal Pool Victoria"],
    metaTitle: "Crystal Pool Schedule & Closure Update",
    metaDescription:
      "Crystal Pool is closed. Find the closure update, interim Victoria Recreation Centre plan and current nearby Greater Victoria swim schedules.",
    heading: "Crystal Pool schedule and closure update",
    summary:
      "Crystal Pool and Fitness Centre closure information, the interim Victoria Recreation Centre plan, and current nearby swim schedule alternatives in Greater Victoria.",
    answers: [
      {
        question: "Is Crystal Pool open today?",
        answer:
          "No. Crystal Pool closed permanently on September 25, 2026 while the City develops a new health and wellness facility.",
      },
      {
        question: "Where can I find a swim schedule while Crystal Pool is closed?",
        answer:
          "Use the current nearby pool schedules on this page for Oak Bay, Esquimalt, Saanich Commonwealth, Gordon Head and Juan de Fuca recreation centres.",
      },
    ],
  },
};

export function getVenueSeo(slug: string): VenueSeo | undefined {
  return VENUE_SEO[slug];
}

export function getVenueSearchName(slug: string): string | undefined {
  return VENUE_SEO[slug]?.searchName;
}

export function venuePageHeading(slug: string, fallbackName: string): string {
  return VENUE_SEO[slug]?.heading || `${fallbackName} drop-in schedule`;
}

// One activity at one venue ("CARSA yoga schedule"), keyed "venue-slug/sport".
const VENUE_SPORT_SEO: Record<string, Omit<VenueSeo, "searchName" | "alternateNames" | "address">> = {
  "carsa-vikes-recreation/yoga": {
    metaTitle: "CARSA Yoga Schedule: UVic Drop-In Yoga Classes",
    metaDescription:
      "This week's CARSA yoga classes at UVic: vinyasa, hatha, yin, restorative, power and beginner yoga times, $20 drop-in or included with a Vikes Yoga membership.",
    heading: "CARSA yoga schedule",
    summary:
      "Every Vikes Recreation yoga class at CARSA, from Beginner and Gentle Yoga to Power Vinyasa, Yang to Yin and Sunset Yoga. Classes are $20 per drop-in or included with a Vikes Yoga membership; bring your own mat.",
    answers: [
      {
        question: "Can UVic students drop in to CARSA yoga?",
        answer:
          "Yes. Yoga isn't part of the base student Athletics and Recreation benefits, so students pay $20 per class or buy a Vikes Yoga membership, which is sold by term.",
      },
      {
        question: "Do I need to book a CARSA yoga class?",
        answer:
          "Each class has a reserve-a-spot link on Vikes Recreation. Tap Book on a class in the schedule to reserve your spot.",
      },
      {
        question: "What should I bring?",
        answer: "Vikes Recreation asks you to bring your own mat. Beginner Yoga is designed for people with no prior yoga experience.",
      },
    ],
  },
};

// Activity pages need enough sessions to be worth a search result of their own.
export const MIN_VENUE_SPORT_SESSIONS = 6;

export function getVenueSportSeo(venue: string, sport: string) {
  return VENUE_SPORT_SEO[`${venue}/${sport}`];
}

export function venueSportCounts(slug: string): [string, number][] {
  const counts = new Map<string, number>();
  for (const event of upcomingEvents()) {
    // Camps have their own pages under /camps.
    if (event.sport_type === "other" || event.offering_type === "camp" || venueSlug(event.venue_name) !== slug) continue;
    counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
  }
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

export function venueSportPages(): { venue: string; sport: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const event of upcomingEvents()) {
    if (event.sport_type === "other" || event.offering_type === "camp") continue;
    const key = `${venueSlug(event.venue_name)}/${event.sport_type}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count >= MIN_VENUE_SPORT_SESSIONS)
    .map(([key, count]) => {
      const [venue, sport] = key.split("/");
      return { venue, sport, count };
    });
}

export function serializeJsonLd(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
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
