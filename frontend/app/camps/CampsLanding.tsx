import Link from "next/link";
import CampsPageClient from "./CampsPageClient";
import { CAMP_SEASONS, getCampSeason, type CampSeason } from "../lib/camps";
import {
  areaLabel,
  campProviders,
  getUpcomingCamps,
  priceRangeLabel,
  seasonSummaries,
  type CampListing,
  type SeasonSummary,
} from "../lib/campPages.server";
import { serializeJsonLd, SITE_URL, snapshotUpdatedLabel } from "../lib/seo";
import { formatDate, toScheduleIso } from "../lib/utils";

// "Winter break camps" -> "winter break camps" (keeping "Pro-D"), singular for one.
function campNoun(searchName: string, count: number): string {
  const noun = searchName.replace(/^(?!Pro-D)\w/, (letter) => letter.toLowerCase());
  return count === 1 ? noun.replace(/camps\b/, "camp") : noun;
}

function listLabel(items: string[]): string {
  if (items.length <= 1) return items[0] || "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function campPageData(season?: CampSeason) {
  const all = getUpcomingCamps();
  const summaries = seasonSummaries(all);
  const camps = season ? all.filter((camp) => camp.season === season) : all;
  return { all, camps, summaries, summary: season ? summaries.find((row) => row.slug === season) : undefined };
}

function seasonTitle(slug: CampSeason, year: number): string {
  switch (slug) {
    case "winter-break":
      return `Winter Break Camps in Victoria, BC ${year}`;
    case "pro-d-days":
      return "Pro-D Day Camps in Victoria, BC";
    case "spring-break":
      return `Spring Break Camps in Victoria, BC ${year}`;
    default:
      return `Summer Camps for Kids in Victoria, BC ${year}`;
  }
}

export function campSeasonMeta(slug: CampSeason, summary?: SeasonSummary) {
  const info = getCampSeason(slug)!;
  const year = summary?.year || new Date().getFullYear();
  const title = seasonTitle(slug, year);
  const areas = (summary?.areas || []).map(areaLabel);
  const name = campNoun(info.searchName, summary?.count || 0);
  const description = summary?.count
    ? `${summary.count} ${name} in Greater Victoria, ${summary.span}: dates, daily hours, ages, prices and spots left${
        areas.length ? ` in ${listLabel(areas)}` : ""
      }.`
    : `${info.searchName} in Victoria, BC for ${year}: the recreation centres and camp providers to watch, with dates added here as soon as they're posted.`;
  return { title, description, info, year };
}

// Answers built from the listings, so dates and prices stay true as camps change.
function campAnswers(summaries: SeasonSummary[], camps: CampListing[], season?: CampSeason) {
  const bySlug = Object.fromEntries(summaries.map((row) => [row.slug, row])) as Record<CampSeason, SeasonSummary>;
  const answers: { question: string; answer: string }[] = [];
  const winter = bySlug["winter-break"];
  const proD = bySlug["pro-d-days"];
  const spring = bySlug["spring-break"];
  const summer = bySlug["summer"];

  if ((!season || season === "winter-break") && winter.count) {
    answers.push({
      question: `When are winter break camps in Victoria in ${winter.year}?`,
      answer: `Winter break camps listed here run ${winter.span}. ${winter.count} camps are listed from ${listLabel(winter.providers.slice(0, 5))}${winter.providers.length > 5 ? " and more" : ""}, from single days to full weeks.`,
    });
    const range = priceRangeLabel(winter);
    const priced = camps
      .filter((camp) => camp.season === "winter-break" && /\$\d/.test(camp.price || ""))
      .sort((a, b) => parseFloat(a.price.replace(/[^\d.]/g, "")) - parseFloat(b.price.replace(/[^\d.]/g, "")));
    if (range && priced.length > 1) {
      const cheapest = priced[0];
      const priciest = priced[priced.length - 1];
      answers.push({
        question: "How much do winter break camps cost?",
        answer: `Listed prices range from ${range}. The lowest is ${cheapest.title} (${cheapest.provider}); the highest is ${priciest.title} (${priciest.provider}). Multi-day camps are priced for the whole run.`,
      });
    }
  }
  if ((!season || season === "pro-d-days") && proD.count) {
    const days = proD.singleDays.slice(0, 6);
    answers.push({
      question: "When is the next Pro-D day camp?",
      answer: `Pro-D day camps listed here fall on ${listLabel(days.map((day) => formatDate(`${day}T00:00:00`)))}. Most run a full school day and fill early, so check spots left before you plan around one.`,
    });
  }
  if (!season || season === "spring-break") {
    answers.push({
      question: `When do spring break camps open for registration?`,
      answer: spring.count
        ? `${spring.count} spring break camps are posted so far (${spring.span}). Recreation centres add more as registration opens; this page updates daily.`
        : `Greater Victoria recreation centres post spring break camps on their registration sites ahead of the March break. They appear on this page as soon as they're posted; the providers below are where to look first.`,
    });
  }
  if (!season || season === "summer") {
    answers.push({
      question: `Where can I find summer camps for kids in Victoria for ${summer.year}?`,
      answer: summer.count
        ? `${summer.count} summer camps are listed so far, ${summer.span}. Municipal day camps from Saanich, Oak Bay, West Shore and Panorama sit alongside independent camps such as Braefoot.`
        : `Summer camp dates for ${summer.year} aren't posted yet. The providers below (municipal recreation, community associations, schools, arts and sports camps) are the ones to watch; ClubHub adds each camp's dates, ages and prices as they're published.`,
    });
  }
  answers.push({
    question: "How current are these camp listings?",
    answer: `Dates, prices and spots left are read from each provider's registration system every day. Last updated ${snapshotUpdatedLabel()}. Register on the provider's own site; spots can go quickly.`,
  });
  return answers;
}

function campJsonLd(camps: CampListing[], path: string, name: string) {
  const events = camps.slice(0, 60).map((camp) => {
    const lastDay = camp.end_date || camp.start_time.slice(0, 10);
    const endTime = (camp.end_time || camp.start_time).replace("T", " ").slice(11, 19) || "17:00:00";
    const price = (/\$\s*(\d+(?:\.\d+)?)/.exec(camp.price || "") || [])[1];
    return {
      "@type": "Event",
      name: camp.title,
      startDate: toScheduleIso(camp.start_time),
      endDate: toScheduleIso(`${lastDay} ${endTime}`),
      eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
      eventStatus: "https://schema.org/EventScheduled",
      ...(camp.ages && /^\d/.test(camp.ages) ? { typicalAgeRange: camp.ages.replace("½", ".5") } : {}),
      ...(camp.description ? { description: camp.description } : {}),
      location: {
        "@type": "Place",
        name: camp.venue_name,
        address: {
          "@type": "PostalAddress",
          addressLocality: camp.municipality === "Panorama" ? "North Saanich" : camp.municipality,
          addressRegion: "BC",
          addressCountry: "CA",
        },
      },
      organizer: { "@type": "Organization", name: camp.provider },
      ...(camp.booking_url
        ? {
            offers: {
              "@type": "Offer",
              url: camp.booking_url,
              ...(price ? { price, priceCurrency: "CAD" } : {}),
              availability: /full/i.test(camp.availability || "")
                ? "https://schema.org/SoldOut"
                : "https://schema.org/InStock",
            },
          }
        : {}),
    };
  });
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        name,
        url: `${SITE_URL}${path}`,
        mainEntity: { "@type": "ItemList", numberOfItems: camps.length, itemListElement: events.map((event, index) => ({ "@type": "ListItem", position: index + 1, item: event })) },
      },
    ],
  };
}

export default function CampsLanding({ season }: { season?: CampSeason }) {
  const { all, camps, summaries, summary } = campPageData(season);
  const providers = campProviders(all).sort((a, b) => b.campCount - a.campCount);
  const seasonCounts = Object.fromEntries(summaries.map((row) => [row.slug, row.count]));
  const info = season ? getCampSeason(season) : undefined;
  const meta = season ? campSeasonMeta(season, summary) : undefined;
  const path = season ? `/camps/${season}` : "/camps";
  const heading = season
    ? season === "pro-d-days"
      ? "Pro-D day camps in Victoria"
      : `${meta!.year} ${campNoun(info!.searchName, 2)}${season === "summer" ? " for kids" : ""} in Victoria`
    : "Kids camps in Victoria, BC";
  const answers = campAnswers(summaries, all, season);
  const open = camps.filter((camp) => !/full/i.test(camp.availability || "")).length;

  const breadcrumbs = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Kids camps", item: `${SITE_URL}/camps` },
      ...(info ? [{ "@type": "ListItem", position: 3, name: info.searchName, item: `${SITE_URL}${path}` }] : []),
    ],
  };

  return (
    <main className="page">
      <div className="container">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbs) }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(campJsonLd(camps, path, heading)) }}
        />
        {season ? (
          <Link href="/camps" className="section-link" style={{ marginTop: "1rem", display: "inline-flex" }}>
            All kids camps
          </Link>
        ) : null}
        <section className="hero hero-simple camp-hero">
          <div className="chip-group-label">Greater Victoria · updated daily</div>
          <h1>{heading}</h1>
          <p className="hero-subtitle">
            {season
              ? summary?.count
                ? `${summary.count} ${campNoun(info!.searchName, summary.count)}, ${summary.span}, with daily hours, ages, prices and spots left. ${info!.blurb}`
                : `${info!.blurb} Dates for ${meta!.year} aren't posted yet; the providers below list them first.`
              : `Winter break, Pro-D day, spring break and summer camps from Saanich, Oak Bay, Esquimalt, the West Shore, the Saanich Peninsula, Sooke and independent providers, with dates, ages, prices and spots left in one place.`}
          </p>
          {camps.length ? (
            <p className="camp-hero-stats">
              <strong>{camps.length}</strong> {camps.length === 1 ? "camp" : "camps"} · <strong>{open}</strong> with spots
              open
            </p>
          ) : null}
        </section>

        {season ? null : (
          <nav className="camp-season-cards" aria-label="Camps by school break">
            {CAMP_SEASONS.map((item) => {
              const row = summaries.find((entry) => entry.slug === item.slug)!;
              return (
                <Link key={item.slug} href={`/camps/${item.slug}`} className="camp-season-card">
                  <span className="camp-season-card-label">{item.searchName}</span>
                  <span className="camp-season-card-detail">
                    {row.count ? `${row.count} ${row.count === 1 ? "camp" : "camps"} · ${row.span}` : `${row.year} dates coming`}
                  </span>
                </Link>
              );
            })}
          </nav>
        )}

        <CampsPageClient camps={camps} providers={providers} season={season} seasonCounts={seasonCounts} />

        <section className="schedule-guide">
          <h2 className="section-title">{info ? `${info.searchName}: quick answers` : "Kids camps: quick answers"}</h2>
          <div className="schedule-guide-grid">
            {answers.map((item) => (
              <article key={item.question} className="schedule-guide-item">
                <h3>{item.question}</h3>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
        </section>

        {season ? (
          <nav className="venue-activity-links" aria-label="Other camps">
            {CAMP_SEASONS.filter((item) => item.slug !== season).map((item) => (
              <Link key={item.slug} href={`/camps/${item.slug}`} className="section-link">
                {item.searchName}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>
    </main>
  );
}
