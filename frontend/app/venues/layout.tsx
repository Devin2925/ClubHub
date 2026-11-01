import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Victoria Rec Centre Schedules",
    template: "%s | ClubHub Victoria",
  },
  description:
    "Browse current drop-in schedules for recreation centres, pools and community centres across Victoria, BC and Greater Victoria.",
  alternates: {
    canonical: "/venues",
  },
  openGraph: {
    title: "Victoria Rec Centre Schedules | ClubHub Victoria",
    description:
      "Browse current drop-in schedules for recreation centres, pools and community centres across Greater Victoria.",
    url: "/venues",
    type: "website",
  },
};

export default function VenuesLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
