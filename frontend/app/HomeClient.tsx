"use client";

import { useEffect, useMemo, useState } from "react";
import EventCard from "./components/EventCard";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./components/SportIcons";
import { DEMO_MODE, fetchDemoEvents } from "./lib/demo";
import {
  API_BASE,
  DISPLAY_TIME_ZONE,
  EventData,
  formatDateTime,
  formatFullDate,
  getDateKey,
  getSportMeta,
  nowScheduleKey,
  venueSlug,
} from "./lib/utils";
import { closureHeadline, VENUE_CLOSURES } from "./lib/closures";
import {
  hasEnded,
  isHappeningNow,
  pickDefaultDate,
  replaceSearch,
  scheduleDates,
  scheduleSearch,
  dayChipLabel,
  type ScheduleQuery,
} from "./lib/schedule";

export interface StatusData {
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

export interface HomeClientProps {
  // Demo mode: the server renders the requested day straight away and the full
  // schedule loads afterwards from /events.json.
  initialEvents: EventData[];
  initialDates: string[];
  catalog: [string, string][]; // [municipality, venue_name]
  initialStatus: StatusData | null;
  initialQuery: ScheduleQuery;
  initialNow: string;
}

const INITIAL_EVENT_LIMIT = 80;
const EVENT_LIMIT_STEP = 80;
const REMEMBERED_PLACE_KEY = "clubhub:place";
const feedbackEmail = "clubhubvictoria@gmail.com";

export default function HomeClient({
  initialEvents,
  initialDates,
  catalog,
  initialStatus,
  initialQuery,
  initialNow,
}: HomeClientProps) {
  const [events, setEvents] = useState<EventData[]>(initialEvents);
  const [fullLoaded, setFullLoaded] = useState(false);
  const [status, setStatus] = useState<StatusData | null>(initialStatus);
  const [loading, setLoading] = useState(!DEMO_MODE);
  const [scraping, setScraping] = useState(false);
  const [scrapeMessage, setScrapeMessage] = useState<string | null>(null);
  const [now, setNow] = useState(initialNow);

  const [activeMunicipality, setActiveMunicipality] = useState(initialQuery.municipality || "");
  const [activeVenue, setActiveVenue] = useState(initialQuery.venue || "");
  // null = default to today (or the next day with activities); "" = All Dates
  const [dateSelection, setDateSelection] = useState<string | null>(initialQuery.date ?? null);
  const [activeSport, setActiveSport] = useState(initialQuery.sport || "");
  const [visibleEventLimit, setVisibleEventLimit] = useState(INITIAL_EVENT_LIMIT);

  async function refreshData() {
    if (DEMO_MODE) {
      setEvents(await fetchDemoEvents());
      setFullLoaded(true);
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
    setFullLoaded(true);
  }

  useEffect(() => {
    refreshData()
      .catch((error) => console.error("Failed to load schedules", error))
      .finally(() => setLoading(false));

    // Reopen on the rec centre this visitor last looked at, unless the link says otherwise.
    const linkHasFilters = Object.values(initialQuery).some((value) => value !== undefined && value !== null);
    if (!linkHasFilters) {
      try {
        const saved = JSON.parse(window.localStorage.getItem(REMEMBERED_PLACE_KEY) || "null");
        const known = catalog.some(
          ([municipality, venue]) =>
            municipality === saved?.municipality && (!saved?.venue || venue === saved.venue)
        );
        if (saved && known) {
          setActiveMunicipality(saved.municipality);
          setActiveVenue(saved.venue || "");
        }
      } catch {
        // Storage can be blocked (private browsing); the default view still works.
      }
    }

    // Sessions drop off as they finish while the page stays open.
    const timer = window.setInterval(() => setNow(nowScheduleKey()), 60_000);
    return () => window.clearInterval(timer);
    // Runs once on load; initialQuery and catalog are fixed for the page's lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function rememberPlace(municipality: string, venue: string) {
    try {
      if (municipality) {
        window.localStorage.setItem(REMEMBERED_PLACE_KEY, JSON.stringify({ municipality, venue }));
      } else {
        window.localStorage.removeItem(REMEMBERED_PLACE_KEY);
      }
    } catch {
      // Not remembering is fine.
    }
  }

  function selectMunicipality(municipality: string) {
    setActiveMunicipality(municipality);
    setActiveVenue("");
    setDateSelection(null);
    setActiveSport("");
    rememberPlace(municipality, "");
  }

  function selectVenue(venue: string) {
    setActiveVenue(venue);
    setDateSelection(null);
    setActiveSport("");
    rememberPlace(activeMunicipality, venue);
  }

  function selectDate(date: string) {
    setDateSelection(date);
    setActiveSport("");
  }

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

  const upcoming = useMemo(() => events.filter((event) => !hasEnded(event, now)), [events, now]);

  const municipalities = useMemo(() => {
    const names = new Set(catalog.map(([municipality]) => municipality));
    for (const event of upcoming) names.add(event.municipality);
    return Array.from(names).sort();
  }, [catalog, upcoming]);

  const venues = useMemo(() => {
    const names = new Set(
      catalog
        .filter(([municipality]) => !activeMunicipality || municipality === activeMunicipality)
        .map(([, venue]) => venue)
    );
    for (const event of upcoming) {
      if (!activeMunicipality || event.municipality === activeMunicipality) names.add(event.venue_name);
    }
    return Array.from(names).sort();
  }, [catalog, upcoming, activeMunicipality]);

  const municipalityClosures = VENUE_CLOSURES.filter(
    (closure) => activeMunicipality && closure.municipality === activeMunicipality
  );

  const placeEvents = useMemo(
    () =>
      upcoming.filter((event) => {
        if (activeMunicipality && event.municipality !== activeMunicipality) return false;
        if (activeVenue && event.venue_name !== activeVenue) return false;
        return true;
      }),
    [upcoming, activeMunicipality, activeVenue]
  );

  // Until the full schedule arrives, the server's date list stands in for the one
  // that can't be computed from a single day of events.
  const computedDates = useMemo(() => scheduleDates(placeEvents), [placeEvents]);
  const placeMatchesServer =
    activeMunicipality === (initialQuery.municipality || "") && activeVenue === (initialQuery.venue || "");
  const dates = fullLoaded || !placeMatchesServer ? computedDates : initialDates;

  const todayKey = now.slice(0, 10);
  const activeDate = dateSelection ?? pickDefaultDate(dates, todayKey);

  const availableSports = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of placeEvents) {
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
    }

    return Array.from(counts.entries())
      .map(([sport, count]) => ({ sport, count }))
      .sort((a, b) => b.count - a.count);
  }, [placeEvents, activeDate]);

  const filteredEvents = useMemo(() => {
    return placeEvents.filter((event) => {
      if (activeDate && getDateKey(event.start_time) !== activeDate) return false;
      if (activeSport && event.sport_type !== activeSport) return false;
      return true;
    });
  }, [placeEvents, activeDate, activeSport]);

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

  const query: ScheduleQuery = {
    municipality: activeMunicipality,
    venue: activeVenue,
    date: dateSelection,
    sport: activeSport,
  };

  useEffect(() => {
    replaceSearch({ municipality: activeMunicipality, venue: activeVenue, date: dateSelection, sport: activeSport });
  }, [activeMunicipality, activeVenue, dateSelection, activeSport]);

  useEffect(() => {
    setVisibleEventLimit(INITIAL_EVENT_LIMIT);
  }, [activeMunicipality, activeVenue, activeDate, activeSport]);

  if (loading && events.length === 0) {
    return (
      <main className="page">
        <div className="container loading-block">Loading schedules...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <section className="hero hero-simple hero-compact">
          <h1>
            Find <strong>drop-ins, classes, and rec schedules</strong> across Victoria
          </h1>
          <p className="hero-subtitle">
            Swims, skates, pickleball, hockey, fitness, and community programs at every Greater Victoria rec centre.
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
        </section>

        <section className="simple-filter-panel">
          <div className="simple-municipality-row">
            <div className="chip-group-label">Municipality</div>
            <div className="municipality-picker">
              <button
                className={`municipality-pill ${activeMunicipality === "" ? "active" : ""}`}
                onClick={() => selectMunicipality("")}
                type="button"
              >
                All Municipalities
              </button>
              {municipalities.map((municipality) => (
                <button
                  key={municipality}
                  className={`municipality-pill ${activeMunicipality === municipality ? "active" : ""}`}
                  onClick={() => selectMunicipality(municipality)}
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
                onChange={(event) => selectVenue(event.target.value)}
                disabled={municipalities.length === 0}
              >
                <option value="">{activeMunicipality ? "All rec centres" : "All rec centres in Greater Victoria"}</option>
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
              <a
                className={`chip ${activeDate === "" ? "active" : ""}`}
                href={scheduleSearch({ ...query, date: "", sport: "" }) || "?date=all"}
                onClick={(event) => {
                  event.preventDefault();
                  selectDate("");
                }}
              >
                All Dates
              </a>
              {dates.map((date) => (
                <a
                  key={date}
                  className={`chip ${activeDate === date ? "active" : ""}`}
                  href={scheduleSearch({ ...query, date, sport: "" })}
                  aria-current={activeDate === date ? "date" : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    selectDate(date);
                  }}
                >
                  {dayChipLabel(date, todayKey)}
                </a>
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
            {activeVenue ? (
              <a href={`/venues/${venueSlug(activeVenue)}${scheduleSearch({ date: dateSelection, sport: activeSport })}`}>
                {activeVenue}
              </a>
            ) : (
              activeMunicipality || "All upcoming activities"
            )}
          </h2>
          <p className="section-copy">
            {activeDate ? `${dayChipLabel(activeDate, todayKey)} · ` : ""}
            Showing {Math.min(filteredEvents.length, visibleEventLimit)} of {filteredEvents.length} activities
          </p>
        </section>

        {groupedEvents.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-mark">No Results</span>
            {loading ? "Loading schedules..." : "Nothing left on this day. Try another date or rec centre."}
          </div>
        ) : (
          groupedEvents.map(([dateKey, dayEvents]) => (
            <div key={dateKey} className="day-group">
              {activeDate ? null : (
                <div className="day-group-header">
                  <span className="day-group-date">{formatFullDate(`${dateKey}T00:00:00`)}</span>
                  <span className="day-count">{dayEvents.length} activities</span>
                </div>
              )}
              <div className="events-list">
                {dayEvents.map((event) => (
                  <EventCard key={event.id} event={event} happeningNow={isHappeningNow(event, now)} />
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

        <section className="trust-strip trust-strip-footer" aria-label="Site status and feedback">
          <div className="trust-card">
            <div className="trust-kicker">Coverage</div>
            <div className="trust-copy">
              Victoria-area municipal rec centres, community schedules, and UVic CARSA where times are publicly posted, so locals can check one site instead of bouncing between rec pages.
            </div>
          </div>
          <div className="trust-card">
            <div className="trust-kicker">Freshness</div>
            <div className="trust-copy">
              Upcoming sessions only: anything that has already finished drops off. Times shown in {DISPLAY_TIME_ZONE}.
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
        </section>
      </div>
    </main>
  );
}
