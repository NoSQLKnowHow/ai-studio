import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRef, type MutableRefObject } from "react";
import { VideoPanel } from "./components/VideoPanel";
import type { ProjectControls } from "./components/ProjectMenu";
import { VIDEO_FORM_KEY, buildVideoRequest, defaultVideoForm, type AnimateRequest, type VideoPictureChoice } from "./video";
import type { KeyValueStore } from "./options";
import { CAPS, STATUS, VIDEO_CONTRACT, makeVideoRun } from "./testdata";
import type { Capabilities, VideoRun } from "./types";

// The Video tab (DESIGN.md §46.11): the states it can be in (why it cannot work, the licence not yet acknowledged, the form), what Make clip sends, how a start picture gets in (history,
// upload, paste, Animate this), and the list of clips under the form. What these protect: no clip is asked for until the licence has been acknowledged by the person; the page repeats none of
// the server's numbers; a refusal is shown in the server's words; and nothing starts playing by itself.

const uploadImage = vi.fn();
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), uploadImage: (file: Blob) => uploadImage(file) }));

interface Call { url: string; method: string; body: unknown }
function server(answer: (call: Call) => { status?: number; body: unknown }): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const call = { url, method: init?.method ?? "GET", body: init?.body ? JSON.parse(init.body as string) : null };
    calls.push(call);
    const { status = 200, body } = answer(call);
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  }));
  return calls;
}

const memoryStore = (initial: Record<string, string> = {}): KeyValueStore & { data: Record<string, string> } => {
  const data = { ...initial };
  return { available: true, data, get: (k) => data[k] ?? null, set: (k, v) => { data[k] = v; } };
};
const capsWith = (video: Partial<Capabilities["video"]>, licence: Partial<Capabilities["video"]["licence"]> = {}): Capabilities => ({
  ...CAPS, video: { ...CAPS.video, ...video, licence: { ...CAPS.video.licence, accepted: true, ...licence } },
});
const NOW = Date.parse("2026-11-02T13:05:00.000Z");
const controls = (): ProjectControls => ({ projects: [], nameMax: 60, onFile: vi.fn(), onUnfile: vi.fn(), onCreate: vi.fn(async () => null) });
const push = vi.fn();

function panel(props: Partial<Parameters<typeof VideoPanel>[0]> = {}) {
  const handlers = { onRun: vi.fn(), onLicenceChanged: vi.fn(), onLoadOlder: vi.fn(), onCancel: vi.fn(), onToggleKeep: vi.fn(), onRestore: vi.fn(), onDelete: vi.fn(), onOpen: vi.fn() };
  const pasteRef: MutableRefObject<((files: File[]) => void) | null> = createRef<(files: File[]) => void>() as MutableRefObject<((files: File[]) => void) | null>;
  pasteRef.current = null;
  const store = memoryStore();
  const all = {
    hidden: false, caps: capsWith({}), status: STATUS, store, runs: [] as VideoRun[], runsReady: true, filterBar: <div data-testid="filter-bar" />, loadProblem: null,
    empty: <p>No clips yet</p>, isTransient: () => false, viewScope: "kept" as const, projects: controls(), more: false, loadingOlder: false, now: NOW, push, choices: [] as VideoPictureChoice[],
    animate: null as AnimateRequest | null, pasteRef, ...handlers, ...props,
  };
  const view = render(<VideoPanel {...all} />);
  return { ...handlers, pasteRef, store, view, rerender: (more: Partial<typeof all>) => view.rerender(<VideoPanel {...all} {...more} />) };
}

const prompt = () => screen.getByLabelText("What happens") as HTMLTextAreaElement;
const sound = () => screen.getByLabelText("What you hear") as HTMLTextAreaElement;
const makeButton = () => screen.getByRole("button", { name: /Make clip|Sending/ }) as HTMLButtonElement;
const type = (field: HTMLElement, value: string) => fireEvent.change(field, { target: { value } });
const queuedRun = (over: Partial<VideoRun> = {}) => makeVideoRun({ status: "queued", video: null, started_at: null, finished_at: null, ...over });

beforeEach(() => {
  uploadImage.mockReset();
  push.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("when the video program cannot run here", () => {
  it("says why and what to do, shows no form, and still lists the clips that were made before", () => {
    const caps = capsWith({ available: false, state: "unavailable", reason: "The LTX-2 folder is not there: /home/YOU/ltx-experiment/LTX-2.", hint: "STUDIO_VIDEO_LTX_DIR must be the folder on the host." });
    panel({ caps, runs: [makeVideoRun()] });
    expect(screen.getByText("Video isn't available on this server")).toBeTruthy();
    expect(screen.getByText("The LTX-2 folder is not there: /home/YOU/ltx-experiment/LTX-2.")).toBeTruthy();
    expect(screen.getByText("STUDIO_VIDEO_LTX_DIR must be the folder on the host.")).toBeTruthy();
    expect(screen.queryByLabelText("What happens")).toBeNull();
    expect(document.querySelector("video")).not.toBeNull(); // a clip made before the program went away can still be watched
  });

  it("says it is still checking, and nothing else, while the start-up check is under way", () => {
    panel({ caps: capsWith({ available: false, state: "checking", reason: "The video program is still being checked." }) });
    expect(screen.getByText("Checking the video program…")).toBeTruthy();
    expect(screen.queryByText("Video isn't available on this server")).toBeNull();
  });

  it("falls back to words of its own when the server gave no reason", () => {
    panel({ caps: capsWith({ available: false, state: "unavailable", reason: null, hint: null }) });
    expect(screen.getByText(/can't run on this server as it is set up/)).toBeTruthy();
  });
});

describe("Check again (DESIGN.md §46.8)", () => {
  const unavailable = () => capsWith({ available: false, state: "unavailable", reason: "The LTX-2 folder is not there: /home/YOU/ltx-experiment/LTX-2.", hint: "Check the path in .env." });

  it("is offered where the tab says why it cannot work, asks the server to look again and has the page read the capabilities again", async () => {
    const calls = server(() => ({ status: 202, body: { started: true, state: "checking" } }));
    const { onLicenceChanged } = panel({ caps: unavailable() });
    expect(screen.getByText(/Put it right on the Spark/)).toBeTruthy();
    expect(screen.getByText(/A line changed in .env needs docker compose up -d/)).toBeTruthy(); // what a look again cannot do
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(onLicenceChanged).toHaveBeenCalledTimes(1));
    expect(calls).toEqual([{ url: "/api/video/check", method: "POST", body: null }]);
  });

  it("shows the server's words when it is too soon or a clip is being made, and does not say it started", async () => {
    server(() => ({ status: 429, body: { detail: "The video program was checked 3 seconds ago.", code: "video_check_too_soon", hint: "Wait 7 seconds and press it again." } }));
    const { onLicenceChanged } = panel({ caps: unavailable() });
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect((await screen.findByRole("alert")).textContent).toBe("The video program was checked 3 seconds ago. Wait 7 seconds and press it again.");
    expect(onLicenceChanged).not.toHaveBeenCalled();
  });

  it("is not offered while the program is being checked (the tab fills in by itself), and takes no second press while its request is on the way", async () => {
    panel({ caps: capsWith({ available: false, state: "checking", reason: "The video program is still being checked." }) });
    expect(screen.queryByRole("button", { name: "Check again" })).toBeNull();
    cleanup();
    let release: (value: unknown) => void = () => undefined;
    const calls = server(() => ({ status: 202, body: {} }));
    vi.stubGlobal("fetch", vi.fn(async () => { calls.push({ url: "x", method: "POST", body: null }); await new Promise((resolve) => { release = resolve; }); return new Response("{}", { status: 202 }); }));
    panel({ caps: unavailable() });
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect((await screen.findByRole("button", { name: "Checking…" }) as HTMLButtonElement).disabled).toBe(true);
    release(null);
  });

  it("is also on the form's own line when the tab works, so that a fix made after a failed clip can be looked at", async () => {
    const calls = server(() => ({ status: 202, body: { started: true, state: "checking" } }));
    const { onLicenceChanged } = panel();
    fireEvent.click(screen.getByRole("button", { name: "Check the video program again" }));
    await waitFor(() => expect(onLicenceChanged).toHaveBeenCalledTimes(1));
    expect(calls[0].url).toBe("/api/video/check");
  });
});

describe("the licence (DESIGN.md §46.7)", () => {
  const unaccepted = () => capsWith({}, { accepted: false, accepted_at: null });

  it("is asked for before anything else: the form is switched off, the box starts unticked and Accept does nothing until it is ticked", () => {
    panel({ caps: unaccepted() });
    expect(screen.getByText("The licence")).toBeTruthy();
    const box = screen.getByRole("checkbox", { name: CAPS.video.licence.statement }) as HTMLInputElement;
    expect(box.checked).toBe(false); // never ticked for the person
    expect((screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement).disabled).toBe(true);
    expect((document.querySelector("fieldset.video-fieldset") as HTMLFieldSetElement).disabled).toBe(true);
    expect(makeButton().disabled).toBe(true);
    expect(screen.getByText("The form is switched off until the licence above is acknowledged.")).toBeTruthy();
  });

  it("shows the model card's words as a summary, not as the licence, and links to the binding text", () => {
    panel({ caps: unaccepted() });
    expect(screen.getByText(/A summary, from the model's card \(not the licence's own words\)/)).toBeTruthy();
    expect(screen.getByText(CAPS.video.licence.summary)).toBeTruthy();
    const link = screen.getByRole("link", { name: /Read the binding text/ });
    expect(link.getAttribute("href")).toBe(CAPS.video.licence.url);
    expect(link.getAttribute("rel")).toContain("noreferrer");
  });

  it("is acknowledged by ticking the box and pressing Accept, with the revision the person saw, and the page then asks for the capabilities again", async () => {
    const calls = server(() => ({ body: { ...CAPS.video.licence, accepted: true } }));
    const { onLicenceChanged } = panel({ caps: unaccepted() });
    fireEvent.click(screen.getByRole("checkbox", { name: CAPS.video.licence.statement }));
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(onLicenceChanged).toHaveBeenCalledTimes(1));
    expect(calls).toEqual([{ url: "/api/video/licence", method: "POST", body: { accept: true, revision: CAPS.video.licence.revision } }]);
  });

  it("shows the server's words when it is refused, and does not say the page may go on", async () => {
    server(() => ({ status: 422, body: { detail: "The licence changed while you read it. Read it again.", code: "licence_revision" } }));
    const { onLicenceChanged } = panel({ caps: unaccepted() });
    fireEvent.click(screen.getByRole("checkbox", { name: CAPS.video.licence.statement }));
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect((await screen.findByRole("alert")).textContent).toContain("The licence changed while you read it.");
    expect(onLicenceChanged).not.toHaveBeenCalled();
  });

  it("says why it is asked again when the licence changed since it was acknowledged", () => {
    panel({ caps: capsWith({}, { accepted: false, outdated: true }) });
    expect(document.querySelector("[data-note='licence-changed']")!.textContent).toContain("The licence has changed since you last acknowledged it");
  });

  it("can be withdrawn from the form's own line, and the page asks again", async () => {
    const calls = server(() => ({ body: { ...CAPS.video.licence, accepted: false } }));
    const { onLicenceChanged } = panel();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw my acknowledgement of the licence" }));
    await waitFor(() => expect(onLicenceChanged).toHaveBeenCalled());
    expect(calls[0]).toMatchObject({ url: "/api/video/licence", method: "DELETE" });
  });

  it("is not asked for again, and the form is on, once it is acknowledged", () => {
    panel();
    expect(screen.queryByText("The licence")).toBeNull();
    expect((document.querySelector("fieldset.video-fieldset") as HTMLFieldSetElement).disabled).toBe(false);
  });
});

describe("the form", () => {
  it("starts with the server's own defaults, takes none of its numbers from the page, and offers the lengths and sizes the server lists", () => {
    panel();
    const limits = CAPS.limits.video;
    expect(screen.getByRole("button", { name: `${limits.seconds.default} s`, pressed: true })).toBeTruthy();
    for (const seconds of limits.seconds.choices) expect(screen.getByRole("button", { name: `${seconds} s` })).toBeTruthy();
    for (const preset of limits.size.presets) expect(screen.getByRole("button", { name: preset.label })).toBeTruthy();
    expect(screen.getByRole("button", { name: limits.size.presets[0].label, pressed: true })).toBeTruthy();
    expect(screen.getByText(/10 s = 241 frames at 24 fps: 10.0 seconds/)).toBeTruthy();
    expect(screen.getByText(/About 5 seconds \(the test engine's own figure\)/)).toBeTruthy(); // the contract's table is the test engine's
  });

  it("keeps Make clip off until there are words, and says what is about to be made", () => {
    panel();
    expect(makeButton().disabled).toBe(true);
    type(prompt(), "a fox in the snow");
    expect(makeButton().disabled).toBe(false);
    expect(document.querySelector("[data-note='make-line']")!.textContent).toContain("10 s, 1280×704, 24 fps, Draft, with sound (241 frames)");
  });

  it("puts nothing in What you hear by itself: the examples are suggestions that go in the box only when pressed", () => {
    panel();
    expect(sound().value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "rain on a window" }));
    expect(sound().value).toBe("rain on a window");
    fireEvent.click(screen.getByRole("button", { name: "soft piano" }));
    expect(sound().value).toBe("rain on a window, soft piano");
  });

  it("warns about a length above the one the model holds together, with the server's words, and not below it", () => {
    panel();
    expect(document.querySelector("[data-note='long']")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "20 s" }));
    expect(document.querySelector("[data-note='long']")!.textContent).toBe(CAPS.limits.video.seconds.long_note);
  });

  it("remembers the form for next time, but not a start picture", () => {
    const { store } = panel();
    type(prompt(), "remember me");
    fireEvent.click(screen.getByRole("button", { name: "5 s" }));
    const saved = JSON.parse(store.data[VIDEO_FORM_KEY]);
    expect(saved).toMatchObject({ prompt: "remember me", seconds: 5, mode: "text" });
    expect(Object.keys(saved)).not.toContain("picture");
  });

  it("says in the server's words what is wrong with a size typed by hand, before anything is sent", () => {
    const calls = server(() => ({ body: {} }));
    panel();
    type(prompt(), "a fox");
    fireEvent.click(screen.getByText(/Custom size and seed/));
    type(screen.getByLabelText("Width"), "700");
    fireEvent.click(makeButton());
    expect(screen.getByRole("alert").textContent).toContain(`multiples of ${CAPS.limits.video.size.multiple}`);
    expect(calls).toEqual([]);
  });

  it("shows when there is not enough free memory right now, and what the clips take on the disk", () => {
    panel({ caps: capsWith({ memory: { ok: false, message: "Not enough free memory to load the video model: 5.0 GB available, 60 GB required (STUDIO_VIDEO_MIN_FREE_GB)." }, clips_bytes: 3 * 1024 ** 3 }) });
    expect(document.querySelector("[data-note='memory']")!.textContent).toContain("5.0 GB available, 60 GB required");
    expect(document.querySelector("[data-note='disk']")!.textContent).toContain("3.0 GB");
  });
});

describe("what is not in 1.27 is not on the form (DESIGN.md §46.16)", () => {
  it("offers no Final quality, no end picture, no joining of clips, no chunked mode and no captions", () => {
    panel();
    const form = document.querySelector("[data-video-form]") as HTMLElement;
    const names = [...form.querySelectorAll("button, input, select, textarea, [role='radio'], summary, label")].map((el) => `${el.textContent} ${el.getAttribute("aria-label") ?? ""}`.toLowerCase()).join("\n");
    for (const word of ["final", "end picture", "last frame", "continue from", "chain", "chunk", "caption", "subtitle", "quantiz", "offload"]) expect(names, word).not.toContain(word);
    expect(form.textContent).toContain("Quality: Draft, the distilled model"); // the one quality, said as what it is
    expect(screen.queryByRole("radio", { name: /final/i })).toBeNull();
  });
});

describe("Make clip", () => {
  const answer = () => ({ status: 201, body: queuedRun({ id: "newrun", prompt: "a fox in the snow" }) });

  it("sends the words, the sound and every option, and hands the queued clip to the page", async () => {
    const calls = server(answer);
    const { onRun } = panel();
    type(prompt(), "  a fox in the snow ");
    type(sound(), "snow crunching");
    fireEvent.click(screen.getByRole("button", { name: "5 s" }));
    fireEvent.click(makeButton());
    await waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    const form = { ...defaultVideoForm(CAPS), prompt: "a fox in the snow", sound: "snow crunching", seconds: 5 };
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ url: "/api/runs", method: "POST" });
    expect(calls[0].body).toEqual(buildVideoRequest(form, CAPS, null));
    expect((calls[0].body as { options: { seed: unknown } }).options.seed).toBeNull(); // a new random seed for every clip, unless it is locked
    expect(onRun.mock.calls[0][0].id).toBe("newrun");
  });

  it("sends the seed when it is locked, and no sound in the file when Keep the sound is off", async () => {
    const calls = server(answer);
    panel();
    type(prompt(), "a fox");
    fireEvent.click(screen.getByLabelText("Keep the sound"));
    fireEvent.click(screen.getByText(/Custom size and seed/));
    fireEvent.click(screen.getByLabelText("Lock seed"));
    type(screen.getByLabelText("Seed"), "4821");
    fireEvent.click(makeButton());
    await waitFor(() => expect(calls).toHaveLength(1));
    expect((calls[0].body as { options: Record<string, unknown> }).options).toMatchObject({ seed: 4821, keep_sound: false });
  });

  it("is sent by Ctrl+Enter from the form as well, and once only while the first is on its way", async () => {
    const calls = server(answer);
    panel();
    type(prompt(), "a fox");
    fireEvent.keyDown(prompt(), { key: "Enter", ctrlKey: true });
    fireEvent.keyDown(prompt(), { key: "Enter", ctrlKey: true });
    await waitFor(() => expect(calls.length).toBeGreaterThanOrEqual(1));
    expect(calls).toHaveLength(1);
  });

  it("shows the server's refusal in its own words with its hint, and keeps what was typed", async () => {
    server(() => ({ status: 507, body: { detail: "A 10 s clip needs about 4 MB of disk, and 0.2 GB is free.", code: "storage_full", hint: "Delete clips you no longer need." } }));
    const { onRun } = panel();
    type(prompt(), "a fox");
    fireEvent.click(makeButton());
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("A 10 s clip needs about 4 MB of disk, and 0.2 GB is free. Delete clips you no longer need.");
    expect(prompt().value).toBe("a fox");
    expect(onRun).not.toHaveBeenCalled();
  });

  it("reads the capabilities again when the server says the licence or the program is no longer what the page believed", async () => {
    server(() => ({ status: 409, body: { detail: "The licence has not been acknowledged.", code: "licence_not_accepted", hint: "Acknowledge it on the Video tab." } }));
    const { onLicenceChanged } = panel();
    type(prompt(), "a fox");
    fireEvent.click(makeButton());
    await screen.findByRole("alert");
    expect(onLicenceChanged).toHaveBeenCalledTimes(1);
  });

  it("says a full queue as a message, not as a problem with the form", async () => {
    server(() => ({ status: 429, body: { detail: "The queue is full (10 jobs). Wait for one to finish.", code: "queue_full" } }));
    panel();
    type(prompt(), "a fox");
    fireEvent.click(makeButton());
    await waitFor(() => expect(push).toHaveBeenCalledWith("error", expect.stringContaining("The queue is full")));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("Image to video", () => {
  const upload = (over: Record<string, unknown> = {}) => uploadImage.mockReturnValue({
    promise: Promise.resolve({ upload_id: "u1", width: 1920, height: 1080, url: "/api/uploads/u1", thumb_url: "/api/uploads/u1/thumb", ...over }), abort: vi.fn(),
  });
  const image = () => new File(["x"], "start.png", { type: "image/png" });
  const toImageMode = () => fireEvent.click(screen.getByRole("radio", { name: "Image to video" }));

  it("asks for a start picture first and keeps the request from being sent without one", async () => {
    const calls = server(() => ({ body: {} }));
    panel();
    toImageMode();
    expect(screen.getByText(/Choose a picture from your history, paste one here/)).toBeTruthy();
    type(prompt(), "the lighthouse comes alive");
    fireEvent.click(makeButton());
    expect(screen.getByRole("alert").textContent).toContain("needs a start picture");
    expect(calls).toEqual([]);
  });

  it("takes an uploaded file, shapes the clip like the picture, and sends the upload as the start picture", async () => {
    upload();
    const calls = server(() => ({ status: 201, body: queuedRun({ inputs: [{ id: "kept1", idx: 0, width: 1920, height: 1080, url: "/i", thumb_url: "/t", role: "input" } as unknown as VideoRun["inputs"][number]] }) }));
    const { onRun } = panel();
    toImageMode();
    const input = screen.getByLabelText("Upload a start picture") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [image()] } });
    await screen.findByAltText(/The start picture: start.png/);
    expect(document.querySelector("[data-note='make-line']")!.textContent).toContain("1280×704"); // 16:9 gives the default size
    type(prompt(), "the lighthouse comes alive");
    fireEvent.click(makeButton());
    await waitFor(() => expect(onRun).toHaveBeenCalled());
    const body = calls[0].body as { input_images: unknown[]; options: { mode: string } };
    expect(body.input_images).toEqual([{ upload_id: "u1" }]);
    expect(body.options.mode).toBe("image");
    // the upload was used up by the clip: the form points at the clip's own copy, so that the same picture can start the next one
    fireEvent.click(makeButton());
    await waitFor(() => expect(calls).toHaveLength(2));
    expect((calls[1].body as { input_images: unknown[] }).input_images).toEqual([{ image_id: "kept1" }]);
  });

  it("says that a picture with transparency is laid on white for the clip, and says nothing for one without", async () => {
    upload({ has_alpha: true });
    panel();
    toImageMode();
    fireEvent.change(screen.getByLabelText("Upload a start picture"), { target: { files: [image()] } });
    await screen.findByAltText(/The start picture/);
    expect(document.querySelector("[data-note='transparency']")!.textContent).toBe("This picture has transparency, which a video does not: it is laid on white for the clip.");
    cleanup();
    upload({ has_alpha: false });
    panel();
    toImageMode();
    fireEvent.change(screen.getByLabelText("Upload a start picture"), { target: { files: [image()] } });
    await screen.findByAltText(/The start picture/);
    expect(document.querySelector("[data-note='transparency']")).toBeNull();
  });

  it("follows the picture's shape: a square one gives a square clip", async () => {
    upload({ width: 1000, height: 1000 });
    panel();
    toImageMode();
    fireEvent.change(screen.getByLabelText("Upload a start picture"), { target: { files: [image()] } });
    await screen.findByAltText(/The start picture/);
    expect(document.querySelector("[data-note='make-line']")!.textContent).toContain("960×960");
    expect(document.querySelector("[data-note='crop']")!.textContent).toContain("all of it is used");
  });

  it("says in the server's words why a file was refused, and goes on without a picture", async () => {
    uploadImage.mockReturnValue({ promise: Promise.reject(Object.assign(new Error("That file is not a picture the studio can read."), { status: 422, name: "ApiError" })), abort: vi.fn() });
    panel();
    toImageMode();
    fireEvent.change(screen.getByLabelText("Upload a start picture"), { target: { files: [image()] } });
    await waitFor(() => expect(document.querySelector(".video-picture [role='alert']")).not.toBeNull());
    expect(screen.queryByAltText(/The start picture/)).toBeNull();
  });

  it("takes a picture from the history, shows how it is cut, and can be removed", async () => {
    const choices: VideoPictureChoice[] = [{ imageId: "img9", thumbUrl: "/t9", width: 1000, height: 2000, label: "a lighthouse (5)" }];
    const calls = server(() => ({ status: 201, body: queuedRun() }));
    panel({ choices });
    toImageMode();
    fireEvent.click(screen.getByRole("button", { name: "From your history" }));
    fireEvent.click(await screen.findByRole("button", { name: "a lighthouse (5)" }));
    expect(await screen.findByAltText("The start picture: a lighthouse (5)")).toBeTruthy();
    expect(document.querySelector("[data-note='crop']")!.textContent).toContain("never stretched"); // a tall picture in a clip of its own shape is whole; the hint names the cut when there is one
    type(prompt(), "it moves");
    fireEvent.click(makeButton());
    await waitFor(() => expect(calls).toHaveLength(1));
    expect((calls[0].body as { input_images: unknown[] }).input_images).toEqual([{ image_id: "img9" }]);
    fireEvent.click(screen.getByRole("button", { name: /Remove the picture/ }));
    expect(screen.queryByAltText(/The start picture/)).toBeNull();
  });

  it("says there is nothing to choose from when the history has no pictures", async () => {
    panel({ choices: [] });
    toImageMode();
    fireEvent.click(screen.getByRole("button", { name: "From your history" }));
    expect(await screen.findByText(/There are no pictures in your history yet/)).toBeTruthy();
  });

  it("takes a pasted picture as the start picture, and only the first of several", async () => {
    upload();
    const { pasteRef } = panel();
    await act(async () => { pasteRef.current?.([image(), image()]); });
    await screen.findByAltText(/The start picture/);
    expect(uploadImage).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("radio", { name: "Image to video", checked: true })).toBeTruthy(); // a pasted picture means Image to video
  });

  it("stops listening for pastes when the tab goes away", () => {
    const { pasteRef, view } = panel();
    expect(pasteRef.current).not.toBeNull();
    view.unmount();
    expect(pasteRef.current).toBeNull();
  });
});

describe("Animate this (DESIGN.md §46.11)", () => {
  const request = (seq: number, prompt = "a lighthouse at dusk"): AnimateRequest => ({
    seq, prompt, picture: { ref: { image_id: "img1" }, thumbUrl: "/t1", width: 2048, height: 2048, label: "a lighthouse at dusk (101)" },
  });

  it("makes the picture the first frame, brings the picture's words, tells the person, and can be undone", async () => {
    const view = panel({ animate: null });
    type(prompt(), "my own words");
    view.rerender({ animate: request(1) });
    expect(await screen.findByAltText("The start picture: a lighthouse at dusk (101)")).toBeTruthy();
    expect(prompt().value).toBe("a lighthouse at dusk");
    expect(screen.getByRole("radio", { name: "Image to video", checked: true })).toBeTruthy();
    expect(push).toHaveBeenCalledWith("info", expect.stringContaining("the picture is the first frame"), expect.objectContaining({ label: "Undo" }));
    act(() => { push.mock.calls[0][2].run(); }); // Undo puts the form back as it was
    await waitFor(() => expect(prompt().value).toBe("my own words"));
    expect(screen.queryByAltText(/The start picture/)).toBeNull();
    expect(screen.getByRole("radio", { name: "Text to video", checked: true })).toBeTruthy();
  });

  it("is a new request each time, but the same request again does nothing", async () => {
    const view = panel({ animate: null });
    view.rerender({ animate: request(1) });
    await screen.findByAltText(/The start picture/);
    view.rerender({ animate: request(1) });
    expect(push).toHaveBeenCalledTimes(1);
    view.rerender({ animate: request(2, "something else") });
    await waitFor(() => expect(push).toHaveBeenCalledTimes(2));
    expect(prompt().value).toBe("something else");
  });

  it("leaves the words as they are when the picture's run had none to bring", async () => {
    const view = panel({ animate: null });
    type(prompt(), "keep these");
    view.rerender({ animate: request(1, "") });
    await screen.findByAltText(/The start picture/);
    expect(prompt().value).toBe("keep these");
  });
});

describe("the clips under the form", () => {
  it("says it is loading, shows the filter bar, and what the list says when it is empty", () => {
    panel({ runsReady: false });
    expect(screen.getByText("Loading your clips…")).toBeTruthy();
    expect(screen.getByTestId("filter-bar")).toBeTruthy();
    cleanup();
    panel({ runs: [] });
    expect(screen.getByText("No clips yet")).toBeTruthy();
  });

  it("shows a load problem in place of Loading, and Load older runs when there are more", () => {
    panel({ runsReady: false, loadProblem: <p>The list could not be loaded.</p> });
    expect(screen.getByText("The list could not be loaded.")).toBeTruthy();
    expect(screen.queryByText("Loading your clips…")).toBeNull();
    cleanup();
    const { onLoadOlder } = panel({ runs: [makeVideoRun()], more: true });
    fireEvent.click(screen.getByRole("button", { name: "Load older runs" }));
    expect(onLoadOlder).toHaveBeenCalledTimes(1);
  });

  it("hands each card's buttons to the page", () => {
    const run = makeVideoRun();
    const { onOpen, onToggleKeep, onDelete, onCancel } = panel({ runs: [run, queuedRun()] });
    fireEvent.click(screen.getAllByRole("button", { name: /Open/ })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /Keep/ })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: /^Delete/ })[0]);
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect([onOpen, onToggleKeep, onDelete, onCancel].map((fn) => fn.mock.calls.length)).toEqual([1, 1, 1, 1]);
    expect(onOpen.mock.calls[0][0].id).toBe(run.id);
  });

  it("loads a clip's words and settings with the seed locked when Reuse is pressed, and tells the person", () => {
    window.scrollTo = vi.fn();
    const run = makeVideoRun({ prompt: "an owl at night" });
    run.options = { ...run.options, sound: "hooting", seconds: 5, seed: 123 };
    panel({ runs: [run] });
    fireEvent.click(screen.getByRole("button", { name: /Reuse/ }));
    expect(prompt().value).toBe("an owl at night");
    expect(sound().value).toBe("hooting");
    expect(push).toHaveBeenCalledWith("info", "Loaded the words and settings. Seed locked to 123.");
    expect(screen.getByRole("button", { name: "5 s", pressed: true })).toBeTruthy();
    expect(screen.getByText(/seed locked to 123/)).toBeTruthy();
  });

  it("asks for the same clip again when Retry is pressed on a clip that failed, with the seed it had", async () => {
    const failed = queuedRun({ status: "failed", error: { message: "It stopped.", hint: null } });
    const calls = server(() => ({ status: 201, body: queuedRun({ id: "again" }) }));
    const { onRun } = panel({ runs: [failed] });
    fireEvent.click(within(screen.getByRole("alert")).getByRole("button", { name: /Retry/ }));
    await waitFor(() => expect(onRun).toHaveBeenCalled());
    expect((calls[0].body as { options: { seed: number } }).options.seed).toBe(failed.options.seed);
  });
});

describe("sound and playing", () => {
  const playing = (video: HTMLVideoElement, paused: boolean) => {
    Object.defineProperty(video, "paused", { configurable: true, value: paused });
    video.pause = vi.fn();
    return video;
  };

  it("lets one clip play at a time: starting one stops the others", () => {
    panel({ runs: [makeVideoRun(), makeVideoRun()] });
    const [first, second] = [...document.querySelectorAll("video")].map((video) => playing(video, false));
    fireEvent(second, new Event("play", { bubbles: false }));
    expect(first.pause).toHaveBeenCalledTimes(1);
    expect(second.pause).not.toHaveBeenCalled();
  });

  it("stops every clip when the tab is not the one on the screen, so that no sound comes from a tab nobody sees", () => {
    const runs = [makeVideoRun()];
    const view = panel({ runs });
    const video = playing(document.querySelector("video")!, false);
    view.rerender({ runs, hidden: true });
    expect(video.pause).toHaveBeenCalled();
  });

  it("says in a polite live region when a clip changes state, and nothing for the first look at the list", () => {
    const run = queuedRun({ id: "c1", prompt: "a fox" });
    const view = panel({ runs: [run] });
    const live = () => document.querySelector("[data-video-live]")!;
    expect(live().textContent).toBe("");
    expect(live().getAttribute("aria-live")).toBe("polite");
    view.rerender({ runs: [{ ...run, status: "running" }] });
    expect(live().textContent).toBe("Clip “a fox” is being made.");
    view.rerender({ runs: [{ ...run, status: "done" }] });
    expect(live().textContent).toBe("Clip “a fox” is done.");
  });
});

describe("HD and Scope (DESIGN.md §46.20)", () => {
  const answer = () => ({ status: 201, body: queuedRun({ id: "newrun", prompt: "a wide shot" }) });
  const chip = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement;
  const note = () => document.querySelector("[data-note='trimmed']");

  it("offers both next to the other sizes, and the first is the one that was chosen before", () => {
    panel();
    expect(chip("1280×704").getAttribute("aria-pressed")).toBe("true");
    expect(chip("HD 1920×1080").getAttribute("aria-pressed")).toBe("false");
    expect(chip("Scope 2.40:1 · 1920×800").getAttribute("aria-pressed")).toBe("false");
    expect(note()).toBeNull();
    // for a size that is made as it is, the line says the rule and where its two exceptions are
    expect(screen.getByText(/Each side is a multiple of 64\. 1280×704\. HD and Scope are the exceptions/)).toBeTruthy();
  });

  it("says, for HD, what the program makes and that the studio trims it, and the custom fields say the same", () => {
    panel();
    fireEvent.click(chip("HD 1920×1080"));
    expect(chip("HD 1920×1080").getAttribute("aria-pressed")).toBe("true");
    expect(chip("1280×704").getAttribute("aria-pressed")).toBe("false");
    expect(note()!.textContent).toContain("the program makes 1920×1088");
    expect(note()!.textContent).toContain("trims the picture to 1920×1080");
    fireEvent.click(screen.getByText(/Custom size and seed/));
    expect((screen.getByLabelText("Width") as HTMLInputElement).value).toBe("1920");
    expect((screen.getByLabelText("Height") as HTMLInputElement).value).toBe("1080");
    expect(screen.getByText("Trimmed from 1920.")).toBeTruthy();
    expect(screen.getByText("Trimmed from 1088.")).toBeTruthy();
    // and going back to a size that is made as it is brings the ordinary words back
    fireEvent.click(chip("1280×704"));
    expect(note()).toBeNull();
    expect(screen.queryByText("Trimmed from 1088.")).toBeNull();
  });

  it("says the same of Scope", () => {
    panel();
    fireEvent.click(chip("Scope 2.40:1 · 1920×800"));
    expect(note()!.textContent).toContain("the program makes 1920×832");
    expect(note()!.textContent).toContain("trims the picture to 1920×800");
  });

  it("sends the size that was chosen and nothing about the size the program makes", async () => {
    const calls = server(answer);
    panel();
    type(prompt(), "a wide shot");
    fireEvent.click(chip("Scope 2.40:1 · 1920×800"));
    fireEvent.click(makeButton());
    await waitFor(() => expect(calls).toHaveLength(1));
    const options = (calls[0].body as { options: Record<string, unknown> }).options;
    expect(options).toMatchObject({ width: 1920, height: 800 });
    expect(Object.keys(options).filter((key) => key.startsWith("make"))).toEqual([]);
  });

  it("gives each card the size the program makes, so that the time left on a working clip counts that size and not the size that is kept", () => {
    // a table in which 4% of the work is minutes: 30,000 s for 5 s at 1920×832, the size Scope is made at
    const estimate = { ...CAPS.limits.video.estimate, points: [[0, 0], [5, 30000]] as [number, number][], reference_pixels: 1920 * 832, overhead_s: 0, history: [] };
    const caps = { ...CAPS, limits: { ...CAPS.limits, video: { ...CAPS.limits.video, estimate } } };
    const working = (height: number) => makeVideoRun({
      status: "running", video: null, finished_at: null, started_at: new Date(NOW - 30_000).toISOString(), progress: { image: 1, of: 1, step: 1, steps: 8, stage: "denoise" },
      options: { ...makeVideoRun().options, seconds: 5, width: 1920, height, fps: 24 },
    });
    const toGo = () => screen.getAllByText(/to go/)[0].textContent;
    panel({ caps, runs: [working(800)] });  // a Scope clip, which the program is making at 1920×832
    const scope = toGo();
    cleanup();
    panel({ caps, runs: [working(832)] });  // a clip that really is 1920×832
    expect(toGo()).toBe(scope);  // the same work, so the same time: were the card told the size that is kept, 800 would read shorter
    cleanup();
    panel({ caps, runs: [working(704)] });  // and a size that is made as it is is counted as it is
    expect(toGo()).not.toBe(scope);
  });

  it("keeps HD as the size of the form when the page is opened again", () => {
    const first = panel();
    fireEvent.click(chip("HD 1920×1080"));
    expect(JSON.parse(first.store.data[VIDEO_FORM_KEY])).toMatchObject({ width: 1920, height: 1080 });
    first.view.unmount();
    cleanup();
    panel({ store: memoryStore({ [VIDEO_FORM_KEY]: first.store.data[VIDEO_FORM_KEY] }) });
    expect(chip("HD 1920×1080").getAttribute("aria-pressed")).toBe("true");
  });
});

describe("the contract's own capability", () => {
  it("is the one these tests are made with: ready, the licence acknowledged, and the test engine", () => {
    expect(VIDEO_CONTRACT.capabilities_video.state).toBe("ready");
    expect(CAPS.video.licence.accepted).toBe(true);
    expect(CAPS.video.engine.id).toBe("fake");
  });
});
