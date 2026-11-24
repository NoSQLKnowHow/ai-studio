// The Video tab's logic (DESIGN.md §46): the form and its saved copy, the length in frames, the time a clip takes, the size that goes with a picture, the request, and the words on
// a clip's card. Pure functions, so every rule is tested without a browser (video.test.ts). The numbers (the longest clip, the sizes, the table of times) are the server's, in
// `capabilities.limits.video`, so none is repeated here.

import { duration, timeAgo } from "./format";
import type { KeyValueStore } from "./options";
import type { Capabilities, CreateVideoBody, InputRef, Progress, VideoEstimateTable, VideoLimits, VideoRun, VideoStage } from "./types";

export const VIDEO_FORM_KEY = "studio.video.v1";

/** What the form remembers (DESIGN.md §46.11). The start picture is not here: it is an upload or a run's picture, and an upload expires, so it is chosen again. */
export interface VideoForm {
  mode: "text" | "image";
  prompt: string; // what happens
  sound: string; // what you hear
  keepSound: boolean; // false takes the sound out of the saved file; it does not make the clip cheaper
  seconds: number;
  width: number;
  height: number;
  fps: number;
  seedLocked: boolean; // false = a new random seed every clip
  seed: number;
}

export function defaultVideoForm(caps: Capabilities): VideoForm {
  const limits = caps.limits.video;
  return {
    mode: "text", prompt: "", sound: "", keepSound: true, seconds: limits.seconds.default, width: limits.size.default[0], height: limits.size.default[1], fps: limits.fps[0],
    seedLocked: false, seed: 42,
  };
}

/** The size the program is asked to make for a clip delivered at `width` × `height` (DESIGN.md §46.20): the same, except for a preset whose size the model cannot make itself, which is made
 *  a few pixels bigger and trimmed (HD 1920×1080 is made 1920×1088). The server's `make_size` is the same rule: only a whole preset's size counts, as a pair. */
export function makeSize(size: VideoLimits["size"], width: number, height: number): [number, number] {
  const preset = size.presets.find((p) => p.width === width && p.height === height && (p.make_width !== p.width || p.make_height !== p.height));
  return preset ? [preset.make_width, preset.make_height] : [width, height];
}

/** Whether a clip of this size is made bigger and trimmed (its sides need not be multiples of the model's). */
export function isTrimmedSize(size: VideoLimits["size"], width: number, height: number): boolean {
  const [madeWidth, madeHeight] = makeSize(size, width, height);
  return madeWidth !== width || madeHeight !== height;
}

/** Whether a width and a height may be asked for together: both multiples of the model's step within its limits, or a preset's trimmed size as the pair it is. The server decides again. */
export function sizeAllowed(size: VideoLimits["size"], width: number, height: number): boolean {
  if (isTrimmedSize(size, width, height)) return true;
  const fits = (side: number): boolean => Number.isInteger(side) && side % size.multiple === 0 && side >= size.min && side <= size.max;
  return fits(width) && fits(height);
}

/** The saved form, made safe: a field that is missing or no longer allowed (a limit changed, the browser's storage was edited) is the default's. Never throws. */
export function loadVideoForm(caps: Capabilities, store: KeyValueStore): VideoForm {
  const base = defaultVideoForm(caps);
  const limits = caps.limits.video;
  let saved: Partial<VideoForm> = {};
  try {
    const raw = store.get(VIDEO_FORM_KEY);
    if (raw) saved = JSON.parse(raw) as Partial<VideoForm>;
  } catch {
    saved = {};
  }
  const whole = (value: unknown, lo: number, hi: number, fallback: number): number => (typeof value === "number" && Number.isFinite(value) && value >= lo && value <= hi ? value : fallback);
  const size = (value: unknown, fallback: number): number => (typeof value === "number" && Number.isInteger(value) && value % limits.size.multiple === 0 && value >= limits.size.min && value <= limits.size.max ? value : fallback);
  // a preset's trimmed size (HD 1920×1080) has a side that is no multiple, so it is kept or dropped as the pair it is
  const savedPair = typeof saved.width === "number" && typeof saved.height === "number" && isTrimmedSize(limits.size, saved.width, saved.height);
  return {
    mode: saved.mode === "image" ? "image" : "text",
    prompt: typeof saved.prompt === "string" ? saved.prompt.slice(0, limits.prompt_chars) : base.prompt,
    sound: typeof saved.sound === "string" ? saved.sound.slice(0, limits.sound_chars) : base.sound,
    keepSound: typeof saved.keepSound === "boolean" ? saved.keepSound : base.keepSound,
    seconds: whole(saved.seconds, limits.seconds.min, limits.seconds.max, base.seconds),
    width: savedPair ? (saved.width as number) : size(saved.width, base.width),
    height: savedPair ? (saved.height as number) : size(saved.height, base.height),
    fps: typeof saved.fps === "number" && limits.fps.includes(saved.fps) ? saved.fps : base.fps,
    seedLocked: saved.seedLocked === true,
    seed: whole(saved.seed, 0, caps.limits.seed.max, base.seed),
  };
}

export function saveVideoForm(form: VideoForm, store: KeyValueStore): void {
  store.set(VIDEO_FORM_KEY, JSON.stringify(form));
}

// ------------------------------------------------------------------ the length
/** The frames a clip of `seconds` at `fps` really has: 8 × round(seconds × fps ÷ 8) + 1, at least 9 (DESIGN.md §46.9). The server's `frames_for` is the same rule, and the rounding is
 *  half-up in both (Math.floor(x + 0.5)), so the page says the number the server will make. */
export function framesFor(seconds: number, fps: number): number {
  return Math.max(9, 8 * Math.floor((seconds * fps) / 8 + 0.5) + 1);
}

/** What will really be made, as the form says it under the length: "10 s = 241 frames at 24 fps: 10.0 seconds". */
export function madeText(seconds: number, fps: number): string {
  const frames = framesFor(seconds, fps);
  return `${formatSeconds(seconds)} = ${frames} frames at ${fps} fps: ${(frames / fps).toFixed(1)} seconds`;
}

/** A length in seconds as a person says it: `5`, `7.5`. */
export const formatSeconds = (seconds: number): string => `${Number.isInteger(seconds) ? seconds : Number(seconds.toFixed(2))} s`;

/** The line under a length above the one the model was seen to hold together (DESIGN.md §46.16, as adjusted by the Spark: odd body motion at 20 and 30 s), or null. */
export function lengthNote(seconds: number, limits: VideoLimits): string | null {
  return seconds > limits.seconds.long_from ? limits.seconds.long_note : null;
}

// ------------------------------------------------------------------ the time a clip takes
/** About how many seconds a clip takes to make (DESIGN.md §46.8), from the server's table of measured times: (seconds of video, seconds of work) at the reference size, joined by straight
 *  lines, the last slope carried on past the last point. Only the part above the fixed cost of one run (loading the models) grows with the picture's size, in proportion to its pixels.
 *  Another frame rate than 24 counts as the length it would be at 24 (more frames, more work). */
export function estimateSeconds(table: VideoEstimateTable, seconds: number, width: number, height: number, fps = 24): number {
  const points = [...table.points].sort((a, b) => a[0] - b[0]);
  if (points.length === 0) return 0;
  if (points.length === 1) return points[0][1];
  const at = (seconds * fps) / 24;
  let i = 1;
  while (i < points.length - 1 && at > points[i][0]) i += 1; // the segment the length is on, or the last one (so its slope is carried on)
  const [x0, y0] = points[i - 1];
  const [x1, y1] = points[i];
  const work = y0 + ((y1 - y0) * (at - x0)) / (x1 - x0);
  const overhead = points[0][1];
  const scale = (width * height) / table.reference_pixels;
  return overhead + Math.max(0, work - overhead) * scale;
}

/** A time in words, rounded the way a person would say it: "about 40 seconds", "about 5 minutes", "about 1 hour 5 minutes". */
export function aboutText(seconds: number): string {
  if (seconds < 90) return `${Math.max(5, Math.round(seconds / 5) * 5)} seconds`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${hours} ${hours === 1 ? "hour" : "hours"}${rest ? ` ${rest} minutes` : ""}`;
}

// ------------------------------------------------------------------ the time, from the clips made HERE (DESIGN.md §46.8, as changed)
// The table above was measured on one setup of one machine, and the same clips took about 30 s longer once natten could be imported (2026-11-23): a time worked out from a table is not
// the machine's own. So the estimate is worked out from the clips THIS installation has made, whenever it has made some of about the length asked for, and the table is the fallback,
// said to be what it is. All of it is pure: the table and the clips' times come from the server (`limits.video.estimate`), and nothing here reads a clock or the page.

/** What an estimate is, and what it was worked out from. */
export interface ClipEstimate {
  seconds: number;
  from: "history" | "table";
  samples: number; // the clips made here that it was worked out from (0 for the table)
  bucket: string | null; // which lengths they were ("up to 5 s"), for the history's
}

/** Which length bucket a length is in: the first whose upper edge it does not pass, or the one above the last edge. */
export function lengthBucket(seconds: number, edges: readonly number[]): number {
  const sorted = [...edges].sort((a, b) => a - b);
  const index = sorted.findIndex((edge) => seconds <= edge);
  return index === -1 ? sorted.length : index;
}

/** A bucket in words: "up to 5 s", "over 5 and up to 10 s", "over 30 s". */
export function bucketLabel(index: number, edges: readonly number[]): string {
  const sorted = [...edges].sort((a, b) => a - b);
  if (sorted.length === 0) return "any length";
  if (index <= 0) return `up to ${sorted[0]} s`;
  if (index >= sorted.length) return `over ${sorted[sorted.length - 1]} s`;
  return `over ${sorted[index - 1]} and up to ${sorted[index]} s`;
}

/** The part of a clip's time that grows with the clip (what the table says above its fixed cost), for a length, a size and a frame rate. It is the table's SHAPE (longer clips cost more
 *  than in proportion, a bigger picture in proportion to its pixels) that this borrows; the level is the machine's own, from its clips. */
export function workSeconds(table: VideoEstimateTable, seconds: number, width: number, height: number, fps = 24): number {
  if (table.points.length === 0) return 0;
  const fixed = [...table.points].sort((a, b) => a[0] - b[0])[0][1];
  return Math.max(0, estimateSeconds(table, seconds, width, height, fps) - fixed);
}

const median = (values: number[]): number => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

/** The time of a clip worked out from the clips made on this installation, or null when it has none of about this length (then the table is used, and says so).
 *
 *  - **The fixed part** of a run (loading the models, starting the program) is taken from the SHORTEST clip made here (the one with the least work): its time less its work, so that a
 *    clip of a few seconds does not pass its work off as overhead. A tiny test clip is nearly all fixed part.
 *  - **The rate** is the MEDIAN, over the clips made here in the SAME LENGTH BUCKET as the one asked for (the form's own length choices are the edges), of the clip's time above the fixed
 *    part divided by the work the table's shape says it has: how much faster or slower than the table this machine is, for clips of about this length. Lengths are not mixed, because
 *    nobody knows yet whether natten helps a 30 s clip as it does a 5 s one. The median is not moved by one clip that was slowed by something else. The shortest clip is left out of its
 *    own bucket's rate when others are there (it is how the fixed part was found).
 *  - The estimate is fixed part + rate × the work asked for. Sizes and frame rates are the work's (`workSeconds`), so clips of other sizes are used, scaled.
 *  With a single clip the estimate for its own length is exactly its time, and for another length in its bucket the table's shape moves from it. */
export function estimateFromHistory(table: VideoEstimateTable, seconds: number, width: number, height: number, fps = 24): ClipEstimate | null {
  const edges = table.buckets ?? [];
  const samples = (table.history ?? [])
    .filter((clip) => clip.took > 0 && clip.seconds > 0 && clip.width > 0 && clip.height > 0 && clip.fps > 0)
    .map((clip) => ({ ...clip, work: workSeconds(table, clip.seconds, clip.width, clip.height, clip.fps), bucket: lengthBucket(clip.seconds, edges) }))
    .filter((clip) => clip.work > 0); // a table with nothing above its fixed cost cannot say what a clip's work is
  const target = lengthBucket(seconds, edges);
  const same = samples.filter((clip) => clip.bucket === target);
  if (same.length === 0) return null;
  const shortest = samples.reduce((a, b) => (b.work < a.work || (b.work === a.work && b.took < a.took) ? b : a));
  const fixed = Math.max(0, shortest.took - shortest.work);
  const pool = same.length > 1 ? same.filter((clip) => clip !== shortest) : same;
  const rate = median(pool.map((clip) => Math.max(0, (clip.took - fixed) / clip.work)));
  return { seconds: fixed + rate * workSeconds(table, seconds, width, height, fps), from: "history", samples: same.length, bucket: bucketLabel(target, edges) };
}

/** How long a clip will take, and from what: the clips made here if there are some of about this length, else the table. Null for a table with no points. */
export function estimateClip(table: VideoEstimateTable | undefined, seconds: number, width: number, height: number, fps = 24): ClipEstimate | null {
  if (!table || table.points.length === 0) return null;
  return estimateFromHistory(table, seconds, width, height, fps) ?? { seconds: estimateSeconds(table, seconds, width, height, fps), from: "table", samples: 0, bucket: null };
}

/** The estimate as the form says it, or null for no table. From the clips made here: "About 3 minutes, from the 4 clips of up to 10 s made on this machine." From the table: "About 5
 *  minutes. Measured on one Spark setup, 2026-11-19/20 (no natten); it follows the clips made on this machine once there are some of about this length." The test engine's table says
 *  that it is the test engine's own. */
export function estimateText(table: VideoEstimateTable | undefined, seconds: number, width: number, height: number, fps: number): string | null {
  const estimate = estimateClip(table, seconds, width, height, fps);
  if (!estimate || !table) return null;
  const about = aboutText(estimate.seconds);
  if (estimate.from === "history") {
    return `About ${about}, from ${estimate.samples === 1 ? "the clip" : `the ${estimate.samples} clips`} of ${estimate.bucket} made on this machine.`;
  }
  if (table.kind === "stand-in") return `About ${about} (the test engine's own figure).`;
  const source = table.source.charAt(0).toUpperCase() + table.source.slice(1);
  return `About ${about}. ${source}; it follows the clips made on this machine once there are some of about this length.`;
}

// ------------------------------------------------------------------ size and the start picture
/** The size to offer for a start picture of `pictureWidth` × `pictureHeight` (DESIGN.md §46.11): the shape of the picture at about the pixels of the default size, each side a
 *  multiple of what the model needs and within the sizes allowed. A 16:9 picture gives 1280×704, a square one 960×960. */
export function sizeForPicture(pictureWidth: number, pictureHeight: number, limits: VideoLimits["size"]): { width: number; height: number } {
  const pixels = limits.default[0] * limits.default[1];
  const aspect = pictureWidth > 0 && pictureHeight > 0 ? pictureWidth / pictureHeight : limits.default[0] / limits.default[1];
  const snap = (value: number): number => Math.min(limits.max, Math.max(limits.min, Math.round(value / limits.multiple) * limits.multiple));
  const height = snap(Math.sqrt(pixels / aspect));
  return { width: snap(height * aspect), height };
}

/** How a start picture is cut to a clip's shape (a cover crop from the middle, never a stretch), as the fractions of the picture that stay: for the preview that shades the part cut off. */
export function coverCrop(pictureWidth: number, pictureHeight: number, clipWidth: number, clipHeight: number): { x: number; y: number; width: number; height: number } {
  if (pictureWidth <= 0 || pictureHeight <= 0 || clipWidth <= 0 || clipHeight <= 0) return { x: 0, y: 0, width: 1, height: 1 };
  const picture = pictureWidth / pictureHeight;
  const clip = clipWidth / clipHeight;
  if (Math.abs(picture - clip) < 1e-6) return { x: 0, y: 0, width: 1, height: 1 };
  if (picture > clip) {
    const kept = clip / picture; // the picture is wider than the clip: the sides are cut
    return { x: (1 - kept) / 2, y: 0, width: kept, height: 1 };
  }
  const kept = picture / clip; // taller: the top and bottom are cut
  return { x: 0, y: (1 - kept) / 2, width: 1, height: kept };
}

// ------------------------------------------------------------------ the request
/** What stops the form from being sent, in words, or null. The server checks all of it again; this is so that the button says why it is greyed. */
export function videoProblem(form: VideoForm, caps: Capabilities, hasPicture: boolean): string | null {
  const limits = caps.limits.video;
  if (!form.prompt.trim()) return "Say what happens in the clip.";
  if (form.prompt.length > limits.prompt_chars) return `The words are ${form.prompt.length} characters; the limit is ${limits.prompt_chars}.`;
  if (form.sound.length > limits.sound_chars) return `What you hear is ${form.sound.length} characters; the limit is ${limits.sound_chars}.`;
  if (form.mode === "image" && !hasPicture) return "Image to video needs a start picture: choose one from your history, paste one or upload one.";
  if (!(form.seconds >= limits.seconds.min && form.seconds <= limits.seconds.max)) return `A clip is between ${limits.seconds.min} and ${limits.seconds.max} seconds.`;
  if (!sizeAllowed(limits.size, form.width, form.height)) {
    return `Width and height are multiples of ${limits.size.multiple}, from ${limits.size.min} to ${limits.size.max} (or one of the HD and Scope sizes).`;
  }
  return null;
}

/** The body of `POST /api/runs` for a clip. The start picture goes in `input_images`, as an edit's pictures do; the quality is the one offered (Draft). */
export function buildVideoRequest(form: VideoForm, caps: Capabilities, picture: InputRef | null): CreateVideoBody {
  const image = form.mode === "image" && picture !== null;
  return {
    mode: "video",
    prompt: form.prompt.trim(),
    ...(image ? { input_images: [picture] } : {}),
    options: {
      mode: image ? "image" : "text", quality: caps.limits.video.qualities.default, width: form.width, height: form.height, seconds: form.seconds, fps: form.fps,
      seed: form.seedLocked ? form.seed : null, sound: form.sound.trim(), keep_sound: form.keepSound,
    },
  };
}

/** Retry: the same clip again, with the seed it had. A clip made from a start picture uses the copy of it the run kept (an image of the run's own, which the server accepts). */
export function videoRetryRequest(run: VideoRun): CreateVideoBody {
  const o = run.options;
  const start = run.inputs[0];
  const image = o.mode === "image" && start !== undefined;
  return {
    mode: "video", prompt: run.prompt, ...(image ? { input_images: [{ image_id: start.id }] } : {}),
    options: { mode: image ? "image" : "text", quality: o.quality, width: o.width, height: o.height, seconds: o.seconds, fps: o.fps, seed: o.seed, sound: o.sound, keep_sound: o.keep_sound },
  };
}

/** Reuse: the form as the clip had it, with its seed locked. The start picture, if it had one, is the page's to put back (`run.inputs[0]`). */
export function videoFormFromRun(run: VideoRun, caps: Capabilities, current: VideoForm): VideoForm {
  const o = run.options;
  const limits = caps.limits.video;
  const fits = (value: number): boolean => value % limits.size.multiple === 0 && value >= limits.size.min && value <= limits.size.max;
  const pair = isTrimmedSize(limits.size, o.width, o.height);  // HD 1920×1080 is a pair: neither side is a multiple on its own
  return {
    ...current, mode: o.mode === "image" ? "image" : "text", prompt: run.prompt, sound: o.sound, keepSound: o.keep_sound, seconds: Math.min(limits.seconds.max, Math.max(limits.seconds.min, o.seconds)),
    width: pair || fits(o.width) ? o.width : current.width, height: pair || fits(o.height) ? o.height : current.height, fps: limits.fps.includes(o.fps) ? o.fps : current.fps, seedLocked: true, seed: o.seed,
  };
}

// ------------------------------------------------------------------ the words on a card
/** What the program is doing, in words (DESIGN.md §46.8): its own stages, which the fake engine reports too. */
export const STAGE_WORDS: Record<VideoStage, string> = {
  start: "Starting the video program",
  text: "Reading your words",
  denoise: "Making the picture and sound (first pass)",
  upscale: "Getting ready to sharpen",
  refine: "Sharpening to full size (second pass)",
  decode: "Decoding the picture and sound",
  write: "Writing the file",
};

const isStage = (value: unknown): value is VideoStage => typeof value === "string" && value in STAGE_WORDS;

/** The stage's words and, in the two passes, which step: "Sharpening to full size (second pass): step 2 of 3". */
export function stageText(progress: Progress | null): string {
  if (!progress || !isStage(progress.stage)) return "Starting the video program";
  const words = STAGE_WORDS[progress.stage];
  return progress.steps > 0 && (progress.stage === "denoise" || progress.stage === "refine") ? `${words}: step ${Math.min(progress.step, progress.steps)} of ${progress.steps}` : words;
}

/** How far a clip has got, 0 to 1, for the bar: the two passes count their steps; the rest are the stage's own place, so that the bar only ever moves forward. */
export function stageFraction(progress: Progress | null): number | null {
  if (!progress || !isStage(progress.stage)) return null;
  const order: VideoStage[] = ["start", "text", "denoise", "upscale", "refine", "decode", "write"];
  // the share of a clip each stage is, from the measured clips: the second pass takes most of the time (DESIGN.md §46.8); the rest are small
  const weight: Record<VideoStage, number> = { start: 0, text: 0.05, denoise: 0.3, upscale: 0.05, refine: 0.45, decode: 0.1, write: 0.05 };
  const index = order.indexOf(progress.stage);
  const before = order.slice(0, index).reduce((sum, stage) => sum + weight[stage], 0);
  const inside = progress.steps > 0 ? Math.min(1, progress.step / progress.steps) : 0;
  return Math.min(1, before + weight[progress.stage] * inside);
}

/** The line a working card shows (DESIGN.md §46.11): what the program is doing, how long it has taken, and about how long is left (from the estimate), or that it is taking longer. */
export function workingText(run: VideoRun, estimate: number | null, now: number): string {
  if (!run.started_at) return run.canceling ? "Stopping the video program…" : stageText(run.progress);
  const elapsed = Math.max(0, Math.round((now - Date.parse(run.started_at)) / 1000));
  // A program whose lines are not recognised never gets past "starting": after the time loading takes (about 45 to 75 s on the Spark) the card says it is working and that it does not say
  // which step it is on, instead of looking stuck (DESIGN.md §46.13 criterion 491)
  const silent = (!run.progress || run.progress.stage === "start" || !isStage(run.progress.stage)) && elapsed >= SILENT_AFTER_SECONDS;
  const stage = run.canceling ? "Stopping the video program…" : silent ? "Working: the program does not say which step it is on" : stageText(run.progress);
  const sofar = `${aboutExact(elapsed)} so far`;
  if (run.canceling || estimate === null) return `${stage} · ${sofar}`;
  const left = estimate - elapsed;
  const tail = left > 15 ? `about ${aboutText(left)} to go` : elapsed > estimate * 1.25 ? "taking longer than the estimate" : "nearly done";
  return `${stage} · ${sofar}, ${tail}`;
}

const SILENT_AFTER_SECONDS = 120;

/** An elapsed time exactly: "45 s", "2 min 10 s". */
export function aboutExact(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m ? `${m} min ${String(s).padStart(2, "0")} s` : `${s} s`;
}

/** The facts line of a card (DESIGN.md §46.11): "10.0 s · 1280×704 · 24 fps · Draft · with sound · seed 4821 · 3 min 52 s". A clip that is not finished says what it was asked for. */
export function videoFacts(run: VideoRun): string {
  const clip = run.video;
  const o = run.options;
  const length = clip ? `${clip.seconds.toFixed(1)} s` : formatSeconds(o.seconds);
  const sound = clip ? (clip.has_audio ? "with sound" : "no sound") : o.keep_sound ? "with sound" : "no sound";
  const took = run.status === "done" ? duration(run.started_at, run.finished_at) : null;
  return [length, `${clip?.width ?? o.width}×${clip?.height ?? o.height}`, `${Math.round(clip?.fps ?? o.fps)} fps`, o.quality === "draft" ? "Draft" : o.quality, sound, `seed ${o.seed}`, took]
    .filter(Boolean).join(" · ");
}

/** The card's title and the words a screen reader hears for it: what happens, shortened. */
export function videoTitle(run: VideoRun): string {
  const text = run.prompt.replace(/\s+/g, " ").trim();
  return text.length > 90 ? `${text.slice(0, 89).trimEnd()}…` : text;
}

/** The words of the status badge. */
export function videoStatusLabel(run: VideoRun): string {
  switch (run.status) {
    case "queued":
      return run.queue_position ? `Queued · #${run.queue_position}` : "Queued";
    case "running":
      return run.canceling ? "Stopping" : "Making clip";
    case "done":
      return "Done";
    case "failed":
      return "Failed";
    case "canceled":
      return "Canceled";
  }
}

/** The line a card announces in the page's polite live region when a clip changes state (DESIGN.md §46.11): never twice for the same state. */
export function videoAnnouncement(run: VideoRun): string {
  const what = `Clip “${videoTitle(run)}”`;
  switch (run.status) {
    case "queued":
      return `${what} is queued.`;
    case "running":
      return `${what} is being made.`;
    case "done":
      return `${what} is done.`;
    case "failed":
      return `${what} failed.`;
    case "canceled":
      return `${what} was canceled.`;
  }
}

/** The time a card says a clip was made, as the other cards do. */
export const madeAgo = (run: VideoRun, now: number): string => timeAgo(run.created_at, now);

/** The size of the clips on disk, for the line the tab shows (clips are large, DESIGN.md §46.9). */
export function diskText(bytes: number): string {
  if (bytes < 1024 * 1024) return "less than 1 MB";
  if (bytes < 1024 ** 3) return `${Math.round(bytes / 1024 / 1024)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

// ------------------------------------------------------------------ the start picture
/** The picture a clip starts from, as the form holds it: how it is named to the server (an upload that waits, or an image the studio already has), what to show of it, and its size
 *  (the clip's shape follows it). Not remembered: an upload expires. */
export interface StartPicture {
  ref: InputRef;
  thumbUrl: string | null;
  width: number;
  height: number;
  label: string;
  hasAlpha?: boolean; // the picture has transparency, which the clip does not: it is laid on white (the form says so, DESIGN.md §46.13 criterion 490)
}

/** A picture of the history that can be chosen as a start picture: a result of a finished run. */
export interface VideoPictureChoice {
  imageId: string;
  thumbUrl: string | null;
  width: number;
  height: number;
  label: string;
  hasAlpha?: boolean;
}

/** Animate this (DESIGN.md §46.11): a request for the Video tab to take this picture as its start, with the words of the picture's run. `seq` makes each press a new request. */
export interface AnimateRequest {
  seq: number;
  picture: StartPicture;
  prompt: string;
}

/** A chosen history picture as a start picture. */
export const pictureFromChoice = (choice: VideoPictureChoice): StartPicture => ({
  ref: { image_id: choice.imageId }, thumbUrl: choice.thumbUrl, width: choice.width, height: choice.height, label: choice.label, hasAlpha: choice.hasAlpha,
});

/** The pictures of finished runs the start picker offers (newest first, at most `limit`): each result of a run that is in the history. */
export function pictureChoices(runs: readonly { id: string; prompt: string; deleted_at: string | null; images: { id: string; seed: number; width: number; height: number; thumb_url: string | null; url: string; has_alpha?: boolean }[] }[], limit = 60): VideoPictureChoice[] {
  const found: VideoPictureChoice[] = [];
  for (const run of runs) {
    if (run.deleted_at !== null) continue;
    for (const image of run.images) {
      if (found.length >= limit) return found;
      const words = run.prompt.length > 60 ? `${run.prompt.slice(0, 60)}…` : run.prompt;
      found.push({ imageId: image.id, thumbUrl: image.thumb_url ?? image.url, width: image.width, height: image.height, label: `${words} (${image.seed})`, hasAlpha: image.has_alpha });
    }
  }
  return found;
}

/** What the quality line says (DESIGN.md §46.11): there is one quality offered now. */
export const QUALITY_LINE = "Quality: Draft, the distilled model. Every clip loads the model first, which takes about 45 seconds.";

/** The suggestions under "What you hear" (DESIGN.md §46.11): pressing one puts its words in the box; nothing is added behind the person's back. */
export const SOUND_EXAMPLES = ["a man says, “Hello”", "rain on a window", "soft piano"] as const;

/** What the line above Make clip says is about to be made (DESIGN.md §46.11): "10 s, 1280×704, 24 fps, Draft, with sound. About 5 minutes, from clips measured on this machine." */
export function makeLine(form: VideoForm, limits: VideoLimits): string {
  const frames = framesFor(form.seconds, form.fps);
  const parts = [formatSeconds(form.seconds), `${form.width}×${form.height}`, `${form.fps} fps`, "Draft", form.keepSound ? "with sound" : "no sound in the saved file"];
  const [madeWidth, madeHeight] = makeSize(limits.size, form.width, form.height);  // the work is the size that is made (HD 1920×1080 is made 1920×1088)
  const estimate = estimateText(limits.estimate, form.seconds, madeWidth, madeHeight, form.fps);
  return `${parts.join(", ")} (${frames} frames).${estimate ? ` ${estimate}` : ""}`;
}
