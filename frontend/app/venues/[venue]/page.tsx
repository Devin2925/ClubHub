import Link from "next/link";
import { Metadata } from "next";
import VenueScheduleClient from "../../components/VenueScheduleClient";
import { DEMO_MODE, getDemoEvents } from "../../lib/demo";
import {
  API_BASE,
  EventData,
  venueSlug,
} from "../../lib/utils";
import { getVenueSearchName, getVenueSnapshot, SITE_NAME } from "../../lib/seo";
import { closureHeadline, getVenueClosure } from "../../lib/closures";

type Props = {
  params: Promise<{ venue: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const resolvedParams = await params;
  const venueData = getVenueSnapshot(resolvedParams.venue);
  const searchName = getVenueSearchName(resolvedParams.venue);
  const displayTitle = searchName ? `${venueData.venueName} (${searchName})` : venueData.venueName;
  const closure = getVenueClosure(resolvedParams.venue);
  const title = closure
    ? `${displayTitle} Schedule: ${closureHeadline(closure)}`
    : `${displayTitle} Schedule | Drop-Ins in ${venueData.municipality}`;
  const description = closure
    ? `${displayTitle} is ${closureHeadline(closure).toLowerCase()}. ${closure.summary}`
    : venueData.eventCount > 0
      ? `${displayTitle} drop-in schedule: ${venueData.eventCount} upcoming activities in ${venueData.municipality}, BC. Browse ${venueData.sportLabels.join(", ") || "drop-ins and classes"} with times and dates on ${SITE_NAME}.`
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

export default async function VenueDetailPage({ params }: Props) {
  const resolvedParams = await params;
  let allEvents: EventData[] = [];
  if (DEMO_MODE) {
    allEvents = getDemoEvents();
  } else {
    const response = await fetch(`${API_BASE}/api/events`, { cache: "no-store" });
    const data = await response.json();
    allEvents = data.events || [];
  }

  const events = allEvents.filter((event) => venueSlug(event.venue_name) === resolvedParams.venue);
  const closure = getVenueClosure(resolvedParams.venue);
  const venueName = events[0]?.venue_name || closure?.venueName || resolvedParams.venue;
  const municipality = events[0]?.municipality || closure?.municipality || "Greater Victoria";
  const searchName = getVenueSearchName(resolvedParams.venue);
  const venueJsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    name: venueName,
    ...(searchName ? { alternateName: searchName } : {}),
    url: `https://clubhubvictoria.ca/venues/${resolvedParams.venue}`,
    address: {
      "@type": "PostalAddress",
      addressLocality: municipality,
      addressRegion: "BC",
      addressCountry: "CA",
    },
    description: `Upcoming recreation schedules, drop-ins, and classes at ${venueName} in ${municipality}, British Columbia.`,
  };
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
        <Link href="/venues" className="section-link" style={{ marginTop: "2rem", display: "inline-flex" }}>
          Back to venue list
        </Link>
        <VenueScheduleClient
          events={events}
          venueName={venueName}
          municipality={municipality}
          closure={closure}
          searchName={searchName}
        />
      </div>
    </main>
  );
}
