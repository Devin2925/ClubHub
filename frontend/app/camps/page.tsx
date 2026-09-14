import type { Metadata } from "next";
import CampsPageClient from "./CampsPageClient";

export const metadata: Metadata = {
  title: "Kids Camps in Victoria BC",
  description:
    "Find kids camps, summer camps, Pro-D day camps, spring break camps, and camp providers across Victoria BC and Greater Victoria.",
  alternates: {
    canonical: "/camps",
  },
  keywords: [
    "Victoria BC kids camps",
    "Victoria BC summer camps",
    "Greater Victoria day camps",
    "Victoria BC Pro-D camps",
    "Saanich summer camps",
    "Oak Bay camps",
    "West Shore camps",
  ],
};

export default function CampsPage() {
  return <CampsPageClient />;
}

