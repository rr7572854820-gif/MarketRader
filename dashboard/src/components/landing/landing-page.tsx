import { LandingNav } from "@/components/landing/landing-nav";
import { HeroSection } from "@/components/landing/hero-section";
import { HowItWorksSection } from "@/components/landing/how-it-works-section";
import { ComparisonSection } from "@/components/landing/comparison-section";
import { SampleReportSection } from "@/components/landing/sample-report-section";
import { AudienceSection } from "@/components/landing/audience-section";
import { PricingSection } from "@/components/landing/pricing-section";
import { LandingFooter } from "@/components/landing/landing-footer";

/** Rendered by both app/page.tsx ("/") and app/landing/page.tsx
 * ("/landing") - same component, so the two URLs never drift apart.
 *
 * Forces dark theme via a scoped "dark" class wrapper, independent of
 * the dashboard's own light/dark toggle (next-themes sets "dark" on
 * <html> based on user/system preference - this page intentionally
 * always looks dark, a deliberate design choice for the marketing page
 * specifically, not a bug in the toggle). Tailwind's dark: variant
 * (globals.css: `@custom-variant dark (&:is(.dark *))`) matches any
 * ".dark" ancestor, not just <html>, so this nested override works
 * correctly regardless of the user's actual theme setting.
 */
export function LandingPage() {
  return (
    <div className="dark relative -mx-4 -my-6 text-foreground sm:-my-8">
      {/* layout.tsx's shared <main> caps content at max-w-6xl - on a
       * wide viewport, that leaves visible space on either side showing
       * the *visitor's own* light/dark background, not this page's
       * forced-dark one, since body's bg-background follows <html>'s
       * real theme class, not this component's nested ".dark"
       * override. A viewport-fixed layer (not constrained by main's
       * own max-width) fixes that without touching layout.tsx itself.
       */}
      <div className="fixed inset-0 -z-10 bg-background" aria-hidden="true" />
      <LandingNav />
      <HeroSection />
      <HowItWorksSection />
      <ComparisonSection />
      <SampleReportSection />
      <AudienceSection />
      <PricingSection />
      <LandingFooter />
    </div>
  );
}
