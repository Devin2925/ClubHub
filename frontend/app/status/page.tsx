import { DEMO_MODE } from "../lib/demo";
import {
  getDemoSnapshot,
  getDemoSourceAlerts,
  getDemoStatus,
  getDemoVenueAlerts,
} from "../lib/snapshot.server";
import StatusPageClient, { type DemoStatusData } from "./StatusPageClient";

export const revalidate = 3600;

export default function StatusPage() {
  let demo: DemoStatusData | null = null;
  if (DEMO_MODE) {
    const status = getDemoStatus();
    demo = {
      rerunSummary: status.rerun_summary,
      sources: getDemoSnapshot().sources as unknown as DemoStatusData["sources"],
      summary: status.source_summary as DemoStatusData["summary"],
      alerts: getDemoSourceAlerts() as unknown as DemoStatusData["alerts"],
      venueAlerts: getDemoVenueAlerts() as unknown as DemoStatusData["venueAlerts"],
    };
  }
  return <StatusPageClient demo={demo} />;
}
