import type { MetadataRoute } from "next";

// "Add to Home Screen" opens ClubHub full-screen like an app, starting on today's schedule.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ClubHub Victoria",
    short_name: "ClubHub",
    description: "Today's drop-ins, swims, skates and classes across Greater Victoria rec centres.",
    start_url: "/",
    display: "standalone",
    background_color: "#111111",
    theme_color: "#111111",
    icons: [
      { src: "/icon1.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
