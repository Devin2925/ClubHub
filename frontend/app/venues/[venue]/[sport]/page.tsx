import Link from "next/link";
import { Metadata } from "next";
import { notFound } from "next/navigation";
import { CITY, IS_VICTORIA } from "../../../lib/city";
import VenueScheduleClient from "../../../components/VenueScheduleClient";
import { DEMO_MODE } from "../../../lib/demo";
import { getDemoEvents, sessionNotes } from "../../../lib/snapshot.server";
import { readDateParam, readParam } from "../../../lib/schedule";
import { API_BASE, EventData, getSportMeta, nowScheduleKey, SPORT_META, venueSlug } from "../../../lib/utils";
import {
  faqJsonLd,
  getVenueSearchName,
  getVenueSnapshot,
  getVenueSportSeo,
  MIN_VENUE_SPORT_SESSIONS,
  serializeJsonLd,
  SITE_NAME,
  SITE_URL,
  snapshotUpdatedLabel,
  venueSportCounts,
  venueSportPages,
} from "../../../lib/seo";

type Props = {
  params: Promise<{ venue: string; sport: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

// One activity at one venue, e.g. /venues/carsa-vikes-recreation/yoga for "carsa yoga".
function pageCopy(venue: string, sport: string) {
  const venueData = getVenueSnapshot(venue);
  const displayName = getVenueSearchName(venue) || venueData.venueName;
  const label = getSportMeta(sport).label;
  const count = venueSportCounts(venue).find(([type]) => type === sport)?.[1] || 0;
  const seo = getVenueSportSeo(venue, sport);
  return {
    ...venueData,
    displayName,
    label,
    count,
    seo,
    title: seo?.metaTitle || `${displayName} ${label} Schedule`,
    heading: seo?.heading || `${displayName} ${label.toLowerCase()} schedule`,
    summary:
      seo?.summary ||
      `Upcoming ${label.toLowerCase()} sessions at ${venueData.venueName} in ${venueData.municipality}, BC, with times and booking links.`,
  };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { venue, sport } = await params;
  const page = pageCopy(venue, sport);
  const updated = `Updated ${snapshotUpdatedLabel()}.`;
  const description = `${
    page.seo?.metaDescription ||
    `${page.count} upcoming ${page.label.toLowerCase()} sessions at ${page.venueName} in ${page.municipality}, BC. See today's times, dates and drop-in details.`
  } ${updated}`;
  const url = `/venues/${venue}/${sport}`;

  return {
    title: page.title,
    description,
    keywords: [
      `${page.displayName} ${page.label.toLowerCase()}`,
      `${page.displayName} ${page.label.toLowerCase()} schedule`,
      `${page.venueName} ${page.label.toLowerCase()}`,
      `${page.label.toLowerCase()} ${page.municipality}`,
    ],
    robots: page.count >= MIN_VENUE_SPORT_SESSIONS ? undefined : { index: false, follow: true },
    openGraph: { title: `${page.title} | ${SITE_NAME}`, description, type: "website", url },
    twitter: { card: "summary", title: `${page.title} | ${SITE_NAME}`, description },
    alternates: { canonical: url },
  };
}

// Static at build (bundled-snapshot data); the client handles live "now" and filters.
// Prebuilt set matches the sitemap's venue×sport pages (excludes "other").
export const dynamic = "force-static";

export function generateStaticParams() {
  return venueSportPages().map(({ venue, sport }) => ({ venue, sport }));
}

export default async function VenueSportPage({ params, searchParams }: Props) {
  const { venue, sport } = await params;
  if (!SPORT_META[sport] || sport === "other") notFound();
  const query = await searchParams;
  const initialQuery = {
    date: query.date === undefined ? undefined : readDateParam(readParam(query.date)),
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
    .filter((event) => venueSlug(event.venue_name) === venue && event.sport_type === sport);
  const notes = sessionNotes(venueEvents);
  const events = venueEvents.map((event) => ({ ...event, description: "", last_fetched: "", source_id: "" }));
  if (events.length === 0 && !getVenueSportSeo(venue, sport)) notFound();

  const page = pageCopy(venue, sport);
  const venueUrl = `${SITE_URL}/venues/${venue}`;
  const generatedAnswers = events.length
    ? [
        {
          question: `Is there drop-in ${page.label.toLowerCase()} at ${page.displayName}?`,
          answer: `Yes — ${page.count} upcoming ${page.label.toLowerCase()} session${
            page.count === 1 ? "" : "s"
          } at ${page.venueName} in ${page.municipality}, BC. Tap one for its time and how to book.`,
        },
        {
          question: "Does this schedule include today?",
          answer: "Yes. Use the date buttons to check today or an upcoming date.",
        },
      ]
    : undefined;
  const answers = page.seo?.answers?.length ? page.seo.answers : IS_VICTORIA ? page.seo?.answers : generatedAnswers;
  const faq = faqJsonLd(answers);
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Rec Centres", item: `${SITE_URL}/venues` },
      { "@type": "ListItem", position: 3, name: page.venueName, item: venueUrl },
      { "@type": "ListItem", position: 4, name: page.label, item: `${venueUrl}/${sport}` },
    ],
  };

  return (
    <main className="page">
      <div className="container">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbJsonLd) }} />
        {faq ? (
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(faq) }} />
        ) : null}
        <Link href={`/venues/${venue}`} className="section-link" style={{ marginTop: "1rem", display: "inline-flex" }}>
          All {page.displayName} activities
        </Link>
        <VenueScheduleClient
          events={events}
          venueName={page.venueName}
          municipality={page.municipality}
          searchName={getVenueSearchName(venue)}
          pageHeading={page.heading}
          summary={page.summary}
          answers={answers}
          updatedLabel={snapshotUpdatedLabel()}
          relatedLinks={[
            { href: `/venues/${venue}`, label: `All ${page.displayName} activities` },
            { href: `/sports/${sport}`, label: `${page.label} across ${CITY.region}` },
          ]}
          hideSportFilter
          notes={notes}
          initialQuery={initialQuery}
          initialNow={nowScheduleKey()}
        />
      </div>
    </main>
  );
}
