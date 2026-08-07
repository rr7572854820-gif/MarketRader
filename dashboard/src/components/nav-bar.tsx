"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar } from "lucide-react";

import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

const LINKS = [
  { href: "/dashboard", label: "Home" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

// Public marketing routes (the landing page) render their own nav
// entirely - see components/landing/landing-nav.tsx - so this shared
// dashboard chrome must not stack above it. "/" itself is the landing
// page now too (see app/page.tsx), not the dashboard home anymore -
// that moved to "/dashboard".
const NO_NAV_ROUTES = ["/", "/landing"];

export function NavBar() {
  const pathname = usePathname();

  if (NO_NAV_ROUTES.includes(pathname)) {
    return null;
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-2 px-3 sm:gap-4 sm:px-4">
        <Link href="/dashboard" className="flex shrink-0 items-center gap-2 font-semibold">
          <Radar className="size-5 text-primary" aria-hidden="true" />
          {/* Hidden below sm: at narrow widths ("MarketRadar" + 3 nav
              links + the theme toggle) doesn't fit in one row without
              overflowing - confirmed by measuring real overflow at
              375px during Task 11's smoke testing. The icon alone is
              still a clear, tappable link back to Home. */}
          <span className="hidden sm:inline">MarketRadar</span>
        </Link>

        <nav aria-label="Main" className="flex min-w-0 items-center gap-0.5 sm:gap-2">
          {LINKS.map((link) => {
            const isActive = pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground sm:px-3",
                  isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                )}
              >
                {link.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
