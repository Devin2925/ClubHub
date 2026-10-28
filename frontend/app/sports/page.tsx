import { DEMO_MODE } from "../lib/demo";
import { getDemoSports } from "../lib/snapshot.server";
import SportsPageClient from "./SportsPageClient";

export const revalidate = 3600;

export default function SportsPage() {
  return <SportsPageClient demoSports={DEMO_MODE ? getDemoSports() : null} />;
}
