import type { MetadataRoute } from "next";
import { CITY } from "./lib/city";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${CITY.siteUrl}/sitemap.xml`,
    host: CITY.siteUrl,
  };
}
