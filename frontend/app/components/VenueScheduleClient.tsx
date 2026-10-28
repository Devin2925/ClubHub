"use client";

import { useEffect, useMemo, useState } from "react";
import EventCard from "./EventCard";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./SportIcons";
import {
  EventData,
  formatDate,
  formatFullDate,
  formatMonthDay,
  formatTime,
  getDateKey,
  getOfferingMeta,
  getSportMeta,
  nowScheduleKey,
} from "../lib/utils";
import {
  hasEnded,
  isHappeningNow,
  pickDefaultDate,
  replaceSearch,
  scheduleDates,
  scheduleSearch,
  dayChipLabel,
  type ScheduleQuery,
} from "../lib/schedule";
import { closureHeadline, VenueClosure } from "../lib/closures";

interface VenueScheduleClientProps {
  events: EventData[];
  venueName: string;
  municipality: string;
  closure?: VenueClosure;
  searchName?: string;
  summary?: string;
  address?: string;
  alternatives?: ClosureAlternativeGroup[];
  initialQuery?: ScheduleQuery;
  initialNow: string;
}

export interface ClosureAlternativeGroup {
  heading: string;
  sportLabel: string;
  venues: {
    name: string;
    slug: string;
    municipality: string;
    count: number;
    next: { title: string; start: string } | null;
  }[];
}

export default function VenueScheduleClient({
  events,
  venueName,
  municipality,
  closure,
  searchName,
  summary,
  address,
  alternatives = [],
  initialQuery = {},
  initialNow,
}: VenueScheduleClientProps) {
  // null = today (or the next day with sessions); "" = all dates
  const [dateSelection, setDateSelection] = useState<string | null>(initialQuery.date ?? null);
  const [activeSport, setActiveSport] = useState(initialQuery.sport || "");
  const [activeOfferingType, setActiveOfferingType] = useState(initialQuery.type || "");
  const [now, setNow] = useState(initialNow);

  useEffect(() => {
    // Sessions drop off as they finish while the page stays open.
    const timer = window.setInterval(() => setNow(nowScheduleKey()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    replaceSearch({ date: dateSelection, sport: activeSport, type: activeOfferingType });
  }, [dateSelection, activeSport, activeOfferingType]);

  const upcoming = useMemo(() => events.filter((event) => !hasEnded(event, now)), [events, now]);
  const dates = useMemo(() => scheduleDates(upcoming), [upcoming]);
  const todayKey = now.slice(0, 10);
  const activeDate = useMemo(
    () => dateSelection ?? pickDefaultDate(dates, todayKey),
    [dateSelection, dates, todayKey]
  );
  const query: ScheduleQuery = { date: dateSelection, sport: activeSport, type: activeOfferingType };

  const sportCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of upcoming) {
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      if (activeOfferingType && event.offering_type !== activeOfferingType) continue;
      counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
    }
    // Keep a chosen sport visible on days without it, so it can be cleared.
    if (activeSport && !counts.has(activeSport)) counts.set(activeSport, 0);
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [upcoming, activeDate, activeOfferingType, activeSport]);

  const offeringCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of upcoming) {
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      if (activeSport && event.sport_type !== activeSport) continue;
      counts.set(event.offering_type, (counts.get(event.offering_type) || 0) + 1);
    }
    if (activeOfferingType && !counts.has(activeOfferingType)) counts.set(activeOfferingType, 0);
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [upcoming, activeDate, activeSport, activeOfferingType]);

  const filteredEvents = useMemo(() => {
    return upcoming.filter((event) => {
      if (activeDate && getDateKey(event.start_time) !== activeDate) return false;
      if (activeSport && event.sport_type !== activeSport) return false;
      if (activeOfferingType && event.offering_type !== activeOfferingType) return false;
      return true;
    });
  }, [upcoming, activeDate, activeSport, activeOfferingType]);

  const groupedByDate = useMemo(() => {
    return Object.entries(
      filteredEvents.reduce<Record<string, EventData[]>>((groups, event) => {
        const key = getDateKey(event.start_time);
        if (!groups[key]) groups[key] = [];
        groups[key].push(event);
        return groups;
      }, {})
    ).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredEvents]);

  const viewLabel =
    activeDate === todayKey
      ? "Today"
      : activeDate
        ? formatFullDate(`${activeDate}T00:00:00`).replace(/, \d{4}$/, "")
        : "All upcoming dates";

  const closureNotice = closure ? (
    <section className="closure-notice" role="status">
      <div className="closure-notice-kicker">{closureHeadline(closure)}</div>
      <p className="closure-notice-copy">{closure.summary}</p>
      {closure.alternative && (
        <p className="closure-notice-copy">
          Interim location: <strong>{closure.alternative.name}</strong>, {closure.alternative.address} (opening{" "}
          {closure.alternative.opensLabel}).
        </p>
      )}
      <a className="inline-link" href={closure.infoUrl} target="_blank" rel="noopener noreferrer">
        City closure details and FAQ
      </a>
    </section>
  ) : null;

  const alternativesSection = alternatives.some((group) => group.venues.length > 0) ? (
    <section className="closure-alternatives">
      {alternatives
        .filter((group) => group.venues.length > 0)
        .map((group) => (
          <div key={group.heading} className="closure-alternatives-group">
            <h2 className="section-title">{group.heading}</h2>
            <ul className="closure-alternatives-list">
              {group.venues.map((venue) => (
                <li key={venue.slug}>
                  <a href={`/venues/${venue.slug}`} className="closure-alternative">
                    <span className="closure-alternative-name">{venue.name}</span>
                    <span className="closure-alternative-meta">
                      {venue.municipality ? `${venue.municipality} · ` : ""}
                      {venue.count} upcoming {group.sportLabel} sessions
                    </span>
                    {venue.next ? (
                      <span className="closure-alternative-next">
                        Next: {venue.next.title}, {formatDate(venue.next.start)} at {formatTime(venue.next.start)}
                      </span>
                    ) : null}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </section>
  ) : null;

  if (closure && events.length === 0) {
    return (
      <>
        <section className="hero" style={{ paddingTop: "3rem" }}>
          <div className="chip-group-label">{municipality}</div>
          <h1>
            <strong>{venueName}</strong>
          </h1>
          <p className="hero-subtitle">
            {venueName} is {closureHeadline(closure).toLowerCase()}, so there are no swim or fitness schedules to
            show. Here are the closest open alternatives with current schedules.
          </p>
        </section>
        {closureNotice}
        {alternativesSection}
      </>
    );
  }

  return (
    <>
      {closureNotice}
      <section className="hero venue-hero">
        <div className="chip-group-label">{municipality}</div>
        <h1>
          <strong>{venueName}</strong>
        </h1>
        {searchName ? <p className="venue-aka">Also known as {searchName}</p> : null}
        {address ? (
          <a
            className="venue-address"
            href={`https://maps.apple.com/?q=${encodeURIComponent(`${venueName}, ${address}`)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            {address}
          </a>
        ) : null}
      </section>

      <section className="simple-date-row sticky-filter-row" id="schedule">
        <div className="chip-group-label">Dates</div>
        <div className="horizontal-scroller full-width-scroller">
          {dates.map((date) => (
            <a
              key={date}
              className={`chip ${activeDate === date ? "active" : ""}`}
              href={scheduleSearch({ ...query, date })}
              aria-current={activeDate === date ? "date" : undefined}
              onClick={(event) => {
                event.preventDefault();
                setDateSelection(date);
              }}
            >
              {dayChipLabel(date, todayKey)}
            </a>
          ))}
          <a
            className={`chip ${activeDate === "" ? "active" : ""}`}
            href={scheduleSearch({ ...query, date: "" })}
            onClick={(event) => {
              event.preventDefault();
              setDateSelection("");
            }}
          >
            All Dates
          </a>
        </div>
      </section>

      <section className="simple-activity-row">
        <div className="chip-group-label">Sports</div>
        <div className="horizontal-scroller">
          <button
            className={`chip emoji-chip ${activeSport === "" ? "active" : ""}`}
            onClick={() => setActiveSport("")}
            type="button"
          >
            <GenericSportIcon width="18" height="18" />
            <span>All</span>
          </button>
          {sportCounts.map(([sport, count]) => {
            const Icon = SPORT_ICON_COMPONENTS[sport] || GenericSportIcon;
            const meta = getSportMeta(sport);
            return (
              <button
                key={sport}
                className={`chip emoji-chip sport-chip ${activeSport === sport ? "active" : ""}`}
                onClick={() => setActiveSport(activeSport === sport ? "" : sport)}
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
      </section>

      <section className="simple-activity-row">
        <div className="chip-group-label">Activity Types</div>
        <div className="horizontal-scroller">
          <button
            className={`chip ${activeOfferingType === "" ? "active" : ""}`}
            onClick={() => setActiveOfferingType("")}
            type="button"
          >
            All Types
          </button>
          {offeringCounts.map(([offeringType, count]) => (
            <button
              key={offeringType}
              className={`chip ${activeOfferingType === offeringType ? "active" : ""}`}
              onClick={() => setActiveOfferingType(activeOfferingType === offeringType ? "" : offeringType)}
              type="button"
            >
              {getOfferingMeta(offeringType).label} {count}
            </button>
          ))}
        </div>
      </section>

      <section className="simple-results-header">
        <h2 className="section-title">{viewLabel}</h2>
        <p className="section-copy">
          {filteredEvents.length} {filteredEvents.length === 1 ? "session" : "sessions"}
          {activeDate === todayKey ? " left today" : ""}
        </p>
      </section>

      {groupedByDate.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-mark">No Results</span>
          {activeDate === todayKey && upcoming.some((event) => getDateKey(event.start_time) > todayKey)
            ? "Nothing else on today. Pick another date above."
            : "No activities match the current filters for this rec centre."}
        </div>
      ) : (
        groupedByDate.map(([dateKey, dayEvents]) => (
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

      <section className="venue-about">
        <h2 className="section-title">About {venueName}</h2>
        <p className="section-copy">
          {summary || `Upcoming drop-ins, classes, swims, skates, and community activities at this venue in ${municipality}, BC.`}
        </p>
        <div className="status-strip status-strip-wide">
          <div className="status-card">
            <div className="status-kicker">Upcoming</div>
            <div className="status-number">{upcoming.length}</div>
            <div className="status-copy">Sessions at this venue</div>
          </div>
          <div className="status-card">
            <div className="status-kicker">Dates</div>
            <div className="status-number">{dates.length}</div>
            <div className="status-copy">Days with sessions</div>
          </div>
          <div className="status-card">
            <div className="status-kicker">Next Date</div>
            <div className="status-number">{upcoming[0] ? formatMonthDay(upcoming[0].start_time) : "-"}</div>
            <div className="status-copy">Earliest upcoming session</div>
          </div>
        </div>
      </section>
    </>
  );
}
