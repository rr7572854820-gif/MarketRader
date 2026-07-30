import Link from "next/link";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function NotFound() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <Compass className="size-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-lg font-medium">Page not found</p>
        <p className="max-w-sm text-muted-foreground">This page doesn&apos;t exist. Try the Home or Reports page instead.</p>
        <Button render={<Link href="/" />} nativeButton={false} variant="outline">
          Go home
        </Button>
      </CardContent>
    </Card>
  );
}
