import { notFound } from "next/navigation";
import { CITY } from "../lib/city";

// Camps are a ClubHub Victoria section (its camp providers); other cities 404 here.
export default function CampsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  if (!CITY.hasCamps) notFound();
  return children;
}
