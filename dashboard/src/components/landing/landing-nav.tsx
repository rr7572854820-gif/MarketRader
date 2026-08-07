import Link from "next/link";
import { Radar } from "lucide-react";

import { Button } from "@/components/ui/button";

/** This page's own nav - deliberately not the shared dashboard NavBar
 * (nav-bar.tsx), which hides itself on this route specifically so the
 * two never stack (see nav-bar.tsx's own NO_NAV_ROUTES comment). Same
 * Radar logo/brand mark as the dashboard for continuity, but otherwise
 * a minimal marketing header, not the dashboard's Home/Reports/Settings
 * chrome.
 */
export function LandingNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Radar className="size-5 text-foreground" aria-hidden="true" />
          <span>MarketRadar</span>
        </Link>
        <Button render={<Link href="/dashboard" />} nativeButton={false} variant="outline" size="sm">
          Open Dashboard →
        </Button>
      </div>
    </header>
  );
}
