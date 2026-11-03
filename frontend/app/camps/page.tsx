import type { Metadata } from "next";
import CampsLanding, { campPageData } from "./CampsLanding";
import { SITE_NAME } from "../lib/seo";

export function generateMetadata(): Metadata {
  const { all, summaries } = campPageData();
  const winter = summaries.find((row) => row.slug === "winter-break");
  const proD = summaries.find((row) => row.slug === "pro-d-days");
  const parts = [
    winter?.count ? `winter break camps ${winter.span}` : "",
    proD?.count ? `Pro-D day camps from ${proD.span?.split(/ – |–/)[0]}` : "",
    "spring break and summer camp providers",
  ].filter(Boolean);
  const title = "Kids Camps in Victoria, BC: Winter Break, Pro-D & Summer Camps";
  const description = `${all.length} kids camps across Greater Victoria: ${parts.join(", ")}. Dates, ages, prices and spots left, updated daily.`;
  return {
    title,
    description,
    alternates: { canonical: "/camps" },
    keywords: [
      "victoria kids camps",
      "kids camps victoria bc",
      "winter camps victoria",
      "winter break camps victoria",
      "pro d day camps victoria",
      "spring break camps victoria",
      "summer camps for kids victoria",
      "saanich camps",
      "oak bay camps",
      "braefoot camps",
    ],
    openGraph: { title: `${title} | ${SITE_NAME}`, description, type: "website", url: "/camps" },
    twitter: { card: "summary", title: `${title} | ${SITE_NAME}`, description },
  };
}

// Rebuilt hourly so finished camps drop off between deploys.
export const revalidate = 3600;

export default function CampsPage() {
  return <CampsLanding />;
}
