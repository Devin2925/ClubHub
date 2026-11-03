import Link from "next/link";
import { campDayCount, formatAges, formatDateRange, formatTime, getDateKey, type EventData } from "../lib/utils";
import { campIsFull, campPrice } from "../lib/camps";

export interface CampCardData extends EventData {
  provider: string;
  venueHref?: string;
}

// A camp at a glance: when, the daily hours, who it's for, what it costs, whether it's full.
export default function CampCard({ camp }: { camp: CampCardData }) {
  const days = campDayCount(camp.start_time, camp.end_date);
  const full = campIsFull(camp);
  const price = campPrice(camp.price);
  // "$224 for 4 days" only for a straight run; a weekly course's price covers its sessions.
  const spanDays = camp.end_date
    ? (Date.parse(`${camp.end_date}T00:00:00Z`) - Date.parse(`${getDateKey(camp.start_time)}T00:00:00Z`)) / 86400000 + 1
    : 1;
  const priceUnit = price && days > 1 && spanDays <= 7 && /^\$[\d.]+$/.test(price) ? ` for ${days} days` : "";

  return (
    <article className={`camp-card${full ? " camp-card-full" : ""}`}>
      <div className="camp-card-when">
        <span className="camp-card-dates">{formatDateRange(camp.start_time, camp.end_date)}</span>
        {camp.availability ? (
          <span className={full ? "camp-spots camp-spots-full" : "camp-spots"}>{camp.availability}</span>
        ) : null}
      </div>
      <h3 className="camp-card-title">{camp.title}</h3>
      <div className="camp-card-facts">
        <span>
          {formatTime(camp.start_time)} – {formatTime(camp.end_time)}
          {days > 1 && spanDays <= 7 ? " daily" : ""}
        </span>
        {camp.ages ? <span>{formatAges(camp.ages)}</span> : null}
        {price ? (
          <span>
            {price}
            {priceUnit}
          </span>
        ) : null}
      </div>
      {camp.description ? <p className="camp-card-note">{camp.description}</p> : null}
      <div className="camp-card-footer">
        <div className="camp-card-where">
          {camp.venueHref ? (
            <Link href={camp.venueHref} className="event-inline-link">
              {camp.venue_name}
            </Link>
          ) : (
            <span>{camp.venue_name}</span>
          )}
          <span>
            {camp.provider !== camp.venue_name ? `${camp.provider} · ` : ""}
            {camp.municipality === "Panorama" ? "Saanich Peninsula" : camp.municipality}
          </span>
        </div>
        {camp.booking_url ? (
          <a href={camp.booking_url} target="_blank" rel="noopener noreferrer" className="event-book-link">
            {full ? (/wait/i.test(camp.availability || "") ? "Waitlist" : "Details") : "Register"}
          </a>
        ) : null}
      </div>
    </article>
  );
}
