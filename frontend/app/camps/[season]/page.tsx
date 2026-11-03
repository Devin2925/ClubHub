import type { Metadata } from "next";
import { notFound } from "next/navigation";
import CampsLanding, { campPageData, campSeasonMeta } from "../CampsLanding";
import { CAMP_SEASONS, getCampSeason, type CampSeason } from "../../lib/camps";
import { SITE_NAME } from "../../lib/seo";

type Props = { params: Promise<{ season: string }> };

const SEASON_KEYWORDS: Record<CampSeason, string[]> = {
  "winter-break": ["winter camps victoria", "winter break camps victoria", "winter camps", "christmas camps victoria bc", "holiday camps victoria"],
  "pro-d-days": ["pro d day camps victoria", "pro-d day camp", "pro d camps saanich", "school year camps victoria"],
  "spring-break": ["spring break camps victoria", "spring break camps victoria bc", "march break camps victoria"],
  summer: ["summer camps for kids victoria", "summer camps victoria bc", "day camps victoria", "braefoot summer camps"],
};

export function generateStaticParams() {
  return CAMP_SEASONS.map((season) => ({ season: season.slug }));
}

export const dynamicParams = false;
export const revalidate = 3600;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { season } = await params;
  if (!getCampSeason(season)) return {};
  const slug = season as CampSeason;
  const { summary } = campPageData(slug);
  const { title, description, year } = campSeasonMeta(slug, summary);
  const path = `/camps/${slug}`;
  return {
    title,
    description,
    alternates: { canonical: path },
    keywords: [...SEASON_KEYWORDS[slug], `${getCampSeason(slug)!.searchName.toLowerCase()} ${year}`],
    openGraph: { title: `${title} | ${SITE_NAME}`, description, type: "website", url: path },
    twitter: { card: "summary", title: `${title} | ${SITE_NAME}`, description },
  };
}

export default async function CampSeasonPage({ params }: Props) {
  const { season } = await params;
  if (!getCampSeason(season)) notFound();
  return <CampsLanding season={season as CampSeason} />;
}
