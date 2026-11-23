// The Video tab (DESIGN.md §46, acceptance criteria 441 to 468), in a real browser against the real server with the FAKE video engine (a real MP4 made by ffmpeg: H.264 and stereo AAC,
// a test pattern and a tone, whatever length is asked for). The real LTX program is not here: it needs the GPU. What this proves is the page and the server together: the licence gate,
// making a clip, playing it (the browser's own player, which starts nothing by itself), the files, Cancel, Animate this, and the page at 360 px.
import { clearHistory, expect, generate, test, unique, useOptions, type Locator, type Page } from "./helpers";

const ASK = { "X-Studio-Client": "1" };
const videoTab = (page: Page) => page.getByRole("tab", { name: "Video" });
const form = (page: Page) => page.getByRole("region", { name: "New clip" });
const make = (page: Page) => page.getByRole("button", { name: "Make clip", exact: true });
const happens = (page: Page) => form(page).getByRole("textbox", { name: "What happens" });
const hear = (page: Page) => form(page).getByRole("textbox", { name: "What you hear" });
const clipCard = (page: Page, text: string): Locator => page.locator("article.video-card", { hasText: text });
const done = (c: Locator) => expect(c.locator(".badge").first()).toHaveText("Done", { timeout: 40_000 });
// the smallest size and the shortest of the offered lengths: a clip of a few seconds, made in a moment by the fake engine
const small = async (page: Page) => {
  await form(page).getByRole("button", { name: "512×320 (a test)" }).click();
  await form(page).getByRole("button", { name: "5 s", exact: true }).click();
};

async function openVideo(page: Page) {
  await page.goto("/");
  await videoTab(page).click();
  await expect(page.getByRole("heading", { name: /New clip|The licence/ }).first()).toBeVisible();
}

/** Acknowledge the licence the way a person does, if it is asked for. */
async function acknowledged(page: Page) {
  const accept = page.getByRole("button", { name: "Accept", exact: true });
  if (await accept.isVisible()) {
    await page.getByRole("checkbox", { name: /I have read/ }).check();
    await accept.click();
  }
  await expect(form(page)).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await clearHistory(page);
  await useOptions(page);
});

test("the licence is asked for first: the form is off until it is acknowledged, and no clip can be made without it", async ({ page }) => {
  await page.request.delete("/api/video/licence", { headers: ASK }); // as a person who has never acknowledged it
  await openVideo(page);
  await expect(page.getByRole("heading", { name: "The licence" })).toBeVisible();
  await expect(make(page)).toBeDisabled();
  const box = page.getByRole("checkbox", { name: /I have read/ });
  await expect(box).not.toBeChecked(); // never ticked for the person
  await expect(page.getByRole("button", { name: "Accept", exact: true })).toBeDisabled();
  await expect(page.getByText(/A summary, from the model's card/)).toBeVisible();
  await expect(make(page)).toBeDisabled();
  await expect(happens(page)).toBeDisabled();
  // the server refuses a clip too, whatever the page does
  const refused = await page.request.post("/api/runs", { headers: ASK, data: { mode: "video", prompt: "a fox", options: { width: 256, height: 128, seconds: 1 } } });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("licence_not_accepted");
  await box.check();
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The licence" })).toHaveCount(0);
  await expect(happens(page)).toBeEnabled();
  await expect(page.getByRole("button", { name: "Withdraw my acknowledgement of the licence" })).toBeVisible();
  await expect(make(page)).toBeDisabled(); // no words yet
  await happens(page).fill("a fox");
  await expect(make(page)).toBeEnabled();
});

test("a clip is made from words and what you hear, is a real MP4 the browser can play, seeks by Range, and starts nothing by itself", async ({ page }) => {
  await openVideo(page);
  await acknowledged(page);
  const words = unique("a fox in the snow");
  await happens(page).fill(words);
  await hear(page).fill("snow crunching underfoot");
  await small(page);
  await expect(page.locator("[data-note='make-line']")).toContainText("5 s, 512×320, 24 fps, Draft, with sound (121 frames)");
  await make(page).click();
  const c = clipCard(page, words).first();
  await expect(c).toBeVisible();
  await done(c);
  await expect(c.getByText("Sound: snow crunching underfoot")).toBeVisible(); // what you hear, as text
  await expect(c.locator("[data-note='facts']")).toContainText("5.0 s · 512×320 · 24 fps · Draft · with sound");

  // the player: the browser's own, with the clip's poster, not playing, and it can say how long the clip is
  const video = c.locator("video");
  await expect(video).toHaveAttribute("controls", "");
  await expect(video).toHaveAttribute("poster", /\/api\/videos\/[0-9a-f]{32}\/poster$/);
  for (const attribute of ["autoplay", "loop", "muted"]) expect(await video.getAttribute(attribute), attribute).toBeNull();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThanOrEqual(1); // the metadata arrived: the browser can read the file
  const facts = await video.evaluate((v: HTMLVideoElement) => ({ duration: v.duration, paused: v.paused, width: v.videoWidth, height: v.videoHeight, error: v.error?.code ?? null }));
  expect(facts.error).toBeNull();
  expect(facts.paused).toBe(true);
  expect(facts.duration).toBeGreaterThan(4.9);
  expect(facts.duration).toBeLessThan(5.2);
  expect([facts.width, facts.height]).toEqual([512, 320]);

  // the file: served with Range (so a player can seek), as an MP4, and downloadable under a name of the studio's own style
  const src = (await video.getAttribute("src"))!;
  const part = await page.request.get(src, { headers: { Range: "bytes=0-99" } });
  expect(part.status()).toBe(206);
  expect(part.headers()["content-type"]).toBe("video/mp4");
  expect(part.headers()["content-range"]).toMatch(/^bytes 0-99\/\d+$/);
  const download = c.getByRole("link", { name: /Download MP4/ });
  await expect(download).toHaveAttribute("href", /\?download=1$/);
  const named = await page.request.get((await download.getAttribute("href"))!);
  expect(named.headers()["content-disposition"]).toMatch(/^attachment; filename="video_[a-z0-9-]+_5s_s\d+_\d{8}-\d{6}\.mp4"/);
  const info = await (await page.request.get("/api/runs?kind=video")).json();
  expect(info.runs[0].video).toMatchObject({ has_audio: true, audio_channels: 2, audio_rate: 48000, width: 512, height: 320 }); // the file's own facts, which the page shows

  // Open: the viewer has a larger player, the words, a download and Close; nothing plays by itself there either
  await c.getByRole("button", { name: /Open/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("video")).toBeVisible();
  expect(await dialog.locator("video").evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);
  await expect(dialog.getByRole("link", { name: /Download MP4/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("Cancel stops a clip that is being made and nothing of it is kept, and the next clip is made", async ({ page }) => {
  await openVideo(page);
  await acknowledged(page);
  const slow = unique("a slow fox [fake:slow]");
  await happens(page).fill(slow);
  await small(page);
  await make(page).click();
  const c = clipCard(page, slow).first();
  await expect(c.locator(".badge").first()).toHaveText("Making clip", { timeout: 20_000 });
  await expect(c.getByRole("progressbar")).toBeVisible();
  await c.getByRole("button", { name: /Cancel/ }).click();
  await expect(page.getByRole("alertdialog").getByText("Stop this clip?")).toBeVisible();
  await page.getByRole("button", { name: "Stop making the clip" }).click();
  await expect(c.locator(".badge").first()).toHaveText("Canceled", { timeout: 20_000 });
  await expect(c.getByText("Canceled. A clip is made whole, so nothing of it was kept.")).toBeVisible();
  await expect(c.locator("video")).toHaveCount(0);
  // and the program is free for the next clip
  const next = unique("the next fox");
  await happens(page).fill(next);
  await make(page).click();
  await done(clipCard(page, next).first());
});

test("Animate this makes a picture the first frame of a clip, and the clip is made from it", async ({ page }) => {
  await page.goto("/");
  const picture = unique("a lighthouse at dusk");
  const c = await generate(page, picture);
  await expect(c.locator(".badge").first()).toHaveText("Done", { timeout: 30_000 });
  await c.getByRole("button", { name: /Animate this/ }).click();
  await expect(videoTab(page)).toHaveAttribute("aria-selected", "true");
  await acknowledged(page);
  await expect(page.getByRole("radio", { name: "Image to video", checked: true })).toBeVisible();
  await expect(form(page).getByAltText(/The start picture/)).toBeVisible();
  await expect(happens(page)).toHaveValue(picture); // the picture's own words
  await expect(page.getByText(/the picture is the first frame/)).toBeVisible();
  await small(page);
  await expect(page.locator("[data-note='crop']")).toBeVisible(); // how the picture is cut to the clip's shape
  await make(page).click();
  const clip = clipCard(page, picture).first();
  await done(clip);
  await expect(clip.locator("video")).toBeVisible();
  const info = await (await page.request.get("/api/runs?kind=video")).json();
  expect(info.runs[0].options.mode).toBe("image");
  expect(info.runs[0].inputs).toHaveLength(1); // the clip kept its own copy of the start picture
});

test("the tab has no sideways scroll at 360 px wide, with the licence, the form and a finished clip", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.request.delete("/api/video/licence", { headers: ASK });
  await openVideo(page);
  const sideways = () => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(await sideways()).toBeLessThanOrEqual(0); // the licence panel
  await acknowledged(page);
  expect(await sideways()).toBeLessThanOrEqual(0); // the form
  const words = unique("a fox at 360 pixels");
  await happens(page).fill(words);
  await small(page);
  await make(page).click();
  const c = clipCard(page, words).first();
  await done(c);
  expect(await sideways()).toBeLessThanOrEqual(0); // a finished clip on its card, with its buttons
  const box = (await c.locator(".video-frame").boundingBox())!;
  expect(box.width).toBeLessThanOrEqual(360);
  for (const button of await c.getByRole("button").all()) {
    const rect = await button.boundingBox();
    if (rect) expect(rect.x + rect.width, "a button is inside the screen").toBeLessThanOrEqual(360);
  }
});

test("the licence can be withdrawn, and the form is off again", async ({ page }) => {
  await openVideo(page);
  await acknowledged(page);
  await page.getByRole("button", { name: "Withdraw my acknowledgement of the licence" }).click();
  await expect(page.getByRole("heading", { name: "The licence" })).toBeVisible();
  await expect(make(page)).toBeDisabled();
});
