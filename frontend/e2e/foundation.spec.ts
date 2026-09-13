import { expect, test } from "@playwright/test";

const apiOrigin = "http://127.0.0.1:8000";
const jobId = "00000000-0000-0000-0000-000000000001";

const artifacts = [
  "english_transcript",
  "traditional_chinese_transcript",
  "english_srt",
  "traditional_chinese_srt",
  "bilingual_srt",
  "english_summary",
  "traditional_chinese_summary",
].map((kind, index) => ({
  artifact_key: kind,
  kind,
  filename: `${kind}.${kind.includes("srt") ? "srt" : "txt"}`,
  media_type: "text/plain; charset=utf-8",
  size_bytes: 20 + index,
}));

const completedStatus = {
  api_version: "1",
  job_id: jobId,
  stage: "COMPLETED",
  stage_label: "Completed",
  progress: 100,
  completed_stages: [
    "EXTRACTING_AUDIO",
    "TRANSCRIBING",
    "TRANSLATING",
    "GENERATING_SUBTITLES",
    "GENERATING_SUMMARY",
  ],
  error: null,
  result: {
    schema_version: "1.0",
    job_id: jobId,
    transcript: {
      language: "en",
      segments: [
        {
          segment_id: "s1",
          start_ms: 0,
          end_ms: 1_000,
          source_text: "Fixture transcript.",
        },
      ],
    },
    translated: {
      language: "zh-TW",
      segments: [
        {
          segment_id: "s1",
          start_ms: 0,
          end_ms: 1_000,
          translated_text: "測試逐字稿。",
        },
      ],
    },
    summaries: [
      { language: "en", text: "Fixture summary." },
      { language: "zh-TW", text: "測試摘要。" },
    ],
    artifacts,
  },
};

async function submitFixtureJob(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByText("本機後端已連線")).toBeVisible();
  await page
    .getByRole("textbox", { name: "YouTube 網址", exact: true })
    .fill("https://youtu.be/dQw4w9WgXcQ");
  await page.getByRole("button", { name: "開始處理" }).click();
}

async function mockSubmission(page: import("@playwright/test").Page) {
  await page.route(`${apiOrigin}/api/jobs`, async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        api_version: "1",
        job_id: jobId,
        status_url: `/api/jobs/${jobId}`,
      }),
    });
  });
}

test("renders the Phase 1 shell and reaches the real backend without overflow", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "把媒體鍛造成雙語字幕。", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("本機後端已連線")).toBeVisible();
  await expect(page.getByRole("button", { name: "開始處理" })).toBeEnabled();
  const mp3Choice = page.getByRole("radio", { name: "MP3 檔案" });
  await mp3Choice.focus();
  await page.keyboard.press("Space");
  await expect(mp3Choice).toBeChecked();

  const hasHorizontalOverflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});

test("completes a fixture-backed Phase 1 job", async ({ page }) => {
  await mockSubmission(page);
  await page.route(`${apiOrigin}/api/jobs/${jobId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(completedStatus),
    });
  });

  await submitFixtureJob(page);

  await expect(page.getByRole("heading", { name: "處理完成" })).toBeVisible();
  await expect(page.getByText("Fixture transcript.")).toBeVisible();
  await expect(page.getByText("測試逐字稿。")).toBeVisible();
  await expect(page.getByRole("link", { name: /下載/ })).toHaveCount(7);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    ),
  ).toBe(false);
});

test("shows safe failure guidance and can return to editing", async ({
  page,
}) => {
  await mockSubmission(page);
  await page.route(`${apiOrigin}/api/jobs/${jobId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...completedStatus,
        stage: "FAILED",
        stage_label: "raw D:\\private\\prompt TOKEN=secret",
        progress: 55,
        error: {
          category: "ollama_unavailable",
          stage: "TRANSLATING",
          message: "raw D:\\private\\prompt TOKEN=secret",
        },
        result: null,
      }),
    });
  });

  await submitFixtureJob(page);

  await expect(page.getByRole("heading", { name: "處理失敗" })).toBeVisible();
  await expect(page.getByText(/Ollama 本機服務或模型/)).toBeVisible();
  await expect(page.getByText(/private|TOKEN|raw D:/)).toHaveCount(0);
  await page.getByRole("button", { name: "修改設定並建立新工作" }).click();
  await expect(
    page.getByRole("heading", { name: "建立字幕工作" }),
  ).toBeVisible();
});

test("recovers after a transient polling disconnect", async ({ page }) => {
  await mockSubmission(page);
  let requestCount = 0;
  await page.route(`${apiOrigin}/api/jobs/${jobId}`, async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await route.abort("connectionfailed");
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(completedStatus),
    });
  });

  await submitFixtureJob(page);

  await expect(page.getByText(/正在以退避間隔重新連線/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "處理完成" })).toBeVisible();
  expect(requestCount).toBe(2);
});

test("downloads a fixture artifact with its server filename", async ({
  page,
}) => {
  await mockSubmission(page);
  await page.route(`${apiOrigin}/api/jobs/${jobId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(completedStatus),
    });
  });
  await page.route(
    `${apiOrigin}/api/jobs/${jobId}/artifacts/english_srt`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/x-subrip",
        headers: {
          "Content-Disposition": 'attachment; filename="english_srt.srt"',
        },
        body: "1\n00:00:00,000 --> 00:00:01,000\nFixture transcript.\n",
      });
    },
  );
  await submitFixtureJob(page);
  await expect(page.getByRole("heading", { name: "處理完成" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下載 英文 SRT" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("english_srt.srt");
});
