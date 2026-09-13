import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("presents the Phase 0 product foundation truthfully", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "Subtitle Forge" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("AI bilingual media knowledge tool"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Phase 0 foundation/i)).toBeInTheDocument();
    expect(
      screen.getByText(/media processing arrives in Phase 1/i),
    ).toBeInTheDocument();
  });
});
