import type { MetadataRoute } from "next";
import snapshot from "../data/demo-snapshot.json";
import { venueSlug } from "./lib/utils";
import { VENUE_CLOSURES } from "./lib/closures";
import { venueSportPages } from "./lib/seo";

const siteUrl = "https://clubhubvictoria.ca";

export default function sitemap(): MetadataRoute.Sitemap {
  // Google recommends an accurate lastmod value, not the time the sitemap was requested.
  const snapshotModified = new Date(`${snapshot.generated_at}Z`);
  const eventRows = snapshot.events || [];
  const sportSet = new Set<string>();
  const venueSet = new Set<string>();

  for (const event of eventRows) {
    if (event.sport_type) {
      sportSet.add(event.sport_type);
    }
    if (event.venue_name) {
      venueSet.add(venueSlug(event.venue_name));
    }
  }

  for (const closure of VENUE_CLOSURES) {
    venueSet.add(venueSlug(closure.venueName));
  }

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: siteUrl,
      lastModified: snapshotModified,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${siteUrl}/sports`,
      lastModified: snapshotModified,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/venues`,
      lastModified: snapshotModified,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/camps`,
      lastModified: snapshotModified,
      changeFrequency: "daily",
      priority: 0.85,
    },
  ];

  const sportPages = Array.from(sportSet)
    .sort()
    .map((sport) => ({
      url: `${siteUrl}/sports/${sport}`,
      lastModified: snapshotModified,
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));

  const venuePages = Array.from(venueSet)
    .sort()
    .map((slug) => ({
      url: `${siteUrl}/venues/${slug}`,
      lastModified: snapshotModified,
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));

  const venueSportUrls = venueSportPages()
    .sort((a, b) => `${a.venue}/${a.sport}`.localeCompare(`${b.venue}/${b.sport}`))
    .map(({ venue, sport }) => ({
      url: `${siteUrl}/venues/${venue}/${sport}`,
      lastModified: snapshotModified,
      changeFrequency: "daily" as const,
      priority: 0.6,
    }));

  return [...staticPages, ...sportPages, ...venuePages, ...venueSportUrls];
}
