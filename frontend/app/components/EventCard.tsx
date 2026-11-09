"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import {
  EventData,
  formatAges,
  formatDateRange,
  formatTime,
  getDateKey,
  toScheduleIso,
  getOfferingMeta,
  getSportMeta,
  isAllDay,
  venueSlug,
} from "../lib/utils";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./SportIcons";

interface EventCardProps {
  event: EventData;
  includeStructuredData?: boolean;
  happeningNow?: boolean;
  // On a venue's own page the venue and town are the same on every card.
  hideVenue?: boolean;
  // One or two lines on what the class is ("LAB" says nothing on its own).
  note?: string;
}

export default function EventCard({
  event,
  includeStructuredData = false,
  happeningNow = false,
  hideVenue = false,
  note,
}: EventCardProps) {
  const sport = getSportMeta(event.sport_type);
  const offering = getOfferingMeta(event.offering_type);
  const Icon = SPORT_ICON_COMPONENTS[event.sport_type] || GenericSportIcon;

  const timeString = formatTime(event.start_time);
  const [timeVal, amPm] = timeString.split(" ");
  const allDay = isAllDay(event);
  // Community events (concerts, markets, ceremonies) link to their listing, not a booking.
  const communityEvent = event.offering_type === "event";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": communityEvent ? "Event" : "SportsEvent",
    name: event.title,
    startDate: toScheduleIso(event.start_time),
    endDate: toScheduleIso(event.end_time),
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    eventStatus: "https://schema.org/EventScheduled",
    location: {
      "@type": "Place",
      name: event.venue_name,
      address: {
        "@type": "PostalAddress",
        addressLocality: event.municipality || "Victoria",
        addressRegion: "BC",
        addressCountry: "CA",
      },
    },
    description:
      event.description || `${offering.label} ${sport.label} at ${event.venue_name}`,
    offers: {
      "@type": "Offer",
      url: event.booking_url,
      price:
        event.price === "Free" || !event.price
          ? "0"
          : event.price.replace(/[^0-9.]/g, ""),
      priceCurrency: "CAD",
    },
    organizer: {
      "@type": "Organization",
      name: event.source === "saanich" ? "Saanich Recreation" : "ClubHub",
    },
  };

  return (
    <>
      {includeStructuredData ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      ) : null}

      <div className={`event-card${happeningNow ? " event-card-live" : ""}`}>
        <div className="event-time">
          {allDay ? (
            <div className="event-time-start">All day</div>
          ) : (
            <>
              <div className="event-time-start">
                {timeVal} <span className="event-time-am">{amPm}</span>
              </div>
              <div className="event-time-end">to {formatTime(event.end_time)}</div>
            </>
          )}
        </div>

        <div className="event-info">
          <div className="event-title">
            {happeningNow ? <span className="event-live-badge">Now</span> : null}
            {event.title}
          </div>
          {event.end_date || event.ages || event.availability ? (
            <div className="event-camp-line">
              {event.end_date ? (
                <span>{formatDateRange(event.run_start || event.start_time, event.end_date)}</span>
              ) : null}
              {event.ages ? <span>{formatAges(event.ages)}</span> : null}
              {event.availability ? (
                <span className={/full/i.test(event.availability) ? "camp-spots camp-spots-full" : "camp-spots"}>
                  {event.availability}
                </span>
              ) : null}
            </div>
          ) : null}
          {note ? <p className="event-note">{note}</p> : null}
          <div className="event-meta">
            {hideVenue ? null : (
              <>
                <span>
                  <Link
                    href={`/venues/${venueSlug(event.venue_name)}?date=${getDateKey(event.start_time)}`}
                    className="event-inline-link"
                  >
                    {event.venue_name}
                  </Link>
                </span>
                <span>{event.municipality}</span>
              </>
            )}
            <span>{offering.label}</span>
            {event.facility_name ? <span>{event.facility_name}</span> : null}
            {event.price ? (
              <span
                style={{
                  color:
                    event.price === "Free" ? "var(--accent-green)" : "inherit",
                }}
              >
                {event.price}
              </span>
            ) : null}
          </div>
        </div>

        <div className="event-actions">
          <span
            className="event-sport-badge"
            style={{ color: sport.color } as CSSProperties}
          >
            <Icon width="16" height="16" /> {sport.label}
          </span>
          {event.booking_url ? (
            <a
              href={event.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="event-book-link"
              onClick={(e) => e.stopPropagation()}
            >
              {communityEvent ? "Details" : "Book"}
            </a>
          ) : null}
        </div>
      </div>
    </>
  );
}
