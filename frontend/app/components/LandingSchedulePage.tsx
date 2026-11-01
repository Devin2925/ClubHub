import Link from "next/link";
import type { Metadata } from "next";
import VenueScheduleClient from "./VenueScheduleClient";
import { initialSchedule } from "../lib/snapshot.server";
import { readDateParam, readParam, type EventFilter } from "../lib/schedule";
import { nowScheduleKey } from "../lib/utils";
import { serializeJsonLd, SITE_NAME, SITE_URL, snapshotUpdatedLabel } from "../lib/seo";

export type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

interface Crumb {
  name: string;
  path: string;
}

interface LandingSchedulePageProps {
  filter: EventFilter;
  searchParams: SearchParams;
  path: string;
  heading: string;
  // Small label above the heading, e.g. the area or "Greater Victoria".
  kicker: string;
  // Used in running text: "How current is this lane swimming schedule?"
  shortName: string;
  subtitle: string;
  summary: string;
  aboutTitle: string;
  // Name for structured data, e.g. "Lane swimming in Victoria, BC".
  collectionName: string;
  breadcrumbs: Crumb[];
  back: Crumb;
  relatedLinks?: { href: string; label: string; count?: number; featured?: boolean }[];
  answers?: { question: string; answer: string }[];
  hideSportFilter?: boolean;
}

export function landingMetadata({
  title,
  description,
  path,
  count,
  keywords,
}: {
  title: string;
  description: string;
  path: string;
  count: number;
  keywords: string[];
}): Metadata {
  const fullDescription = `${description} Updated ${snapshotUpdatedLabel()}.`;
  return {
    title,
    description: fullDescription,
    keywords,
    robots: count > 0 ? undefined : { index: false, follow: true },
    openGraph: { title: `${title} | ${SITE_NAME}`, description: fullDescription, type: "website", url: path },
    twitter: { card: "summary", title: `${title} | ${SITE_NAME}`, description: fullDescription },
    alternates: { canonical: path },
  };
}

// A schedule page for a search that spans venues: a sport, a kind of session or
// an area. The visitor's day is server-rendered; the rest loads in the browser.
export default async function LandingSchedulePage({
  filter,
  searchParams,
  path,
  heading,
  kicker,
  shortName,
  subtitle,
  summary,
  aboutTitle,
  collectionName,
  breadcrumbs,
  back,
  relatedLinks,
  answers,
  hideSportFilter,
}: LandingSchedulePageProps) {
  const query = await searchParams;
  const initialQuery = {
    date: query.date === undefined ? undefined : readDateParam(readParam(query.date)),
    sport: hideSportFilter ? undefined : readParam(query.sport) || undefined,
    type: readParam(query.type) || undefined,
  };
  const now = nowScheduleKey();
  const schedule = initialSchedule(filter, initialQuery.date, now);

  const collectionJsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: collectionName,
    description: summary,
    url: `${SITE_URL}${path}`,
    isPartOf: { "@type": "WebSite", name: SITE_NAME, url: SITE_URL },
  };
  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: breadcrumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.name,
      item: `${SITE_URL}${crumb.path}`,
    })),
  };

  return (
    <main className="page">
      <div className="container">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(collectionJsonLd) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbJsonLd) }} />
        <Link href={back.path} className="section-link" style={{ marginTop: "1rem", display: "inline-flex" }}>
          {back.name}
        </Link>
        <VenueScheduleClient
          events={schedule.events}
          loadFilter={filter}
          initialDates={schedule.dates}
          initialTotal={schedule.upcoming.length}
          venueName={collectionName}
          subtitle={subtitle}
          aboutTitle={aboutTitle}
          municipality={kicker}
          searchName={shortName}
          pageHeading={heading}
          summary={summary}
          answers={answers}
          updatedLabel={snapshotUpdatedLabel()}
          relatedLinks={relatedLinks}
          hideSportFilter={hideSportFilter}
          initialQuery={initialQuery}
          initialNow={now}
        />
      </div>
    </main>
  );
}
