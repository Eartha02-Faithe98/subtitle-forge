"use client";

import { useEffect, useState } from "react";

import { getApiBaseUrl } from "@/lib/config";

type ConnectionState = "checking" | "connected" | "unavailable";

function isHealthyPayload(value: unknown): value is { status: "ok" } {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    value.status === "ok"
  );
}

export function HealthStatus() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");

  useEffect(() => {
    let active = true;

    async function checkBackend() {
      try {
        const response = await fetch(`${getApiBaseUrl()}/health`, {
          headers: { Accept: "application/json" },
        });
        const body: unknown = await response.json();

        if (!response.ok || !isHealthyPayload(body)) {
          throw new Error("Backend health contract was not satisfied");
        }

        if (active) {
          setConnectionState("connected");
        }
      } catch {
        if (active) {
          setConnectionState("unavailable");
        }
      }
    }

    void checkBackend();
    return () => {
      active = false;
    };
  }, []);

  if (connectionState === "checking") {
    return (
      <div className="health health--checking" role="status">
        <span className="health__dot" aria-hidden="true" />
        <span>Checking backend…</span>
      </div>
    );
  }

  if (connectionState === "connected") {
    return (
      <div className="health health--connected" role="status">
        <span className="health__dot" aria-hidden="true" />
        <span>Backend connected</span>
      </div>
    );
  }

  return (
    <div className="health health--unavailable" role="alert">
      <div className="health__summary">
        <span className="health__dot" aria-hidden="true" />
        <span>Backend unavailable</span>
      </div>
      <p>Start or check the local backend, then refresh this page.</p>
    </div>
  );
}
