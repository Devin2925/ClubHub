import type { Metadata } from "next";
import { DEMO_MODE } from "../lib/demo";
import { getDemoCampSources, getDemoEvents } from "../lib/snapshot.server";
import CampsPageClient, { type DemoCampData } from "./CampsPageClient";

export const metadata: Metadata = {
  title: "Kids Camps in Victoria BC",
  description:
    "Find kids camps, summer camps, Pro-D day camps, spring break camps, and camp providers across Victoria BC and Greater Victoria.",
  alternates: {
    canonical: "/camps",
  },
  keywords: [
    "Victoria BC kids camps",
    "Victoria BC summer camps",
    "Greater Victoria day camps",
    "Victoria BC Pro-D camps",
    "Saanich summer camps",
    "Oak Bay camps",
    "West Shore camps",
  ],
};

// Rebuilt hourly so finished camps drop off between deploys.
export const revalidate = 3600;

export default function CampsPage() {
  const demo: DemoCampData | null = DEMO_MODE
    ? {
        events: getDemoEvents().filter((event) => event.offering_type === "camp"),
        sources: getDemoCampSources() as unknown as DemoCampData["sources"],
      }
    : null;
  return <CampsPageClient demo={demo} />;
}

