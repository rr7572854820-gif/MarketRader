import { Search, Zap, BarChart3 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: Search,
    title: "Describe what you're researching",
    text: "Type any topic in plain English. No technical queries needed.",
  },
  {
    icon: Zap,
    title: "MarketRadar searches for you",
    text: "Simultaneously searches GitHub and Hacker News for real complaints, bugs, and feature requests.",
  },
  {
    icon: BarChart3,
    title: "Get verified opportunities",
    text: "Every insight is verified against its source. No AI hallucinations. Real quotes from real people.",
  },
];

export function HowItWorksSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:py-28">
      <h2 className="text-balance text-center text-3xl font-semibold tracking-tight sm:text-4xl">
        Research in 3 steps
      </h2>
      <div className="mt-14 grid gap-8 sm:grid-cols-3 sm:gap-6">
        {STEPS.map((step, i) => (
          <div key={step.title} className="relative rounded-xl border border-white/10 bg-card/50 p-6">
            <span className="text-sm font-medium text-muted-foreground">Step {i + 1}</span>
            <step.icon className="mt-3 size-6 text-foreground" aria-hidden="true" />
            <h3 className="mt-4 text-lg font-medium">{step.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{step.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
