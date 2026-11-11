"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import EventCard from "./components/EventCard";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./components/SportIcons";
import { DEMO_MODE, fetchDemoEvents } from "./lib/demo";
import { CITY, forCity, IS_VICTORIA } from "./lib/city";
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
  readScheduleSearch,
  replaceSearch,
  scheduleDates,
  scheduleSearch,
  dayChipLabel,
  buildCatalog,
  type CatalogVenue,
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

interface SavedPlace {
  municipality: string;
  venue: string;
}

// Show this many rec centres before "+ N more places" (City of Vancouver has dozens).
const VISIBLE_PLACES = 12;

export interface HomeClientProps {
  // Demo mode: the server renders the requested day straight away and the full
  // schedule loads afterwards from /events.json.
  initialEvents: EventData[];
  initialDates: string[];
  catalog: CatalogVenue[];
  initialStatus: StatusData | null;
  // "Last sync" text formatted on the server, shown while the status is still initialStatus.
  initialSyncLabel?: string;
  initialQuery: ScheduleQuery;
  initialNow: string;
}

const INITIAL_EVENT_LIMIT = 80;
const EVENT_LIMIT_STEP = 80;
const REMEMBERED_PLACE_KEY = "clubhub:place";
const HERO_COPY = forCity({
  victoria: {
    where: "Victoria",
    subtitle: "Swims, skates, pickleball, hockey, fitness, and community programs at every Greater Victoria rec centre.",
    allVenues: "All rec centres in Greater Victoria",
    coverage:
      "Victoria-area municipal rec centres, community schedules, and UVic CARSA where times are publicly posted, so locals can check one site instead of bouncing between rec pages.",
  },
  vancouver: {
    where: "Metro Vancouver",
    subtitle:
      "Swims, skates, pickleball, hockey, fitness, and community programs at rec centres and community centres across Metro Vancouver.",
    allVenues: "All rec centres in Metro Vancouver",
    coverage:
      "City rec centres, pools, rinks and community centres in Vancouver, Burnaby, Richmond, the Tri-Cities, the North Shore and beyond, where times are publicly posted, so locals can check one site instead of bouncing between rec pages.",
  },
});

export default function HomeClient({
  initialEvents,
  initialDates,
  catalog,
  initialStatus,
  initialSyncLabel,
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

  // A ?venue= link without ?municipality= still opens that venue's municipality in the picker.
  const linkedMunicipality =
    initialQuery.municipality ||
    (initialQuery.venue ? catalog.find((place) => place.venue === initialQuery.venue)?.municipality : "") ||
    "";
  const [activeMunicipality, setActiveMunicipality] = useState(linkedMunicipality);
  const [activeVenue, setActiveVenue] = useState(initialQuery.venue || "");
  const [showAllPlaces, setShowAllPlaces] = useState(false);
  // The rec centre this device last picked ("Your rec centre"); it reopens on the next visit.
  const [savedPlace, setSavedPlace] = useState<SavedPlace | null>(null);
  // Once a rec centre is chosen the picker folds into a one-line card until "Change".
  const [pickerOpen, setPickerOpen] = useState(false);
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

    // Static pages render with empty searchParams, so restore the link's filters from the URL
    // here on mount (after hydration), before the saved-rec-centre restore below and before the
    // replaceSearch effect writes state back to the URL. In dev the server seeds the same values.
    let urlQuery: ScheduleQuery = {};
    try {
      urlQuery = readScheduleSearch(window.location.search);
    } catch {
      // No URL access; the default view still works.
    }
    if (urlQuery.municipality || urlQuery.venue) {
      const municipality =
        urlQuery.municipality ||
        (urlQuery.venue ? catalog.find((place) => place.venue === urlQuery.venue)?.municipality : "") ||
        "";
      if (municipality) setActiveMunicipality(municipality);
      if (urlQuery.venue) setActiveVenue(urlQuery.venue);
    }
    if (urlQuery.date !== undefined) setDateSelection(urlQuery.date);
    if (urlQuery.sport) setActiveSport(urlQuery.sport);

    // A link's filters — from the prop on dynamic pages, or the URL on static ones — take
    // precedence over this visitor's saved rec centre.
    const linkHasFilters =
      Object.values(initialQuery).some((value) => value !== undefined && value !== null) ||
      Object.values(urlQuery).some((value) => value !== undefined && value !== null);

    // Reopen on this visitor's rec centre, unless the link asks for something else.
    try {
      const saved = JSON.parse(window.localStorage.getItem(REMEMBERED_PLACE_KEY) || "null") as SavedPlace | null;
      const known =
        saved &&
        catalog.some(
          (place) => place.municipality === saved.municipality && (!saved.venue || place.venue === saved.venue)
        );
      if (saved && known) {
        if (saved.venue) setSavedPlace(saved);
        if (!linkHasFilters) {
          setActiveMunicipality(saved.municipality);
          setActiveVenue(saved.venue || "");
        }
      }
    } catch {
      // Storage can be blocked (private browsing); the default view still works.
    }

    // Static pages bake "now" at build time, so sync to the visitor's real clock immediately
    // on mount — this lands the default date on their actual today, not the build day — then
    // keep it current so sessions drop off as they finish while the page stays open.
    setNow(nowScheduleKey());
    const timer = window.setInterval(() => setNow(nowScheduleKey()), 60_000);
    return () => window.clearInterval(timer);
    // Runs once on load; initialQuery and catalog are fixed for the page's lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function rememberPlace(place: SavedPlace | null) {
    setSavedPlace(place);
    try {
      if (place) {
        window.localStorage.setItem(REMEMBERED_PLACE_KEY, JSON.stringify(place));
      } else {
        window.localStorage.removeItem(REMEMBERED_PLACE_KEY);
      }
    } catch {
      // Not remembering is fine.
    }
  }

  // Browsing municipalities doesn't change the saved rec centre; picking a rec centre does.
  function selectMunicipality(municipality: string) {
    setActiveMunicipality(municipality);
    setActiveVenue("");
    setShowAllPlaces(false);
    setDateSelection(null);
    setActiveSport("");
  }

  function selectVenue(venue: string) {
    setActiveVenue(venue);
    setDateSelection(null);
    setActiveSport("");
    if (venue) {
      rememberPlace({ municipality: activeMunicipality, venue });
      setPickerOpen(false);
    }
  }

  function openSavedPlace() {
    if (!savedPlace) return;
    setActiveMunicipality(savedPlace.municipality);
    setActiveVenue(savedPlace.venue);
    setDateSelection(null);
    setActiveSport("");
    setPickerOpen(false);
  }

  // Dropdown values: "" = everywhere, "area:<municipality>" = a whole municipality (only
  // offered when a link opened one), otherwise "<municipality>::<venue>".
  function placeOptionValue(municipality: string, venue: string) {
    return `${municipality}::${venue}`;
  }

  function choosePlace(value: string) {
    setDateSelection(null);
    setActiveSport("");
    const place = places.find((candidate) => placeOptionValue(candidate.municipality, candidate.venue) === value);
    if (place) {
      setActiveMunicipality(place.municipality);
      setActiveVenue(place.venue);
      rememberPlace({ municipality: place.municipality, venue: place.venue });
      return;
    }
    setActiveVenue("");
    setActiveMunicipality(value.startsWith("area:") ? value.slice("area:".length) : "");
  }

  function openPicker() {
    setShowAllPlaces(false);
    setPickerOpen(true);
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

  // The server's catalog covers every upcoming session; without one (API mode) count the loaded schedule.
  const places = useMemo(() => (catalog.length ? catalog : buildCatalog(upcoming)), [catalog, upcoming]);

  const municipalities = useMemo(
    () => Array.from(new Set(places.map((place) => place.municipality))).sort(),
    [places]
  );

  // Step two of the picker: the chosen municipality's rec centres, biggest first, then the
  // places that only host one-off events or camps.
  const municipalityPlaces = useMemo(() => {
    const here = places
      .filter((place) => place.municipality === activeMunicipality)
      .sort((a, b) => b.sessions - a.sessions || a.venue.localeCompare(b.venue));
    return { recCentres: here.filter((place) => place.recCentre), otherPlaces: here.filter((place) => !place.recCentre) };
  }, [places, activeMunicipality]);

  // Victoria picks its rec centre from one A-Z dropdown (about 35 centres); Vancouver's
  // ~140 venues stay on the municipality-then-tiles picker.
  const dropdownPlaces = useMemo(() => {
    const byName = (a: CatalogVenue, b: CatalogVenue) => a.venue.localeCompare(b.venue);
    return {
      recCentres: places.filter((place) => place.recCentre).sort(byName),
      otherPlaces: places.filter((place) => !place.recCentre).sort(byName),
    };
  }, [places]);

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
    activeMunicipality === linkedMunicipality && activeVenue === (initialQuery.venue || "");
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

  // Sessions per rec centre on the chosen day, shown on the picker tiles once the full schedule is in.
  const placeDayCounts = useMemo(() => {
    const counts = new Map<string, number>();
    if (!activeMunicipality || !fullLoaded) return counts;
    for (const event of upcoming) {
      if (event.municipality !== activeMunicipality) continue;
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      counts.set(event.venue_name, (counts.get(event.venue_name) || 0) + 1);
    }
    return counts;
  }, [upcoming, activeMunicipality, activeDate, fullLoaded]);

  const { recCentres, otherPlaces } = municipalityPlaces;
  const activePlaceHidden =
    activeVenue !== "" &&
    (otherPlaces.some((place) => place.venue === activeVenue) ||
      recCentres.findIndex((place) => place.venue === activeVenue) >= VISIBLE_PLACES);
  const placesExpanded = showAllPlaces || activePlaceHidden;
  const shownRecCentres = placesExpanded ? recCentres : recCentres.slice(0, VISIBLE_PLACES);
  const hiddenPlaceCount = placesExpanded ? 0 : recCentres.length - shownRecCentres.length + otherPlaces.length;
  const isSavedPlace = Boolean(
    savedPlace && activeVenue && savedPlace.venue === activeVenue && savedPlace.municipality === activeMunicipality
  );
  const placeCollapsed = activeVenue !== "" && !pickerOpen;
  const selectedPlaceValue = activeVenue
    ? placeOptionValue(activeMunicipality, activeVenue)
    : activeMunicipality
      ? `area:${activeMunicipality}`
      : "";
  const selectedPlaceListed = places.some(
    (place) => placeOptionValue(place.municipality, place.venue) === selectedPlaceValue
  );
  const placeDayLabel = activeDate ? dayChipLabel(activeDate, todayKey).toLowerCase() : "upcoming";

  function placeTile(place: CatalogVenue) {
    const count = fullLoaded ? placeDayCounts.get(place.venue) || 0 : null;
    const active = activeVenue === place.venue;
    return (
      <button
        key={place.venue}
        className={`venue-tile ${active ? "active" : ""} ${count === 0 ? "venue-tile-quiet" : ""}`}
        onClick={() => (active ? setPickerOpen(false) : selectVenue(place.venue))}
        aria-pressed={active}
        title={count === null ? place.venue : `${place.venue}: ${count} ${placeDayLabel}`}
        type="button"
      >
        <span className="venue-tile-name">{place.venue}</span>
        {count === null ? null : <span className="venue-tile-count">{count}</span>}
      </button>
    );
  }

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
            Find <strong>drop-ins, classes, and rec schedules</strong> across {HERO_COPY.where}
          </h1>
          <p className="hero-subtitle">
            {HERO_COPY.subtitle}
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
                ? `Last sync: ${status === initialStatus && initialSyncLabel ? initialSyncLabel : formatDateTime(status.last_fetched)}`
                : "No sync recorded yet"}
            </span>
          </div>

          {scrapeMessage ? <div className="hero-message">{scrapeMessage}</div> : null}
        </section>

        <section className="simple-filter-panel">
          {IS_VICTORIA ? (
            <>
              <div className="simple-venue-row rec-centre-dropdown">
                <label className="chip-group-label" htmlFor="rec-centre-select">
                  {isSavedPlace ? "Your rec centre" : "Rec centre"}
                </label>
                <select
                  id="rec-centre-select"
                  className="filter-select rec-centre-select"
                  value={selectedPlaceValue}
                  onChange={(event) => choosePlace(event.target.value)}
                >
                  <option value="">{HERO_COPY.allVenues}</option>
                  {activeMunicipality && !activeVenue ? (
                    <option value={selectedPlaceValue}>All of {activeMunicipality}</option>
                  ) : null}
                  {activeVenue && !selectedPlaceListed ? <option value={selectedPlaceValue}>{activeVenue}</option> : null}
                  <optgroup label="Rec centres">
                    {dropdownPlaces.recCentres.map((place) => (
                      <option key={place.venue} value={placeOptionValue(place.municipality, place.venue)}>
                        {place.venue}
                      </option>
                    ))}
                  </optgroup>
                  {dropdownPlaces.otherPlaces.length ? (
                    <optgroup label="Other places · events and camps">
                      {dropdownPlaces.otherPlaces.map((place) => (
                        <option key={place.venue} value={placeOptionValue(place.municipality, place.venue)}>
                          {place.venue}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </select>
                {isSavedPlace ? (
                  <p className="rec-centre-note">
                    Opens here next time.{" "}
                    <button className="saved-place-forget" onClick={() => rememberPlace(null)} type="button">
                      Forget
                    </button>
                  </p>
                ) : savedPlace ? (
                  <div className="saved-place-row">
                    <button className="saved-place-return" onClick={openSavedPlace} type="button">
                      ← Back to your rec centre: <strong>{savedPlace.venue}</strong>
                    </button>
                    <button className="saved-place-forget" onClick={() => rememberPlace(null)} type="button">
                      Forget
                    </button>
                  </div>
                ) : activeVenue === "" ? (
                  <p className="venue-picker-hint">
                    Or browse the{" "}
                    <Link className="inline-link" href="/venues">
                      rec centre list
                    </Link>{" "}
                    with addresses.
                  </p>
                ) : null}
              </div>

              {(activeMunicipality ? municipalityClosures : activeVenue ? [] : VENUE_CLOSURES).map((closure) => (
                <p key={closure.venueName} className="closure-inline-note">
                  <strong>{closure.venueName}</strong> is {closureHeadline(closure).toLowerCase()}.{" "}
                  <a className="inline-link" href={`/venues/${venueSlug(closure.venueName)}`}>
                    Details
                  </a>
                </p>
              ))}
            </>
          ) : placeCollapsed ? (
            <div className="place-card">
              <div className="place-card-text">
                <div className="chip-group-label">{isSavedPlace ? "Your rec centre" : "Rec centre"}</div>
                <div className="place-card-name">{activeVenue}</div>
                <div className="place-card-meta">
                  {activeMunicipality}
                  {isSavedPlace ? " · opens here next time" : ""}
                </div>
              </div>
              <button className="place-card-change" onClick={openPicker} aria-expanded={false} type="button">
                Change
              </button>
            </div>
          ) : (
            <>
              {savedPlace && !isSavedPlace ? (
                <div className="saved-place-row">
                  <button className="saved-place-return" onClick={openSavedPlace} type="button">
                    ← Back to your rec centre: <strong>{savedPlace.venue}</strong>
                  </button>
                  <button className="saved-place-forget" onClick={() => rememberPlace(null)} type="button">
                    Forget
                  </button>
                </div>
              ) : null}
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

              <div className="simple-venue-row">
                <div className="chip-group-label" id="venue-picker-label">
                  {activeMunicipality ? `Rec centres in ${activeMunicipality}` : "Rec Centre"}
                </div>
                {activeMunicipality ? (
                  <div className="venue-picker" role="group" aria-labelledby="venue-picker-label">
                    <button
                      className={`venue-tile venue-tile-all ${activeVenue === "" ? "active" : ""}`}
                      onClick={() => selectVenue("")}
                      aria-pressed={activeVenue === ""}
                      type="button"
                    >
                      <span className="venue-tile-name">All of {activeMunicipality}</span>
                    </button>
                    {shownRecCentres.map(placeTile)}
                    {placesExpanded && otherPlaces.length ? (
                      <>
                        <span className="venue-picker-sub">Other places · one-off events and camps</span>
                        {otherPlaces.map(placeTile)}
                      </>
                    ) : null}
                    {hiddenPlaceCount > 0 ? (
                      <button className="venue-tile venue-tile-more" onClick={() => setShowAllPlaces(true)} type="button">
                        <span className="venue-tile-name">
                          + {hiddenPlaceCount} more {hiddenPlaceCount === 1 ? "place" : "places"}
                        </span>
                      </button>
                    ) : null}
                  </div>
                ) : (
                  <p className="venue-picker-hint">
                    Pick a municipality above to see its rec centres, or browse{" "}
                    <Link className="inline-link" href="/venues">
                      {HERO_COPY.allVenues.replace(/^All\b/, "all")}
                    </Link>
                    .
                  </p>
                )}
              </div>

              {municipalityClosures.map((closure) => (
                <p key={closure.venueName} className="closure-inline-note">
                  <strong>{closure.venueName}</strong> is {closureHeadline(closure).toLowerCase()}.{" "}
                  <a className="inline-link" href={`/venues/${venueSlug(closure.venueName)}`}>
                    Details
                  </a>
                </p>
              ))}
            </>
          )}

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
              {HERO_COPY.coverage}
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
          {CITY.contactPhone ? (
            <div className="trust-card">
              <div className="trust-kicker">Contact</div>
              <div className="trust-copy">
                Call or text{" "}
                <a href={`tel:${CITY.contactPhone.tel}`} className="inline-link">
                  {CITY.contactPhone.display}
                </a>
                .
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
