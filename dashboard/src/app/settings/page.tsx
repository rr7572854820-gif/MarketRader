"use client";

import * as React from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { HealthResponse, VersionResponse } from "@/lib/api/types";
import {
  getApiBaseUrl,
  getDefaultApiBaseUrl,
  getDefaultMockMode,
  setApiBaseUrl,
  setDefaultMockMode,
} from "@/lib/settings";
import { useClientValue } from "@/hooks/use-client-value";

type ConnectionState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "ok"; health: HealthResponse; version: VersionResponse }
  | { status: "error"; message: string };

export default function SettingsPage() {
  // Settings live in localStorage, which doesn't exist during SSR.
  // useClientValue (see hooks/use-client-value.ts) reads the real value
  // hydration-safely without an effect; *Draft below tracks an edit
  // made on this page, which should win over the synced value once the
  // user actually touches a field.
  const syncedApiBaseUrl = useClientValue(getApiBaseUrl, "");
  const [apiBaseUrlDraft, setApiBaseUrlDraft] = React.useState<string | null>(null);
  const apiBaseUrl = apiBaseUrlDraft ?? syncedApiBaseUrl;

  const syncedDefaultMockMode = useClientValue(getDefaultMockMode, true);
  const [defaultMockModeDraft, setDefaultMockModeDraft] = React.useState<boolean | null>(null);
  const defaultMockMode = defaultMockModeDraft ?? syncedDefaultMockMode;

  const [connection, setConnection] = React.useState<ConnectionState>({ status: "idle" });

  function handleSaveApiBaseUrl(event: React.FormEvent) {
    event.preventDefault();
    setApiBaseUrl(apiBaseUrl);
    toast.success("API base URL saved.");
    setConnection({ status: "idle" });
  }

  function handleResetApiBaseUrl() {
    setApiBaseUrl("");
    setApiBaseUrlDraft(getDefaultApiBaseUrl());
    toast.success("API base URL reset to default.");
    setConnection({ status: "idle" });
  }

  function handleMockModeChange(checked: boolean) {
    setDefaultMockModeDraft(checked);
    setDefaultMockMode(checked);
  }

  async function handleTestConnection() {
    setConnection({ status: "checking" });
    try {
      const [health, version] = await Promise.all([api.health(), api.version()]);
      setConnection({ status: "ok", health, version });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Unknown error.";
      setConnection({ status: "error", message });
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Settings</h1>
        <p className="text-muted-foreground">Configure how this dashboard talks to the MarketRadar API.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>API connection</CardTitle>
          <CardDescription>
            Where the FastAPI backend (<code>uvicorn src.api.app:app</code>) is running. Stored in this browser
            only - never sent anywhere but your own requests.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSaveApiBaseUrl} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="api-base-url">API base URL</Label>
              <Input
                id="api-base-url"
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrlDraft(e.target.value)}
                placeholder={getDefaultApiBaseUrl()}
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit">Save</Button>
              <Button type="button" variant="outline" onClick={handleResetApiBaseUrl}>
                Reset
              </Button>
            </div>
          </form>

          <Separator />

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">Test connection</p>
              <p className="text-sm text-muted-foreground">Checks GET /health and GET /version - no analysis is run.</p>
            </div>
            <Button variant="outline" onClick={handleTestConnection} disabled={connection.status === "checking"}>
              {connection.status === "checking" ? <Loader2 className="size-4 animate-spin" /> : null}
              Test connection
            </Button>
          </div>

          {connection.status === "ok" ? (
            <div className="flex items-start gap-2 rounded-lg border border-emerald-600/30 bg-emerald-600/10 p-3 text-sm">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
              <div>
                <p className="font-medium text-emerald-700 dark:text-emerald-400">
                  Connected to {connection.version.name} v{connection.version.version}
                </p>
                <p className="text-muted-foreground">
                  Gemini configured: {connection.health.gemini_configured ? "yes" : "no"} · Reddit configured:{" "}
                  {connection.health.reddit_configured ? "yes" : "no"}
                </p>
              </div>
            </div>
          ) : null}

          {connection.status === "error" ? (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm">
              <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
              <p className="text-destructive">{connection.message}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Defaults</CardTitle>
          <CardDescription>Applied the next time you open the Home page.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label htmlFor="default-mock-mode" className="font-medium">
                Default to mock mode
              </Label>
              <p className="text-sm text-muted-foreground">
                Recommended: keeps the Home page free and offline by default. Turn off per-run when you actually
                want real Reddit/Gemini data.
              </p>
            </div>
            <Switch id="default-mock-mode" checked={defaultMockMode} onCheckedChange={handleMockModeChange} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
