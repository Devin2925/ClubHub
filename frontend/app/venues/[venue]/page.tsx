import Link from "next/link";
import { Metadata } from "next";
import VenueScheduleClient from "../../components/VenueScheduleClient";
import { DEMO_MODE, getDemoEvents } from "../../lib/demo";
import {
  API_BASE,
  EventData,
  venueSlug,
} from "../../lib/utils";
import { getVenueSnapshot, SITE_NAME } from "../../lib/seo";

type Props = {
  params: Promise<{ venue: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const resolvedParams = await params;
  const venueData = getVenueSnapshot(resolvedParams.venue);
  const displayTitle = venueData.venueName;
  const title = `${displayTitle} | Drop-In and Recreation Schedules in ${venueData.municipality}`;
  const description =
    venueData.eventCount > 0
      ? `See ${venueData.eventCount} upcoming activities at ${displayTitle} in ${venueData.municipality}, BC. Browse ${venueData.sportLabels.join(", ") || "drop-ins and classes"} with times and dates on ${SITE_NAME}.`
      : `See upcoming drop-ins, classes, and recreation schedules at ${displayTitle} in ${venueData.municipality}, BC on ${SITE_NAME}.`;

  return {
    title,
    description,
    keywords: [
      `${displayTitle} schedule`,
      `${displayTitle} Victoria BC`,
      `${displayTitle} drop-in`,
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
  const venueName = events[0]?.venue_name || resolvedParams.venue;
  const municipality = events[0]?.municipality || "Greater Victoria";
  const venueJsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsActivityLocation",
    name: venueName,
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
        <VenueScheduleClient events={events} venueName={venueName} municipality={municipality} />
      </div>
    </main>
  );
}
