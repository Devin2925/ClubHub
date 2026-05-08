"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import {
  EventData,
  formatTime,
  getOfferingMeta,
  getSportMeta,
  venueSlug,
} from "../lib/utils";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "./SportIcons";

interface EventCardProps {
  event: EventData;
}

export default function EventCard({ event }: EventCardProps) {
  const sport = getSportMeta(event.sport_type);
  const offering = getOfferingMeta(event.offering_type);
  const Icon = SPORT_ICON_COMPONENTS[event.sport_type] || GenericSportIcon;

  const timeString = formatTime(event.start_time);
  const [timeVal, amPm] = timeString.split(" ");

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SportsEvent",
    name: event.title,
    startDate: event.start_time,
    endDate: event.end_time,
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
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="event-card">
        <div className="event-time">
          <div className="event-time-start">
            {timeVal} <span className="event-time-am">{amPm}</span>
          </div>
          <div className="event-time-end">to {formatTime(event.end_time)}</div>
        </div>

        <div className="event-info">
          <div className="event-title">{event.title}</div>
          <div className="event-meta">
            <span>
              <Link href={`/venues/${venueSlug(event.venue_name)}`} className="event-inline-link">
                {event.venue_name}
              </Link>
            </span>
            <span>{event.municipality}</span>
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
              Book
            </a>
          ) : null}
        </div>
      </div>
    </>
  );
}
