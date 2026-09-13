import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HealthStatus } from "./health-status";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("HealthStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading before the backend responds", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    render(<HealthStatus />);

    expect(screen.getByText("Checking backend…")).toBeInTheDocument();
  });

  it("shows connected for the complete health contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "ok" })),
    );

    render(<HealthStatus />);

    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
  });

  it.each([
    jsonResponse({ status: "starting" }),
    jsonResponse({ status: "ok" }, 503),
  ])("shows unavailable for an invalid health response", async (response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    render(<HealthStatus />);

    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/start or check the local backend/i),
    ).toBeInTheDocument();
  });

  it("shows unavailable without exposing the thrown error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValue(
          new Error("D:\\private\\server.py API_KEY=do-not-render"),
        ),
    );

    render(<HealthStatus />);

    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
    expect(
      screen.queryByText(/private|API_KEY|do-not-render/),
    ).not.toBeInTheDocument();
  });
});
