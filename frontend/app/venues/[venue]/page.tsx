import Link from "next/link";
import { Metadata } from "next";
import VenueScheduleClient from "../../components/VenueScheduleClient";
import { DEMO_MODE } from "../../lib/demo";
import { getDemoEvents } from "../../lib/snapshot.server";
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
  SITE_NAME,
  snapshotUpdatedLabel,
} from "../../lib/seo";
import { closureHeadline, getVenueClosure } from "../../lib/closures";

type Props = {
  params: Promise<{ venue: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const resolvedParams = await params;
  const venueData = getVenueSnapshot(resolvedParams.venue);
  const seo = getVenueSeo(resolvedParams.venue);
  const searchName = seo?.searchName;
  const displayTitle = searchName ? `${venueData.venueName} (${searchName})` : venueData.venueName;
  const closure = getVenueClosure(resolvedParams.venue);
  const activities = venueData.sportLabels.slice(0, 2).join(" & ");
  const updated = `Updated ${snapshotUpdatedLabel()}.`;
  const title = closure
    ? `${displayTitle} Schedule: ${closureHeadline(closure)}`
    : `${displayTitle} Schedule: ${activities ? `${activities} ` : ""}Drop-Ins in ${venueData.municipality}`;
  const description = closure
    ? `${displayTitle} is ${closureHeadline(closure).toLowerCase()}. See nearby pool swim times and the interim Victoria Recreation Centre plans. ${updated}`
    : seo && venueData.eventCount > 0
      ? `${seo.summary} ${venueData.eventCount} upcoming sessions with times and dates. ${updated}`
      : venueData.eventCount > 0
        ? `${displayTitle} drop-in schedule: ${venueData.eventCount} upcoming activities in ${venueData.municipality}, BC. Browse ${venueData.sportLabels.join(", ") || "drop-ins and classes"} with times and dates on ${SITE_NAME}. ${updated}`
        : `See upcoming drop-ins, classes, and recreation schedules at ${displayTitle} in ${venueData.municipality}, BC on ${SITE_NAME}.`;

  return {
    title,
    description,
    keywords: [
      `${venueData.venueName} schedule`,
      `${venueData.venueName} Victoria BC`,
      `${venueData.venueName} drop-in`,
      ...(searchName ? [`${searchName} schedule`, `${searchName} drop-in`] : []),
      `${venueData.municipality} recreation centre`,
      `${SITE_NAME} ${displayTitle}`,
    ],
    openGraph: {
      title,
      description,
      type: "website",
      url: `/venues/${resolvedParams.venue}`,
    },
    alternates: {
      canonical: `/venues/${resolvedParams.venue}`,
    },
  };
}

export const dynamic = "force-dynamic";

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

  const events = allEvents
    .filter((event) => venueSlug(event.venue_name) === resolvedParams.venue)
    .map((event) => ({ ...event, description: "", last_fetched: "", source_id: "" }));
  const closure = getVenueClosure(resolvedParams.venue);
  const venueName = events[0]?.venue_name || closure?.venueName || resolvedParams.venue;
  const municipality = events[0]?.municipality || closure?.municipality || "Greater Victoria";
  const seo = getVenueSeo(resolvedParams.venue);
  const searchName = getVenueSearchName(resolvedParams.venue);
  const venueJsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    name: venueName,
    ...(searchName ? { alternateName: searchName } : {}),
    url: `https://clubhubvictoria.ca/venues/${resolvedParams.venue}`,
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
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: "https://clubhubvictoria.ca",
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Rec Centres",
        item: "https://clubhubvictoria.ca/venues",
      },
      {
        "@type": "ListItem",
        position: 3,
        name: venueName,
        item: `https://clubhubvictoria.ca/venues/${resolvedParams.venue}`,
      },
    ],
  };

  return (
    <main className="page">
      <div className="container">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(venueJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
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
          summary={seo?.summary}
          address={seo?.address}
          alternatives={alternatives}
          initialQuery={initialQuery}
          initialNow={now}
        />
      </div>
    </main>
  );
}
