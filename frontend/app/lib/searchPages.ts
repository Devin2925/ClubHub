// Landing pages for the searches people make without naming a venue: a sport
// ("drop in basketball victoria"), a kind of session ("lane swim", "stick and
// puck"), or a municipality ("saanich drop in schedule"). Server-only.
import { getUnfinishedEvents } from "./snapshot.server";
import { eventMatcher, type EventFilter } from "./schedule";
import { getSportMeta, nowScheduleKey, SPORT_META, venueSlug, type EventData } from "./utils";
import { CITY, forCity, IS_VICTORIA } from "./city";

interface LandingCopy {
  // Search-result title; the root layout appends the site name.
  title: string;
  heading: string;
  // What the page covers, in the words people search with. Venue names and counts
  // are added from the data so the copy stays true as schedules change.
  summary: string;
}

// Sports whose searches don't follow "drop-in <sport>".
const VICTORIA_SPORT_COPY: Record<string, LandingCopy> = {
  swimming: {
    title: "Swim Times in Victoria, BC Today: Lane & Public Swims",
    heading: "Swimming in Victoria today",
    summary: "Lane swims, public and family swims, aquafit and water slide times at pools across Greater Victoria.",
  },
  skating: {
    title: "Public Skating in Victoria, BC: Today's Skate Times",
    heading: "Public skating in Victoria today",
    summary: "Everyone Welcome, family, adult and parent-and-tot skates at arenas across Greater Victoria.",
  },
  hockey: {
    title: "Drop-In Hockey in Victoria, BC: Duffer, Shinny & Stick and Puck",
    heading: "Drop-in hockey in Victoria today",
    summary: "Duffer and adult drop-in hockey, stick and puck, and parent and child hockey ice times across Greater Victoria.",
  },
  yoga: {
    title: "Drop-In Yoga in Victoria, BC: Today's Classes",
    heading: "Drop-in yoga in Victoria today",
    summary:
      "Hatha, vinyasa, yin, gentle, chair and beginner yoga classes at rec centres, community centres and UVic's CARSA across Greater Victoria.",
  },
  fitness: {
    title: "Drop-In Fitness Classes in Victoria, BC Today",
    heading: "Drop-in fitness classes in Victoria today",
    summary:
      "Spin, circuit, strength, Zumba, Pilates and fitness centre drop-in times at rec centres across Greater Victoria.",
  },
  other: {
    title: "Community Centre Drop-Ins in Victoria, BC Today",
    heading: "Community centre drop-ins in Victoria today",
    summary: "Seniors' socials, youth drop-ins, playgroups, dance and other community centre programs across Greater Victoria.",
  },
  kids: {
    title: "Kids' Drop-In Programs in Victoria, BC Today",
    heading: "Kids' drop-ins in Victoria today",
    summary: "Kindergym, playgroups and other drop-in programs for kids across Greater Victoria.",
  },
};

const VANCOUVER_SPORT_COPY: Record<string, LandingCopy> = {
  swimming: {
    title: "Swim Times in Vancouver, BC Today: Lane & Public Swims",
    heading: "Swimming in Vancouver today",
    summary: "Lane swims, public and family swims, aquafit and leisure pool times at pools across Metro Vancouver.",
  },
  skating: {
    title: "Public Skating in Vancouver, BC: Today's Skate Times",
    heading: "Public skating in Vancouver today",
    summary: "Public, family, adult and parent-and-tot skates at rinks across Metro Vancouver.",
  },
  hockey: {
    title: "Drop-In Hockey in Vancouver, BC: Shinny & Stick and Puck",
    heading: "Drop-in hockey in Vancouver today",
    summary: "Adult drop-in hockey, shinny, and stick and puck ice times at rinks across Metro Vancouver.",
  },
  yoga: {
    title: "Drop-In Yoga in Vancouver, BC: Today's Classes",
    heading: "Drop-in yoga in Vancouver today",
    summary: "Hatha, vinyasa, yin, gentle and chair yoga classes at community centres and rec centres across Metro Vancouver.",
  },
  fitness: {
    title: "Drop-In Fitness Classes in Vancouver, BC Today",
    heading: "Drop-in fitness classes in Vancouver today",
    summary: "Spin, circuit, strength, Zumba, Pilates and fitness centre drop-in times at rec centres across Metro Vancouver.",
  },
  other: {
    title: "Community Centre Drop-Ins in Vancouver, BC Today",
    heading: "Community centre drop-ins in Vancouver today",
    summary: "Seniors' socials, youth drop-ins, playgroups, dance and other community centre programs across Metro Vancouver.",
  },
  kids: {
    title: "Kids' Drop-In Programs in Vancouver, BC Today",
    heading: "Kids' drop-ins in Vancouver today",
    summary: "Parent-and-tot gyms, playgroups and other drop-in programs for kids across Metro Vancouver.",
  },
};

const SPORT_COPY = forCity({ victoria: VICTORIA_SPORT_COPY, vancouver: VANCOUVER_SPORT_COPY });

export function getSportCopy(sport: string): LandingCopy {
  const label = getSportMeta(sport).label;
  return (
    SPORT_COPY[sport] || {
      title: `Drop-In ${label} in ${CITY.place} Today`,
      heading: `Drop-in ${label.toLowerCase()} in ${CITY.name} today`,
      summary: `Drop-in ${label.toLowerCase()} times at rec centres and community centres across ${CITY.region}.`,
    }
  );
}

export interface ActivityPage extends LandingCopy {
  sport: string;
  slug: string;
  label: string;
  filter: EventFilter;
}

// Kinds of session people search for by name, matched on session titles.
const VICTORIA_ACTIVITY_PAGES: ActivityPage[] = [
  {
    sport: "swimming",
    slug: "lane-swimming",
    label: "Lane swimming",
    filter: { sports: ["swimming"], pattern: "length|\\blanes?\\b|lap\\s*swim" },
    title: "Lane Swimming in Victoria, BC Today: Lengths Times",
    heading: "Lane swimming in Victoria today",
    summary:
      "Lengths, lap and lane swim times at Greater Victoria pools, with lane counts where the pool publishes them.",
  },
  {
    sport: "swimming",
    slug: "public-swimming",
    label: "Public swims",
    filter: {
      sports: ["swimming"],
      pattern:
        "leisure|everyone\\s*welcome|family\\s*swim|fun\\s*swim|open\\s*swim|public\\s*swim|swim\\s*party|water\\s*slide|waterslide|better\\s*swim",
    },
    title: "Public Swims in Victoria, BC Today: Leisure & Family Swim Times",
    heading: "Public swims in Victoria today",
    summary: "Leisure, family, open and fun swims, plus water slide times, at pools across Greater Victoria.",
  },
  {
    sport: "swimming",
    slug: "aquafit",
    label: "Aquafit",
    filter: {
      sports: ["swimming", "fitness"],
      pattern: "aqua\\s*fit|aquafit|water\\s*walking|waterworks|swim\\s*fit|shallow\\s*fit|deep\\s*fit",
    },
    title: "Aquafit in Victoria, BC: Today's Aquafit & Water Walking Classes",
    heading: "Aquafit in Victoria today",
    summary: "Shallow and deep water aquafit, water walking and other pool fitness classes across Greater Victoria.",
  },
  {
    sport: "skating",
    slug: "public-skating",
    label: "Public skating",
    filter: {
      sports: ["skating", "hockey"],
      pattern:
        "everyone\\s*welcome|family\\s*skate|adult\\s*skate|youth\\s*skate|public\\s*skate|skate\\s*party|tot\\s*skate|ice\\s*play",
    },
    title: "Public Skating in Victoria, BC Today: Everyone Welcome Skates",
    heading: "Public skating in Victoria today",
    summary: "Everyone Welcome, family, adult, youth and parent-and-tot skates at Greater Victoria arenas.",
  },
  {
    sport: "hockey",
    slug: "stick-and-puck",
    label: "Stick and puck",
    filter: { sports: ["hockey", "skating"], pattern: "stick\\s*(&|and|n)\\s*puck" },
    title: "Stick and Puck in Victoria, BC: Today's Ice Times",
    heading: "Stick and puck in Victoria today",
    summary: "Stick and puck ice times for skaters and goalies at Greater Victoria arenas.",
  },
  {
    sport: "hockey",
    slug: "drop-in-hockey",
    label: "Drop-in hockey",
    filter: {
      sports: ["hockey"],
      pattern: "duffer|shinny|drop-?in\\s*hockey|scrimmage|adult\\s*hockey|ice\\s*hockey|friends\\s*hockey",
    },
    title: "Drop-In Hockey & Duffer Hockey in Victoria, BC Today",
    heading: "Drop-in hockey in Victoria today",
    summary: "Duffer hockey by age group, adult scrimmages and other drop-in hockey for skaters and goalies across Greater Victoria.",
  },
  {
    sport: "fitness",
    slug: "spin-classes",
    label: "Spin classes",
    filter: { sports: ["fitness"], pattern: "cycle|\\bride\\b|spin|cycling" },
    title: "Spin & Indoor Cycling Classes in Victoria, BC Today",
    heading: "Spin classes in Victoria today",
    summary: "Indoor cycling and spin classes, including cycle-and-strength formats, at rec centres and CARSA across Greater Victoria.",
  },
];

// Vancouver uses the same session matching with its own wording.
const VANCOUVER_ACTIVITY_COPY: Record<string, LandingCopy> = {
  "lane-swimming": {
    title: "Lane Swimming in Vancouver, BC Today: Lengths Times",
    heading: "Lane swimming in Vancouver today",
    summary: "Lengths, lap and lane swim times at pools across Metro Vancouver.",
  },
  "public-swimming": {
    title: "Public Swims in Vancouver, BC Today: Leisure & Family Swim Times",
    heading: "Public swims in Vancouver today",
    summary: "Public, leisure, family and open swims at pools across Metro Vancouver.",
  },
  aquafit: {
    title: "Aquafit in Vancouver, BC: Today's Aquafit & Water Walking Classes",
    heading: "Aquafit in Vancouver today",
    summary: "Shallow and deep water aquafit, water walking and other pool fitness classes across Metro Vancouver.",
  },
  "public-skating": {
    title: "Public Skating in Vancouver, BC Today: Family & Adult Skates",
    heading: "Public skating in Vancouver today",
    summary: "Public, family, adult, youth and parent-and-tot skates at rinks across Metro Vancouver.",
  },
  "stick-and-puck": {
    title: "Stick and Puck in Vancouver, BC: Today's Ice Times",
    heading: "Stick and puck in Vancouver today",
    summary: "Stick and puck ice times for skaters and goalies at rinks across Metro Vancouver.",
  },
  "drop-in-hockey": {
    title: "Drop-In Hockey & Shinny in Vancouver, BC Today",
    heading: "Drop-in hockey in Vancouver today",
    summary: "Adult drop-in hockey, shinny and scrimmages for skaters and goalies at rinks across Metro Vancouver.",
  },
  "spin-classes": {
    title: "Spin & Indoor Cycling Classes in Vancouver, BC Today",
    heading: "Spin classes in Vancouver today",
    summary: "Indoor cycling and spin classes at rec centres and community centres across Metro Vancouver.",
  },
};

export const ACTIVITY_PAGES: ActivityPage[] = IS_VICTORIA
  ? VICTORIA_ACTIVITY_PAGES
  : VICTORIA_ACTIVITY_PAGES.map((page) => ({ ...page, ...VANCOUVER_ACTIVITY_COPY[page.slug] }));

export function getActivityPage(sport: string, slug: string): ActivityPage | undefined {
  return ACTIVITY_PAGES.find((page) => page.sport === sport && page.slug === slug);
}

interface AreaCopy {
  name: string;
  title: string;
  // Communities the area covers, for searches by town name.
  places?: string;
}

// Keyed by the snapshot's municipality value.
const VICTORIA_AREA_COPY: Record<string, AreaCopy> = {
  Saanich: { name: "Saanich", title: "Saanich Rec Centre Drop-In Schedule Today" },
  "Oak Bay": { name: "Oak Bay", title: "Oak Bay Recreation Drop-In Schedule Today" },
  Victoria: { name: "Victoria", title: "City of Victoria Community Centre Drop-Ins Today" },
  UVic: { name: "UVic", title: "UVic Drop-In Schedule Today: CARSA & Vikes Rec" },
  "West Shore": {
    name: "West Shore",
    title: "West Shore Drop-In Schedule Today: Langford & Colwood",
    places: "Langford, Colwood, View Royal, Metchosin and Highlands",
  },
  Sooke: { name: "Sooke", title: "Sooke Drop-In Schedule Today: SEAPARC" },
  Esquimalt: { name: "Esquimalt", title: "Esquimalt Rec Centre Drop-In Schedule Today" },
  Panorama: {
    name: "Saanich Peninsula",
    title: "Saanich Peninsula Drop-In Schedule Today: Panorama Recreation",
    places: "Sidney, North Saanich and Central Saanich",
  },
};

const VANCOUVER_AREA_COPY: Record<string, AreaCopy> = {
  Vancouver: { name: "Vancouver", title: "Vancouver Community Centre Drop-In Schedule Today" },
  Burnaby: { name: "Burnaby", title: "Burnaby Rec Centre Drop-In Schedule Today" },
  "North Vancouver": { name: "North Vancouver", title: "North Vancouver Drop-In Schedule Today: NVRC" },
  Richmond: { name: "Richmond", title: "Richmond Community Centre Drop-In Schedule Today" },
  Coquitlam: { name: "Coquitlam", title: "Coquitlam Rec Centre Drop-In Schedule Today" },
  Surrey: {
    name: "Surrey",
    title: "Surrey Rec Centre Drop-In Schedule Today",
    places: "Guildford, Newton, Cloverdale, Fleetwood, South Surrey and Whalley",
  },
  Delta: {
    name: "Delta",
    title: "Delta Rec Centre Drop-In Schedule Today",
    places: "Ladner, Tsawwassen and North Delta",
  },
  "New Westminster": {
    name: "New Westminster",
    title: "New Westminster Drop-In Schedule Today",
    places: "Uptown and Queensborough",
  },
  "Port Coquitlam": { name: "Port Coquitlam", title: "Port Coquitlam (PoCo) Drop-In Schedule Today" },
  "Port Moody": { name: "Port Moody", title: "Port Moody Drop-In Schedule Today" },
  "Maple Ridge": { name: "Maple Ridge", title: "Maple Ridge Drop-In Schedule Today", places: "including Albion" },
  "Langley City": {
    name: "Langley City",
    title: "Langley City Drop-In Schedule Today: Timms Community Centre",
  },
  "Township of Langley": {
    name: "Township of Langley",
    title: "Township of Langley Skating & Arena Drop-In Schedule Today",
    places: "Aldergrove, Walnut Grove, Willoughby and Brookswood",
  },
  "White Rock": { name: "White Rock", title: "White Rock Drop-In Schedule Today" },
  UBC: { name: "UBC", title: "UBC Recreation Drop-In Schedule Today: Pool, Gym & Fitness" },
  SFU: { name: "SFU", title: "SFU Recreation Drop-In Sports Schedule Today" },
};

const AREA_COPY = forCity({ victoria: VICTORIA_AREA_COPY, vancouver: VANCOUVER_AREA_COPY });

export function getAreaCopy(municipality: string): AreaCopy {
  return (
    AREA_COPY[municipality] || { name: municipality, title: `${municipality} Drop-In Schedule Today` }
  );
}

export function areaSlug(municipality: string): string {
  return venueSlug(municipality);
}

function upcoming(filter: EventFilter = {}): EventData[] {
  return getUnfinishedEvents(nowScheduleKey()).filter(eventMatcher(filter));
}

export function findArea(slug: string): string | undefined {
  return Array.from(new Set(upcoming().map((event) => event.municipality))).find((name) => areaSlug(name) === slug);
}

export function venueCounts(filter: EventFilter): [string, number][] {
  const counts = new Map<string, number>();
  for (const event of upcoming(filter)) counts.set(event.venue_name, (counts.get(event.venue_name) || 0) + 1);
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

export function sessionCount(filter: EventFilter): number {
  return upcoming(filter).length;
}

// Pages need enough sessions to be worth a search result of their own.
export const MIN_LANDING_SESSIONS = 6;

export function areaPages(): { slug: string; municipality: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const event of upcoming()) counts.set(event.municipality, (counts.get(event.municipality) || 0) + 1);
  return Array.from(counts.entries())
    .filter(([, count]) => count >= MIN_LANDING_SESSIONS)
    .sort((a, b) => b[1] - a[1])
    .map(([municipality, count]) => ({ slug: areaSlug(municipality), municipality, count }));
}

export function activityPages(): (ActivityPage & { count: number })[] {
  return ACTIVITY_PAGES.map((page) => ({ ...page, count: sessionCount(page.filter) })).filter(
    (page) => page.count >= MIN_LANDING_SESSIONS
  );
}

export function sportPages(): { sport: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const event of upcoming()) counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
  return Array.from(counts.entries())
    .filter(([sport, count]) => SPORT_META[sport] && count >= MIN_LANDING_SESSIONS)
    .sort((a, b) => b[1] - a[1])
    .map(([sport, count]) => ({ sport, count }));
}

// "Saanich Commonwealth Place, G. R. Pearkes and 3 more"
export function venueListLabel(venues: string[], limit = 3): string {
  const shown = venues.slice(0, limit);
  const rest = venues.length - shown.length;
  if (rest > 0) return `${shown.join(", ")} and ${rest} more`;
  if (shown.length > 1) return `${shown.slice(0, -1).join(", ")} and ${shown[shown.length - 1]}`;
  return shown[0] || "";
}
