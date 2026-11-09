import type { Metadata } from "next";
import { CITY } from "../lib/city";

export const metadata: Metadata = {
  title: {
    default: `${CITY.name} Rec Centre Schedules`,
    template: `%s | ${CITY.siteName}`,
  },
  description: `Browse current drop-in schedules for recreation centres, pools and community centres across ${CITY.place} and ${CITY.region}.`,
  alternates: {
    canonical: "/venues",
  },
  openGraph: {
    title: `${CITY.name} Rec Centre Schedules | ${CITY.siteName}`,
    description: `Browse current drop-in schedules for recreation centres, pools and community centres across ${CITY.region}.`,
    url: "/venues",
    type: "website",
  },
};

export default function VenuesLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
