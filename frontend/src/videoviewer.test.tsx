import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmCancel, ConfirmDelete, Lightbox } from "./components/Dialogs";
import { EmptyHistory } from "./components/FilterBar";
import { RunCard } from "./components/RunCard";
import { VideoViewer } from "./components/VideoViewer";
import { AnnotationsContext, DEFAULT_LIMITS, type AnnotationActions } from "./annotations";
import { NO_FILTER, ONLY_DELETED, ONLY_KEPT } from "./history";
import { makeImage, makeRun, makeVideoInfo, makeVideoRun } from "./testdata";
import type { VideoRun } from "./types";

// The viewer of a clip, and the parts of the shared dialogs and cards that know about clips (DESIGN.md §46.11): Cancel and Delete say what is true of a clip, an empty Video history says
// what it holds, and Animate this is offered on a finished picture. What these protect: the viewer plays nothing by itself, a clip in the bin is not shown there, and Animate this is
// offered only where the Video tab can work and only on a result of a finished run.

afterEach(cleanup);
const nothing = () => undefined;
/** What the page gives the viewer for tags and notes (DESIGN.md §45.8): the viewer shows its button only when it has it. */
const annotations: AnnotationActions = {
  limits: DEFAULT_LIMITS, setTags: async (run) => run, setNotes: async (run) => run, knownTags: async () => [], suggest: { available: false, reason: null } as AnnotationActions["suggest"],
  suggestTags: async () => [], reachability: async () => null,
};
const made = (over: Partial<VideoRun> = {}) => makeVideoRun({ started_at: "2026-11-02T13:00:00.000Z", finished_at: "2026-11-02T13:03:52.000Z", ...over });

describe("the viewer of a clip", () => {
  it("shows a larger player that plays nothing by itself, with the poster, the words, what you hear, the facts and a download", () => {
    const run = made();
    run.options = { ...run.options, sound: "snow crunching" };
    render(<VideoViewer run={run} onClose={nothing} />);
    const video = document.querySelector("video")!;
    expect(video.getAttribute("src")).toBe(run.video!.url);
    expect(video.getAttribute("poster")).toBe(run.video!.poster_url);
    expect(video.hasAttribute("controls")).toBe(true);
    for (const attribute of ["autoplay", "loop", "muted"]) expect(video.hasAttribute(attribute), attribute).toBe(false);
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Sound: snow crunching")).toBeTruthy();
    expect(document.querySelector("[data-note='facts']")!.textContent).toContain("256×128 · 24 fps · Draft · with sound · seed 77");
    expect(screen.getByRole("link", { name: /Download MP4/ }).getAttribute("href")).toBe(run.video!.download_url);
    expect(screen.getByText(/Captions are not available/)).toBeTruthy(); // said, not silently missing
  });

  it("shows what the checks found about the clip", () => {
    render(<VideoViewer run={made({ video: makeVideoInfo({ has_audio: false, note: "This clip has no sound track." }) })} onClose={nothing} />);
    expect(screen.getByText("This clip has no sound track.")).toBeTruthy();
  });

  it("closes with its Close button and with Escape, and says so to the page", () => {
    const onClose = vi.fn();
    render(<VideoViewer run={made()} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("opens its tags and notes panel from its own button, and Escape closes the panel before the viewer", () => {
    const onClose = vi.fn();
    render(<AnnotationsContext.Provider value={annotations}><VideoViewer run={made()} onClose={onClose} /></AnnotationsContext.Provider>);
    fireEvent.click(screen.getByRole("button", { name: /Tags and notes/ }));
    expect(document.querySelector("[id]#" + CSS.escape(screen.getByRole("button", { name: /Tags and notes/ }).getAttribute("aria-controls")!))).not.toBeNull();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled(); // the first Escape closes the panel
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("is not on the screen for nothing, for a clip with no file yet, or for a clip in the bin (the server does not serve it from there)", () => {
    render(<VideoViewer run={null} onClose={nothing} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    cleanup();
    render(<VideoViewer run={made({ video: null, status: "running" })} onClose={nothing} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    cleanup();
    render(<VideoViewer run={made({ deleted_at: "2026-11-02T13:04:00.000Z" })} onClose={nothing} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("Cancel and Delete, said of a clip", () => {
  it("Stop this clip? says that nothing of a clip is kept and that the program starts again from the beginning", () => {
    render(<ConfirmCancel run={made({ status: "running", video: null })} onBack={nothing} onConfirm={nothing} />);
    expect(screen.getByText("Stop this clip?")).toBeTruthy();
    expect(screen.getByText(/Nothing of a clip is kept: it is made whole or not at all/)).toBeTruthy();
    expect(screen.getByText(/loading its models takes about 45 seconds/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Stop making the clip" })).toBeTruthy();
  });

  it("Delete this clip? says its clip is removed from the Spark when it goes for good, and that the bin keeps it", () => {
    render(<ConfirmDelete run={made()} binDays={30} projectName={null} onCancel={nothing} onConfirm={nothing} />);
    expect(screen.getByText("Delete this clip?")).toBeTruthy();
    cleanup();
    render(<ConfirmDelete run={made({ deleted_at: "2026-11-02T13:04:00.000Z" })} binDays={30} projectName={null} onCancel={nothing} onConfirm={nothing} />);
    expect(screen.getByText("Delete this clip for good?")).toBeTruthy();
    expect(screen.getByText(/Its clip is removed from the Spark/)).toBeTruthy();
  });
});

describe("an empty Video history", () => {
  const empty = (filter = NO_FILTER) => render(<EmptyHistory kind="video" filter={filter} binDays={30} project={null} onShowAll={nothing} onShowAnyProject={nothing} />);

  it("says what the tab will hold and how to fill it", () => {
    empty();
    expect(screen.getByText("No clips yet")).toBeTruthy();
    expect(screen.getByText(/Say what happens above and press Make clip/)).toBeTruthy();
  });

  it("says no clips are kept or deleted, in the words of its own tab", () => {
    empty(ONLY_KEPT);
    expect(screen.getByText("No kept clips yet")).toBeTruthy();
    cleanup();
    empty(ONLY_DELETED);
    expect(screen.getByText("No deleted clips")).toBeTruthy();
  });
});

describe("Animate this (DESIGN.md §46.11)", () => {
  const card = (run = makeRun({ images: [makeImage(0)] }), extra: Record<string, unknown> = {}) => render(
    <RunCard run={run} now={Date.parse("2026-11-02T12:00:00.000Z")} workerState="ready" worker={null} canEdit making4k={new Set()} enlarging={new Set()} enlargeWaiting={new Set()}
      transient={false} viewScope="kept" upscaler={null} projects={{ projects: [], nameMax: 60, onFile: nothing, onUnfile: nothing, onCreate: async () => null }}
      onReuse={nothing} onRegenerateLarger={nothing} onMake4K={nothing} onEnlarge={nothing} onEditThis={nothing} onRetry={nothing} onCancel={nothing} onToggleKeep={nothing}
      onRestore={nothing} onDelete={nothing} onCopy={nothing} onOpenImage={nothing} {...extra} />);
  const animate = () => document.querySelector('[data-action="animate-this"]') as HTMLButtonElement | null;

  it("is on a finished picture's card when the Video tab can work, and asks the page to take the picture", () => {
    const onAnimateThis = vi.fn();
    card(undefined, { canAnimate: true, onAnimateThis });
    fireEvent.click(animate()!);
    expect(onAnimateThis).toHaveBeenCalledTimes(1);
  });

  it("is not there when the Video tab cannot work, on a run that is not finished, or on a run with several pictures", () => {
    card(undefined, { canAnimate: false, onAnimateThis: nothing });
    expect(animate()).toBeNull();
    cleanup();
    card(makeRun({ status: "running", images: [] }), { canAnimate: true, onAnimateThis: nothing });
    expect(animate()).toBeNull();
    cleanup();
    card(makeRun({ images: [makeImage(0), makeImage(1)] }), { canAnimate: true, onAnimateThis: nothing });
    expect(animate()).toBeNull(); // which picture is meant is the viewer's to say
  });

  it("is on the viewer of a picture, for the picture on the screen", () => {
    const run = makeRun({ images: [makeImage(0), makeImage(1)] });
    const onAnimateThis = vi.fn(() => true);
    render(<Lightbox run={run} index={1} notice={null} canEdit={false} canAnimate readOnly={false} making4k={new Set()} enlarging={new Set()} enlargeWaiting={new Set()} upscaler={null}
      onIndex={nothing} onRegenerateLarger={nothing} onMake4K={nothing} onEnlarge={nothing} onEditThis={() => true} onAnimateThis={onAnimateThis} onDeletePicture={nothing} onClose={nothing} />);
    fireEvent.click(animate()!);
    expect(onAnimateThis).toHaveBeenCalledTimes(1);
    expect((onAnimateThis.mock.calls[0] as unknown as [{ imageId: string }, unknown])[0].imageId).toBe(run.images[1].id); // the one on the screen, not the first
  });

  it("is not on the viewer when the tab cannot work or the viewer is read-only", () => {
    const run = makeRun({ images: [makeImage(0)] });
    const base = { run, index: 0, notice: null, canEdit: false, making4k: new Set<string>(), enlarging: new Set<string>(), enlargeWaiting: new Set<string>(), upscaler: null, onIndex: nothing,
      onRegenerateLarger: nothing, onMake4K: nothing, onEnlarge: nothing, onEditThis: () => true, onAnimateThis: () => true, onDeletePicture: nothing, onClose: nothing };
    render(<Lightbox {...base} canAnimate={false} readOnly={false} />);
    expect(animate()).toBeNull();
    cleanup();
    render(<Lightbox {...base} canAnimate readOnly />);
    expect(animate()).toBeNull();
  });
});
