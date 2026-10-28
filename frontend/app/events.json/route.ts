import { getUnfinishedEvents, packEvents } from "../lib/snapshot.server";

// The browser's copy of the upcoming schedule. Dropping finished sessions per
// request keeps it accurate between snapshot exports; the CDN shares one copy
// for 15 minutes.
export function GET() {
  return Response.json(packEvents(getUnfinishedEvents()), {
    headers: {
      "Cache-Control": "public, max-age=300, s-maxage=900, stale-while-revalidate=3600",
    },
  });
}
