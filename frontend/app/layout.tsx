import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import Link from "next/link";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "./lib/seo";

// Static metadata
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "ClubHub Victoria | Drop-In Sports, Classes, and Rec Schedules",
    template: "%s | ClubHub Victoria",
  },
  description: SITE_DESCRIPTION,
  keywords: [
    "ClubHub Victoria",
    "Victoria BC recreation schedules",
    "Greater Victoria drop-in sports",
    "Victoria BC classes and rec centres",
    "Victoria BC kids camps",
    "Victoria BC summer camps",
    "Victoria BC pickleball hockey swimming",
  ],
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
    title: "ClubHub Victoria | Recreation schedules across Greater Victoria",
    description: "Track drop-ins, classes, swims, skates, and recreation times across Victoria, BC.",
    type: "website",
    locale: "en_CA",
    url: SITE_URL,
    siteName: SITE_NAME,
  },
  twitter: {
    card: "summary",
    title: "ClubHub Victoria | Recreation schedules across Greater Victoria",
    description: "Track drop-ins, classes, swims, skates, and recreation times across Victoria, BC.",
  },
};

const feedbackEmail = "clubhubvictoria@gmail.com";
// Worded the way people search for these venues (Search Console top queries).
const popularSchedules = [
  { href: "/venues/henderson-recreation-centre", label: "Henderson Rec Centre schedule" },
  { href: "/venues/saanich-commonwealth-place", label: "Commonwealth Pool schedule" },
  { href: "/venues/carsa-vikes-recreation", label: "CARSA drop-in schedule" },
  { href: "/venues/g-r-pearkes-recreation-centre", label: "Pearkes Rec Centre skating" },
  { href: "/venues/fairfield-community-place", label: "Fairfield Community Centre" },
  { href: "/venues/crystal-pool-and-fitness-centre", label: "Crystal Pool closure & alternatives" },
];
const brandMark = (
  <svg width="22" height="22" viewBox="0 0 64 64" fill="none" aria-hidden="true" style={{ marginRight: 6 }}>
    <defs>
      <linearGradient id="brandBg" x1="10" y1="6" x2="54" y2="58" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#0a5aa8" />
        <stop offset="1" stopColor="#002554" />
      </linearGradient>
    </defs>
    <circle cx="32" cy="32" r="31" fill="url(#brandBg)" />
    <circle cx="32" cy="32" r="28" fill="none" stroke="#f5aa1c" strokeWidth="2.5" />
    <path
      d="M32 14C22.1 14 14 22.1 14 32s8.1 18 18 18c4.2 0 8-1.4 11-3.8"
      fill="none"
      stroke="#ffffff"
      strokeWidth="6"
      strokeLinecap="round"
    />
    <path
      d="M33 28.5h10.6l-3.4-3.4a2.5 2.5 0 1 1 3.5-3.5l7.6 7.6a2.5 2.5 0 0 1 0 3.5l-7.6 7.6a2.5 2.5 0 1 1-3.5-3.5l3.4-3.4H33a2.7 2.7 0 0 1 0-5.4Z"
      fill="#f5aa1c"
    />
    <path d="M32 32 24.5 25.5" fill="none" stroke="#f5aa1c" strokeWidth="3.6" strokeLinecap="round" />
    <circle cx="32" cy="32" r="2.4" fill="#ffffff" />
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
      name: "Greater Victoria, British Columbia",
    },
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      email: feedbackEmail,
      areaServed: "CA",
    },
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
              <Link href="/camps" style={{ color: "var(--text-secondary)", fontSize: "0.9rem", fontWeight: 500 }}>
                Camps
              </Link>
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
              Club<strong>Hub</strong> Victoria
            </div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
              Recreation schedules for drop-ins, classes, and community activities across Victoria, BC and Greater Victoria.
            </p>
            <nav className="footer-popular" aria-label="Popular schedules">
              {popularSchedules.map((item) => (
                <Link key={item.href} href={item.href} className="inline-link">
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="footer-trust-links">
              <span>Victoria, BC schedule aggregator</span>
              <span>Upcoming dates only</span>
              <a href={`mailto:${feedbackEmail}?subject=ClubHub feedback`} className="inline-link">
                Report an issue
              </a>
            </div>
          </div>
        </footer>
        <Analytics />
      </body>
    </html>
  );
}
