import { DEMO_MODE } from "../lib/demo";
import { getUnfinishedEvents } from "../lib/snapshot.server";
import { summarizeVenues } from "../lib/venues";
import VenuesPageClient from "./VenuesPageClient";

// Rebuilt hourly so counts and "next activity" stay current between deploys.
export const revalidate = 3600;

export default function VenuesPage() {
  return <VenuesPageClient demoVenues={DEMO_MODE ? summarizeVenues(getUnfinishedEvents()) : null} />;
}
