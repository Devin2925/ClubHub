import type { NextConfig } from "next";

// One app, two sites: NEXT_PUBLIC_CITY picks the city (app/lib/city.ts) and its data
// snapshot. Victoria is the default, so an unset variable builds clubhubvictoria.ca.
const city = process.env.NEXT_PUBLIC_CITY === "vancouver" ? "vancouver" : "victoria";
const snapshotFile = city === "vancouver" ? "./data/vancouver-snapshot.json" : "./data/demo-snapshot.json";
const canonicalHost = city === "vancouver" ? "clubhubvancouver.ca" : "clubhubvictoria.ca";

const nextConfig: NextConfig = {
  turbopack: {
    resolveAlias: {
      "@clubhub/snapshot": snapshotFile,
    },
  },
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: `www.${canonicalHost}`,
          },
        ],
        destination: `https://${canonicalHost}/:path*`,
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
