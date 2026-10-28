"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DEMO_MODE } from "../lib/demo";
import { API_BASE, formatFullDate, venueSlug } from "../lib/utils";
import { summarizeVenues, type VenueSummary } from "../lib/venues";
import { closureHeadline, VENUE_CLOSURES } from "../lib/closures";

export default function VenuesPageClient({ demoVenues }: { demoVenues: VenueSummary[] | null }) {
  const [venues, setVenues] = useState<VenueSummary[]>(() => demoVenues || []);
  const [loading, setLoading] = useState(!DEMO_MODE);
  const [activeMunicipality, setActiveMunicipality] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (DEMO_MODE) return;
    fetch(`${API_BASE}/api/events`)
      .then((response) => response.json())
      .then((data) => setVenues(summarizeVenues(data.events || [])))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const municipalities = useMemo(() => {
    return Array.from(new Set(venues.map((venue) => venue.municipality))).sort();
  }, [venues]);

  const venueCards = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();
    const cards = venues
      .filter((venue) => !activeMunicipality || venue.municipality === activeMunicipality)
      .filter((venue) => !search || venue.venueName.toLowerCase().includes(search))
      .map((venue) => ({
        ...venue,
        closure: VENUE_CLOSURES.find((closure) => closure.venueName === venue.venueName),
      }));

    for (const closure of VENUE_CLOSURES) {
      if (venues.some((venue) => venue.venueName === closure.venueName)) continue;
      if (activeMunicipality && closure.municipality !== activeMunicipality) continue;
      if (search && !closure.venueName.toLowerCase().includes(search)) continue;
      cards.push({ venueName: closure.venueName, municipality: closure.municipality, count: 0, nextTime: "", closure });
    }

    return cards.sort((a, b) => a.venueName.localeCompare(b.venueName));
  }, [activeMunicipality, venues, searchTerm]);

  if (loading) {
    return (
      <main className="page">
        <div className="container loading-block">Loading venues...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <section className="hero">
          <h1>
            Browse by <strong>rec centre</strong>
          </h1>
          <p className="hero-subtitle">
            Pick a municipality, then open a venue page to see what is happening there this week.
          </p>
        </section>

        <section className="filter-container">
          <div className="filter-grid filter-grid-compact">
            <select
              className="filter-select"
              value={activeMunicipality || ""}
              onChange={(event) => setActiveMunicipality(event.target.value || null)}
            >
              <option value="">All Municipalities</option>
              {municipalities.map((municipality) => (
                <option key={municipality} value={municipality}>
                  {municipality}
                </option>
              ))}
            </select>
            <input
              className="filter-input"
              placeholder="Search a rec centre or venue"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </div>
        </section>

        <div className="venue-grid">
          {venueCards.map((venue) => (
            <Link key={venue.venueName} href={`/venues/${venueSlug(venue.venueName)}`} className="venue-card">
              <div className="venue-card-municipality">{venue.municipality}</div>
              <div className="venue-card-name">{venue.venueName}</div>
              {venue.closure && <div className="venue-card-closure">{closureHeadline(venue.closure)}</div>}
              {venue.count > 0 ? (
                <>
                  <div className="venue-card-count">{venue.count} upcoming activities</div>
                  <div className="venue-card-next">
                    Next activity: {formatFullDate(venue.nextTime)}
                  </div>
                </>
              ) : (
                <div className="venue-card-count">No scheduled activities</div>
              )}
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
