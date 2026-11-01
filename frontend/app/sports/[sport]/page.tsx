import { Metadata } from "next";
import { notFound } from "next/navigation";
import LandingSchedulePage, { landingMetadata, type SearchParams } from "../../components/LandingSchedulePage";
import { getSportMeta, SPORT_META, venueSlug } from "../../lib/utils";
import { MIN_VENUE_SPORT_SESSIONS, SITE_NAME } from "../../lib/seo";
import { activityPages, getSportCopy, sessionCount, venueCounts, venueListLabel } from "../../lib/searchPages";

type Props = {
  params: Promise<{ sport: string }>;
  searchParams: SearchParams;
};

function sportPage(sport: string) {
  const filter = { sports: [sport] };
  const venues = venueCounts(filter);
  return {
    filter,
    venues,
    count: sessionCount(filter),
    copy: getSportCopy(sport),
    label: getSportMeta(sport).label,
  };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { sport } = await params;
  const page = sportPage(sport);
  const venues = page.venues.map(([name]) => name);
  return landingMetadata({
    title: page.copy.title,
    description:
      page.count > 0
        ? `${page.copy.summary} ${page.count} upcoming sessions at ${venueListLabel(venues, 2)}.`
        : page.copy.summary,
    path: `/sports/${sport}`,
    count: page.count,
    keywords: [
      `drop in ${page.label.toLowerCase()} victoria`,
      `${page.label.toLowerCase()} victoria bc`,
      `${page.label.toLowerCase()} schedule victoria`,
      `${page.label.toLowerCase()} today victoria`,
      `${SITE_NAME} ${page.label}`,
    ],
  });
}

export const dynamic = "force-dynamic";

export default async function SportDetailPage({ params, searchParams }: Props) {
  const { sport } = await params;
  if (!SPORT_META[sport]) notFound();
  const page = sportPage(sport);
  const venueNames = page.venues.map(([name]) => name);

  const relatedLinks = [
    ...activityPages()
      .filter((activity) => activity.sport === sport)
      .map((activity) => ({
        href: `/sports/${sport}/${activity.slug}`,
        label: activity.label,
        count: activity.count,
        featured: true,
      })),
    ...page.venues.map(([name, count]) => ({
      href:
        count >= MIN_VENUE_SPORT_SESSIONS ? `/venues/${venueSlug(name)}/${sport}` : `/venues/${venueSlug(name)}`,
      label: name,
      count,
    })),
  ];

  return (
    <LandingSchedulePage
      filter={page.filter}
      searchParams={searchParams}
      path={`/sports/${sport}`}
      heading={page.copy.heading}
      kicker="Greater Victoria"
      shortName={page.label.toLowerCase()}
      subtitle={`${page.count} upcoming sessions at ${page.venues.length} ${page.venues.length === 1 ? "venue" : "venues"}`}
      summary={venueNames.length ? `${page.copy.summary} Venues include ${venueListLabel(venueNames, 4)}.` : page.copy.summary}
      aboutTitle={`${page.label} across Greater Victoria`}
      collectionName={`${page.label} in Victoria, BC`}
      breadcrumbs={[
        { name: "Home", path: "/" },
        { name: "Sports", path: "/sports" },
        { name: page.label, path: `/sports/${sport}` },
      ]}
      back={{ name: "All sports", path: "/sports" }}
      relatedLinks={relatedLinks}
      hideSportFilter
    />
  );
}
