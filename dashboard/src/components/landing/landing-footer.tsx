import Link from "next/link";
import { Radar } from "lucide-react";

import { Button } from "@/components/ui/button";

export function LandingFooter() {
  return (
    <footer className="border-t border-white/10">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-4 py-10 text-center sm:flex-row sm:justify-between sm:text-left">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Radar className="size-5 text-foreground" aria-hidden="true" />
          <span>MarketRadar</span>
        </Link>
        <p className="text-sm text-muted-foreground">Evidence-backed market intelligence for builders</p>
        <Button render={<Link href="/dashboard" />} nativeButton={false} variant="outline" size="sm">
          Open Dashboard →
        </Button>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-muted-foreground">
        Built by a solo founder.
      </div>
    </footer>
  );
}
