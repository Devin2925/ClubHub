import Link from "next/link";
import { Metadata } from "next";
import EventCard from "../../components/EventCard";
import { DEMO_MODE, getDemoEvents } from "../../lib/demo";
import {
  API_BASE,
  EventData,
  formatFullDate,
  formatMonthDay,
  getDateKey,
  getOfferingMeta,
  getSportMeta,
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

  const groupedByDate = Object.entries(
    events.reduce<Record<string, EventData[]>>((groups, event) => {
      const key = getDateKey(event.start_time);
      if (!groups[key]) groups[key] = [];
      groups[key].push(event);
      return groups;
    }, {})
  ).sort(([a], [b]) => a.localeCompare(b));

  const sportCounts = Object.entries(
    events.reduce<Record<string, number>>((counts, event) => {
      counts[event.sport_type] = (counts[event.sport_type] || 0) + 1;
      return counts;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  const offeringCounts = Object.entries(
    events.reduce<Record<string, number>>((counts, event) => {
      counts[event.offering_type] = (counts[event.offering_type] || 0) + 1;
      return counts;
    }, {})
  ).sort((a, b) => b[1] - a[1]);
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

        <section className="hero" style={{ paddingTop: "3rem" }}>
          <div className="chip-group-label">{municipality}</div>
          <h1>
            What&apos;s on at <strong>{venueName}</strong>
          </h1>
          <p className="hero-subtitle">
            Upcoming drop-ins, classes, swims, skates, and community activities at this venue in {municipality}, BC.
          </p>

          <div className="status-strip status-strip-wide">
            <div className="status-card">
              <div className="status-kicker">Upcoming</div>
              <div className="status-number">{events.length}</div>
              <div className="status-copy">Activities at this venue</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Sports And Types</div>
              <div className="status-number">{sportCounts.length}</div>
              <div className="status-copy">Different categories represented</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Next Date</div>
              <div className="status-number">
                {events[0] ? formatMonthDay(events[0].start_time) : "-"}
              </div>
              <div className="status-copy">Earliest upcoming session</div>
            </div>
          </div>
        </section>

        <section className="browse-layout browse-layout-tight">
          <aside className="browse-sidebar">
            <div className="sidebar-card">
              <div className="chip-group-label">Sport Mix</div>
              <div className="sidebar-links">
                {sportCounts.map(([sport, count]) => (
                  <div key={sport} className="sidebar-link static">
                    <span>{getSportMeta(sport).label}</span>
                    <span>{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="sidebar-card">
              <div className="chip-group-label">Activity Types</div>
              <div className="sidebar-links">
                {offeringCounts.map(([offeringType, count]) => (
                  <div key={offeringType} className="sidebar-link static">
                    <span>{getOfferingMeta(offeringType).label}</span>
                    <span>{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <section className="browse-main">
            {groupedByDate.length === 0 ? (
              <div className="empty-state">
                <span className="empty-state-mark">No Upcoming Activity</span>
                This venue does not have any future sessions in the current schedule.
              </div>
            ) : (
              groupedByDate.map(([dateKey, dayEvents]) => (
                <div key={dateKey} className="day-group">
                  <div className="day-group-header">
                    <span className="day-group-date">{formatFullDate(`${dateKey}T00:00:00`)}</span>
                    <span className="day-count">{dayEvents.length} activities</span>
                  </div>
                  <div className="events-list">
                    {dayEvents.map((event) => (
                      <EventCard key={event.id} event={event} />
                    ))}
                  </div>
                </div>
              ))
            )}
          </section>
        </section>
      </div>
    </main>
  );
}
