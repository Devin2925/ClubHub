"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import CampCard from "../components/CampCard";
import {
  AGE_FILTERS,
  CAMP_SEASONS,
  campFitsAge,
  campIsFull,
  type CampSeason,
} from "../lib/camps";
import { formatFullDate, getDateKey } from "../lib/utils";
import type { CampListing, CampProviderRow } from "../lib/campPages.server";

interface Props {
  camps: CampListing[];
  providers: CampProviderRow[];
  // A season page shows one break; the hub shows them all with season tabs.
  season?: CampSeason;
  seasonCounts: Partial<Record<CampSeason, number>>;
}

function areaName(municipality: string) {
  return municipality === "Panorama" ? "Saanich Peninsula" : municipality;
}

export default function CampsPageClient({ camps, providers, season, seasonCounts }: Props) {
  const [activeSeason, setActiveSeason] = useState<CampSeason | "">(season || "");
  const [area, setArea] = useState("");
  const [age, setAge] = useState("");
  const [openOnly, setOpenOnly] = useState(false);
  const [search, setSearch] = useState("");

  const areas = useMemo(
    () => Array.from(new Set(camps.map((camp) => camp.municipality))).sort((a, b) => areaName(a).localeCompare(areaName(b))),
    [camps]
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return camps.filter((camp) => {
      if (activeSeason && camp.season !== activeSeason) return false;
      if (area && camp.municipality !== area) return false;
      if (age && !campFitsAge(camp, age)) return false;
      if (openOnly && campIsFull(camp)) return false;
      if (!needle) return true;
      return [camp.title, camp.venue_name, camp.provider, camp.municipality, camp.description]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [camps, activeSeason, area, age, openOnly, search]);

  // Grouped by break, then by the week (or day) a camp starts.
  const groups = useMemo(() => {
    const bySeason = CAMP_SEASONS.map((info) => {
      const list = filtered.filter((camp) => camp.season === info.slug);
      const byDay = new Map<string, CampListing[]>();
      for (const camp of list) {
        const key = getDateKey(camp.start_time);
        byDay.set(key, [...(byDay.get(key) || []), camp]);
      }
      return { info, days: Array.from(byDay.entries()), count: list.length };
    });
    return bySeason.filter((group) => group.count > 0);
  }, [filtered]);

  const filtersActive = Boolean(area || age || openOnly || search || (!season && activeSeason));

  return (
    <>
      <section className="camp-filters" aria-label="Filter camps">
        {season ? null : (
          <div className="chip-row" role="tablist" aria-label="School break">
            <button type="button" className={`chip ${activeSeason === "" ? "active" : ""}`} onClick={() => setActiveSeason("")}>
              All camps {camps.length}
            </button>
            {CAMP_SEASONS.filter((info) => seasonCounts[info.slug]).map((info) => (
              <button
                key={info.slug}
                type="button"
                className={`chip ${activeSeason === info.slug ? "active" : ""}`}
                onClick={() => setActiveSeason(activeSeason === info.slug ? "" : info.slug)}
              >
                {info.label} {seasonCounts[info.slug]}
              </button>
            ))}
          </div>
        )}
        <div className="chip-row" aria-label="Age">
          {AGE_FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`chip ${age === item.key ? "active" : ""}`}
              onClick={() => setAge(age === item.key ? "" : item.key)}
            >
              {item.label}
            </button>
          ))}
          <button type="button" className={`chip ${openOnly ? "active" : ""}`} onClick={() => setOpenOnly(!openOnly)}>
            Spots open
          </button>
        </div>
        <div className="camp-filter-fields">
          <select className="filter-select" value={area} onChange={(event) => setArea(event.target.value)} aria-label="Area">
            <option value="">All areas</option>
            {areas.map((name) => (
              <option key={name} value={name}>
                {areaName(name)}
              </option>
            ))}
          </select>
          <input
            className="filter-input"
            type="search"
            placeholder="Search LEGO, basketball, Saanich…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search camps"
          />
        </div>
        <p className="section-copy camp-results-count">
          {filtered.length} {filtered.length === 1 ? "camp" : "camps"}
          {filtersActive ? (
            <>
              {" "}
              ·{" "}
              <button
                type="button"
                className="inline-link camp-clear"
                onClick={() => {
                  setArea("");
                  setAge("");
                  setOpenOnly(false);
                  setSearch("");
                  setActiveSeason(season || "");
                }}
              >
                Clear filters
              </button>
            </>
          ) : null}
        </p>
      </section>

      {groups.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-mark">No camps match</span>
          {camps.length ? "Try another age or area." : "No dates are posted yet. The providers below list them first."}
        </div>
      ) : (
        groups.map(({ info, days, count }) => (
          <section key={info.slug} className="camp-season" id={info.slug}>
            {season ? null : (
              <div className="camp-season-header">
                <h2 className="section-title">{info.searchName}</h2>
                <span className="camp-season-count">
                  {count} {count === 1 ? "camp" : "camps"} ·{" "}
                  <Link href={`/camps/${info.slug}`} className="inline-link">
                    {info.searchName} page
                  </Link>
                </span>
              </div>
            )}
            {days.map(([day, list]) => (
              <div key={day} className="camp-day">
                <h3 className="camp-day-heading">
                  {list.some((camp) => camp.end_date) ? "Starting " : ""}
                  {formatFullDate(`${day}T00:00:00`)}
                  <span>{list.length}</span>
                </h3>
                <div className="camp-grid">
                  {list.map((camp) => (
                    <CampCard key={camp.id} camp={camp} />
                  ))}
                </div>
              </div>
            ))}
          </section>
        ))
      )}

      <section className="camp-providers" id="providers">
        <h2 className="section-title">Camp providers in Greater Victoria</h2>
        <p className="section-copy">
          Recreation centres, community associations and independent camps. Providers with dates listed above are checked
          every day; the rest link to their own camp pages.
        </p>
        <div className="camp-provider-grid">
          {providers.map((provider) => (
            <article key={provider.key} className="camp-provider">
              <div className="camp-provider-area">{provider.area}</div>
              <h3 className="camp-provider-name">{provider.name}</h3>
              <p className="camp-provider-places">{provider.places.join(" · ")}</p>
              <div className="camp-provider-tags">
                {provider.tags
                  .filter((tag) => !["municipal", "multi-activity"].includes(tag))
                  .slice(0, 4)
                  .map((tag) => (
                    <span key={tag}>{tag.replace(/-/g, " ")}</span>
                  ))}
              </div>
              <div className="camp-provider-actions">
                {provider.campCount ? (
                  <span className="camp-provider-count">{provider.campCount} camps listed here</span>
                ) : (
                  <span className="camp-provider-count camp-provider-count-muted">Dates on provider site</span>
                )}
                <a href={provider.infoUrl} target="_blank" rel="noopener noreferrer" className="inline-link">
                  Camp info
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
