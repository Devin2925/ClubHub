import { Metadata } from "next";
import { notFound } from "next/navigation";
import { CITY } from "../../lib/city";
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
      `drop in ${page.label.toLowerCase()} ${CITY.searchTerm}`,
      `${page.label.toLowerCase()} ${CITY.searchTerm} bc`,
      `${page.label.toLowerCase()} schedule ${CITY.searchTerm}`,
      `${page.label.toLowerCase()} today ${CITY.searchTerm}`,
      `${SITE_NAME} ${page.label}`,
    ],
  });
}

// Prerendered at build and served from the CDN: the data is the bundled snapshot,
// so there is nothing request-specific to compute. force-static makes the page static
// even though it still accepts searchParams (which it neutralizes to empty); the
// client fills in live "now" and any ?date=/?sport= filter on hydration.
export const dynamic = "force-static";

export function generateStaticParams() {
  return Object.keys(SPORT_META).map((sport) => ({ sport }));
}

export default async function SportDetailPage({ params, searchParams }: Props) {
  const { sport } = await params;
  if (!SPORT_META[sport]) notFound();
  const page = sportPage(sport);
  const venueNames = page.venues.map(([name]) => name);

  const relatedLinks = [
    // Kids' sessions include camp days; the full camp listings live on /camps.
    ...(sport === "kids" && CITY.hasCamps ? [{ href: "/camps", label: "Kids camps", featured: true }] : []),
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
      kicker={CITY.region}
      shortName={page.label.toLowerCase()}
      subtitle={`${page.count} upcoming sessions at ${page.venues.length} ${page.venues.length === 1 ? "venue" : "venues"}`}
      summary={venueNames.length ? `${page.copy.summary} Venues include ${venueListLabel(venueNames, 4)}.` : page.copy.summary}
      aboutTitle={`${page.label} across ${CITY.region}`}
      collectionName={`${page.label} in ${CITY.place}`}
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
