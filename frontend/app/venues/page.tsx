"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DEMO_MODE, getDemoEvents } from "../lib/demo";
import { API_BASE, EventData, formatFullDate, venueSlug } from "../lib/utils";

export default function VenuesPage() {
  const [events, setEvents] = useState<EventData[]>(() => (DEMO_MODE ? getDemoEvents() : []));
  const [loading, setLoading] = useState(!DEMO_MODE);
  const [activeMunicipality, setActiveMunicipality] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (DEMO_MODE) return;
    fetch(`${API_BASE}/api/events`)
      .then((response) => response.json())
      .then((data) => setEvents(data.events || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const municipalities = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.municipality))).sort();
  }, [events]);

  const venueCards = useMemo(() => {
    const map = new Map<string, { municipality: string; count: number; nextTime: string }>();
    for (const event of events) {
      if (activeMunicipality && event.municipality !== activeMunicipality) continue;
      if (searchTerm.trim() && !event.venue_name.toLowerCase().includes(searchTerm.trim().toLowerCase())) continue;

      const existing = map.get(event.venue_name);
      if (!existing) {
        map.set(event.venue_name, {
          municipality: event.municipality,
          count: 1,
          nextTime: event.start_time,
        });
      } else {
        existing.count += 1;
        if (event.start_time < existing.nextTime) existing.nextTime = event.start_time;
      }
    }

    return Array.from(map.entries())
      .map(([venueName, value]) => ({
        venueName,
        municipality: value.municipality,
        count: value.count,
        nextTime: value.nextTime,
      }))
      .sort((a, b) => a.venueName.localeCompare(b.venueName));
  }, [activeMunicipality, events, searchTerm]);

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
              <div className="venue-card-count">{venue.count} upcoming activities</div>
              <div className="venue-card-next">
                Next activity: {formatFullDate(venue.nextTime)}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
