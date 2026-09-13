import { describe, expect, it } from "vitest";

import { getApiBaseUrl } from "./config";

describe("getApiBaseUrl", () => {
  it("uses a safe localhost default", () => {
    expect(getApiBaseUrl(undefined)).toBe("http://127.0.0.1:8000");
  });

  it("accepts an explicit HTTP URL and removes a trailing slash", () => {
    expect(getApiBaseUrl("http://localhost:8100/")).toBe(
      "http://localhost:8100",
    );
  });

  it.each([
    "not-a-url",
    "ftp://localhost:8000",
    "http://user:pass@localhost:8000",
  ])("rejects unsafe public API URL %s", (value) => {
    expect(() => getApiBaseUrl(value)).toThrow("NEXT_PUBLIC_API_BASE_URL");
  });
});
