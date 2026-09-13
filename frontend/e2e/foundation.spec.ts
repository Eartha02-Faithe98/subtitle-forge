import { expect, test } from "@playwright/test";

test("renders the Phase 0 shell and reaches the real backend", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Subtitle Forge", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Backend connected")).toBeVisible();
  await expect(
    page.getByText(/media processing arrives in Phase 1/i),
  ).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
