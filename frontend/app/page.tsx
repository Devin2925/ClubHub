import HomeClient, { type HomeClientProps } from "./HomeClient";
import { DEMO_MODE } from "./lib/demo";
import { getDemoStatus, getUnfinishedEvents, slimEvent } from "./lib/snapshot.server";
import { buildCatalog, pickDefaultDate, readDateParam, readParam, scheduleDates } from "./lib/schedule";
import { getDateKey, nowScheduleKey } from "./lib/utils";

const INITIAL_EVENT_LIMIT = 80;

type Props = {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

// The home page is the most-visited URL, and its data is the bundled snapshot, so
// prerender it at build and serve from the CDN. force-static neutralizes searchParams
// (the ?municipality=/?date= deep-link state) and freezes "now" to build time; HomeClient
// reads the live URL params and current time on hydration. (In dev, pages still render
// on-demand, so the local backend path keeps working.)
export const dynamic = "force-static";

export default async function HomePage({ searchParams }: Props) {
  const params = await searchParams;
  const initialQuery: HomeClientProps["initialQuery"] = {
    municipality: readParam(params.municipality) || undefined,
    venue: readParam(params.venue) || undefined,
    date: params.date === undefined ? undefined : readDateParam(readParam(params.date)),
    sport: readParam(params.sport) || undefined,
  };
  const now = nowScheduleKey();

  if (!DEMO_MODE) {
    return (
      <HomeClient
        initialEvents={[]}
        initialDates={[]}
        catalog={[]}
        initialStatus={null}
        initialQuery={initialQuery}
        initialNow={now}
      />
    );
  }

  // Render the day the visitor will see first (from the link, or today) on the
  // server so phones show sessions without waiting for the full schedule.
  const upcoming = getUnfinishedEvents(now);
  const catalog = buildCatalog(upcoming);
  const placeEvents = upcoming.filter((event) => {
    if (initialQuery.municipality && event.municipality !== initialQuery.municipality) return false;
    if (initialQuery.venue && event.venue_name !== initialQuery.venue) return false;
    return true;
  });
  const dates = scheduleDates(placeEvents);
  const day = initialQuery.date ?? pickDefaultDate(dates, now.slice(0, 10));
  const initialEvents = (
    day
      ? placeEvents.filter((event) => getDateKey(event.start_time) === day)
      : placeEvents.slice(0, INITIAL_EVENT_LIMIT)
  ).map(slimEvent);

  return (
    <HomeClient
      initialEvents={initialEvents}
      initialDates={dates}
      catalog={catalog}
      initialStatus={getDemoStatus()}
      initialQuery={initialQuery}
      initialNow={now}
    />
  );
}
