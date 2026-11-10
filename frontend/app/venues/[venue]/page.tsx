import Link from "next/link";
import { Metadata } from "next";
import snapshot from "@clubhub/snapshot";
import VenueScheduleClient from "../../components/VenueScheduleClient";
import CampCard from "../../components/CampCard";
import { getUpcomingCamps } from "../../lib/campPages.server";
import { getCampSeason } from "../../lib/camps";
import { DEMO_MODE } from "../../lib/demo";
import { getDemoEvents, sessionNotes } from "../../lib/snapshot.server";
import { CITY, IS_VICTORIA } from "../../lib/city";
import { readDateParam, readParam } from "../../lib/schedule";
import {
  API_BASE,
  EventData,
  getSportMeta,
  nowScheduleKey,
  venueSlug,
} from "../../lib/utils";
import {
  getVenueSearchName,
  getVenueSeo,
  getVenueSnapshot,
  getVenueSportSeo,
  MIN_VENUE_SPORT_SESSIONS,
  serializeJsonLd,
  SITE_NAME,
  SITE_URL,
  snapshotUpdatedLabel,
  venuePageHeading,
  venueSportCounts,
} from "../../lib/seo";
import { closureHeadline, getVenueClosure, VENUE_CLOSURES } from "../../lib/closures";

type Props = {
  params: Promise<{ venue: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const resolvedParams = await params;
  const venueData = getVenueSnapshot(resolvedParams.venue);
  const seo = getVenueSeo(resolvedParams.venue);
  const searchName = seo?.searchName;
  const displayTitle = searchName || venueData.venueName;
  const closure = getVenueClosure(resolvedParams.venue);
  const updated = `Updated ${snapshotUpdatedLabel()}.`;
  const title =
    seo?.metaTitle ||
    (closure
      ? `${displayTitle} Schedule: ${closureHeadline(closure)}`
      : `${displayTitle} Drop-In Schedule`);
  const description = closure
    ? `${seo?.metaDescription || seo?.summary || `${displayTitle} is ${closureHeadline(closure).toLowerCase()}. ${IS_VICTORIA ? "See nearby pool swim times and the interim Victoria Recreation Centre plans." : "See nearby schedules while it is closed."}`} ${updated}`
    : seo && venueData.eventCount > 0
      ? `${seo.metaDescription || `${seo.summary} ${venueData.eventCount} upcoming sessions with times and dates.`} ${updated}`
      : venueData.eventCount > 0
        ? `${displayTitle} drop-in schedule: ${venueData.eventCount} upcoming activities in ${venueData.municipality}, BC. Browse ${venueData.sportLabels.join(", ") || "drop-ins and classes"} with times and dates on ${SITE_NAME}. ${updated}`
        : `See upcoming drop-ins, classes, and recreation schedules at ${displayTitle} in ${venueData.municipality}, BC on ${SITE_NAME}.`;

  return {
    title,
    description,
    keywords: [
      `${venueData.venueName} schedule`,
      `${venueData.venueName} ${CITY.name} BC`,
      `${venueData.venueName} drop-in`,
      ...(searchName ? [`${searchName} schedule`, `${searchName} drop-in`] : []),
      ...(seo?.alternateNames || []).flatMap((name) => [`${name} schedule`, `${name} drop-in`]),
      `${venueData.municipality} recreation centre`,
      `${SITE_NAME} ${displayTitle}`,
    ],
    robots: venueData.eventCount > 0 || closure ? undefined : { index: false, follow: true },
    openGraph: {
      title: `${title} | ${SITE_NAME}`,
      description,
      type: "website",
      url: `/venues/${resolvedParams.venue}`,
    },
    twitter: {
      card: "summary",
      title: `${title} | ${SITE_NAME}`,
      description,
    },
    alternates: {
      canonical: `/venues/${resolvedParams.venue}`,
    },
  };
}

// Static at build (bundled-snapshot data). The closed-venue "nearby" counts freeze at
// build time (a no-op for open venues) and the client corrects live "now" on hydration.
// Prebuilt set mirrors the sitemap's venue list (schedule venues + closures, not
// camp-only / event-only spots).
export const dynamic = "force-static";

export function generateStaticParams() {
  const slugs = new Set<string>();
  for (const event of snapshot.events || []) {
    if (event.venue_name && event.offering_type !== "camp" && event.offering_type !== "event") {
      slugs.add(venueSlug(event.venue_name));
    }
  }
  for (const closure of VENUE_CLOSURES) slugs.add(venueSlug(closure.venueName));
  return Array.from(slugs).map((venue) => ({ venue }));
}

export default async function VenueDetailPage({ params, searchParams }: Props) {
  const resolvedParams = await params;
  const query = await searchParams;
  const initialQuery = {
    date: query.date === undefined ? undefined : readDateParam(readParam(query.date)),
    sport: readParam(query.sport) || undefined,
    type: readParam(query.type) || undefined,
  };
  let allEvents: EventData[] = [];
  if (DEMO_MODE) {
    allEvents = getDemoEvents();
  } else {
    const response = await fetch(`${API_BASE}/api/events`, { cache: "no-store" });
    const data = await response.json();
    allEvents = data.events || [];
  }

  const venueEvents = allEvents
    .filter((event) => venueSlug(event.venue_name) === resolvedParams.venue);
  const notes = sessionNotes(venueEvents);
  const events = venueEvents.map((event) => ({ ...event, description: "", last_fetched: "", source_id: "" }));
  const closure = getVenueClosure(resolvedParams.venue);
  const venueName = events[0]?.venue_name || closure?.venueName || resolvedParams.venue;
  const municipality = events[0]?.municipality || closure?.municipality || CITY.region;
  const seo = getVenueSeo(resolvedParams.venue);
  const searchName = getVenueSearchName(resolvedParams.venue);
  const pageHeading = venuePageHeading(resolvedParams.venue, venueName);
  const relatedLinks = venueSportCounts(resolvedParams.venue)
    .filter(([, count]) => count >= MIN_VENUE_SPORT_SESSIONS)
    .map(([sport, count]) => ({
      href: `/venues/${resolvedParams.venue}/${sport}`,
      label: `${searchName || venueName} ${getSportMeta(sport).label.toLowerCase()}`,
      count,
      featured: Boolean(getVenueSportSeo(resolvedParams.venue, sport)),
    }));
  const venueJsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    name: venueName,
    ...(searchName || seo?.alternateNames?.length
      ? { alternateName: [searchName, ...(seo?.alternateNames || [])].filter(Boolean) }
      : {}),
    url: `${SITE_URL}/venues/${resolvedParams.venue}`,
    address: {
      "@type": "PostalAddress",
      ...(seo?.address ? { streetAddress: seo.address.split(",")[0] } : {}),
      addressLocality: municipality,
      addressRegion: "BC",
      addressCountry: "CA",
    },
    description:
      seo?.summary ||
      `Upcoming recreation schedules, drop-ins, and classes at ${venueName} in ${municipality}, British Columbia.`,
  };

  // While a venue is closed, point visitors at open venues that still run the same activity.
  const now = nowScheduleKey();
  const alternatives = (closure?.nearby || []).map((group) => ({
    heading: group.heading,
    sportLabel: getSportMeta(group.sport).label.toLowerCase(),
    venues: group.venues
      .map((name) => {
        const sessions = allEvents
          .filter(
            (event) =>
              event.venue_name === name &&
              event.sport_type === group.sport &&
              event.start_time.replace("T", " ") >= now
          )
          .sort((a, b) => a.start_time.localeCompare(b.start_time));
        return {
          name,
          slug: venueSlug(name),
          municipality: sessions[0]?.municipality || "",
          count: sessions.length,
          next: sessions[0] ? { title: sessions[0].title, start: sessions[0].start_time } : null,
        };
      })
      .filter((venue) => venue.count > 0),
  }));
  const venueCamps = getUpcomingCamps().filter((camp) => venueSlug(camp.venue_name) === resolvedParams.venue);
  const campSeasons = Array.from(new Set(venueCamps.map((camp) => camp.season)));
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: SITE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Rec Centres",
        item: `${SITE_URL}/venues`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: venueName,
        item: `${SITE_URL}/venues/${resolvedParams.venue}`,
      },
    ],
  };

  return (
    <main className="page">
      <div className="container">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(venueJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbJsonLd) }}
        />
        <Link href="/venues" className="section-link" style={{ marginTop: "1rem", display: "inline-flex" }}>
          Back to venue list
        </Link>
        <VenueScheduleClient
          events={events}
          venueName={venueName}
          municipality={municipality}
          closure={closure}
          searchName={searchName}
          pageHeading={pageHeading}
          summary={seo?.summary}
          address={seo?.address}
          answers={seo?.answers}
          updatedLabel={snapshotUpdatedLabel()}
          relatedLinks={relatedLinks}
          alternatives={alternatives}
          notes={notes}
          initialQuery={initialQuery}
          initialNow={now}
        />
        {venueCamps.length ? (
          <section className="venue-camps" id="camps">
            <h2 className="section-title">Kids camps at {searchName || venueName}</h2>
            <p className="section-copy">
              {venueCamps.length} upcoming {venueCamps.length === 1 ? "camp" : "camps"} with dates, ages and spots left. More
              across {CITY.region}:{" "}
              {campSeasons.map((season, index) => (
                <span key={season}>
                  {index ? ", " : ""}
                  <Link href={`/camps/${season}`} className="inline-link">
                    {getCampSeason(season)?.searchName.toLowerCase()}
                  </Link>
                </span>
              ))}
              .
            </p>
            <div className="camp-grid">
              {venueCamps.slice(0, 12).map((camp) => (
                <CampCard key={camp.id} camp={{ ...camp, venueHref: undefined }} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
