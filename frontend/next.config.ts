import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "www.clubhubvictoria.ca",
          },
        ],
        destination: "https://clubhubvictoria.ca/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
