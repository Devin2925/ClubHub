"use client";

import { useEffect, useMemo, useState } from "react";
import EventCard from "./components/EventCard";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./components/SportIcons";
import { DEMO_MODE, getDemoEvents, getDemoStatus } from "./lib/demo";
import { API_BASE, DISPLAY_TIME_ZONE, EventData, formatDateTime, formatFullDate, getDateKey, getSportMeta, venueSlug } from "./lib/utils";
import { closureHeadline, VENUE_CLOSURES } from "./lib/closures";

interface StatusData {
  last_fetched: string | null;
  admin_access?: boolean;
  source_summary?: {
    total: number;
    healthy: number;
    warning?: number;
    stale?: number;
    error: number;
    running?: number;
  };
  venue_summary?: {
    total: number;
    alerts: number;
  };
}

const INITIAL_EVENT_LIMIT = 80;
const EVENT_LIMIT_STEP = 80;

export default function HomePage() {
  const [events, setEvents] = useState<EventData[]>([]);
  const [status, setStatus] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [scrapeMessage, setScrapeMessage] = useState<string | null>(null);

  const [activeMunicipality, setActiveMunicipality] = useState("");
  const [activeVenue, setActiveVenue] = useState("");
  const [activeDate, setActiveDate] = useState("");
  const [activeSport, setActiveSport] = useState("");
  const [visibleEventLimit, setVisibleEventLimit] = useState(INITIAL_EVENT_LIMIT);
  const feedbackEmail = "clubhubvictoria@gmail.com";

  async function refreshData() {
    if (DEMO_MODE) {
      setEvents(getDemoEvents());
      setStatus(getDemoStatus());
      return;
    }
    const [eventsRes, statusRes] = await Promise.all([
      fetch(`${API_BASE}/api/events`),
      fetch(`${API_BASE}/api/status`),
    ]);

    const eventsData = await eventsRes.json();
    const statusData = await statusRes.json();

    setEvents(eventsData.events || []);
    setStatus(statusData || null);
  }

  useEffect(() => {
    async function fetchData() {
      try {
        await refreshData();
      } catch (error) {
        console.error("Failed to load schedules", error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  async function handleScrape() {
    if (DEMO_MODE) {
      setScrapeMessage("Demo mode is using a frozen snapshot. Local reruns are disabled.");
      return;
    }
    try {
      setScraping(true);
      setScrapeMessage("Refreshing schedules...");
      const response = await fetch(`${API_BASE}/api/scrape`, { method: "POST" });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Refresh failed");
      }

      await refreshData();
      setScrapeMessage(`Refresh complete. ${data.count} upcoming activities in cache.`);
    } catch (error) {
      console.error(error);
      setScrapeMessage("Refresh failed. Check status.");
    } finally {
      setScraping(false);
    }
  }

  const municipalities = useMemo(() => {
    return Array.from(new Set(events.map((event) => event.municipality))).sort();
  }, [events]);

  const venues = useMemo(() => {
    const filtered = events.filter((event) => !activeMunicipality || event.municipality === activeMunicipality);
    return Array.from(new Set(filtered.map((event) => event.venue_name))).sort();
  }, [events, activeMunicipality]);

  const municipalityClosures = VENUE_CLOSURES.filter(
    (closure) => activeMunicipality && closure.municipality === activeMunicipality
  );

  const dates = useMemo(() => {
    const filtered = events.filter((event) => {
      if (activeMunicipality && event.municipality !== activeMunicipality) return false;
      if (activeVenue && event.venue_name !== activeVenue) return false;
      return true;
    });
    return Array.from(new Set(filtered.map((event) => getDateKey(event.start_time)))).sort().slice(0, 21);
  }, [events, activeMunicipality, activeVenue]);

  const availableSports = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      if (activeMunicipality && event.municipality !== activeMunicipality) continue;
      if (activeVenue && event.venue_name !== activeVenue) continue;
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
    }

    return Array.from(counts.entries())
      .map(([sport, count]) => ({ sport, count }))
      .sort((a, b) => b.count - a.count);
  }, [events, activeMunicipality, activeVenue, activeDate]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      if (activeMunicipality && event.municipality !== activeMunicipality) return false;
      if (activeVenue && event.venue_name !== activeVenue) return false;
      if (activeDate && getDateKey(event.start_time) !== activeDate) return false;
      if (activeSport && event.sport_type !== activeSport) return false;
      return true;
    });
  }, [events, activeMunicipality, activeVenue, activeDate, activeSport]);

  const groupedEvents = useMemo(() => {
    const groups: Record<string, EventData[]> = {};
    for (const event of filteredEvents.slice(0, visibleEventLimit)) {
      const key = getDateKey(event.start_time);
      if (!groups[key]) groups[key] = [];
      groups[key].push(event);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredEvents, visibleEventLimit]);

  const hasMoreEvents = filteredEvents.length > visibleEventLimit;

  useEffect(() => {
    setActiveVenue("");
    setActiveDate("");
    setActiveSport("");
  }, [activeMunicipality]);

  useEffect(() => {
    setActiveDate("");
    setActiveSport("");
  }, [activeVenue]);

  useEffect(() => {
    setActiveSport("");
  }, [activeDate]);

  useEffect(() => {
    setVisibleEventLimit(INITIAL_EVENT_LIMIT);
  }, [activeMunicipality, activeVenue, activeDate, activeSport]);

  if (loading) {
    return (
      <main className="page">
        <div className="container loading-block">Loading schedules...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <section className="hero hero-simple">
          <h1>
            Find <strong>drop-ins, classes, and rec schedules</strong> across Victoria
          </h1>
          <p className="hero-subtitle">
            Pick a municipality, choose a rec centre, and scan upcoming swims, skates, pickleball, hockey, fitness, and community programs.
          </p>

          <div className="hero-actions">
            {status?.admin_access ? (
              <button
                className="chip active"
                onClick={handleScrape}
                disabled={scraping}
                type="button"
                style={{ opacity: scraping ? 0.7 : 1 }}
              >
                {scraping ? "Refreshing..." : "Refresh Schedules"}
              </button>
            ) : null}
            <span className="hero-timestamp">
              {status?.last_fetched
                ? `Last sync: ${formatDateTime(status.last_fetched)}`
                : "No sync recorded yet"}
            </span>
          </div>

          {scrapeMessage ? <div className="hero-message">{scrapeMessage}</div> : null}
          <div className="hero-message">
            {DEMO_MODE ? "Mode: demo snapshot" : `Mode: live API at ${API_BASE}`} · Times shown in {DISPLAY_TIME_ZONE}
          </div>

          <div className="trust-strip" aria-label="Site status and feedback">
            <div className="trust-card">
              <div className="trust-kicker">Coverage</div>
              <div className="trust-copy">
                Victoria-area municipal rec centres, community schedules, and UVic CARSA where times are publicly posted, so locals can check one site instead of bouncing between rec pages.
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-kicker">Freshness</div>
              <div className="trust-copy">
                Upcoming dates only, refreshed from source schedules so Victoria, BC activity times stay useful instead of stale.
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-kicker">Health</div>
              <div className="trust-copy">
                {status?.source_summary
                  ? `${status.source_summary.healthy}/${status.source_summary.total} sources healthy, ${status.venue_summary?.alerts ?? 0} venue alerts.`
                  : "Health summary unavailable."}{" "}
                <a href="/status" className="inline-link">
                  Check source status
                </a>
                .
              </div>
            </div>
            <div className="trust-card">
              <div className="trust-kicker">Feedback</div>
              <div className="trust-copy">
                Spot a wrong schedule or missing venue?{" "}
                <a href={`mailto:${feedbackEmail}?subject=ClubHub schedule issue`} className="inline-link">
                  Report it here
                </a>
                .
              </div>
            </div>
          </div>
        </section>

        <section className="simple-filter-panel">
          <div className="simple-municipality-row">
            <div className="chip-group-label">Municipality</div>
            <div className="municipality-picker">
              <button
                className={`municipality-pill ${activeMunicipality === "" ? "active" : ""}`}
                onClick={() => setActiveMunicipality("")}
                type="button"
              >
                All Municipalities
              </button>
              {municipalities.map((municipality) => (
                <button
                  key={municipality}
                  className={`municipality-pill ${activeMunicipality === municipality ? "active" : ""}`}
                  onClick={() => setActiveMunicipality(municipality)}
                  type="button"
                >
                  {municipality}
                </button>
              ))}
            </div>
          </div>

          <div className="simple-filter-grid">
            <div className="simple-filter-field">
              <label className="chip-group-label" htmlFor="venue-select">
                Rec Centre
              </label>
              <select
                id="venue-select"
                className="filter-select"
                value={activeVenue}
                onChange={(event) => setActiveVenue(event.target.value)}
                disabled={municipalities.length === 0}
              >
                <option value="">{activeMunicipality ? "Choose a rec centre" : "Choose a municipality above"}</option>
                {venues.map((venue) => (
                  <option key={venue} value={venue}>
                    {venue}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {municipalityClosures.map((closure) => (
            <p key={closure.venueName} className="closure-inline-note">
              <strong>{closure.venueName}</strong> is {closureHeadline(closure).toLowerCase()}.{" "}
              <a className="inline-link" href={`/venues/${venueSlug(closure.venueName)}`}>
                Details
              </a>
            </p>
          ))}

          <div className="simple-date-row">
            <div className="chip-group-label">Dates</div>
            <div className="horizontal-scroller full-width-scroller">
              <button
                className={`chip ${activeDate === "" ? "active" : ""}`}
                onClick={() => setActiveDate("")}
                type="button"
              >
                All Dates
              </button>
              {dates.map((date) => (
                <button
                  key={date}
                  className={`chip ${activeDate === date ? "active" : ""}`}
                  onClick={() => setActiveDate(date)}
                  type="button"
                >
                  {formatFullDate(`${date}T00:00:00`).replace(", 2026", "")}
                </button>
              ))}
            </div>
          </div>

          <div className="simple-activity-row">
            <div className="chip-group-label">Activities</div>
            <div className="horizontal-scroller">
              <button
                className={`chip emoji-chip ${activeSport === "" ? "active" : ""}`}
                onClick={() => setActiveSport("")}
                type="button"
              >
                <GenericSportIcon width="18" height="18" />
                <span>All</span>
              </button>
              {availableSports.map(({ sport, count }) => {
                const Icon = SPORT_ICON_COMPONENTS[sport] || GenericSportIcon;
                const meta = getSportMeta(sport);
                return (
                  <button
                    key={sport}
                    className={`chip emoji-chip sport-chip ${activeSport === sport ? "active" : ""}`}
                    onClick={() => setActiveSport(sport)}
                    type="button"
                    style={{ color: activeSport === sport ? undefined : meta.color }}
                  >
                    <Icon width="18" height="18" />
                    <span>{meta.label}</span>
                    <span className="emoji-chip-count">{count}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <section className="simple-results-header">
          <div className="chip-group-label">Current View</div>
          <h2 className="section-title">
            {activeVenue || activeMunicipality || "All upcoming activities"}
          </h2>
          <p className="section-copy">
            Showing {Math.min(filteredEvents.length, visibleEventLimit)} of {filteredEvents.length} activities
          </p>
        </section>

        {groupedEvents.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-mark">No Results</span>
            Choose a municipality and rec centre to start browsing.
          </div>
        ) : (
          groupedEvents.map(([dateKey, dayEvents]) => (
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
        {hasMoreEvents ? (
          <div className="show-more-row">
            <button
              className="show-more-button"
              type="button"
              onClick={() => setVisibleEventLimit((current) => current + EVENT_LIMIT_STEP)}
            >
              Show {Math.min(EVENT_LIMIT_STEP, filteredEvents.length - visibleEventLimit)} more
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}
