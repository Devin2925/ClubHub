import type { Metadata, Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import Link from "next/link";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "./lib/seo";
import { CITY, forCity, IS_VICTORIA } from "./lib/city";
import { getUnfinishedEvents } from "./lib/snapshot.server";
import { activityPages, areaPages, getAreaCopy, sportPages } from "./lib/searchPages";
import { nowScheduleKey, venueSlug } from "./lib/utils";

// Matches the navbar so the phone's status bar blends in.
export const viewport: Viewport = {
  themeColor: "#111111",
};

// Static metadata
const SHARE_COPY = forCity({
  victoria: {
    title: "ClubHub Victoria | Recreation schedules across Greater Victoria",
    description: "Track drop-ins, classes, swims, skates, and recreation times across Victoria, BC.",
  },
  vancouver: {
    title: "ClubHub Vancouver | Recreation schedules across Metro Vancouver",
    description: "Track drop-ins, classes, swims, skates, and recreation times across Vancouver, BC and Metro Vancouver.",
  },
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} | Drop-In Sports, Classes, and Rec Schedules`,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  appleWebApp: {
    capable: true,
    title: "ClubHub",
    statusBarStyle: "black",
  },
  keywords: forCity({
    victoria: [
      "ClubHub Victoria",
      "Victoria BC recreation schedules",
      "Greater Victoria drop-in sports",
      "Victoria BC classes and rec centres",
      "Victoria BC kids camps",
      "Victoria BC summer camps",
      "Victoria BC pickleball hockey swimming",
    ],
    vancouver: [
      "ClubHub Vancouver",
      "Vancouver BC recreation schedules",
      "Metro Vancouver drop-in sports",
      "Vancouver community centre schedules",
      "Burnaby Richmond Coquitlam drop-ins",
      "Vancouver BC pickleball hockey swimming",
    ],
  }),
  alternates: {
    canonical: SITE_URL,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  openGraph: {
    title: SHARE_COPY.title,
    description: SHARE_COPY.description,
    type: "website",
    locale: "en_CA",
    url: SITE_URL,
    siteName: SITE_NAME,
  },
  twitter: {
    card: "summary",
    title: SHARE_COPY.title,
    description: SHARE_COPY.description,
  },
};

// Worded the way people search for these venues (Search Console top queries).
const campPages = [
  { href: "/camps", label: "Kids camps in Victoria" },
  { href: "/camps/winter-break", label: "Winter break camps" },
  { href: "/camps/pro-d-days", label: "Pro-D day camps" },
  { href: "/camps/spring-break", label: "Spring break camps" },
  { href: "/camps/summer", label: "Summer camps" },
];

const victoriaPopularSchedules = [
  { href: "/venues/henderson-recreation-centre", label: "Henderson Rec Centre schedule" },
  { href: "/venues/saanich-commonwealth-place", label: "Commonwealth Pool schedule" },
  { href: "/venues/carsa-vikes-recreation", label: "CARSA drop-in schedule" },
  { href: "/venues/carsa-vikes-recreation/yoga", label: "CARSA yoga schedule" },
  { href: "/venues/g-r-pearkes-recreation-centre", label: "Pearkes Rec Centre skating" },
  { href: "/venues/fairfield-community-place", label: "Fairfield Community Centre" },
  { href: "/venues/crystal-pool-and-fitness-centre", label: "Crystal Pool closure & alternatives" },
];
// Searches that span venues: "lane swim victoria", "drop in basketball victoria".
const victoriaPopularActivities = [
  { href: "/sports/swimming/lane-swimming", label: "Lane swimming" },
  { href: "/sports/swimming/public-swimming", label: "Public swims" },
  { href: "/sports/swimming/aquafit", label: "Aquafit" },
  { href: "/sports/skating/public-skating", label: "Public skating" },
  { href: "/sports/hockey/drop-in-hockey", label: "Drop-in hockey" },
  { href: "/sports/hockey/stick-and-puck", label: "Stick and puck" },
  { href: "/sports/pickleball", label: "Drop-in pickleball" },
  { href: "/sports/basketball", label: "Drop-in basketball" },
  { href: "/sports/volleyball", label: "Drop-in volleyball" },
  { href: "/sports/badminton", label: "Drop-in badminton" },
  { href: "/sports/yoga", label: "Drop-in yoga" },
  { href: "/sports/fitness/spin-classes", label: "Spin classes" },
];
const victoriaAreaSchedules = [
  { href: "/areas/saanich", label: "Saanich" },
  { href: "/areas/victoria", label: "Victoria" },
  { href: "/areas/oak-bay", label: "Oak Bay" },
  { href: "/areas/esquimalt", label: "Esquimalt" },
  { href: "/areas/west-shore", label: "Langford & West Shore" },
  { href: "/areas/panorama", label: "Saanich Peninsula" },
  { href: "/areas/sooke", label: "Sooke" },
  { href: "/areas/uvic", label: "UVic" },
];
type FooterLink = { href: string; label: string };

// ClubHub Vancouver has no Search Console history yet, so its footer is built from the
// data: the busiest venues, the activity and sport pages that exist, and every area page.
function vancouverFooterLinks(): { popularSchedules: FooterLink[]; popularActivities: FooterLink[]; areaSchedules: FooterLink[] } {
  const venueCounts = new Map<string, number>();
  for (const event of getUnfinishedEvents(nowScheduleKey())) {
    if (event.sport_type === "other") continue;
    venueCounts.set(event.venue_name, (venueCounts.get(event.venue_name) || 0) + 1);
  }
  const popularSchedules = Array.from(venueCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 7)
    .map(([name]) => ({ href: `/venues/${venueSlug(name)}`, label: `${name} schedule` }));
  const livePaths = new Set([
    ...activityPages().map(({ sport, slug }) => `/sports/${sport}/${slug}`),
    ...sportPages().map(({ sport }) => `/sports/${sport}`),
  ]);
  const popularActivities = victoriaPopularActivities.filter((link) => livePaths.has(link.href));
  const areaSchedules = areaPages().map(({ slug, municipality }) => ({
    href: `/areas/${slug}`,
    label: getAreaCopy(municipality).name,
  }));
  return { popularSchedules, popularActivities, areaSchedules };
}

function footerGroups(): { label: string; links: FooterLink[] }[] {
  if (IS_VICTORIA) {
    return [
      { label: "Popular schedules", links: victoriaPopularSchedules },
      { label: "Drop-ins by activity", links: victoriaPopularActivities },
      { label: "Drop-ins by area", links: victoriaAreaSchedules },
      { label: "Kids camps", links: campPages },
    ];
  }
  const links = vancouverFooterLinks();
  return [
    { label: "Popular schedules", links: links.popularSchedules },
    { label: "Drop-ins by activity", links: links.popularActivities },
    { label: "Drop-ins by area", links: links.areaSchedules },
  ];
}

const brandMark = (
  <svg width="22" height="22" viewBox="0 0 64 64" fill="none" aria-hidden="true" style={{ marginRight: 6 }}>
    <defs>
      <linearGradient id="brandBg" x1="32" y1="0" x2="32" y2="64" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#0d47b5" />
        <stop offset="1" stopColor="#1a7fd6" />
      </linearGradient>
      <linearGradient id="brandGold" x1="32" y1="12" x2="32" y2="52" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#ffd23f" />
        <stop offset="1" stopColor="#f5a412" />
      </linearGradient>
    </defs>
    <circle cx="32" cy="32" r="31" fill="url(#brandBg)" />
    <path d="M45.6 18.1A19.5 19.5 0 1 0 45.6 45.9" stroke="#0a2a6e" strokeWidth="12.5" strokeLinecap="round" />
    <path d="M45.6 18.1A19.5 19.5 0 1 0 45.6 45.9" stroke="url(#brandGold)" strokeWidth="8" strokeLinecap="round" />
    <path
      d="M41.5 5.5 23 35H32.5L26.5 58.5 46 28H36.5L41.5 5.5Z"
      fill="#ffffff"
      stroke="#0a2a6e"
      strokeWidth="3"
      strokeLinejoin="round"
    />
  </svg>
);

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const organizationJsonLd = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
    logo: `${SITE_URL}/icon-512.png`,
    areaServed: {
      "@type": "AdministrativeArea",
      name: `${CITY.region}, British Columbia`,
    },
    ...(CITY.contactPhone
      ? {
          contactPoint: {
            "@type": "ContactPoint",
            contactType: "customer support",
            telephone: CITY.contactPhone.schema,
            areaServed: "CA",
          },
        }
      : {}),
  };
  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
    },
    inLanguage: "en-CA",
  };

  return (
    <html lang="en">
      <head>
        {/* The Outfit font is loaded in globals.css */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
      </head>
      <body>
        <nav className="navbar">
          <div className="navbar-inner">
            <Link href="/" className="navbar-brand">
              {brandMark}
              <span>Club<strong>Hub</strong></span>
            </Link>
            
            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              <Link href="/" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 500 }}>
                Browse
              </Link>
              <Link href="/venues" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 500 }}>
                Rec Centres
              </Link>
              {CITY.hasCamps ? (
                <Link href="/camps" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 500 }}>
                  Camps
                </Link>
              ) : null}
              <Link href="/status" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 500 }}>
                Status
              </Link>
            </div>
          </div>
        </nav>
        
        {children}
        
        <footer style={{ borderTop: "1px solid var(--border-color)", padding: "3rem 0", textAlign: "center", background: "var(--bg-glass)" }}>
          <div className="container">
            <div style={{ fontWeight: 800, fontSize: "1.2rem", marginBottom: "0.5rem" }}>
              Club<strong>Hub</strong> {CITY.name}
            </div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
              Recreation schedules for drop-ins, classes, and community activities across {CITY.place} and {CITY.region}.
            </p>
            {footerGroups().map((group) => (
              <nav key={group.label} className="footer-popular" aria-label={group.label}>
                <span className="footer-popular-label">{group.label}</span>
                {group.links.map((item) => (
                  <Link key={item.href} href={item.href} className="inline-link">
                    {item.label}
                  </Link>
                ))}
              </nav>
            ))}
            <div className="footer-trust-links">
              <span>{CITY.place} schedule aggregator</span>
              <span>Upcoming dates only</span>
              {CITY.contactPhone ? (
                <span>
                  Contact:{" "}
                  <a href={`tel:${CITY.contactPhone.tel}`} className="inline-link">
                    {CITY.contactPhone.display}
                  </a>
                </span>
              ) : null}
            </div>
          </div>
        </footer>
        <Analytics />
      </body>
    </html>
  );
}
