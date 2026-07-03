import { Metadata } from "next";
import { DEMO_MODE, getDemoEvents } from "../../lib/demo";
import { getSportMeta, API_BASE, formatFullDate, getDateKey, EventData } from "../../lib/utils";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "../../components/SportIcons";
import EventCard from "../../components/EventCard";
import Link from "next/link";
import { getSportSnapshot, SITE_NAME } from "../../lib/seo";

type Props = {
  params: Promise<{ sport: string }>;
};

export async function generateMetadata(
  { params }: Props
): Promise<Metadata> {
  const resolvedParams = await params;
  const sport = resolvedParams.sport;
  const sportData = getSportSnapshot(sport);
  const sportMeta = getSportMeta(sport);
  const title = `${sportData.label} in Victoria, BC | Drop-In Schedules, Venues, and Times`;
  const description =
    sportData.eventCount > 0
      ? `Browse ${sportData.eventCount} upcoming ${sportData.label.toLowerCase()} sessions across ${sportData.venueCount} venues in Greater Victoria, BC. Check times, locations, and drop-in details on ${SITE_NAME}.`
      : `Browse upcoming ${sportData.label.toLowerCase()} sessions in Greater Victoria, BC. Check venues, dates, and recreation schedule updates on ${SITE_NAME}.`;

  return {
    title,
    description,
    keywords: [
      `${sportMeta.label} Victoria BC`,
      `${sportMeta.label} Greater Victoria`,
      `drop-in ${sportMeta.label.toLowerCase()} Victoria`,
      `${sportMeta.label} schedule Victoria BC`,
      `${SITE_NAME} ${sportMeta.label}`,
    ],
    openGraph: {
      title,
      description,
      type: "website",
      url: `/sports/${sport}`,
    },
    alternates: {
      canonical: `/sports/${sport}`,
    },
  };
}

export const dynamic = "force-dynamic";

export default async function SportDetailPage({ params }: Props) {
  const resolvedParams = await params;
  const sport = resolvedParams.sport;
  const meta = getSportMeta(sport);
  const Icon = SPORT_ICON_COMPONENTS[sport] || GenericSportIcon;

  let events: EventData[] = [];
  if (DEMO_MODE) {
    events = getDemoEvents().filter((event) => event.sport_type === sport);
  } else {
    const res = await fetch(`${API_BASE}/api/events?sport=${sport}`, { cache: 'no-store' });
    const data = await res.json();
    events = data.events || [];
  }

  // Group by date
  const groups: Record<string, EventData[]> = {};
  for (const ev of events) {
    const key = getDateKey(ev.start_time);
    if (!groups[key]) groups[key] = [];
    groups[key].push(ev);
  }
  const grouped = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));

  // Unique venues for this sport
  const counts: Record<string, number> = {};
  for (const ev of events) {
    counts[ev.venue_name] = (counts[ev.venue_name] || 0) + 1;
  }
  const venueBreakdown = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const sportJsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${meta.label} in Victoria, BC`,
    description: `Upcoming ${meta.label.toLowerCase()} schedules across Greater Victoria.`,
    url: `https://clubhubvictoria.ca/sports/${sport}`,
    isPartOf: {
      "@type": "WebSite",
      name: SITE_NAME,
      url: "https://clubhubvictoria.ca",
    },
    about: {
      "@type": "Thing",
      name: meta.label,
    },
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
        name: "Sports",
        item: "https://clubhubvictoria.ca/sports",
      },
      {
        "@type": "ListItem",
        position: 3,
        name: meta.label,
        item: `https://clubhubvictoria.ca/sports/${sport}`,
      },
    ],
  };

  return (
    <main className="page">
      <div className="container">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(sportJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
        />
        <Link href="/sports" style={{ color: "var(--text-muted)", fontSize: "0.9rem", display: "inline-block", marginBottom: "1.5rem", fontWeight: 500 }}>
          ← Back to All Sports
        </Link>

        <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", marginBottom: "2rem" }}>
          <div style={{
            color: meta.color,
            background: "var(--bg-card)",
            border: `1px solid ${meta.color}40`,
            width: "60px", height: "60px",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Icon width="32" height="32" />
          </div>
          <div>
            <h1 style={{ fontSize: "2.5rem", fontWeight: 300, letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: "0.25rem" }}>
              <strong>{meta.label}</strong> in Victoria, BC
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem" }}>
              {events.length} upcoming sessions across {venueBreakdown.length} venues in Greater Victoria.
            </p>
          </div>
        </div>

        <div style={{ marginTop: "2rem" }}>
          {grouped.length === 0 ? (
            <div style={{ textAlign: "center", padding: "4rem 0", color: "var(--text-muted)" }}>
               No upcoming matches scheduled.
            </div>
          ) : (
            grouped.map(([dateKey, dayEvents]) => (
              <div key={dateKey} className="day-group">
                <div className="day-group-header">
                  <span className="day-group-date">{formatFullDate(dateKey + "T00:00:00")}</span>
                  <span style={{ background: "var(--bg-glass)", padding: "0.2rem 0.6rem", borderRadius: "100px", fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "0.5rem" }}>
                    {dayEvents.length} sessions
                  </span>
                </div>
                <div className="events-list">
                  {dayEvents.map((event) => (
                    <EventCard key={event.id} event={event} />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
