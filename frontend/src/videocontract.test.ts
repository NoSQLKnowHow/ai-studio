import { describe, expect, it } from "vitest";
import type { Counts } from "./history";
import { CAPS, VIDEO_CONTRACT, makeVideoRun } from "./testdata";
import type { ClipTiming, QueueItem, QueueListing, VideoCaps, VideoEstimateTable, VideoInfo, VideoLicence, VideoLimits, VideoOptionsSnapshot, VideoRun, VideoSegment } from "./types";
import { buildVideoRequest, defaultVideoForm, videoRetryRequest } from "./video";

// The page and the server must say the same keys (DESIGN.md §46.10, as §38.9 does for Speech and §31.12 for Vector). The server's tests check that what it sends has the keys of
// backend/tests/video_contract.json (test_video_contract.py); these tests check that the page's types have exactly those keys, so a key added on either side fails one of the two.
//
// Each table below is typed `Record<keyof T, true>`: TypeScript itself refuses a table that misses a key of the type or has one the type has not, so the list cannot be wrong about
// the type; and the test compares the list with the contract's keys, so it cannot be wrong about the server.

type Keys<T> = Record<keyof T, true>;
const same = (table: object, sample: object) => expect(Object.keys(table).sort()).toEqual(Object.keys(sample).sort());
const C = VIDEO_CONTRACT;

const RUN: Keys<VideoRun> = {
  id: true, status: true, prompt: true, effective_prompt: true, model_id: true, created_at: true, started_at: true, finished_at: true, error: true, pinned: true, expires_at: true,
  deleted_at: true, purge_at: true, project_id: true, prompt_ref: true, tags: true, notes: true, queue_position: true, progress: true, canceling: true, mode: true, options: true,
  lyrics: true, inputs: true, images: true, binned_images: true, tracks: true, binned_tracks: true, vectors: true, binned_vectors: true, video: true, segments: true,
};
const OPTIONS: Keys<VideoOptionsSnapshot> = {
  mode: true, quality: true, engine: true, variant: true, width: true, height: true, seconds: true, frames: true, fps: true, seed: true, seed_was_random: true, sound: true,
  keep_sound: true, segments: true, start: true,
};
const START: Keys<NonNullable<VideoOptionsSnapshot["start"]>> = { image: true, frame: true, strength: true };
const VIDEO: Keys<VideoInfo> = {
  id: true, url: true, download_url: true, poster_url: true, thumb_url: true, width: true, height: true, fps: true, frames: true, seconds: true, seed: true, has_audio: true,
  audio_channels: true, audio_rate: true, bytes: true, note: true,
};
const SEGMENT: Keys<VideoSegment> = { idx: true, status: true, seconds: true };
const CAPS_VIDEO: Keys<VideoCaps> = {
  available: true, state: true, reason: true, hint: true, engine: true, licence: true, qualities: true, chaining: true, tools: true, memory: true, clips_bytes: true,
};
const ENGINE: Keys<VideoCaps["engine"]> = {
  id: true, title: true, model_id: true, variants: true, default_variant: true, memory_gb: true, interruptible: true, image_to_video: true, sound: true, notes: true, licence: true,
};
// what the engine says of its own licence is the capability's licence less what only the person's acknowledgement has (whether, when, and whether it is out of date)
const ENGINE_LICENCE: Keys<VideoCaps["engine"]["licence"]> = { name: true, summary: true, url: true, revision: true, statement: true, noncommercial: true, notice: true };
const LICENCE: Keys<VideoLicence> = {
  name: true, summary: true, url: true, revision: true, statement: true, noncommercial: true, notice: true, accepted: true, accepted_at: true, outdated: true,
};
const QUALITY: Keys<VideoCaps["qualities"][number]> = { id: true, label: true, available: true, reason: true };
const CHAINING: Keys<VideoCaps["chaining"]> = { available: true, reason: true };
const TOOLS: Keys<VideoCaps["tools"]> = { ffmpeg: true, ffprobe: true };
const MEMORY: Keys<VideoCaps["memory"]> = { ok: true, message: true };
const LIMITS: Keys<VideoLimits> = { size: true, seconds: true, fps: true, images: true, sound_chars: true, prompt_chars: true, estimate: true, qualities: true };
const SIZE: Keys<VideoLimits["size"]> = { multiple: true, min: true, max: true, default: true, presets: true };
const PRESET: Keys<VideoLimits["size"]["presets"][number]> = { id: true, label: true, width: true, height: true };
const SECONDS: Keys<VideoLimits["seconds"]> = { min: true, max: true, default: true, choices: true, long_from: true, long_note: true };
const IMAGES: Keys<VideoLimits["images"]> = { start: true, end: true };
const ESTIMATE: Keys<VideoEstimateTable> = { points: true, reference_pixels: true, kind: true, source: true, overhead_s: true, buckets: true, history: true };
const TIMING: Keys<ClipTiming> = { seconds: true, width: true, height: true, fps: true, took: true };
const QUALITIES: Keys<VideoLimits["qualities"]> = { default: true, offered: true };
const QUEUE: Keys<QueueListing> = { running: true, queued: true, cap: true };
const QUEUE_ITEM: Keys<QueueItem> = { id: true, kind: true, title: true, draft: true, movable: true, position: true };
const COUNTS: Keys<Counts["video"]> = { all: true, kept: true, deleted: true, deleted_items: true };

describe("what the server sends is what the page's types say", () => {
  it("a clip's run, in each state the page draws: queued, made, silent, from a picture, failed, canceled", () => {
    for (const name of ["run_queued", "run_text", "run_image", "run_silent", "run_failed", "run_canceled"] as const) same(RUN, C[name]);
  });

  it("what a run used, and the start picture it records (an Image to video run) or null (Text to video)", () => {
    same(OPTIONS, C.run_text.options);
    same(OPTIONS, C.run_image.options);
    same(START, C.run_image.options.start!);
    expect(C.run_text.options.start).toBeNull();
  });

  it("the clip a run made, and its segments", () => {
    same(VIDEO, C.run_text.video);
    same(VIDEO, C.run_silent.video);
    same(SEGMENT, C.run_text.segments[0]);
    expect(C.run_queued.video).toBeNull(); // a clip that is not made yet has no file to describe
    expect(C.run_failed.video).toBeNull();
  });

  it("the capability, with and without the licence acknowledged, and each part of it", () => {
    same(CAPS_VIDEO, C.capabilities_video);
    same(CAPS_VIDEO, C.capabilities_video_unaccepted);
    same(ENGINE, C.capabilities_video.engine);
    same(LICENCE, C.capabilities_video.licence);
    same(LICENCE, C.capabilities_video_unaccepted.licence);
    same(ENGINE_LICENCE, C.capabilities_video.engine.licence);
    same(QUALITY, C.capabilities_video.qualities[0]);
    same(CHAINING, C.capabilities_video.chaining);
    same(TOOLS, C.capabilities_video.tools);
    same(MEMORY, C.capabilities_video.memory);
  });

  it("the licence answers: the one a person accepts, the one they withdraw, and what the capability says", () => {
    same(LICENCE, C.licence_answer);
    same(LICENCE, C.licence_withdrawn);
    expect(C.licence_answer.accepted).toBe(true);
    expect(C.licence_withdrawn.accepted).toBe(false);
    expect(C.licence_refusal.code).toBe("licence_not_accepted"); // the form's words come from the server, with this code
  });

  it("the limits and the table that says how long a clip takes", () => {
    same(LIMITS, C.limits_video);
    same(SIZE, C.limits_video.size);
    same(PRESET, C.limits_video.size.presets[0]);
    same(SECONDS, C.limits_video.seconds);
    same(IMAGES, C.limits_video.images);
    same(ESTIMATE, C.limits_video.estimate);
    same(ESTIMATE, C.limits_video_with_history.estimate);
    same(TIMING, C.limits_video_with_history.estimate.history[0]); // the times of the clips made here, which the estimate is worked out from
    same(QUALITIES, C.limits_video.qualities);
  });

  it("the queue, which names a clip's kind, and the tab's counts", () => {
    same(QUEUE, C.queue);
    same(QUEUE_ITEM, C.queue.running!);
    expect(C.queue.running!.kind).toBe("video");
    same(COUNTS, C.counts);
  });

  it("the test data the other tests are built from is the contract's, in the page's types", () => {
    expect(CAPS.video).toEqual(C.capabilities_video as unknown as VideoCaps);
    expect(CAPS.limits.video).toEqual(C.limits_video);
    same(RUN, makeVideoRun());
    same(VIDEO, makeVideoRun().video!);
  });
});

describe("what the page sends is what the server accepts", () => {
  const form = { ...defaultVideoForm(CAPS), prompt: "a fox", seedLocked: true };

  it("the options of a request are names the server reads (it refuses the rest by name, and ignores nothing the page means)", () => {
    for (const body of [buildVideoRequest(form, CAPS, null), buildVideoRequest({ ...form, mode: "image" }, CAPS, { upload_id: "u" }), videoRetryRequest(makeVideoRun())]) {
      for (const key of Object.keys(body.options)) expect(C.requests.run_options, `the server does not read ${key}`).toContain(key);
    }
  });

  it("the request is the one body with the run's words and options (and a picture only for Image to video)", () => {
    expect(Object.keys(buildVideoRequest(form, CAPS, null)).sort()).toEqual(["mode", "options", "prompt"]);
    expect(Object.keys(buildVideoRequest({ ...form, mode: "image" }, CAPS, { upload_id: "u" })).sort()).toEqual(["input_images", "mode", "options", "prompt"]);
  });

  it("the licence's acknowledgement has exactly the fields of the server's model", () => {
    expect(["accept", "revision"]).toEqual(C.requests.licence);
  });

  it("the server lists the requests the page's API calls are checked against", () => {
    expect(Object.keys(C.requests).sort()).toEqual(["licence", "run_options"]);
  });
});
