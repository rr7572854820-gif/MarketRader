import Link from "next/link";

import { Button } from "@/components/ui/button";

/** "in minutes, not weeks" - deliberately not a specific latency claim
 * like "in 40 seconds". Real source="all" runs against the live
 * pipeline have measured anywhere from ~20s (best case) to 150-250s+
 * (typical, once Groq's free-tier rate limit is hit during extraction -
 * see SESSION.md's several entries on this) - no fixed number here
 * would be honest across that whole range, so this leans on the true,
 * defensible comparison instead (replacing days/weeks of manual
 * reading with one sitting), not a fabricated precise figure.
 */
export function HeroSection() {
  return (
    <section className="mx-auto max-w-4xl px-4 pt-16 pb-20 text-center sm:pt-24 sm:pb-28">
      <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
        Stop Guessing.
        <br />
        Start Building What
        <br />
        People Actually Need.
      </h1>
      <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground sm:text-xl">
        MarketRadar analyzes thousands of real GitHub issues and Hacker News discussions to surface verified
        customer pain points — in minutes, not weeks.
      </p>
      <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
        <Button
          render={<Link href="/dashboard" />}
          nativeButton={false}
          size="lg"
          className="h-11 px-6 text-base"
        >
          Start Researching Free →
        </Button>
        <Button
          render={<Link href="#sample-report" />}
          nativeButton={false}
          variant="outline"
          size="lg"
          className="h-11 px-6 text-base"
        >
          See a Sample Report
        </Button>
      </div>
      <p className="mt-8 text-sm text-muted-foreground">
        2 sources · Real-time data · Evidence verified · No hallucinations
      </p>
    </section>
  );
}
