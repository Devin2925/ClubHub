"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { DEMO_MODE, getDemoSports } from "../lib/demo";
import { API_BASE, getSportMeta } from "../lib/utils";
import { GenericSportIcon, SPORT_ICON_COMPONENTS } from "../components/SportIcons";

interface SportCount {
  sport: string;
  count: number;
}

export default function SportsPage() {
  const [sports, setSports] = useState<SportCount[]>(() => (DEMO_MODE ? getDemoSports() : []));
  const [loading, setLoading] = useState(!DEMO_MODE);

  useEffect(() => {
    if (DEMO_MODE) return;
    fetch(`${API_BASE}/api/sports`)
      .then((r) => r.json())
      .then((data) => setSports(data.sports || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="page">
        <div className="container" style={{ textAlign: "center", paddingTop: "5rem", color: "var(--text-muted)" }}>
          <div>Loading sports...</div>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="container">
        <h1 style={{ fontSize: "2rem", fontWeight: 800, marginBottom: "0.5rem", letterSpacing: "-0.02em" }}>
          Drop-in Sports in Victoria BC
        </h1>
        <p style={{ color: "var(--text-secondary)", marginBottom: "2rem" }}>
          Browse all available sports across Greater Victoria recreation centres.
        </p>
        <div className="sport-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
          {sports.map(({ sport, count }) => {
            const meta = getSportMeta(sport);
            const Icon = SPORT_ICON_COMPONENTS[sport] || GenericSportIcon;
            return (
              <Link
                key={sport}
                href={`/sports/${sport}`}
                className="sport-card"
              >
                <div style={{ color: meta.color, marginBottom: "1rem" }}>
                  <Icon width="40" height="40" />
                </div>
                <div>
                  <div className="sport-card-name" style={{ fontSize: "1.1rem" }}>{meta.label}</div>
                  <div className="sport-card-count" style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{count} upcoming sessions</div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </main>
  );
}
