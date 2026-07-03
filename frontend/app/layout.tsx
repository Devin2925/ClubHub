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
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
  },
};

const feedbackEmail = "clubhubvictoria@gmail.com";
const brandMark = (
  <svg width="22" height="22" viewBox="0 0 64 64" fill="none" aria-hidden="true" style={{ marginRight: 6 }}>
    <defs>
      <linearGradient id="brandBg" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#31465f" />
        <stop offset="1" stopColor="#08111d" />
      </linearGradient>
      <linearGradient id="brandAccent" x1="18" y1="18" x2="49" y2="45" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#e7fbff" />
        <stop offset="0.5" stopColor="#97ece1" />
        <stop offset="1" stopColor="#57d6ce" />
      </linearGradient>
    </defs>
    <circle cx="32" cy="32" r="30" fill="url(#brandBg)" />
    <circle cx="32" cy="32" r="29" fill="none" stroke="#d7efff" strokeOpacity="0.28" />
    <path
      d="M32 11C21.5 11 13 19.5 13 30s8.5 19 19 19c4.4 0 8.4-1.5 11.6-4.1"
      fill="none"
      stroke="#e8f2ff"
      strokeOpacity="0.82"
      strokeWidth="5"
      strokeLinecap="round"
    />
    <path
      d="M34 29h11.3l-3.8-3.8a2.2 2.2 0 1 1 3.1-3.1l7.4 7.4a2.2 2.2 0 0 1 0 3.1L44.6 40a2.2 2.2 0 1 1-3.1-3.1l3.8-3.9H34a2 2 0 0 1 0-4Z"
      fill="url(#brandAccent)"
    />
    <circle cx="32" cy="32" r="1.7" fill="#f4fbff" />
    <path d="M32 32 23.8 25.6" fill="none" stroke="url(#brandAccent)" strokeWidth="3.1" strokeLinecap="round" />
    <path d="M32 32 38.6 24.5" fill="none" stroke="url(#brandAccent)" strokeWidth="3.1" strokeLinecap="round" />
    <path d="M32 19.3v-2.6" fill="none" stroke="#f1f7ff" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M20.2 32h-2.5" fill="none" stroke="#f1f7ff" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M32 44.7v2.6" fill="none" stroke="#f1f7ff" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M43.8 32h2.5" fill="none" stroke="#f1f7ff" strokeWidth="1.8" strokeLinecap="round" />
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
    logo: `${SITE_URL}/icon.svg`,
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
