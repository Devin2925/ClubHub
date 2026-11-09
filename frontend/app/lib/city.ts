// Which ClubHub this build is: one Next app deployed twice, picked by NEXT_PUBLIC_CITY
// at build time (Vercel project env var). Victoria is the default so an unset
// variable never changes clubhubvictoria.ca. next.config.ts uses the same variable to
// pick the data snapshot (data/demo-snapshot.json or data/vancouver-snapshot.json).
//
// Shared by server and browser code, so no snapshot imports here.

export type CityKey = "victoria" | "vancouver";

export interface CityConfig {
  key: CityKey;
  siteUrl: string;
  siteName: string;
  // The city as people search for it ("drop in hockey victoria").
  name: string;
  // "Victoria, BC" — used in titles ("Lane Swimming in Victoria, BC Today").
  place: string;
  // The whole area the site covers ("across Greater Victoria").
  region: string;
  // Lowercase search term for keywords ("victoria").
  searchTerm: string;
  // Whether the site has the /camps section (Victoria's camp providers only).
  hasCamps: boolean;
  // Shown in the footer, the home page's contact card and the Organization JSON-LD.
  // None means the site shows no contact details.
  contactPhone: { display: string; tel: string; schema: string } | null;
}

export const CITIES: Record<CityKey, CityConfig> = {
  victoria: {
    key: "victoria",
    siteUrl: "https://clubhubvictoria.ca",
    siteName: "ClubHub Victoria",
    name: "Victoria",
    place: "Victoria, BC",
    region: "Greater Victoria",
    searchTerm: "victoria",
    hasCamps: true,
    contactPhone: { display: "203-979-3744", tel: "+12039793744", schema: "+1-203-979-3744" },
  },
  vancouver: {
    key: "vancouver",
    siteUrl: "https://clubhubvancouver.ca",
    siteName: "ClubHub Vancouver",
    name: "Vancouver",
    place: "Vancouver, BC",
    region: "Metro Vancouver",
    searchTerm: "vancouver",
    hasCamps: false,
    // Devin hasn't picked Vancouver's contact yet.
    contactPhone: null,
  },
};

export const CITY_KEY: CityKey = process.env.NEXT_PUBLIC_CITY === "vancouver" ? "vancouver" : "victoria";
export const CITY: CityConfig = CITIES[CITY_KEY];
export const IS_VICTORIA = CITY_KEY === "victoria";

// Pick this city's entry from a per-city table.
export function forCity<T>(table: Record<CityKey, T>): T {
  return table[CITY_KEY];
}
