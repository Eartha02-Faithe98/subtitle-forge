import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("presents the Phase 1 local workflow truthfully", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    render(<Home />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "把媒體鍛造成雙語字幕。",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "建立字幕工作" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/YouTube、MP3 或 MP4/)).toBeInTheDocument();
    expect(screen.getAllByText(/Local Whisper/).length).toBeGreaterThanOrEqual(
      1,
    );
    expect(await screen.findByText("本機後端已連線")).toBeInTheDocument();
    expect(
      screen.queryByText(/RAG|billing|authentication/i),
    ).not.toBeInTheDocument();
  });
});
