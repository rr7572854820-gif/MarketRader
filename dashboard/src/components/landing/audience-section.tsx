import { Rocket, Package, Microscope } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const AUDIENCES: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: Rocket,
    title: "SaaS Founders",
    text: "Validate ideas before building. Find problems worth solving. Stop building what nobody wants.",
  },
  {
    icon: Package,
    title: "Product Managers",
    text: "Prioritize with real evidence. Understand what customers actually complain about.",
  },
  {
    icon: Microscope,
    title: "Indie Hackers",
    text: "Find your next project idea backed by real market data, not gut feeling.",
  },
];

export function AudienceSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:py-28">
      <h2 className="text-balance text-center text-3xl font-semibold tracking-tight sm:text-4xl">
        Built for builders
      </h2>
      <div className="mt-14 grid gap-6 sm:grid-cols-3">
        {AUDIENCES.map((a) => (
          <div key={a.title} className="rounded-xl border border-white/10 bg-card/50 p-6 text-center">
            <a.icon className="mx-auto size-6 text-foreground" aria-hidden="true" />
            <h3 className="mt-4 text-lg font-medium">{a.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{a.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
