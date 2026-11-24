import { describe, expect, it } from "vitest";
import type { KeyValueStore } from "./options";
import { CAPS, makeVideoRun } from "./testdata";
import type { Capabilities, ClipTiming, Progress, VideoEstimateTable, VideoRun } from "./types";
import {
  QUALITY_LINE, SOUND_EXAMPLES, VIDEO_FORM_KEY, aboutExact, aboutText, bucketLabel, buildVideoRequest, coverCrop, defaultVideoForm, diskText, estimateClip, estimateFromHistory, estimateSeconds,
  estimateText, formatSeconds, framesFor, lengthBucket, workSeconds,
  isTrimmedSize, lengthNote, loadVideoForm, madeText, makeLine, makeSize, pictureChoices, pictureFromChoice, saveVideoForm, sizeForPicture, stageFraction, stageText, videoAnnouncement, videoFacts,
  sizeAllowed, videoFormFromRun, videoProblem, videoRetryRequest, videoStatusLabel, videoTitle, workingText, type VideoForm,
} from "./video";

// The Video tab's logic, as pure functions (DESIGN.md §46): every rule here is also a rule on the server, which has the numbers (`capabilities.limits.video`); the page repeats none of
// them, so these tests take them from the contract's own limits (the test engine's: sizes from 64, a table of 1 to 6 seconds) and never from a constant written in the test.

const memoryStore = (initial: Record<string, string> = {}): KeyValueStore & { data: Record<string, string> } => {
  const data = { ...initial };
  return { available: true, data, get: (k) => data[k] ?? null, set: (k, v) => { data[k] = v; } };
};
const LIMITS = CAPS.limits.video;
const form = (over: Partial<VideoForm> = {}): VideoForm => ({ ...defaultVideoForm(CAPS), prompt: "a fox in the snow", ...over });
const progress = (stage: Progress["stage"], step = 0, steps = 0): Progress => ({ image: 1, of: 1, step, steps, stage });
const run = (over: Partial<VideoRun> = {}): VideoRun => makeVideoRun(over);

// The Spark's own table, for the tests of what a person is told (the contract's is the test engine's): 5 s took 154 s, 10 s 293 s, 30 s 1,036 s, and starting costs 45 s.
const SPARK: VideoEstimateTable = {
  points: [[0, 45], [5, 154], [10, 293], [20, 604], [30, 1036]], reference_pixels: 1280 * 704, kind: "measured", source: "measured on one Spark setup, 2026-11-19/20 (no natten)", overhead_s: 45,
  buckets: [5, 10, 20, 30], history: [],
};
const withHistory = (history: ClipTiming[], table: VideoEstimateTable = SPARK): VideoEstimateTable => ({ ...table, history });
/** A clip made here: what was asked for, and how long it took. */
const clip = (seconds: number, took: number, width = 1280, height = 704, fps = 24): ClipTiming => ({ seconds, width, height, fps, took });

// ---------------------------------------------------------------- the length
describe("the length of a clip", () => {
  it("is 8n + 1 frames, rounded half up, at least 9, the same numbers the server makes (DESIGN.md §46.9)", () => {
    // the same cases as backend/tests/test_video_options.py: the page says the number the server will make
    expect([0.1, 0.5, 1, 2.5, 5, 7.5, 10, 20, 30].map((s) => framesFor(s, 24))).toEqual([9, 17, 25, 65, 121, 185, 241, 481, 721]);
    expect(framesFor(1, 25)).toBe(25); // 25 frames a second: 3.125 rounds to 3, so 25
    expect(framesFor(0.01, 24)).toBe(9); // never fewer than the model takes
  });

  it("is said under the field as what will really be made", () => {
    expect(madeText(10, 24)).toBe("10 s = 241 frames at 24 fps: 10.0 seconds");
    expect(madeText(7.5, 24)).toBe("7.5 s = 185 frames at 24 fps: 7.7 seconds");
  });

  it("is written as a person says it", () => {
    expect([5, 7.5, 7.123, 1].map(formatSeconds)).toEqual(["5 s", "7.5 s", "7.12 s", "1 s"]);
  });

  it("carries the server's own note for a length above the one the model holds together, and none at or below it", () => {
    expect(lengthNote(LIMITS.seconds.long_from, LIMITS)).toBeNull();
    expect(lengthNote(LIMITS.seconds.long_from + 1, LIMITS)).toBe(LIMITS.seconds.long_note);
    expect(lengthNote(30, LIMITS)).toBe(LIMITS.seconds.long_note);
  });
});

// ---------------------------------------------------------------- the time a clip takes
describe("how long a clip takes", () => {
  const table: VideoEstimateTable = { points: [[0, 1], [5, 2], [30, 6]], reference_pixels: 901120, kind: "stand-in", source: "x", overhead_s: 1, buckets: [5, 10, 20, 30], history: [] };

  it("is read off the table by straight lines between its points, and its last slope is carried on past the end", () => {
    expect(estimateSeconds(table, 5, 1280, 704)).toBeCloseTo(2);
    expect(estimateSeconds(table, 2.5, 1280, 704)).toBeCloseTo(1.5);
    expect(estimateSeconds(table, 10, 1280, 704)).toBeCloseTo(2.8);
    expect(estimateSeconds(table, 30, 1280, 704)).toBeCloseTo(6);
    expect(estimateSeconds(table, 55, 1280, 704)).toBeCloseTo(6 + (4 / 25) * 25); // beyond the table: the slope of the last segment goes on
    expect(estimateSeconds(table, 0, 1280, 704)).toBeCloseTo(1); // a length of nothing still costs the fixed part
  });

  it("grows with the picture's pixels, but only the part above the fixed cost of starting", () => {
    expect(estimateSeconds(table, 5, 1280 * 2, 704)).toBeCloseTo(1 + (2 - 1) * 2); // twice the pixels: the work doubles, the start does not
    expect(estimateSeconds(table, 5, 640, 352)).toBeCloseTo(1 + (2 - 1) * 0.25);
  });

  it("counts a frame rate other than 24 as the length it would be at 24", () => {
    expect(estimateSeconds(table, 5, 1280, 704, 48)).toBeCloseTo(estimateSeconds(table, 10, 1280, 704, 24));
  });

  it("is zero for a table with no points and the one point's value for a table with one", () => {
    expect(estimateSeconds({ ...table, points: [] }, 5, 1280, 704)).toBe(0);
    expect(estimateSeconds({ ...table, points: [[0, 7]] }, 5, 1280, 704)).toBe(7);
  });

  it("is said in a person's words: seconds up to a minute and a half, then minutes, then hours", () => {
    expect([2, 12, 44, 89].map(aboutText)).toEqual(["5 seconds", "10 seconds", "45 seconds", "90 seconds"]);
    expect([90, 293, 3500].map(aboutText)).toEqual(["2 minutes", "5 minutes", "58 minutes"]);
    expect(aboutText(3599)).toBe("1 hour"); // 59.98 minutes is said as the hour it nearly is, not as "60 minutes"
    expect([3600, 3900, 7200, 7500].map(aboutText)).toEqual(["1 hour", "1 hour 5 minutes", "2 hours", "2 hours 5 minutes"]);
  });

  it("says where its figure comes from: the table's own words when there are no clips made here, or the test engine's own", () => {
    expect(estimateText(SPARK, 10, 1280, 704, 24)).toBe(
      "About 5 minutes. Measured on one Spark setup, 2026-11-19/20 (no natten); it follows the clips made on this machine once there are some of about this length.");
    expect(estimateText(table, 5, 1280, 704, 24)).toBe("About 5 seconds (the test engine's own figure).");
    expect(estimateText(undefined, 5, 1280, 704, 24)).toBeNull();
    expect(estimateText({ ...table, points: [] }, 5, 1280, 704, 24)).toBeNull();
  });

  it("matches the measured clips the table was made from (5 s took 154 s, 10 s 293 s, 30 s 1,036 s at 1280x704)", () => {
    expect([5, 10, 20, 30].map((s) => Math.round(estimateSeconds(SPARK, s, 1280, 704)))).toEqual([154, 293, 604, 1036]);
  });
});

// ---------------------------------------------------------------- the time, from the clips made HERE (DESIGN.md §46.8, as changed)
// The times in these tests are the Spark's own, from the brief: with natten importable a tiny clip took 75.1 s and 73.8 s (it had taken 45.0 and 46.3), and 5 s at 1280x704 took 186.4 s (it had
// taken 154.5). The table above is the earlier setup's, and must not be claimed as universal: the page goes by this machine's clips when it has some of about the length asked for.
describe("the length buckets", () => {
  it("sort a length by the form's own choices: the first edge it does not pass, and one above the last", () => {
    expect([1, 5, 5.5, 10, 10.04, 20, 30, 31].map((s) => lengthBucket(s, [5, 10, 20, 30]))).toEqual([0, 0, 1, 1, 2, 2, 3, 4]);
    expect(lengthBucket(7, [30, 5, 20, 10])).toBe(1); // the edges need not come in order
    expect(lengthBucket(7, [])).toBe(0);
  });

  it("are said in words", () => {
    expect([0, 1, 3, 4].map((i) => bucketLabel(i, [5, 10, 20, 30]))).toEqual(["up to 5 s", "over 5 and up to 10 s", "over 20 and up to 30 s", "over 30 s"]);
    expect(bucketLabel(0, [])).toBe("any length");
  });
});

describe("the work of a clip, by the table's shape", () => {
  it("is what the table says above its fixed cost, for a size and a frame rate", () => {
    expect(workSeconds(SPARK, 5, 1280, 704)).toBeCloseTo(109); // 154 - 45
    expect(workSeconds(SPARK, 10, 1280, 704)).toBeCloseTo(248);
    expect(workSeconds(SPARK, 5, 640, 352)).toBeCloseTo(109 / 4); // a quarter of the pixels
    expect(workSeconds(SPARK, 5, 1280, 704, 48)).toBeCloseTo(workSeconds(SPARK, 10, 1280, 704, 24)); // twice the frames
    expect(workSeconds({ ...SPARK, points: [] }, 5, 1280, 704)).toBe(0);
    expect(workSeconds({ ...SPARK, points: [[0, 45]] }, 5, 1280, 704)).toBe(0);
  });
});

describe("the estimate from the clips made here", () => {
  it("is nothing for an empty history, and the table is what is used (and says so)", () => {
    expect(estimateFromHistory(SPARK, 10, 1280, 704)).toBeNull();
    expect(estimateClip(SPARK, 10, 1280, 704)).toEqual({ seconds: 293, from: "table", samples: 0, bucket: null });
    expect(estimateClip(undefined, 10, 1280, 704)).toBeNull();
    expect(estimateClip({ ...SPARK, points: [] }, 10, 1280, 704)).toBeNull();
  });

  it("with one clip is exactly its time for its own length, and the table's shape moves from it for another length of the same bucket", () => {
    const one = withHistory([clip(5, 186.4)]); // the fixed part is 186.4 - 109 = 77.4
    expect(estimateFromHistory(one, 5, 1280, 704)).toMatchObject({ from: "history", samples: 1, bucket: "up to 5 s" });
    expect(estimateFromHistory(one, 5, 1280, 704)!.seconds).toBeCloseTo(186.4);
    expect(estimateFromHistory(one, 3, 1280, 704)!.seconds).toBeCloseTo(77.4 + 65.4); // 3 s: the table's work at 3 s is 0.6 x 109
    expect(estimateFromHistory(one, 5, 640, 352)!.seconds).toBeCloseTo(77.4 + 109 / 4); // a smaller picture: the work shrinks, the fixed part does not
  });

  it("does not guess for a length no clip made here is of: another bucket is the table's", () => {
    const one = withHistory([clip(5, 186.4)]);
    expect(estimateFromHistory(one, 10, 1280, 704)).toBeNull();
    expect(estimateClip(one, 10, 1280, 704)).toEqual({ seconds: 293, from: "table", samples: 0, bucket: null });
    expect(estimateClip(one, 30, 1280, 704)!.from).toBe("table"); // whether natten helps a 30 s clip is not known: nothing is carried over to it
  });

  it("takes the fixed part from the shortest clip, so that a tiny clip's 75 s is the overhead and not a rate", () => {
    const tiny = clip(1, 75.1, 512, 320); // 1 s at 512x320: almost all fixed part
    const five = clip(5, 186.4);
    const estimate = estimateFromHistory(withHistory([five, tiny]), 5, 1280, 704)!;
    expect(estimate).toMatchObject({ from: "history", samples: 2, bucket: "up to 5 s" });
    expect(estimate.seconds).toBeGreaterThan(180);
    expect(estimate.seconds).toBeLessThan(195); // the Spark's own: 186.4 s
    expect(estimateFromHistory(withHistory([tiny]), 5, 1280, 704)!.seconds).toBeCloseTo(75.1 - workSeconds(SPARK, 1, 512, 320) + 109, 1); // one tiny clip says the fixed part, and the table the rest
  });

  it("uses the median of the clips of the same length, so that one that was slowed by something else does not move it", () => {
    const tiny = clip(1, 75.1, 512, 320);
    const steady = [clip(5, 186.4), clip(5, 190), clip(5, 188)];
    const withOutlier = estimateFromHistory(withHistory([...steady, clip(5, 400), tiny]), 5, 1280, 704)!.seconds;
    expect(withOutlier).toBeGreaterThan(180);
    expect(withOutlier).toBeLessThan(200); // not pulled to 400 by the one slow clip
    // and several steady clips agree with their own middle
    const middle = estimateFromHistory(withHistory(steady), 5, 1280, 704)!;
    expect(middle.samples).toBe(3);
    expect(middle.seconds).toBeCloseTo(189, 0);
  });

  it("leaves the shortest clip out of the rate of its own bucket when others are there (it is how the fixed part was found)", () => {
    const tiny = clip(1, 75.1, 512, 320);
    const only = estimateFromHistory(withHistory([tiny, clip(5, 300)]), 5, 1280, 704)!.seconds;
    const without = 71.1 + ((300 - 71.1) / 109) * 109; // the rate is the 5 s clip's alone: the tiny one would have pulled the median toward the table's
    expect(only).toBeCloseTo(without, 0);
  });

  it("scales clips of other sizes by the table's shape, so that a clip made at 1024x576 informs one at 1280x704", () => {
    const tiny = clip(1, 75.1, 512, 320);
    const smaller = clip(5, 71.14 + workSeconds(SPARK, 5, 1024, 576) * 1.1, 1024, 576); // 10 % slower than the table, at a smaller size
    const estimate = estimateFromHistory(withHistory([tiny, smaller]), 5, 1280, 704)!;
    expect(estimate.seconds).toBeCloseTo(71.14 + 1.1 * 109, 0);
    const bigger = estimateFromHistory(withHistory([tiny, smaller]), 5, 1920, 1088)!; // and one at another size than either: the work, scaled by pixels
    expect(bigger.seconds).toBeCloseTo(71.14 + 1.1 * workSeconds(SPARK, 5, 1920, 1088), 0);
  });

  it("goes by the bucket of the length asked for: 5 s and 10 s clips each make their own", () => {
    const history = withHistory([clip(1, 75.1, 512, 320), clip(5, 186.4), clip(10, 330)]);
    expect(estimateFromHistory(history, 10, 1280, 704)).toMatchObject({ from: "history", samples: 1, bucket: "over 5 and up to 10 s" });
    expect(estimateFromHistory(history, 10, 1280, 704)!.seconds).toBeCloseTo(330, 0);
    expect(estimateFromHistory(history, 5, 1280, 704)!.samples).toBe(2);
    expect(estimateFromHistory(history, 20, 1280, 704)).toBeNull();
  });

  it("ignores entries that cannot be used: no time, no length, no size, or a table with no work to measure by", () => {
    const junk = withHistory([clip(5, 0), clip(0, 100), clip(5, -3), clip(5, 100, 0, 704), clip(5, 100, 1280, 704, 0)]);
    expect(estimateFromHistory(junk, 5, 1280, 704)).toBeNull();
    expect(estimateFromHistory(withHistory([clip(5, 186.4)], { ...SPARK, points: [[0, 45]] }), 5, 1280, 704)).toBeNull();
  });

  it("is said with where it comes from, and what the table says when there is nothing to go by", () => {
    const steady = withHistory([clip(5, 186.4), clip(5, 190), clip(5, 188)]);
    expect(estimateText(steady, 5, 1280, 704, 24)).toBe("About 3 minutes, from the 3 clips of up to 5 s made on this machine.");
    expect(estimateText(withHistory([clip(5, 186.4)]), 5, 1280, 704, 24)).toBe("About 3 minutes, from the clip of up to 5 s made on this machine.");
    expect(estimateText(withHistory([clip(1, 75.1, 512, 320), clip(10, 330), clip(10, 335)]), 10, 1280, 704, 24)).toBe("About 6 minutes, from the 2 clips of over 5 and up to 10 s made on this machine.");
    expect(estimateText(steady, 20, 1280, 704, 24)).toContain("Measured on one Spark setup, 2026-11-19/20 (no natten)"); // no clip of that length made here: the table, labelled
    expect(estimateText(steady, 20, 1280, 704, 24)).not.toContain("made on this machine.");
  });

  it("does not change what the stand-in table says, which is the test engine's own", () => {
    const standIn: VideoEstimateTable = { points: [[0, 1], [5, 2], [30, 6]], reference_pixels: 901120, kind: "stand-in", source: "x", overhead_s: 1, buckets: [5, 10, 20, 30], history: [] };
    expect(estimateText(standIn, 5, 1280, 704, 24)).toBe("About 5 seconds (the test engine's own figure).");
  });
});

// ---------------------------------------------------------------- the size that goes with a picture
describe("the size of a clip from a start picture", () => {
  const size = LIMITS.size; // default 1280x704, multiples of 64, 64 to 1920

  it("keeps the picture's shape at about the pixels of the default size, each side a multiple of what the model needs", () => {
    expect(sizeForPicture(1920, 1080, size)).toEqual({ width: 1280, height: 704 });
    expect(sizeForPicture(1000, 1000, size)).toEqual({ width: 960, height: 960 });
    expect(sizeForPicture(1080, 1920, size)).toEqual({ width: 704, height: 1280 });
  });

  it("stays inside the sizes allowed, however extreme the picture", () => {
    const wide = sizeForPicture(10000, 100, size);
    expect(wide.width).toBeLessThanOrEqual(size.max);
    expect(wide.height).toBeGreaterThanOrEqual(size.min);
    expect(wide.width % size.multiple + wide.height % size.multiple).toBe(0);
  });

  it("gives the default shape for a picture with no size", () => {
    expect(sizeForPicture(0, 0, size)).toEqual({ width: 1280, height: 704 });
  });
});

describe("how a start picture is cut to the clip's shape", () => {
  it("is not cut when it is the clip's shape, and a zero size is taken as the whole", () => {
    expect(coverCrop(1280, 704, 1280, 704)).toEqual({ x: 0, y: 0, width: 1, height: 1 });
    expect(coverCrop(0, 0, 1280, 704)).toEqual({ x: 0, y: 0, width: 1, height: 1 });
  });

  it("cuts the sides of a picture that is wider than the clip, from the middle", () => {
    const crop = coverCrop(4000, 1000, 1000, 1000);
    expect(crop).toEqual({ x: 0.375, y: 0, width: 0.25, height: 1 });
  });

  it("cuts the top and bottom of a picture that is taller than the clip, from the middle", () => {
    const crop = coverCrop(1000, 1000, 1000, 500);
    expect(crop).toEqual({ x: 0, y: 0.25, width: 1, height: 0.5 });
  });
});

// ---------------------------------------------------------------- the form, and the copy that is kept
describe("the form", () => {
  it("starts at the server's defaults and asks for nothing the server did not offer", () => {
    expect(defaultVideoForm(CAPS)).toEqual({
      mode: "text", prompt: "", sound: "", keepSound: true, seconds: LIMITS.seconds.default, width: LIMITS.size.default[0], height: LIMITS.size.default[1], fps: LIMITS.fps[0], seedLocked: false, seed: 42,
    });
  });

  it("is remembered between visits, but not the start picture (an upload expires)", () => {
    const store = memoryStore();
    saveVideoForm(form({ sound: "rain", seconds: 5, seedLocked: true, seed: 9 }), store);
    expect(Object.keys(JSON.parse(store.data[VIDEO_FORM_KEY]))).not.toContain("picture");
    expect(loadVideoForm(CAPS, store)).toEqual(form({ sound: "rain", seconds: 5, seedLocked: true, seed: 9 }));
  });

  it("is the default when nothing is saved, when what is saved is not JSON, or when the storage will not answer", () => {
    expect(loadVideoForm(CAPS, memoryStore())).toEqual(defaultVideoForm(CAPS));
    expect(loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: "{not json" }))).toEqual(defaultVideoForm(CAPS));
    const broken: KeyValueStore = { available: true, get: () => { throw new Error("blocked"); }, set: () => {} };
    expect(loadVideoForm(CAPS, broken)).toEqual(defaultVideoForm(CAPS));
  });

  it("takes from a saved copy only what is still allowed: a limit that changed, or a copy that was edited, never makes a request the server would refuse", () => {
    const saved = { mode: "image", prompt: "x".repeat(LIMITS.prompt_chars + 50), sound: "y".repeat(LIMITS.sound_chars + 5), seconds: 999, width: 100, height: LIMITS.size.max + 64, fps: 30,
      seedLocked: "yes", seed: -3, keepSound: "no" };
    const loaded = loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: JSON.stringify(saved) }));
    const base = defaultVideoForm(CAPS);
    expect(loaded.prompt).toHaveLength(LIMITS.prompt_chars);
    expect(loaded.sound).toHaveLength(LIMITS.sound_chars);
    expect(loaded).toMatchObject({ mode: "image", seconds: base.seconds, width: base.width, height: base.height, fps: base.fps, seedLocked: false, seed: base.seed, keepSound: true });
  });

  it("follows a changed limit: a length that is now too long becomes the default", () => {
    const store = memoryStore();
    saveVideoForm(form({ seconds: 30 }), store);
    const shorter: Capabilities = { ...CAPS, limits: { ...CAPS.limits, video: { ...LIMITS, seconds: { ...LIMITS.seconds, max: 20 } } } };
    expect(loadVideoForm(shorter, store).seconds).toBe(LIMITS.seconds.default);
  });
});

describe("what stops the form from being sent", () => {
  it("is said in words, in the order a person would fix it", () => {
    expect(videoProblem(form({ prompt: "   " }), CAPS, false)).toBe("Say what happens in the clip.");
    expect(videoProblem(form({ prompt: "x".repeat(LIMITS.prompt_chars + 1) }), CAPS, false)).toContain(`the limit is ${LIMITS.prompt_chars}`);
    expect(videoProblem(form({ sound: "x".repeat(LIMITS.sound_chars + 1) }), CAPS, false)).toContain(`the limit is ${LIMITS.sound_chars}`);
    expect(videoProblem(form({ mode: "image" }), CAPS, false)).toContain("needs a start picture");
    expect(videoProblem(form({ seconds: 0 }), CAPS, false)).toBe(`A clip is between ${LIMITS.seconds.min} and ${LIMITS.seconds.max} seconds.`);
    expect(videoProblem(form({ seconds: LIMITS.seconds.max + 1 }), CAPS, false)).toContain("A clip is between");
    expect(videoProblem(form({ width: 700 }), CAPS, false)).toContain(`multiples of ${LIMITS.size.multiple}`);
    expect(videoProblem(form({ height: LIMITS.size.max + LIMITS.size.multiple }), CAPS, false)).toContain("multiples of");
  });

  it("is nothing for a form the server will take, with or without a picture where one is wanted", () => {
    expect(videoProblem(form(), CAPS, false)).toBeNull();
    expect(videoProblem(form({ mode: "image" }), CAPS, true)).toBeNull();
  });
});

// ---------------------------------------------------------------- the request
describe("the request for a clip", () => {
  it("is the words trimmed, the sound trimmed, and every option the server reads, with no seed unless it is locked", () => {
    const body = buildVideoRequest(form({ prompt: "  a fox  ", sound: " snow crunching ", keepSound: false, seconds: 5, width: 1024, height: 576 }), CAPS, null);
    expect(body).toEqual({
      mode: "video", prompt: "a fox",
      options: { mode: "text", quality: LIMITS.qualities.default, width: 1024, height: 576, seconds: 5, fps: 24, seed: null, sound: "snow crunching", keep_sound: false },
    });
    expect("input_images" in body).toBe(false); // a text clip names no picture at all
  });

  it("names the start picture as an edit's pictures are named, and says Image to video", () => {
    const upload = buildVideoRequest(form({ mode: "image" }), CAPS, { upload_id: "u1" });
    expect(upload.input_images).toEqual([{ upload_id: "u1" }]);
    expect(upload.options.mode).toBe("image");
    expect(buildVideoRequest(form({ mode: "image" }), CAPS, { image_id: "i9" }).input_images).toEqual([{ image_id: "i9" }]);
  });

  it("is a text clip when the form says Image to video but there is no picture (the button would have been greyed first), and ignores a picture left over in Text to video", () => {
    expect(buildVideoRequest(form({ mode: "image" }), CAPS, null).options.mode).toBe("text");
    const left = buildVideoRequest(form({ mode: "text" }), CAPS, { upload_id: "u1" });
    expect(left.options.mode).toBe("text");
    expect("input_images" in left).toBe(false);
  });

  it("carries the seed when it is locked", () => {
    expect(buildVideoRequest(form({ seedLocked: true, seed: 4821 }), CAPS, null).options.seed).toBe(4821);
    expect(buildVideoRequest(form({ seedLocked: false, seed: 4821 }), CAPS, null).options.seed).toBeNull();
  });

  it("is, for Retry, the same clip with the seed it had, and a start picture by the copy the run kept", () => {
    const text = run({ prompt: "a fox", options: { ...makeVideoRun().options, mode: "text", start: null, seed: 77, sound: "wind", keep_sound: false } });
    expect(videoRetryRequest(text)).toEqual({
      mode: "video", prompt: "a fox",
      options: { mode: "text", quality: text.options.quality, width: text.options.width, height: text.options.height, seconds: text.options.seconds, fps: text.options.fps, seed: 77, sound: "wind", keep_sound: false },
    });
    const image = run({ options: { ...makeVideoRun().options, mode: "image", start: { image: 1, frame: 0, strength: 1 } },
      inputs: [{ id: "kept1", idx: 0, width: 100, height: 100, role: "input", url: "/u", thumb_url: "/t" } as unknown as VideoRun["inputs"][number]] });
    expect(videoRetryRequest(image).input_images).toEqual([{ image_id: "kept1" }]);
    expect(videoRetryRequest(image).options.mode).toBe("image");
  });

  it("is a text clip for Retry when an image clip lost its picture", () => {
    const image = run({ options: { ...makeVideoRun().options, mode: "image", start: { image: 1, frame: 0, strength: 1 } }, inputs: [] });
    expect(videoRetryRequest(image).options.mode).toBe("text");
  });
});

describe("Reuse", () => {
  it("loads the words and settings of a clip with the seed locked, and leaves what is not the clip's alone", () => {
    const old = run({ prompt: "an owl", options: { ...makeVideoRun().options, sound: "hooting", keep_sound: false, seconds: 5, width: 1024, height: 576, seed: 123, mode: "text" } });
    const reused = videoFormFromRun(old, CAPS, form({ prompt: "something else" }));
    expect(reused).toMatchObject({ mode: "text", prompt: "an owl", sound: "hooting", keepSound: false, seconds: 5, width: 1024, height: 576, seedLocked: true, seed: 123 });
  });

  it("keeps the form's own size when the clip's no longer fits (a limit changed), and the length inside the limits", () => {
    const old = run({ options: { ...makeVideoRun().options, width: 100, height: 100, seconds: 999, fps: 30 } });
    const reused = videoFormFromRun(old, CAPS, form({ width: 640, height: 384 }));
    expect(reused).toMatchObject({ width: 640, height: 384, seconds: LIMITS.seconds.max, fps: LIMITS.fps[0] });
  });
});

// ---------------------------------------------------------------- the words on a working card
describe("what a working clip says", () => {
  it("names the stage in words and, in the two passes, the step", () => {
    expect(stageText(null)).toBe("Starting the video program");
    expect(stageText(progress("denoise", 3, 8))).toBe("Making the picture and sound (first pass): step 3 of 8");
    expect(stageText(progress("refine", 2, 3))).toBe("Sharpening to full size (second pass): step 2 of 3");
    expect(stageText(progress("refine", 9, 3))).toBe("Sharpening to full size (second pass): step 3 of 3"); // never past the end
    expect(stageText(progress("decode"))).toBe("Decoding the picture and sound");
    expect(stageText(progress("text", 1, 5))).toBe("Reading your words"); // a stage that does not count steps does not say them
    expect(stageText({ image: 1, of: 1, step: 0, steps: 0 })).toBe("Starting the video program"); // a picture's progress, or an older server's
  });

  it("makes the bar only ever go forward, through the stages in their order, and end at the last", () => {
    const sequence: Progress[] = [progress("start"), progress("text"), progress("denoise", 0, 8), progress("denoise", 4, 8), progress("denoise", 8, 8), progress("upscale"), progress("refine", 0, 3),
      progress("refine", 2, 3), progress("refine", 3, 3), progress("decode"), progress("write")];
    const fractions = sequence.map((p) => stageFraction(p) as number);
    expect(fractions.every((f) => f >= 0 && f <= 1)).toBe(true);
    expect([...fractions].sort((a, b) => a - b)).toEqual(fractions);
    expect(fractions[0]).toBe(0);
    expect(fractions[fractions.length - 1]).toBeGreaterThan(0.9);
    expect(stageFraction(null)).toBeNull();
    expect(stageFraction({ image: 1, of: 1, step: 3, steps: 8 })).toBeNull(); // no stage: the bar is not drawn as a number
  });

  it("says how long it has taken and about how long is left, or that it is taking longer, or nearly done", () => {
    const started = "2026-11-02T13:00:00.000Z";
    const at = (seconds: number) => Date.parse(started) + seconds * 1000;
    const working = run({ status: "running", started_at: started, progress: progress("refine", 2, 3) });
    expect(workingText(working, 300, at(100))).toBe("Sharpening to full size (second pass): step 2 of 3 · 1 min 40 s so far, about 3 minutes to go");
    expect(workingText(working, 300, at(290))).toContain("nearly done");
    expect(workingText(working, 300, at(400))).toContain("taking longer than the estimate");
    expect(workingText(working, null, at(100))).toBe("Sharpening to full size (second pass): step 2 of 3 · 1 min 40 s so far");
    expect(workingText({ ...working, started_at: null }, 300, at(100))).toBe("Sharpening to full size (second pass): step 2 of 3");
    expect(workingText({ ...working, canceling: true }, 300, at(100))).toBe("Stopping the video program… · 1 min 40 s so far");
  });

  it("says the program does not report steps when two minutes have passed and it has not said what it is doing, and not before", () => {
    const started = "2026-11-02T13:00:00.000Z";
    const at = (seconds: number) => Date.parse(started) + seconds * 1000;
    const quiet = run({ status: "running", started_at: started, progress: null });
    expect(workingText(quiet, null, at(60))).toBe("Starting the video program · 1 min 00 s so far");
    expect(workingText(quiet, null, at(150))).toBe("Working: the program does not say which step it is on · 2 min 30 s so far");
    expect(workingText({ ...quiet, progress: progress("start") }, null, at(150))).toContain("does not say which step");
    expect(workingText({ ...quiet, progress: progress("denoise", 2, 8) }, null, at(150))).toContain("Making the picture and sound (first pass): step 2 of 8"); // one that does say is believed
    expect(workingText({ ...quiet, canceling: true }, null, at(150))).toBe("Stopping the video program… · 2 min 30 s so far");
  });

  it("writes an elapsed time exactly", () => {
    expect([45, 60, 130, 3605].map(aboutExact)).toEqual(["45 s", "1 min 00 s", "2 min 10 s", "60 min 05 s"]);
  });
});

// ---------------------------------------------------------------- the card
describe("the words on a clip's card", () => {
  const done = () => run({ started_at: "2026-11-02T13:00:00.000Z", finished_at: "2026-11-02T13:03:52.000Z" });

  it("gives the facts line of a finished clip from the file's own numbers", () => {
    expect(videoFacts(done())).toBe(`${done().video!.seconds.toFixed(1)} s · 256×128 · 24 fps · Draft · with sound · seed 77 · 3m 52s`);
  });

  it("says no sound for a clip whose file has none, and what was asked for while the clip is not made", () => {
    const silent = done();
    silent.video = { ...silent.video!, has_audio: false };
    expect(videoFacts(silent)).toContain("no sound");
    const waiting = run({ status: "queued", video: null, started_at: null, finished_at: null });
    expect(videoFacts(waiting)).toBe("1 s · 256×128 · 24 fps · Draft · with sound · seed 77");
    expect(videoFacts({ ...waiting, options: { ...waiting.options, keep_sound: false } })).toContain("no sound");
  });

  it("names a quality other than Draft as it is", () => {
    expect(videoFacts({ ...done(), options: { ...done().options, quality: "final" } })).toContain("· final ·");
  });

  it("titles a card with what happens, on one line, cut at 90 characters", () => {
    expect(videoTitle(run({ prompt: "a  fox\nin   the snow" }))).toBe("a fox in the snow");
    const long = videoTitle(run({ prompt: "w".repeat(200) }));
    expect(long).toHaveLength(90);
    expect(long.endsWith("…")).toBe(true);
  });

  it("labels the state, with the place in the queue and the stopping that takes a moment", () => {
    expect(videoStatusLabel(run({ status: "queued", queue_position: 2 }))).toBe("Queued · #2");
    expect(videoStatusLabel(run({ status: "queued", queue_position: null }))).toBe("Queued");
    expect(videoStatusLabel(run({ status: "running" }))).toBe("Making clip");
    expect(videoStatusLabel(run({ status: "running", canceling: true }))).toBe("Stopping");
    expect([done(), run({ status: "failed" }), run({ status: "canceled" })].map(videoStatusLabel)).toEqual(["Done", "Failed", "Canceled"]);
  });

  it("announces each state in a sentence that names the clip", () => {
    const named = (status: VideoRun["status"]) => videoAnnouncement(run({ status, prompt: "a fox" }));
    expect(named("queued")).toBe("Clip “a fox” is queued.");
    expect(named("running")).toBe("Clip “a fox” is being made.");
    expect(named("done")).toBe("Clip “a fox” is done.");
    expect(named("failed")).toBe("Clip “a fox” failed.");
    expect(named("canceled")).toBe("Clip “a fox” was canceled.");
  });

  it("says what the clips take on the disk", () => {
    expect([0, 500 * 1024, 5 * 1024 * 1024, 3 * 1024 ** 3].map(diskText)).toEqual(["less than 1 MB", "less than 1 MB", "5 MB", "3.0 GB"]);
  });
});

// ---------------------------------------------------------------- the start picture's choices
describe("the pictures a start can be chosen from", () => {
  const picture = (id: string, over: object = {}) => ({ id, seed: 5, width: 800, height: 600, thumb_url: `/t/${id}`, url: `/u/${id}`, ...over });
  const runs = [
    { id: "r1", prompt: "a lighthouse", deleted_at: null, images: [picture("a"), picture("b", { thumb_url: null })] },
    { id: "r2", prompt: "in the bin", deleted_at: "2026-10-01T00:00:00.000Z", images: [picture("c")] },
    { id: "r3", prompt: "w".repeat(80), deleted_at: null, images: [picture("d")] },
  ];

  it("are the results of the runs that are in the history, newest first, not the bin's", () => {
    expect(pictureChoices(runs).map((c) => c.imageId)).toEqual(["a", "b", "d"]);
  });

  it("show the thumbnail, or the picture itself when it has none, and are labelled by their words and seed", () => {
    const [first, second, third] = pictureChoices(runs);
    expect(first).toMatchObject({ thumbUrl: "/t/a", width: 800, height: 600, label: "a lighthouse (5)" });
    expect(second.thumbUrl).toBe("/u/b");
    expect(third.label).toBe(`${"w".repeat(60)}… (5)`);
  });

  it("stop at the limit", () => {
    expect(pictureChoices(runs, 2).map((c) => c.imageId)).toEqual(["a", "b"]);
    expect(pictureChoices([], 5)).toEqual([]);
  });

  it("become a start picture that names the studio's own image", () => {
    const [choice] = pictureChoices(runs);
    expect(pictureFromChoice(choice)).toEqual({ ref: { image_id: "a" }, thumbUrl: "/t/a", width: 800, height: 600, label: "a lighthouse (5)", hasAlpha: undefined });
  });

  it("carry whether the picture has transparency, for the form's note", () => {
    const withAlpha = [{ id: "r9", prompt: "a logo", deleted_at: null, images: [{ ...picture("z"), has_alpha: true }] }];
    const [choice] = pictureChoices(withAlpha);
    expect(choice.hasAlpha).toBe(true);
    expect(pictureFromChoice(choice).hasAlpha).toBe(true);
  });
});

// ---------------------------------------------------------------- the line above Make clip
describe("the line above Make clip", () => {
  it("says what is about to be made and how long it takes, with the test engine's table for the fake pipeline", () => {
    expect(makeLine(form(), LIMITS)).toBe("10 s, 1280×704, 24 fps, Draft, with sound (241 frames). About 5 seconds (the test engine's own figure).");
  });

  it("says when the saved file has no sound, and the Spark table's own label for a time that is not from this machine", () => {
    const line = makeLine(form({ keepSound: false }), { ...LIMITS, estimate: SPARK });
    expect(line).toBe("10 s, 1280×704, 24 fps, Draft, no sound in the saved file (241 frames). About 5 minutes. Measured on one Spark setup, 2026-11-19/20 (no natten); it follows the clips made on this machine once there are some of about this length.");
  });

  it("has no estimate sentence when the server sent no table", () => {
    expect(makeLine(form(), { ...LIMITS, estimate: { ...LIMITS.estimate, points: [] } })).toBe("10 s, 1280×704, 24 fps, Draft, with sound (241 frames).");
  });
});

describe("the fixed words", () => {
  it("tell the person that every clip loads the model first, and the sound examples are only suggestions", () => {
    expect(QUALITY_LINE).toContain("about 45 seconds");
    expect(SOUND_EXAMPLES.length).toBeGreaterThan(0);
  });
});


// ---------------------------------------------------------------- HD and Scope (DESIGN.md §46.20)
// The program makes only multiples of 64, so HD 1920×1080 and Scope 1920×800 are made 1920×1088 and 1920×832 and trimmed from the middle by the studio. The server decides which size is made
// for which (`make_width` and `make_height` in the presets); the page repeats no number, and these tests take every one from the limits the server sent.
describe("HD and Scope: sizes the program makes a little taller and trims", () => {
  const SIZE = LIMITS.size;
  const preset = (id: string) => {
    const found = SIZE.presets.find((p) => p.id === id);
    if (!found) throw new Error(`the limits have no preset ${id}`);
    return found;
  };

  it("offers both, with the size the program makes for each, and says an ordinary size is made as it is", () => {
    expect(preset("hd")).toMatchObject({ width: 1920, height: 1080, make_width: 1920, make_height: 1088 });
    expect(preset("scope")).toMatchObject({ width: 1920, height: 800, make_width: 1920, make_height: 832 });
    expect(preset("landscape")).toMatchObject({ width: 1280, height: 704, make_width: 1280, make_height: 704 });
  });

  it("makes the size a preset names, and only for the whole size as a pair (nothing nearby is rounded up)", () => {
    expect(makeSize(SIZE, 1920, 1080)).toEqual([1920, 1088]);
    expect(makeSize(SIZE, 1920, 800)).toEqual([1920, 832]);
    expect(makeSize(SIZE, 1280, 704)).toEqual([1280, 704]);
    for (const [w, h] of [[1920, 1081], [1080, 1920], [800, 1920], [1856, 800], [1918, 1080], [1920, 1088], [1920, 832]]) {
      expect(makeSize(SIZE, w, h)).toEqual([w, h]);
      expect(isTrimmedSize(SIZE, w, h)).toBe(false);
    }
    expect(isTrimmedSize(SIZE, 1920, 1080)).toBe(true);
    expect(isTrimmedSize(SIZE, 1920, 800)).toBe(true);
    expect(isTrimmedSize(SIZE, 1280, 704)).toBe(false);
  });

  it("allows a trimmed size as the pair it is, an ordinary size by the old rule, and nothing beside either", () => {
    expect(sizeAllowed(SIZE, 1920, 1080)).toBe(true);
    expect(sizeAllowed(SIZE, 1920, 800)).toBe(true);
    expect(sizeAllowed(SIZE, 1280, 704)).toBe(true);
    expect(sizeAllowed(SIZE, 1920, 1088)).toBe(true);
    for (const [w, h] of [[1920, 1081], [1080, 1920], [1856, 800], [1280, 700], [100, 100], [SIZE.max + SIZE.multiple, 704], [1920, 0]]) expect(sizeAllowed(SIZE, w, h)).toBe(false);
  });

  it("keeps a saved HD size as a pair when the form is loaded, and drops a size beside it a side at a time as before", () => {
    const hd = loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: JSON.stringify({ width: 1920, height: 1080 }) }));
    expect([hd.width, hd.height]).toEqual([1920, 1080]);
    const scope = loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: JSON.stringify({ width: 1920, height: 800 }) }));
    expect([scope.width, scope.height]).toEqual([1920, 800]);
    const beside = loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: JSON.stringify({ width: 1920, height: 1081 }) }));
    expect(beside.height).toBe(defaultVideoForm(CAPS).height);  // 1081 is no size: the default's height
    // a saved size from before the preset existed is untouched by it
    expect(loadVideoForm(CAPS, memoryStore({ [VIDEO_FORM_KEY]: JSON.stringify({ width: 1024, height: 576 }) }))).toMatchObject({ width: 1024, height: 576 });
  });

  it("lets the form be sent at HD and Scope, and says the exceptions in words when another size is not a multiple", () => {
    expect(videoProblem(form({ width: 1920, height: 1080 }), CAPS, false)).toBeNull();
    expect(videoProblem(form({ width: 1920, height: 800 }), CAPS, false)).toBeNull();
    const problem = videoProblem(form({ width: 1920, height: 1081 }), CAPS, false);
    expect(problem).toContain(`multiples of ${SIZE.multiple}`);
    expect(problem).toContain("HD and Scope");
  });

  it("asks the server for the size the person chose, and says nothing of the size the program makes (the server knows it)", () => {
    const body = buildVideoRequest(form({ width: 1920, height: 1080 }), CAPS, null);
    expect(body.options).toMatchObject({ width: 1920, height: 1080 });
    expect(Object.keys(body.options as Record<string, unknown>).filter((k) => k.startsWith("make"))).toEqual([]);
  });

  it("brings a clip made at HD back into the form whole on Reuse", () => {
    const old = run({ options: { ...makeVideoRun().options, width: 1920, height: 1080 } });
    expect(videoFormFromRun(old, CAPS, form({ width: 640, height: 384 }))).toMatchObject({ width: 1920, height: 1080 });
    const scope = run({ options: { ...makeVideoRun().options, width: 1920, height: 800 } });
    expect(videoFormFromRun(scope, CAPS, form({ width: 640, height: 384 }))).toMatchObject({ width: 1920, height: 800 });
  });

  it("counts the size that is made, not the size that is kept, in the time the line above Make clip gives", () => {
    // a table made so that 4% more or less work is a visible difference in the words: the reference is the size Scope is made at
    const table: VideoEstimateTable = { points: [[0, 0], [10, 600000]], reference_pixels: 1920 * 832, kind: "measured", source: "a test table", overhead_s: 0, buckets: [5, 10, 20, 30], history: [] };
    const limits = { ...LIMITS, estimate: table };
    const made = estimateText(table, 10, 1920, 832, 24);
    const kept = estimateText(table, 10, 1920, 800, 24);
    expect(made).not.toBe(kept);  // the test means something only if the two sizes read differently
    const line = makeLine(form({ seconds: 10, width: 1920, height: 800 }), limits);
    expect(line).toContain(made as string);
    expect(line).not.toContain(kept as string);
  });
});
