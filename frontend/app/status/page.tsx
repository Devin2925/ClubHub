"use client";

import { useEffect, useMemo, useState } from "react";
import {
  API_BASE,
  DISPLAY_TIME_ZONE,
  formatDateTime,
  formatFreshnessLabel,
} from "../lib/utils";
import { DEMO_MODE, getDemoSnapshot, getDemoSourceAlerts, getDemoStatus, getDemoVenueAlerts } from "../lib/demo";

interface SourceRow {
  source_key: string;
  display_name: string;
  municipality: string;
  status: string;
  last_succeeded_at: string | null;
  last_error: string | null;
  last_event_count: number;
  previous_event_count: number;
  last_event_delta: number;
  freshness: string;
  age_hours: number | null;
}

interface SourcesResponse {
  sources: SourceRow[];
  summary: {
    total: number;
    healthy: number;
    warning: number;
    stale: number;
    error: number;
    running: number;
  };
}

interface AlertRow {
  source_key: string;
  display_name: string;
  municipality: string;
  severity: string;
  reasons: string[];
  last_error: string | null;
}

interface AlertsResponse {
  alerts: AlertRow[];
  summary: {
    total: number;
    errors: number;
    warnings: number;
  };
}

interface VenueAlertRow {
  venue_key: string;
  municipality: string;
  venue_name: string;
  severity: string;
  reasons: string[];
  last_error: string | null;
  last_event_count: number;
  previous_event_count: number;
  last_event_delta: number;
}

interface VenueAlertsResponse {
  alerts: VenueAlertRow[];
}

interface SyncTarget {
  source_key: string;
  display_name: string;
  municipality: string;
}

interface SyncTargetsResponse {
  sources: SyncTarget[];
  municipalities: string[];
}

interface StatusResponse {
  admin_access: boolean;
  latest_sync_completed_at: string | null;
  rerun_summary: {
    changed_sources: number;
    source_alerts: number;
    venue_alerts: number;
    latest_completed_at: string | null;
  };
}

export default function StatusPage() {
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [summary, setSummary] = useState<SourcesResponse["summary"] | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [venueAlerts, setVenueAlerts] = useState<VenueAlertRow[]>([]);
  const [syncTargets, setSyncTargets] = useState<SyncTarget[]>([]);
  const [municipalities, setMunicipalities] = useState<string[]>([]);
  const [runningTarget, setRunningTarget] = useState<string | null>(null);
  const [adminAccess, setAdminAccess] = useState(false);
  const [rerunSummary, setRerunSummary] = useState<StatusResponse["rerun_summary"] | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchStatus() {
    if (DEMO_MODE) {
      const demoStatus = getDemoStatus();
      const snapshot = getDemoSnapshot();
      setAdminAccess(false);
      setRerunSummary(demoStatus.rerun_summary || null);
      setSources(snapshot.sources || []);
      setSummary(demoStatus.source_summary || null);
      setAlerts(getDemoSourceAlerts());
      setVenueAlerts(getDemoVenueAlerts());
      setSyncTargets([]);
      setMunicipalities([]);
      setLoading(false);
      return;
    }
    try {
      const [statusRes, sourcesRes, alertsRes, venueAlertsRes, syncTargetsRes] = await Promise.all([
        fetch(`${API_BASE}/api/status`),
        fetch(`${API_BASE}/api/sources`),
        fetch(`${API_BASE}/api/source-alerts`),
        fetch(`${API_BASE}/api/venue-alerts`),
        fetch(`${API_BASE}/api/sync-targets`),
      ]);

      const statusData: StatusResponse = await statusRes.json();
      const sourcesData: SourcesResponse = await sourcesRes.json();
      const alertsData: AlertsResponse = await alertsRes.json();
      const venueAlertsData: VenueAlertsResponse = await venueAlertsRes.json();
      const syncTargetsData: SyncTargetsResponse = await syncTargetsRes.json();

      setAdminAccess(Boolean(statusData.admin_access));
      setRerunSummary(statusData.rerun_summary || null);
      setSources(sourcesData.sources || []);
      setSummary(sourcesData.summary || null);
      setAlerts(alertsData.alerts || []);
      setVenueAlerts(venueAlertsData.alerts || []);
      setSyncTargets(syncTargetsData.sources || []);
      setMunicipalities(syncTargetsData.municipalities || []);
    } catch (error) {
      console.error("Failed to fetch source status", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatus();
  }, []);

  async function triggerRerun(payload: { source_keys?: string[]; municipalities?: string[] }, label: string) {
    try {
      setRunningTarget(label);
      const response = await fetch(`${API_BASE}/api/scrape`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Rerun failed for ${label}`);
      }

      await fetchStatus();
    } catch (error) {
      console.error(error);
    } finally {
      setRunningTarget(null);
    }
  }

  const groupedSources = useMemo(() => {
    const groups: Record<string, SourceRow[]> = {};
    for (const source of sources) {
      if (!groups[source.municipality]) {
        groups[source.municipality] = [];
      }
      groups[source.municipality].push(source);
    }

    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [sources]);

  if (loading) {
    return (
      <main className="page">
        <div className="container loading-block">Loading source status...</div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <section className="hero" style={{ paddingBottom: "2.5rem" }}>
          <h1>
            Source <strong>Status</strong>
          </h1>
          <p className="hero-subtitle">
            This is the backend ingest view: source freshness, recent counts, and
            obvious scrape failures after reruns.
          </p>
          {DEMO_MODE ? (
            <div className="hero-message">
              Demo mode is using a frozen snapshot. Live reruns and alerts are disabled on this deployment.
            </div>
          ) : null}
          <div className="hero-message">
            {DEMO_MODE ? "Source: demo snapshot" : `Source: ${API_BASE}`} · Times shown in {DISPLAY_TIME_ZONE}
          </div>
          <div className="status-strip">
            <div className="status-card">
              <div className="status-kicker">Sources</div>
              <div className="status-number">{summary?.total ?? 0}</div>
              <div className="status-copy">Connectors in the weekly refresh set</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Healthy</div>
              <div className="status-number">{summary?.healthy ?? 0}</div>
              <div className="status-copy">
                {summary?.running ?? 0} running, {summary?.error ?? 0} errors
              </div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Alerts</div>
              <div className="status-number">{alerts.length + venueAlerts.length}</div>
              <div className="status-copy">Flagged sources or venues after the latest runs</div>
            </div>
            <div className="status-card">
              <div className="status-kicker">Last Rerun</div>
              <div className="status-number">{rerunSummary?.changed_sources ?? 0}</div>
              <div className="status-copy">
                {rerunSummary?.latest_completed_at
                  ? `Completed ${formatDateTime(rerunSummary.latest_completed_at)}`
                  : "No rerun recorded"}
              </div>
            </div>
          </div>
        </section>

        {alerts.length > 0 ? (
          <section className="alert-panel" style={{ marginBottom: "2rem" }}>
            <div className="chip-group-label">Current Alerts</div>
            <div className="alert-list">
              {alerts.map((alert) => (
                <div key={alert.source_key} className={`alert-item alert-${alert.severity}`}>
                  <div className="alert-title">
                    {alert.display_name} <span>{alert.municipality}</span>
                  </div>
                  <div className="alert-copy">{alert.reasons.join(", ")}</div>
                  {alert.last_error ? (
                    <div className="alert-copy">{alert.last_error}</div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {venueAlerts.length > 0 ? (
          <section className="alert-panel" style={{ marginBottom: "2rem" }}>
            <div className="chip-group-label">Venue Alerts</div>
            <div className="alert-list">
              {venueAlerts.map((alert) => (
                <div key={alert.venue_key} className={`alert-item alert-${alert.severity}`}>
                  <div className="alert-title">
                    {alert.venue_name} <span>{alert.municipality}</span>
                  </div>
                  <div className="alert-copy">{alert.reasons.join(", ")}</div>
                  <div className="alert-copy">
                    Previous {alert.previous_event_count} | Latest {alert.last_event_count} | Delta{" "}
                    {alert.last_event_delta >= 0 ? "+" : ""}
                    {alert.last_event_delta}
                  </div>
                  {alert.last_error ? <div className="alert-copy">{alert.last_error}</div> : null}
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {adminAccess ? (
          <section className="day-group" style={{ marginBottom: "2rem" }}>
            <div className="day-group-header">
              <span className="day-group-date">Rerun Controls</span>
              <span className="day-count">{runningTarget ? `Running ${runningTarget}` : "Manual refresh"}</span>
            </div>
            <div className="source-grid">
              <div className="source-card">
                <div className="source-card-name">Municipalities</div>
                <div className="source-card-copy">
                  Re-run one municipality when a new monthly or biweekly schedule drops.
                </div>
                <div className="chip-group" style={{ marginTop: "1rem" }}>
                  {municipalities.map((municipality) => (
                    <button
                      key={municipality}
                      className="chip"
                      onClick={() => triggerRerun({ municipalities: [municipality] }, municipality)}
                      disabled={Boolean(runningTarget)}
                      type="button"
                    >
                      {municipality}
                    </button>
                  ))}
                </div>
              </div>
              <div className="source-card">
                <div className="source-card-name">Sources</div>
                <div className="source-card-copy">
                  Re-run one connector if a source failed or came back low.
                </div>
                <div className="chip-group" style={{ marginTop: "1rem" }}>
                  {syncTargets.map((target) => (
                    <button
                      key={target.source_key}
                      className="chip"
                      onClick={() => triggerRerun({ source_keys: [target.source_key] }, target.display_name)}
                      disabled={Boolean(runningTarget)}
                      type="button"
                      title={target.municipality}
                    >
                      {target.display_name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        <section>
          {groupedSources.map(([municipality, rows]) => (
            <div key={municipality} className="day-group">
              <div className="day-group-header">
                <span className="day-group-date">{municipality}</span>
                <span className="day-count">{rows.length} sources</span>
              </div>
              <div className="source-grid">
                {rows.map((row) => (
                  <div key={row.source_key} className="source-card">
                    <div className="source-card-top">
                      <div className="source-card-name">{row.display_name}</div>
                      <span className={`freshness-pill freshness-${row.freshness}`}>
                        {formatFreshnessLabel(row.freshness)}
                      </span>
                    </div>
                    <div className="source-card-meta">
                      <span>{row.last_event_count} events</span>
                      <span>
                        {row.age_hours === null
                          ? "Never synced"
                          : `${row.age_hours}h since success`}
                      </span>
                      <span>
                        Delta {row.last_event_delta >= 0 ? "+" : ""}
                        {row.last_event_delta}
                      </span>
                    </div>
                    {row.last_succeeded_at ? (
                      <div className="source-card-copy">
                        Last success: {formatDateTime(row.last_succeeded_at)}
                      </div>
                    ) : null}
                    {row.last_error ? (
                      <div className="source-card-copy">{row.last_error}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
