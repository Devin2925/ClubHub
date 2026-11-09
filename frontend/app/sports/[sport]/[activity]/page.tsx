import { Metadata } from "next";
import { notFound } from "next/navigation";
import { CITY } from "../../../lib/city";
import LandingSchedulePage, { landingMetadata, type SearchParams } from "../../../components/LandingSchedulePage";
import { getSportMeta, venueSlug } from "../../../lib/utils";
import {
  activityPages,
  getActivityPage,
  sessionCount,
  venueCounts,
  venueListLabel,
} from "../../../lib/searchPages";

type Props = {
  params: Promise<{ sport: string; activity: string }>;
  searchParams: SearchParams;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { sport, activity } = await params;
  const page = getActivityPage(sport, activity);
  if (!page) return {};
  const count = sessionCount(page.filter);
  const venues = venueCounts(page.filter).map(([name]) => name);
  return landingMetadata({
    title: page.title,
    description: count > 0 ? `${page.summary} ${count} upcoming sessions at ${venueListLabel(venues, 2)}.` : page.summary,
    path: `/sports/${sport}/${activity}`,
    count,
    keywords: [
      `${page.label.toLowerCase()} ${CITY.searchTerm}`,
      `${page.label.toLowerCase()} ${CITY.searchTerm} bc`,
      `${page.label.toLowerCase()} today`,
      `${page.label.toLowerCase()} schedule ${CITY.searchTerm}`,
    ],
  });
}

export const dynamic = "force-dynamic";

export default async function ActivityPage({ params, searchParams }: Props) {
  const { sport, activity } = await params;
  const page = getActivityPage(sport, activity);
  if (!page) notFound();
  const venues = venueCounts(page.filter);
  const count = venues.reduce((total, [, venueCount]) => total + venueCount, 0);
  const sportLabel = getSportMeta(sport).label;

  const relatedLinks = [
    ...activityPages()
      .filter((other) => other.sport === sport && other.slug !== activity)
      .map((other) => ({ href: `/sports/${sport}/${other.slug}`, label: other.label, count: other.count })),
    { href: `/sports/${sport}`, label: `All ${sportLabel.toLowerCase()}` },
    ...venues.map(([name, venueCount]) => ({ href: `/venues/${venueSlug(name)}`, label: name, count: venueCount })),
  ];

  return (
    <LandingSchedulePage
      filter={page.filter}
      searchParams={searchParams}
      path={`/sports/${sport}/${activity}`}
      heading={page.heading}
      kicker={CITY.region}
      shortName={page.label.toLowerCase()}
      subtitle={`${count} upcoming sessions at ${venues.length} ${venues.length === 1 ? "venue" : "venues"}`}
      summary={
        venues.length
          ? `${page.summary} Venues include ${venueListLabel(venues.map(([name]) => name), 4)}.`
          : page.summary
      }
      aboutTitle={`${page.label} across ${CITY.region}`}
      collectionName={`${page.label} in ${CITY.place}`}
      breadcrumbs={[
        { name: "Home", path: "/" },
        { name: "Sports", path: "/sports" },
        { name: sportLabel, path: `/sports/${sport}` },
        { name: page.label, path: `/sports/${sport}/${activity}` },
      ]}
      back={{ name: `All ${sportLabel.toLowerCase()}`, path: `/sports/${sport}` }}
      relatedLinks={relatedLinks}
      hideSportFilter
    />
  );
}
