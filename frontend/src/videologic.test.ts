import { describe, expect, it } from "vitest";
import { binContents, canceledText, deleteProjectQuestion, emptyBinQuestion, projectContents } from "./format";
import { NO_FILTER, matches, searchableWords, type HistoryFilter } from "./history";
import { modelAction, MODEL_LABEL } from "./model";
import { TABS, readTab, saveTab, tabAfterKey } from "./music";
import { routePaste, type PasteFacts } from "./paste";
import { kindWords } from "./queue";
import { STATUS, makeRun, makeVideoRun } from "./testdata";
import type { KeyValueStore } from "./options";
import type { WorkerStatus } from "./types";

// The small additions the Video tab (DESIGN.md §46) made to the page's shared logic: what a canceled clip says, what the bin and a project say of clips, what a search finds in a clip, where a
// paste goes on the tab, that the model button is not offered there, and the sixth tab. Each protects a promise of §46, named in its test.

const memoryStore = (initial: Record<string, string> = {}): KeyValueStore & { data: Record<string, string> } => {
  const data = { ...initial };
  return { available: true, data, get: (k) => data[k] ?? null, set: (k, v) => { data[k] = v; } };
};

describe("the sixth tab", () => {
  it("is Video, after Speech, remembered like the others, and reachable by the arrow keys", () => {
    expect(TABS.map((tab) => tab.id)).toEqual(["images", "music", "vector", "builder", "speech", "video"]);
    const store = memoryStore();
    saveTab("video", store);
    expect(readTab(store)).toBe("video");
    expect(tabAfterKey("speech", "ArrowRight")).toBe("video");
    expect(tabAfterKey("video", "ArrowRight")).toBe("images");
    expect(tabAfterKey("images", "End")).toBe("video");
  });
});

describe("a canceled clip", () => {
  it("says that nothing of it was kept: a clip is made whole or not at all (DESIGN.md §46.8)", () => {
    expect(canceledText(makeVideoRun({ status: "canceled", video: null }))).toBe("Canceled. A clip is made whole, so nothing of it was kept.");
  });
});

describe("the bin and the projects, with clips in them", () => {
  it("count a clip in the bin as a run and nothing of its own: there are no pictures or tracks to delete alone", () => {
    const bin = binContents({ image: { deleted: 0, deleted_items: 0 }, music: { deleted: 0, deleted_items: 0 }, video: { deleted: 2, deleted_items: 0 } });
    expect(bin.video).toEqual({ runs: 2, items: 0 });
    expect(binContents({ image: { deleted: 0, deleted_items: 0 }, music: { deleted: 0, deleted_items: 0 } }).video).toEqual({ runs: 0, items: 0 }); // an older server says nothing of clips
  });

  it("name the Video tab in the question Empty bin asks, with the clips in the total", () => {
    const bin = binContents({ image: { deleted: 1, deleted_items: 0 }, music: { deleted: 0, deleted_items: 0 }, video: { deleted: 2, deleted_items: 0 } });
    const question = emptyBinQuestion(bin, false);
    expect(question).toContain("3 runs");
    expect(question).toContain("1 on Images, 2 on Video");
  });

  it("say a project's clips as clips, and count them among the runs that stay when it is deleted", () => {
    expect(projectContents({ image: 1, music: 0, video: 2 })).toBe("1 picture, 2 clips");
    expect(projectContents({ image: 0, music: 0, video: 1 })).toBe("1 clip");
    expect(projectContents({ image: 0, music: 0 })).toBe("no runs");
    const question = deleteProjectQuestion({ name: "Fox", counts: { image: 0, music: 0, video: 2 } });
    expect(question).toContain("Its 2 runs (2 clips) are not deleted");
  });
});

describe("a search finds a clip by what happens, what you hear, its notes and tags, and not by its settings (DESIGN.md §45.4 rule 1, §46.9)", () => {
  const clip = makeVideoRun({ prompt: "A heron on a frozen lake", notes: "for the intro", tags: ["birds"] });
  clip.options = { ...clip.options, sound: "wind over ice, distant crows", seed: 31337, width: 1280, height: 704 };
  const search = (q: string): HistoryFilter => ({ ...NO_FILTER, q });

  it("has the words of the sound text among the words it is found by", () => {
    const words = searchableWords(clip);
    expect(words).toEqual(expect.arrayContaining(["heron", "crows", "intro", "birds"]));
    expect(words).not.toContain("31337");
    expect(words).not.toContain("1280");
    expect(words).not.toContain("distilled");
  });

  it("is found by each of them, and every word of a search must be there", () => {
    for (const word of ["heron", "crow", "wind over", "intro", "birds", "heron crows"]) expect(matches(clip, search(word)), word).toBe(true);
    expect(matches(clip, search("heron tractor"))).toBe(false);
    for (const setting of ["draft", "31337", "1280", "704", "24"]) expect(matches(clip, search(setting)), setting).toBe(false);
  });

  it("is not a mistake for a picture run: only a clip's own `sound` is read", () => {
    const picture = makeRun({ prompt: "a fox" });
    expect(searchableWords(picture)).not.toContain("crows");
  });
});

describe("where a paste goes on the Video tab (DESIGN.md §46.11)", () => {
  const png = new File(["x"], "start.png", { type: "image/png" });
  const facts = (over: Partial<PasteFacts> = {}): PasteFacts => ({ files: [png], plainText: false, target: document.body, tab: "video", modalOpen: false, ready: true, ...over });
  const field = (): HTMLTextAreaElement => document.createElement("textarea");

  it("is the clip's start picture", () => {
    expect(routePaste(facts())).toEqual({ kind: "video", files: [png] });
  });

  it("is left to the browser in a text box with text beside the picture, which is the text that was meant", () => {
    expect(routePaste(facts({ target: field(), plainText: true }))).toEqual({ kind: "ignore" });
    expect(routePaste(facts({ target: field(), plainText: false }))).toEqual({ kind: "video", files: [png] }); // a picture alone, wherever the cursor is
  });

  it("is never taken while a dialog is open, with no picture, or before the page knows what the server can do", () => {
    expect(routePaste(facts({ modalOpen: true }))).toEqual({ kind: "ignore" });
    expect(routePaste(facts({ files: [] }))).toEqual({ kind: "ignore" });
    expect(routePaste(facts({ ready: false }))).toEqual({ kind: "ignore" });
  });

  it("is not taken by the tabs that have no use for a picture, which say where pictures are used", () => {
    expect(routePaste(facts({ tab: "music" }))).toEqual({ kind: "wrong-tab" });
    expect(routePaste(facts({ tab: "speech" }))).toEqual({ kind: "wrong-tab" });
  });
});

describe("the model button on the Video tab", () => {
  const worker = (over: Partial<WorkerStatus>): WorkerStatus => ({ ...STATUS.worker, ...over });

  it("is not offered, whatever the worker holds: the program loads its models for every clip and ends, so there is nothing to load ahead of time or to unload (DESIGN.md §46.6)", () => {
    for (const state of ["unloaded", "ready", "error"] as const) expect(modelAction(worker({ state, model: "video" }), "video"), state).toBeNull();
    expect(modelAction(worker({ state: "ready", model: "image" }), "video")).toBeNull();
  });

  it("is still offered on the tabs that have a model that stays loaded", () => {
    expect(modelAction(worker({ state: "unloaded" }), "image")).toEqual({ kind: "load", model: "image" });
  });

  it("calls the model the Video model, and a job in the queue a Video job", () => {
    expect(MODEL_LABEL.video).toBe("Video model");
    expect(kindWords("video")).toBe("Video");
  });
});
