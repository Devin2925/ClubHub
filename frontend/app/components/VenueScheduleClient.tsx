"use client";

import { useMemo, useState } from "react";
import EventCard from "./EventCard";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./SportIcons";
import {
  EventData,
  formatFullDate,
  formatMonthDay,
  getDateKey,
  getOfferingMeta,
  getSportMeta,
} from "../lib/utils";

interface VenueScheduleClientProps {
  events: EventData[];
  venueName: string;
  municipality: string;
}

export default function VenueScheduleClient({
  events,
  venueName,
  municipality,
}: VenueScheduleClientProps) {
  const [activeDate, setActiveDate] = useState("");
  const [activeSport, setActiveSport] = useState("");
  const [activeOfferingType, setActiveOfferingType] = useState("");

  const dates = useMemo(() => {
    return Array.from(new Set(events.map((event) => getDateKey(event.start_time))))
      .sort()
      .slice(0, 21);
  }, [events]);

  const sportCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      if (activeOfferingType && event.offering_type !== activeOfferingType) continue;
      counts.set(event.sport_type, (counts.get(event.sport_type) || 0) + 1);
    }

    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [events, activeDate, activeOfferingType]);

  const offeringCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      if (activeDate && getDateKey(event.start_time) !== activeDate) continue;
      if (activeSport && event.sport_type !== activeSport) continue;
      counts.set(event.offering_type, (counts.get(event.offering_type) || 0) + 1);
    }

    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [events, activeDate, activeSport]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      if (activeDate && getDateKey(event.start_time) !== activeDate) return false;
      if (activeSport && event.sport_type !== activeSport) return false;
      if (activeOfferingType && event.offering_type !== activeOfferingType) return false;
      return true;
    });
  }, [events, activeDate, activeSport, activeOfferingType]);

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

  return (
    <>
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
            <div className="status-kicker">Sports</div>
            <div className="status-number">{sportCounts.length}</div>
            <div className="status-copy">Categories available</div>
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

      <section className="simple-date-row">
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
      </section>

      <section className="simple-activity-row" style={{ marginTop: "1rem" }}>
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
      </section>

      <section className="simple-activity-row" style={{ marginTop: "1rem" }}>
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
              onClick={() => setActiveOfferingType(offeringType)}
              type="button"
            >
              {getOfferingMeta(offeringType).label} {count}
            </button>
          ))}
        </div>
      </section>

      <section className="simple-results-header">
        <div className="chip-group-label">Current View</div>
        <h2 className="section-title">{venueName}</h2>
        <p className="section-copy">{filteredEvents.length} activities showing</p>
      </section>

      {groupedByDate.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-mark">No Results</span>
          No activities match the current filters for this rec centre.
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
    </>
  );
}
