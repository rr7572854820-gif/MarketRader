import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Illustrative only (confirmed explicitly before building this) - this
 * is a personal, single-user MVP with no billing, accounts, usage
 * quotas, email, or public API (see CLAUDE.md/ENGINEERING_GUIDE.md's
 * own recorded scope) - none of these tiers are actually purchasable.
 * Every CTA below links to the real, free dashboard, never a payment
 * flow, and the note beneath the cards says so plainly rather than
 * letting a visitor reasonably assume otherwise.
 */
const TIERS = [
  {
    name: "Free",
    price: "$0",
    features: ["3 analyses per month", "GitHub source", "5 reports per analysis", "7 day history"],
    cta: "Start Free",
    highlighted: false,
  },
  {
    name: "Starter",
    price: "$19",
    badge: "Most Popular",
    features: [
      "Unlimited analyses",
      "GitHub + Hacker News",
      "10 reports per analysis",
      "30 day history",
      "Email alerts",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Professional",
    price: "$49",
    features: [
      "Everything in Starter",
      "All future sources",
      "Unlimited reports",
      "Full history",
      "API access",
      "Priority support",
    ],
    cta: "Start Free Trial",
    highlighted: false,
  },
];

export function PricingSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:py-28">
      <h2 className="text-balance text-center text-3xl font-semibold tracking-tight sm:text-4xl">Simple pricing</h2>

      <div className="mt-14 grid gap-6 sm:grid-cols-3">
        {TIERS.map((tier) => (
          <div
            key={tier.name}
            className={cn(
              "flex flex-col rounded-xl border p-6",
              tier.highlighted ? "border-foreground/30 bg-card shadow-lg" : "border-white/10 bg-card/50"
            )}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{tier.name}</h3>
              {tier.badge ? <Badge>{tier.badge}</Badge> : null}
            </div>
            <p className="mt-3">
              <span className="text-3xl font-semibold">{tier.price}</span>
              <span className="text-muted-foreground">/month</span>
            </p>
            <ul className="mt-6 flex-1 space-y-2 text-sm text-muted-foreground">
              {tier.features.map((f) => (
                <li key={f}>· {f}</li>
              ))}
            </ul>
            <Button
              render={<Link href="/dashboard" />}
              nativeButton={false}
              variant={tier.highlighted ? "default" : "outline"}
              className="mt-6 w-full"
            >
              {tier.cta}
            </Button>
          </div>
        ))}
      </div>
      <p className="mt-8 text-center text-xs text-muted-foreground">
        Pricing shown for illustration - this is a personal project, not a commercial product yet. Every button
        above just opens the real, free dashboard.
      </p>
    </section>
  );
}
