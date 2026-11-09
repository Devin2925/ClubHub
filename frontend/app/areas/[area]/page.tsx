import { Metadata } from "next";
import { notFound } from "next/navigation";
import { CITY } from "../../lib/city";
import LandingSchedulePage, { landingMetadata, type SearchParams } from "../../components/LandingSchedulePage";
import { getSportMeta, nowScheduleKey, venueSlug } from "../../lib/utils";
import { findArea, getAreaCopy, sessionCount, venueCounts, venueListLabel } from "../../lib/searchPages";
import { getUnfinishedEvents } from "../../lib/snapshot.server";

type Props = {
  params: Promise<{ area: string }>;
  searchParams: SearchParams;
};

function areaPage(municipality: string) {
  const filter = { municipality };
  const sportCounts = new Map<string, number>();
  for (const event of getUnfinishedEvents(nowScheduleKey())) {
    if (event.municipality !== municipality || event.sport_type === "other") continue;
    sportCounts.set(event.sport_type, (sportCounts.get(event.sport_type) || 0) + 1);
  }
  const sports = Array.from(sportCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([sport]) => getSportMeta(sport).label.toLowerCase());
  const venues = venueCounts(filter);
  const copy = getAreaCopy(municipality);
  const activities = sports.length ? `${venueListLabel(sports.slice(0, 4), 4)} drop-ins` : "drop-ins";
  const venueNames = venues.map(([name]) => name);
  const places = copy.places ? ` Covers ${copy.places}.` : "";
  const summary = `${activities.charAt(0).toUpperCase()}${activities.slice(1)} at ${venueListLabel(venueNames, 4)}.${places}`;
  const description = `Today's ${copy.name} drop-in schedule: ${activities} at ${venueListLabel(venueNames, 2)}.${places}`;
  return { filter, venues, copy, summary, description, count: sessionCount(filter) };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { area } = await params;
  const municipality = findArea(area);
  if (!municipality) return {};
  const page = areaPage(municipality);
  return landingMetadata({
    title: page.copy.title,
    description: page.description,
    path: `/areas/${area}`,
    count: page.count,
    keywords: [
      `${page.copy.name} drop in schedule`,
      `${page.copy.name} recreation schedule`,
      `${page.copy.name} rec centre schedule`,
      ...(page.copy.places || "")
        .split(/, | and /)
        .filter(Boolean)
        .map((name) => `${name} drop in schedule`),
    ],
  });
}

export const dynamic = "force-dynamic";

export default async function AreaPage({ params, searchParams }: Props) {
  const { area } = await params;
  const municipality = findArea(area);
  if (!municipality) notFound();
  const page = areaPage(municipality);

  return (
    <LandingSchedulePage
      filter={page.filter}
      searchParams={searchParams}
      path={`/areas/${area}`}
      heading={`${page.copy.name} drop-in schedule`}
      kicker={page.copy.name}
      shortName={page.copy.name}
      subtitle={`${page.count} upcoming sessions at ${page.venues.length} ${page.venues.length === 1 ? "venue" : "venues"}`}
      summary={page.summary}
      aboutTitle={`Recreation in ${page.copy.name}`}
      collectionName={`${page.copy.name} drop-in schedule`}
      breadcrumbs={[
        { name: "Home", path: "/" },
        { name: page.copy.name, path: `/areas/${area}` },
      ]}
      back={{ name: `All of ${CITY.region}`, path: "/" }}
      relatedLinks={page.venues.map(([name, count]) => ({ href: `/venues/${venueSlug(name)}`, label: name, count }))}
    />
  );
}
