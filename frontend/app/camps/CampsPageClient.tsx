"use client";

import { useEffect, useMemo, useState } from "react";
import EventCard from "../components/EventCard";
import { DEMO_MODE, getDemoCampSources, getDemoEvents } from "../lib/demo";
import {
  API_BASE,
  DISPLAY_TIME_ZONE,
  EventData,
  formatFullDate,
  getDateKey,
} from "../lib/utils";

interface CampSource {
  source_key: string;
  name: string;
  municipality: string;
  venue_names: string[];
  primary_url: string;
  registration_url: string;
  automation_status: "active" | "partial" | "planned";
  scrape_strategy: string;
  tags: string[];
}

interface CampSourcePayload {
  sources: CampSource[];
  summary?: {
    total: number;
    active: number;
    partial: number;
    planned: number;
  };
}

export default function CampsPageClient() {
  const [events, setEvents] = useState<EventData[]>(() =>
    DEMO_MODE ? getDemoEvents().filter((event) => event.offering_type === "camp") : []
  );
  const [sources, setSources] = useState<CampSource[]>(() => (DEMO_MODE ? getDemoCampSources() : []));
  const [summary, setSummary] = useState<CampSourcePayload["summary"] | null>(() =>
    DEMO_MODE ? buildCampSourceSummary(getDemoCampSources()) : null
  );
  const [loading, setLoading] = useState(!DEMO_MODE);
  const [activeMunicipality, setActiveMunicipality] = useState("");
  const [activeStatus, setActiveStatus] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (DEMO_MODE) return;
    async function fetchCamps() {
      try {
        const [campRes, sourceRes] = await Promise.all([
          fetch(`${API_BASE}/api/camps`),
          fetch(`${API_BASE}/api/camp-sources`),
        ]);
        const campData = await campRes.json();
        const sourceData = (await sourceRes.json()) as CampSourcePayload;
        setEvents(campData.events || []);
        setSources(sourceData.sources || []);
        setSummary(sourceData.summary || null);
      } catch (error) {
        console.error("Failed to load camps", error);
      } finally {
        setLoading(false);
      }
    }

    fetchCamps();
  }, []);

  const sourceMunicipalities = useMemo(() => {
    return Array.from(new Set(sources.map((source) => source.municipality))).sort();
  }, [sources]);

  const filteredSources = useMemo(() => {
    const needle = searchTerm.trim().toLowerCase();
    return sources.filter((source) => {
      if (activeMunicipality && source.municipality !== activeMunicipality) return false;
      if (activeStatus && source.automation_status !== activeStatus) return false;
      if (!needle) return true;
      return [
        source.name,
        source.municipality,
        source.venue_names.join(" "),
        source.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });
  }, [activeMunicipality, activeStatus, searchTerm, sources]);

  const groupedEvents = useMemo(() => {
    return Object.entries(
      events.reduce<Record<string, EventData[]>>((groups, event) => {
        const key = getDateKey(event.start_time);
        if (!groups[key]) groups[key] = [];
        groups[key].push(event);
        return groups;
      }, {})
    ).sort(([a], [b]) => a.localeCompare(b));
  }, [events]);

  if (loading) {
    return (
      <main className="page">
        <div className="container loading-block">Loading camps...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <section className="hero hero-simple">
          <div className="chip-group-label">Greater Victoria</div>
          <h1>
            Find <strong>kids camps</strong> around Victoria
          </h1>
          <p className="hero-subtitle">
            Summer camps, Pro-D day camps, spring break camps, arts, STEM, sports, outdoor adventure, and school-break care from municipal and independent providers.
          </p>

          <div className="status-strip status-strip-wide">
            <div className="status-card">
              <div className="status-kicker">Upcoming</div>
              <div className="status-number">{events.length}</div>
              <div className="status-copy">Camp sessions in cache</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Sources</div>
              <div className="status-number">{summary?.total ?? sources.length}</div>
              <div className="status-copy">Camp providers tracked</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Automated</div>
              <div className="status-number">{summary?.active ?? 0}</div>
              <div className="status-copy">Already in sync pipeline</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Time Zone</div>
              <div className="status-number">PT</div>
              <div className="status-copy">Times shown in {DISPLAY_TIME_ZONE}</div>
            </div>
          </div>
        </section>

        {groupedEvents.length > 0 ? (
          <section className="municipality-section">
            <div className="section-header-row">
              <div>
                <div className="chip-group-label">Current Camp Sessions</div>
                <h2 className="section-title">Upcoming camps</h2>
                <p className="section-copy">Live camp rows found by the scheduled scraper pipeline.</p>
              </div>
            </div>
            {groupedEvents.map(([dateKey, dayEvents]) => (
              <div key={dateKey} className="day-group">
                <div className="day-group-header">
                  <span className="day-group-date">{formatFullDate(`${dateKey}T00:00:00`)}</span>
                  <span className="day-count">{dayEvents.length} camps</span>
                </div>
                <div className="events-list">
                  {dayEvents.map((event) => (
                    <EventCard key={event.id} event={event} />
                  ))}
                </div>
              </div>
            ))}
          </section>
        ) : (
          <div className="empty-state">
            <span className="empty-state-mark">No Scheduled Camps In Cache</span>
            Camp sources are tracked below; many summer providers publish registration months before school break.
          </div>
        )}

        <section className="filter-container">
          <div className="section-header-row">
            <div>
              <div className="chip-group-label">Provider Directory</div>
              <h2 className="section-title">Camp sources to scrape</h2>
              <p className="section-copy">Use this as the working map for current coverage and future provider-specific scrapers.</p>
            </div>
          </div>
          <div className="filter-grid">
            <select
              className="filter-select"
              value={activeMunicipality}
              onChange={(event) => setActiveMunicipality(event.target.value)}
            >
              <option value="">All Areas</option>
              {sourceMunicipalities.map((municipality) => (
                <option key={municipality} value={municipality}>
                  {municipality}
                </option>
              ))}
            </select>
            <select
              className="filter-select"
              value={activeStatus}
              onChange={(event) => setActiveStatus(event.target.value)}
            >
              <option value="">All Scrape States</option>
              <option value="active">Active</option>
              <option value="partial">Partial</option>
              <option value="planned">Planned</option>
            </select>
            <input
              className="filter-input"
              placeholder="Search arts, STEM, soccer, outdoor, Saanich..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </div>
        </section>

        <div className="source-grid">
          {filteredSources.map((source) => (
            <article key={source.source_key} className="source-card">
              <div className="section-header-row">
                <div>
                  <div className="venue-card-municipality">{source.municipality}</div>
                  <h3 className="source-title">{source.name}</h3>
                  <p className="section-copy">{source.venue_names.join("; ")}</p>
                </div>
                <span className={`source-status source-status-${source.automation_status}`}>
                  {source.automation_status}
                </span>
              </div>
              <div className="camp-source-tags">
                {source.tags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
              <div className="camp-source-actions">
                <a href={source.primary_url} target="_blank" rel="noopener noreferrer" className="section-link">
                  Provider
                </a>
                <a href={source.registration_url} target="_blank" rel="noopener noreferrer" className="section-link">
                  Registration
                </a>
                <span>{source.scrape_strategy}</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}

function buildCampSourceSummary(sources: CampSource[]): CampSourcePayload["summary"] {
  return {
    total: sources.length,
    active: sources.filter((source) => source.automation_status === "active").length,
    partial: sources.filter((source) => source.automation_status === "partial").length,
    planned: sources.filter((source) => source.automation_status === "planned").length,
  };
}
