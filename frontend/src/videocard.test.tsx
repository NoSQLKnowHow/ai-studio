import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProjectControls } from "./components/ProjectMenu";
import { VideoCard } from "./components/VideoCard";
import { makeVideoInfo, makeVideoRun } from "./testdata";
import type { Project, VideoEstimateTable, VideoRun } from "./types";

// The card of a clip (DESIGN.md §46.11): the player, the facts line, what you hear as text, the state while it works, and the buttons each state has. What these protect:
// nothing ever plays by itself (a clip may have sound), the player is the browser's own with the clip's poster, a clip in the bin is not played, what you hear is written out as text for
// a reader who cannot hear it, and a card says in words what it is doing and what went wrong.

afterEach(cleanup);

const NOW = Date.parse("2026-11-02T13:05:00.000Z");
const PROJECT: Project = { id: "a".repeat(32), name: "Fox clips", created_at: "2026-10-01T00:00:00.000Z", counts: { image: 0, music: 0, video: 1 } };
const controls = (over: Partial<ProjectControls> = {}): ProjectControls => ({ projects: [PROJECT], nameMax: 60, onFile: vi.fn(), onUnfile: vi.fn(), onCreate: vi.fn(async () => null), ...over });
const TABLE: VideoEstimateTable = { points: [[0, 45], [5, 154], [10, 293]], reference_pixels: 1280 * 704, kind: "measured", source: "measured on one Spark setup, 2026-11-19/20 (no natten)", overhead_s: 45, buckets: [5, 10, 20, 30], history: [] };

function card(run: VideoRun, props: Partial<Parameters<typeof VideoCard>[0]> = {}) {
  const handlers = { onReuse: vi.fn(), onRetry: vi.fn(), onCancel: vi.fn(), onToggleKeep: vi.fn(), onRestore: vi.fn(), onDelete: vi.fn(), onOpen: vi.fn() };
  const view = render(<VideoCard run={run} now={NOW} estimate={TABLE} transient={false} viewScope="kept" projects={controls()} {...handlers} {...props} />);
  return { ...handlers, view };
}
const button = (name: string | RegExp) => screen.queryByRole("button", { name });
const made = (over: Partial<VideoRun> = {}) => makeVideoRun({ started_at: "2026-11-02T13:00:00.000Z", finished_at: "2026-11-02T13:03:52.000Z", ...over });
const player = (): HTMLVideoElement | null => document.querySelector("video");

describe("a finished clip", () => {
  it("shows the browser's own player with the clip's poster and no way to start by itself", () => {
    const run = made();
    card(run);
    const video = player()!;
    expect(video.getAttribute("src")).toBe(run.video!.url);
    expect(video.getAttribute("poster")).toBe(run.video!.poster_url);
    expect(video.hasAttribute("controls")).toBe(true);
    expect(video.getAttribute("preload")).toBe("metadata"); // the first bytes only: a history of clips is not downloaded to be shown
    for (const attribute of ["autoplay", "loop", "muted"]) expect(video.hasAttribute(attribute), attribute).toBe(false); // a clip may have sound: nothing starts, nothing loops (§46.16 item 12)
    expect(video.autoplay).toBe(false);
    expect(video.getAttribute("aria-label")).toBe(`Play the clip: ${run.prompt}`);
  });

  it("has the clip's own shape, so that nothing jumps when the poster arrives", () => {
    card(made({ video: makeVideoInfo({ width: 704, height: 1280 }) }));
    expect((document.querySelector(".video-frame") as HTMLElement).style.aspectRatio).toBe("704 / 1280");
  });

  it("says its facts from the file's own numbers, and what happens as text", () => {
    card(made());
    expect(screen.getByText(/^1\.0 s · 256×128 · 24 fps · Draft · with sound · seed 77 · 3m 52s$/)).toBeTruthy();
    expect(screen.getByText("a fox in the snow")).toBeTruthy();
    expect(screen.getByRole("article", { name: /Done: clip, a fox in the snow/ })).toBeTruthy();
  });

  it("writes what you hear out as text, so that a reader who cannot hear it still has the words, and says nothing when there are none", () => {
    const run = made();
    run.options = { ...run.options, sound: "snow crunching underfoot" };
    card(run);
    expect(screen.getByText("Sound: snow crunching underfoot")).toBeTruthy();
    cleanup();
    const silent = made();
    silent.options = { ...silent.options, sound: "" };
    card(silent);
    expect(document.querySelector("[data-note='sound']")).toBeNull();
  });

  it("says what the checks found, such as a clip with no sound track, and shows it still plays", () => {
    card(made({ video: makeVideoInfo({ has_audio: false, note: "This clip has no sound track." }) }));
    expect(screen.getByText("This clip has no sound track.")).toBeTruthy();
    expect(document.querySelector("[data-note='facts']")!.textContent).toContain("no sound");
    expect(player()).not.toBeNull();
  });

  it("offers Open, Download MP4 (a real link to the file), Reuse, Keep, Project and Delete", () => {
    const run = made();
    const handlers = card(run);
    const download = screen.getByRole("link", { name: /Download MP4/ });
    expect(download.getAttribute("href")).toBe(run.video!.download_url);
    expect(download.hasAttribute("download")).toBe(true);
    fireEvent.click(button(/Open/)!);
    fireEvent.click(button(/Reuse/)!);
    fireEvent.click(button(/Keep/)!);
    fireEvent.click(button(/^Delete/)!);
    expect([handlers.onOpen, handlers.onReuse, handlers.onToggleKeep, handlers.onDelete].map((fn) => fn.mock.calls.length)).toEqual([1, 1, 1, 1]);
    expect(button(/Cancel/)).toBeNull(); // nothing is going on
    expect(button(/Add to project/)).not.toBeNull();
  });

  it("warns that it will be deleted automatically, until it is kept", () => {
    const soon = made({ expires_at: new Date(NOW + 3 * 86_400_000).toISOString() });
    card(soon);
    expect(screen.getByText(/Will be deleted in 3 days/)).toBeTruthy();
    cleanup();
    card({ ...soon, pinned: true });
    expect(screen.queryByText(/Will be deleted/)).toBeNull();
    expect(button(/Keep/)!.getAttribute("aria-pressed")).toBe("true");
  });

  it("is kept for as long as it is in a project, and says so", () => {
    card(made({ project_id: PROJECT.id, pinned: true }));
    expect(button(/Keep/)!.getAttribute("aria-disabled")).toBe("true");
    expect(button(/Keep/)!.getAttribute("title")).toContain("Fox clips");
    expect(document.querySelector("[data-project-chip]")!.textContent).toContain("Fox clips");
  });

  it("folds a long prompt and unfolds it", () => {
    card(made({ prompt: "a ".repeat(200) }));
    expect(document.querySelector(".run-prompt")!.className).toContain("clamped");
    fireEvent.click(screen.getByRole("button", { name: "Show full text" }));
    expect(document.querySelector(".run-prompt")!.className).not.toContain("clamped");
  });
});

describe("a clip that is waiting or being made", () => {
  it("says what it waits for, and that every clip loads the model first, and can be canceled", () => {
    const handlers = card(made({ status: "queued", video: null, started_at: null, finished_at: null, queue_position: 2 }));
    expect(screen.getByText(/Queued · #2/)).toBeTruthy();
    expect(document.querySelector("[data-note='queued']")!.textContent).toContain("Other models are unloaded first");
    expect(document.querySelector("[data-note='queued']")!.textContent).toContain("about 45 seconds");
    expect(player()).toBeNull(); // no file yet: no player, no Open, no Download
    expect(button(/Open/)).toBeNull();
    expect(screen.queryByRole("link", { name: /Download/ })).toBeNull();
    fireEvent.click(button(/Cancel/)!);
    expect(handlers.onCancel).toHaveBeenCalledTimes(1);
  });

  it("shows a bar that goes with the stage and says in words what the program is doing, how long it has taken and about how long is left", () => {
    const working = made({ status: "running", video: null, finished_at: null, progress: { image: 1, of: 1, step: 2, steps: 3, stage: "refine" } });
    card(working);
    const bar = screen.getByRole("progressbar", { name: "How far the clip has got" });
    expect(Number(bar.getAttribute("aria-valuenow"))).toBeGreaterThan(50);
    expect(screen.getByText(/Sharpening to full size \(second pass\): step 2 of 3 · 5 min 00 s so far/)).toBeTruthy();
    expect(button(/Delete/)!.hasAttribute("disabled")).toBe(true); // not while it is being made
  });

  it("shows a bar that is not a number while the program has not said what it is doing", () => {
    card(made({ status: "running", video: null, finished_at: null, progress: null }));
    expect(document.querySelector(".progress-track")!.className).toContain("indeterminate");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("says it is stopping while Cancel is working, and does not take a second press", () => {
    const handlers = card(made({ status: "running", video: null, finished_at: null, canceling: true }));
    expect(screen.getByText("Stopping")).toBeTruthy();
    expect(screen.getByText(/Stopping the video program…/)).toBeTruthy();
    fireEvent.click(button(/Stopping/)!);
    expect(handlers.onCancel).not.toHaveBeenCalled();
  });

  it("counts the time from the clips made here when it has some, and from the table when it has none", () => {
    const working = made({ status: "running", video: null, finished_at: null, progress: { image: 1, of: 1, step: 1, steps: 8, stage: "denoise" } });
    working.options = { ...working.options, seconds: 5, width: 1280, height: 704, fps: 24 };
    card(working, { now: Date.parse("2026-11-02T13:00:30.000Z") });
    expect(screen.getByText(/about 2 minutes to go/)).toBeTruthy(); // the table: 154 s for 5 s, less the 30 s so far
    cleanup();
    const slow: VideoEstimateTable = { ...TABLE, history: [{ seconds: 5, width: 1280, height: 704, fps: 24, took: 500 }] };
    card(working, { now: Date.parse("2026-11-02T13:00:30.000Z"), estimate: slow });
    expect(screen.getByText(/about 8 minutes to go/)).toBeTruthy(); // this machine's own clip took 500 s: 470 s are left
  });

  it("counts the size the program makes and not the size that is kept, when it is told how (HD and Scope are made a little taller and trimmed)", () => {
    // a table in which 4% of the work is minutes: 30,000 s for 5 s at 1920×832, the size Scope is made at
    const table: VideoEstimateTable = { ...TABLE, points: [[0, 0], [5, 30000]], reference_pixels: 1920 * 832, history: [] };
    const working = made({ status: "running", video: null, finished_at: null, progress: { image: 1, of: 1, step: 1, steps: 8, stage: "denoise" } });
    working.options = { ...working.options, seconds: 5, width: 1920, height: 800, fps: 24 };
    const now = Date.parse("2026-11-02T13:00:30.000Z");
    const toGo = () => screen.getByText(/to go/).textContent;

    card(working, { now, estimate: table, makeSize: (width, height) => [width, height === 800 ? 832 : height] });
    const told = toGo();
    cleanup();
    card(working, { now, estimate: table });  // no mapping given: counted at the size that is kept
    const kept = toGo();
    cleanup();
    expect(told).not.toBe(kept);  // the test means something only if the two read differently
    card({ ...working, options: { ...working.options, height: 832 } }, { now, estimate: table });  // a clip that really is 1920×832
    expect(toGo()).toBe(told);
  });
});

describe("a clip that failed or was canceled", () => {
  it("says what went wrong in the server's words with its hint, and offers Retry", () => {
    const handlers = card(made({ status: "failed", video: null, error: { message: "This clip needed more memory than was free.", hint: "Try a smaller size." } }));
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("This clip needed more memory than was free.")).toBeTruthy();
    expect(within(alert).getByText("Try a smaller size.")).toBeTruthy();
    fireEvent.click(within(alert).getByRole("button", { name: /Retry/ }));
    expect(handlers.onRetry).toHaveBeenCalledTimes(1);
    expect(player()).toBeNull();
  });

  it("says that nothing of a canceled clip was kept", () => {
    card(made({ status: "canceled", video: null }));
    expect(screen.getByText("Canceled. A clip is made whole, so nothing of it was kept.")).toBeTruthy();
  });
});

describe("a clip in the bin", () => {
  const binned = () => made({ deleted_at: "2026-11-02T13:04:00.000Z", purge_at: "2026-12-02T13:04:00.000Z" });

  it("is not played (the server does not serve it from there), says so, and offers Restore, Reuse and Delete forever", () => {
    const handlers = card(binned());
    expect(player()).toBeNull();
    expect(document.querySelector("[data-note='in-bin']")!.textContent).toContain("A clip in the bin cannot be played: restore it first.");
    expect(screen.getByText("Deleted")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Download/ })).toBeNull();
    fireEvent.click(button(/Restore/)!);
    fireEvent.click(button(/Delete forever/)!);
    expect([handlers.onRestore, handlers.onDelete].map((fn) => fn.mock.calls.length)).toEqual([1, 1]);
    expect(button(/Keep/)).toBeNull();
  });

  it("has no Retry on a clip that failed and was deleted", () => {
    card({ ...binned(), status: "failed", video: null, error: { message: "It stopped.", hint: null } });
    expect(button(/Retry/)).toBeNull();
  });
});

describe("a clip that is shown only because it is working", () => {
  it("says which filter it is outside of, as the other cards do", () => {
    card(made({ status: "running", video: null, finished_at: null }), { transient: true, viewScope: "kept" });
    expect(document.querySelector("[data-note='working-in-kept']")).not.toBeNull();
  });
});
