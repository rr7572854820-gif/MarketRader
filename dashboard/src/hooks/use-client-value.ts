"use client";

import * as React from "react";

function noopSubscribe() {
  return () => {};
}

/**
 * Reads a value that only really exists on the client (localStorage-
 * backed settings, "has this component mounted yet") without the
 * useEffect-that-calls-setState pattern - this project's ESLint config
 * (react-hooks/set-state-in-effect) flags that as a cascading-render
 * risk, and useSyncExternalStore is the primitive React actually
 * recommends for "give me the server-safe placeholder during SSR/first
 * paint, then swap to the real client value" instead. There is no
 * subscription here (the noop subscribe never notifies) - this is a
 * one-time hydration-safe read, not a live store.
 */
export function useClientValue<T>(getClientValue: () => T, serverValue: T): T {
  return React.useSyncExternalStore(noopSubscribe, getClientValue, () => serverValue);
}
