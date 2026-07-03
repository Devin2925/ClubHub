import type { MetadataRoute } from "next";
import snapshot from "../data/demo-snapshot.json";
import { venueSlug } from "./lib/utils";

const siteUrl = "https://clubhubvictoria.ca";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
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

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: siteUrl,
      lastModified: now,
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${siteUrl}/sports`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/venues`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
  ];

  const sportPages = Array.from(sportSet)
    .sort()
    .map((sport) => ({
      url: `${siteUrl}/sports/${sport}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));

  const venuePages = Array.from(venueSet)
    .sort()
    .map((slug) => ({
      url: `${siteUrl}/venues/${slug}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.7,
    }));

  return [...staticPages, ...sportPages, ...venuePages];
}
