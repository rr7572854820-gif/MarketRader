import { AlertCircle, WifiOff } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/errors";

/**
 * The single, reused way every page renders "the API call failed" -
 * distinguishes an unreachable backend (network error) from a real API
 * error response, and offers a retry when the caller provides one.
 * Requirement 13 ("handle API failures gracefully") is satisfied here
 * once, not re-implemented per page.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const isNetwork = error instanceof ApiError && error.isNetworkError;
  const message = error instanceof Error ? error.message : "Something went wrong.";

  return (
    <Alert variant="destructive">
      {isNetwork ? <WifiOff className="size-4" /> : <AlertCircle className="size-4" />}
      <AlertTitle>{isNetwork ? "Can't reach the MarketRadar API" : "Request failed"}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {onRetry ? (
          <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
