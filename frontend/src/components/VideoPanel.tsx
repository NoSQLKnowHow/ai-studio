import { useCallback, useEffect, useId, useRef, useState, type MutableRefObject, type ReactNode } from "react";
import { ApiError, uploadImage } from "../api";
import type { ToastAction, ToastKind } from "../hooks";
import type { KeyValueStore } from "../options";
import type { ViewScope } from "../format";
import type { Capabilities, Status, VideoRun } from "../types";
import { videoApi } from "../videoApi";
import {
  QUALITY_LINE, SOUND_EXAMPLES, diskText, lengthNote, loadVideoForm, madeText, makeLine, pictureFromChoice, saveVideoForm, sizeForPicture, videoAnnouncement, videoFormFromRun, videoProblem,
  videoRetryRequest, buildVideoRequest,
  type AnimateRequest, type StartPicture, type VideoForm, type VideoPictureChoice,
} from "../video";
import { QueueBar } from "./Feedback";
import { NumberField } from "./NumberField";
import type { ProjectControls } from "./ProjectMenu";
import { panelId, tabId } from "./Tabs";
import { VideoCard } from "./VideoCard";
import { VideoLicencePanel } from "./VideoLicencePanel";
import { VideoPicture } from "./VideoPicture";
import { VideoIcon } from "./icons";

// The Video tab (DESIGN.md §46.11): the form that describes a clip, and the clips made so far. This file is the tab's frame and what ties its parts together. The tab says why it
// cannot work (no form), asks for the licence (a form that is switched off), or shows the form; the clips made so far are shown whichever it is, so that a clip made before the
// program went away can still be watched.
//
// What a clip is made of, and how long it takes, are the server's numbers (`capabilities.limits.video`): this file has none of its own.

interface Props {
  hidden: boolean;
  caps: Capabilities;
  status: Status | null;
  store: KeyValueStore;
  runs: VideoRun[]; // newest first
  runsReady: boolean;
  filterBar: ReactNode; // the filter bar, shared with the other tabs (DESIGN.md §29)
  loadProblem: ReactNode | null; // shown in place of "Loading…" when the filtered list could not be loaded
  empty: ReactNode; // what the list says when there is nothing to show for the filter, or that it is still looking
  isTransient: (run: VideoRun) => boolean; // in a filtered view only because it is working (§29.3, §32)
  viewScope: ViewScope;
  projects: ProjectControls;
  more: boolean; // older runs can be loaded
  loadingOlder: boolean;
  now: number;
  push: (kind: ToastKind, text: string, action?: ToastAction) => void;
  choices: VideoPictureChoice[]; // the pictures of the history a clip can start from
  animate: AnimateRequest | null; // Animate this: a new request each time (DESIGN.md §46.11)
  pasteRef: MutableRefObject<((files: File[]) => void) | null>; // the page's paste listener hands pictures to this
  onRun: (run: VideoRun) => void; // a clip was queued: the page adds it to its list
  onLicenceChanged: () => void; // the licence was accepted or withdrawn: the page reads the capabilities again
  onLoadOlder: () => void;
  onCancel: (run: VideoRun) => void;
  onToggleKeep: (run: VideoRun) => void;
  onRestore: (run: VideoRun) => void;
  onDelete: (run: VideoRun) => void;
  onOpen: (run: VideoRun) => void;
}

export function VideoPanel({
  hidden, caps, status, store, runs, runsReady, filterBar, loadProblem, empty, isTransient, viewScope, projects, more, loadingOlder, now, push, choices, animate, pasteRef,
  onRun, onLicenceChanged, onLoadOlder, onCancel, onToggleKeep, onRestore, onDelete, onOpen,
}: Props) {
  const ids = useId();
  const root = useRef<HTMLDivElement>(null);
  const video = caps.video;
  const limits = caps.limits.video;
  const [form, setForm] = useState<VideoForm>(() => loadVideoForm(caps, store));
  const [picture, setPicture] = useState<StartPicture | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [pictureProblem, setPictureProblem] = useState<string | null>(null);
  const [sending, setSending] = useState(false); // a file is being uploaded
  const [submitting, setSubmitting] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [licenceProblem, setLicenceProblem] = useState<string | null>(null);
  const [checking, setChecking] = useState(false); // Check again has been pressed and the server has not yet said it started
  const [checkProblem, setCheckProblem] = useState<string | null>(null);
  const [said, setSaid] = useState(""); // the polite live region: the state of a clip, said once

  useEffect(() => saveVideoForm(form, store), [form, store]);

  // Only one clip plays at a time: starting one stops the others (the "play" event does not bubble, so it is listened to at the top). Nothing ever starts by itself.
  useEffect(() => {
    const onPlay = (e: Event) => {
      const target = e.target;
      if (!(target instanceof HTMLVideoElement) || !root.current?.contains(target)) return;
      root.current.querySelectorAll("video").forEach((other) => {
        if (other !== target && !other.paused) other.pause();
      });
    };
    document.addEventListener("play", onPlay, true);
    return () => document.removeEventListener("play", onPlay, true);
  }, []);
  // and no sound from a tab that is not on the screen
  useEffect(() => {
    if (hidden) root.current?.querySelectorAll("video").forEach((clip) => clip.pause());
  }, [hidden]);

  // The state of each clip is said once in the live region, as it changes (DESIGN.md §46.11): the first look at the list says nothing, so a page that opens does not read out its history.
  const seen = useRef<Map<string, string> | null>(null);
  useEffect(() => {
    const now = new Map(runs.map((run) => [run.id, run.status]));
    if (seen.current !== null) {
      const changed = runs.find((run) => seen.current?.get(run.id) !== run.status);
      if (changed) setSaid(videoAnnouncement(changed));
    }
    seen.current = now;
  }, [runs]);

  const update = useCallback((patch: Partial<VideoForm>) => {
    setForm((current) => ({ ...current, ...patch }));
    setProblem(null);
  }, []);

  // A start picture is chosen: the clip takes its shape from it (the size nearest to the picture's at about the default pixels), and the form is in Image to video.
  const takePicture = useCallback((next: StartPicture) => {
    setPicture(next);
    setPictureProblem(null);
    setForm((current) => ({ ...current, mode: "image", ...sizeForPicture(next.width, next.height, limits.size) }));
    setProblem(null);
  }, [limits.size]);

  // A file (chosen, or pasted): sent to the server, which checks it and keeps it for a while until a clip claims it (the same upload an edit's pictures use)
  const sendFile = useCallback(async (file: File) => {
    setSending(true);
    setPictureProblem(null);
    try {
      const sent = await uploadImage(file).promise;
      takePicture({ ref: { upload_id: sent.upload_id }, thumbUrl: sent.thumb_url ?? sent.url, width: sent.width, height: sent.height, label: file.name || "a pasted picture", hasAlpha: sent.has_alpha });
    } catch (error) {
      setPictureProblem(error instanceof ApiError ? error.message : "The picture could not be sent.");
    } finally {
      setSending(false);
    }
  }, [takePicture]);
  // the page's paste listener (Ctrl+V on this tab, DESIGN.md §46.11): the first picture is the start picture
  useEffect(() => {
    pasteRef.current = (files) => { if (files[0]) void sendFile(files[0]); };
    return () => { pasteRef.current = null; };
  }, [pasteRef, sendFile]);

  // Animate this: a picture's own Edit-this-like button asks for it. Image to video with that picture, the words of the picture's run, and an Undo that puts the form back.
  const lastAnimate = useRef(animate?.seq ?? 0);
  useEffect(() => {
    if (!animate || animate.seq === lastAnimate.current) return;
    lastAnimate.current = animate.seq;
    const before = { form, picture };
    takePicture(animate.picture);
    if (animate.prompt) setForm((current) => ({ ...current, prompt: animate.prompt }));
    push("info", "Image to video: the picture is the first frame, and the words of the picture are in What happens. Change them, then press Make clip.",
      { label: "Undo", run: () => { setForm(before.form); setPicture(before.picture); setProblem(null); } });
  }, [animate?.seq]);

  const blocked = videoProblem(form, caps, picture !== null);
  const usable = video.available && video.licence.accepted;
  const submit = async () => {
    if (submitting || !usable) return;
    if (blocked) {
      setProblem(blocked);
      return;
    }
    setSubmitting(true);
    setProblem(null);
    try {
      const queued = await videoApi.createClip(buildVideoRequest(form, caps, picture?.ref ?? null));
      onRun(queued);
      // An upload is used up by the clip that claimed it, and the clip keeps its own copy: the form points at that copy from now on (as an edit's tray does), so that the same
      // picture can start the next clip too
      if (picture && "upload_id" in picture.ref && queued.inputs[0]) setPicture({ ...picture, ref: { image_id: queued.inputs[0].id } });
    } catch (error) {
      const err = error as ApiError;
      if (err.status === 422 || err.status === 409 || err.status === 507) {
        setProblem(err.hint ? `${err.message} ${err.hint}` : err.message);
        if (err.code === "licence_not_accepted" || err.code === "video_unavailable") onLicenceChanged(); // what the page believed is out of date: read it again
      } else push("error", err.status === 429 ? err.message : `Couldn't start the clip: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const acceptLicence = async () => {
    setAccepting(true);
    setLicenceProblem(null);
    try {
      await videoApi.acceptLicence(video.licence.revision);
      onLicenceChanged();
    } catch (error) {
      setLicenceProblem((error as ApiError).message);
    } finally {
      setAccepting(false);
    }
  };
  // Check again (DESIGN.md §46.8): the server runs the start-up check again and tells every page when it is done (the capabilities change); a refusal is shown in its own words
  const checkAgain = async () => {
    setChecking(true);
    setCheckProblem(null);
    try {
      await videoApi.checkAgain();
      onLicenceChanged();
    } catch (error) {
      const err = error as ApiError;
      setCheckProblem(err.hint ? `${err.message} ${err.hint}` : err.message);
    } finally {
      setChecking(false);
    }
  };
  const withdrawLicence = async () => {
    try {
      await videoApi.withdrawLicence();
      onLicenceChanged();
    } catch (error) {
      push("error", `Couldn't withdraw it: ${(error as ApiError).message}`);
    }
  };

  const reuse = (run: VideoRun) => {
    setForm((current) => videoFormFromRun(run, caps, current));
    const start = run.inputs[0];
    setPicture(run.options.mode === "image" && start ? { ref: { image_id: start.id }, thumbUrl: start.thumb_url ?? start.url, width: start.width, height: start.height, label: run.prompt, hasAlpha: start.has_alpha } : null);
    setProblem(null);
    push("info", `Loaded the words and settings. Seed locked to ${run.options.seed}.`);
    window.scrollTo({ top: 0, behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  const retry = async (run: VideoRun) => {
    try {
      onRun(await videoApi.createClip(videoRetryRequest(run)));
    } catch (error) {
      push("error", `Couldn't retry: ${(error as Error).message}`);
    }
  };

  const idOf = (name: string) => `${ids}-${name}`;
  const note = lengthNote(form.seconds, limits);
  const presetId = limits.size.presets.find((preset) => preset.width === form.width && preset.height === form.height)?.id ?? "custom";
  const chosenShape = `${form.width}×${form.height}`;

  const body: ReactNode = (() => {
    if (!video.available) {
      const checkingNow = video.state === "checking";
      return (
        <section className="music-form music-unavailable" aria-label="Video is not available">
          <h2><VideoIcon /> {checkingNow ? "Checking the video program…" : "Video isn't available on this server"}</h2>
          {checkingNow ? (
            <p role="status">The studio is checking whether the video program can run here. This tab fills in by itself when it knows.</p>
          ) : (
            <>
              <p role="status" data-video-reason>{video.reason ?? "The video program can't run on this server as it is set up."}</p>
              {video.hint && <p className="hint">{video.hint}</p>}
            </>
          )}
          {!checkingNow && (
            <div className="prompt-row">
              <p className="prompt-help">Put it right on the Spark (a folder, a permission, a program), then look again: the container need not be restarted for that. A line changed in .env needs docker compose up -d.</p>
              <div className="prompt-row-end">
                <button type="button" className="button primary" data-action="check-again" disabled={checking} onClick={() => void checkAgain()}>{checking ? "Checking…" : "Check again"}</button>
              </div>
            </div>
          )}
          {checkProblem && <p className="form-error" role="alert" data-check-problem>{checkProblem}</p>}
          <p className="hint">Images, music and the other tabs work as usual.</p>
        </section>
      );
    }
    return (
      <>
        {!video.licence.accepted && <VideoLicencePanel licence={video.licence} busy={accepting} problem={licenceProblem} onAccept={() => void acceptLicence()} />}
        <section className="music-form video-form" aria-label="New clip" data-video-form
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              void submit();
            }
          }}>
          <fieldset className="video-fieldset" disabled={!usable}>
            <div className="music-title">
              <h2><VideoIcon /> New clip</h2>
              <p className="hint">Describe what happens, and what you hear. {video.engine.title} makes the picture and the sound together, as one MP4 file.</p>
              {!video.licence.accepted && <p className="hint" data-note="form-off">The form is switched off until the licence above is acknowledged.</p>}
            </div>

            <div className="field">
              <span className="field-label" id={idOf("mode")}>What to start from</span>
              <div className="segmented" role="radiogroup" aria-labelledby={idOf("mode")}>
                <button type="button" role="radio" aria-checked={form.mode === "text"} data-mode="text" onClick={() => update({ mode: "text" })}>Text to video</button>
                <button type="button" role="radio" aria-checked={form.mode === "image"} data-mode="image" onClick={() => update({ mode: "image" })}>Image to video</button>
              </div>
            </div>

            {form.mode === "image" && (
              <VideoPicture picture={picture} clipWidth={form.width} clipHeight={form.height} choices={choices} busy={sending} problem={pictureProblem} disabled={!usable}
                onChoose={(choice) => takePicture(pictureFromChoice(choice))} onFile={(file) => void sendFile(file)} onRemove={() => { setPicture(null); setProblem(null); }} />
            )}

            <div className="field">
              <label htmlFor={idOf("prompt")}>What happens</label>
              <textarea id={idOf("prompt")} className="prompt-input" rows={4} value={form.prompt} maxLength={limits.prompt_chars} placeholder="A red fox trots through fresh snow at dawn; the camera follows it."
                aria-describedby={`${idOf("prompt")}-hint`} onChange={(e) => update({ prompt: e.target.value })} />
              <p id={`${idOf("prompt")}-hint`} className="field-hint">
                The scene, the action and the camera, in your own words.{form.prompt.length > limits.prompt_chars * 0.8 ? ` ${form.prompt.length} / ${limits.prompt_chars}` : ""}
              </p>
            </div>

            <div className="field">
              <label htmlFor={idOf("sound")}>What you hear</label>
              <textarea id={idOf("sound")} className="prompt-input" rows={2} value={form.sound} maxLength={limits.sound_chars} placeholder="Snow crunching underfoot, a soft wind, far-off birds."
                aria-describedby={`${idOf("sound")}-hint`} onChange={(e) => update({ sound: e.target.value })} />
              <div className="chips" role="group" aria-label="Examples of what you hear">
                {SOUND_EXAMPLES.map((example) => (
                  <button key={example} type="button" className="chip" onClick={() => update({ sound: form.sound.trim() ? `${form.sound.trim()}, ${example}` : example })}>{example}</button>
                ))}
              </div>
              <p id={`${idOf("sound")}-hint`} className="field-hint">Dialogue, ambience, music. The model makes the sound with the picture and is told these words; it is not bound to follow them. The examples are only suggestions: pressing one puts its words in the box.</p>
            </div>

            <div className="field">
              <label className="choice">
                <input type="checkbox" checked={form.keepSound} onChange={(e) => update({ keepSound: e.target.checked })} />
                Keep the sound
              </label>
              <p className="field-hint">Turning it off only takes the sound out of the saved file. The model still makes it, so the clip is no cheaper to make.</p>
            </div>

            <div className="music-settings">
              <div className="field">
                <span className="field-label" id={idOf("length")}>Length</span>
                <div className="chips" role="group" aria-labelledby={idOf("length")}>
                  {limits.seconds.choices.map((seconds) => (
                    <button key={seconds} type="button" className="chip" aria-pressed={form.seconds === seconds} onClick={() => update({ seconds })}>{seconds} s</button>
                  ))}
                </div>
                <NumberField label="Seconds" value={form.seconds} min={limits.seconds.min} max={limits.seconds.max} hint={madeText(form.seconds, form.fps)} onChange={(seconds) => update({ seconds })} />
                {note && <p className="field-hint" data-note="long">{note}</p>}
              </div>
              <div className="field">
                <span className="field-label" id={idOf("size")}>Size</span>
                <div className="chips" role="group" aria-labelledby={idOf("size")}>
                  {limits.size.presets.map((preset) => (
                    <button key={preset.id} type="button" className="chip" aria-pressed={presetId === preset.id} onClick={() => update({ width: preset.width, height: preset.height })}>{preset.label}</button>
                  ))}
                </div>
                <p className="field-hint">Each side is a multiple of {limits.size.multiple}. {chosenShape}.</p>
              </div>
            </div>

            <details className="music-advanced">
              <summary>Custom size and seed{form.seedLocked ? ` · seed locked to ${form.seed}` : ""}</summary>
              <div className="music-advanced-body">
                <NumberField label="Width" value={form.width} min={limits.size.min} max={limits.size.max} step={limits.size.multiple} hint={`A multiple of ${limits.size.multiple}.`} onChange={(width) => update({ width })} />
                <NumberField label="Height" value={form.height} min={limits.size.min} max={limits.size.max} step={limits.size.multiple} hint={`A multiple of ${limits.size.multiple}.`} onChange={(height) => update({ height })} />
                <div className="field">
                  <label className="choice">
                    <input type="checkbox" checked={form.seedLocked} onChange={(e) => update({ seedLocked: e.target.checked })} />
                    Lock seed
                  </label>
                  <NumberField label="Seed" value={form.seed} min={0} max={caps.limits.seed.max} disabled={!form.seedLocked}
                    hint={form.seedLocked ? "The same words, size, length and seed make the same clip." : "A new random seed for every clip. Lock it to repeat one."} onChange={(seed) => update({ seed })} />
                </div>
              </div>
            </details>

            <p className="field-hint" data-note="quality">{QUALITY_LINE}</p>
            <p className="video-line" data-note="make-line" role="status">{makeLine(form, limits)}</p>
            {!video.memory.ok && video.memory.message && <p className="music-note" role="status" data-note="memory">{video.memory.message}</p>}

            <div className="prompt-row">
              <p className="prompt-help">Ctrl + Enter (⌘ + Enter on a Mac) makes the clip.</p>
              <div className="prompt-row-end">
                <button type="button" className="button primary" data-action="make-clip" onClick={() => void submit()} disabled={!usable || submitting || form.prompt.trim() === ""}>
                  <VideoIcon />
                  {submitting ? "Sending…" : "Make clip"}
                </button>
              </div>
            </div>
            {problem && <p className="form-error" role="alert" data-video-problem>{problem}</p>}
            <p className="music-licence">
              Made with {video.engine.title}, under the {video.licence.name}. Every file says so in its file information.
              {video.licence.accepted && (
                <> <button type="button" className="link-button" data-action="withdraw-licence" onClick={() => void withdrawLicence()}>Withdraw my acknowledgement of the licence</button></>
              )}
              {" "}<button type="button" className="link-button" data-action="check-again" disabled={checking} onClick={() => void checkAgain()}>Check the video program again</button>
            </p>
            {checkProblem && <p className="form-error" role="alert" data-check-problem>{checkProblem}</p>}
            {video.clips_bytes > 0 && <p className="field-hint" data-note="disk">Your clips take {diskText(video.clips_bytes)} on the Spark's disk.</p>}
          </fieldset>
        </section>
      </>
    );
  })();

  return (
    <div className="tab-panel video-panel" role="tabpanel" id={panelId("video")} aria-labelledby={tabId("video")} hidden={hidden} ref={root}>
      {body}
      <p className="sr-only" role="status" aria-live="polite" data-video-live>{said}</p>
      {video.available && <QueueBar status={status} />}
      {filterBar}
      <section className="timeline" aria-label="Your clips">
        {!runsReady ? (
          loadProblem ?? <p className="loading" role="status">Loading your clips…</p>
        ) : runs.length === 0 ? (
          empty
        ) : (
          runs.map((run) => (
            <VideoCard key={run.id} run={run} now={now} estimate={limits.estimate} transient={isTransient(run)} viewScope={viewScope} projects={projects}
              onReuse={() => reuse(run)} onRetry={() => void retry(run)} onCancel={() => onCancel(run)} onToggleKeep={() => onToggleKeep(run)} onRestore={() => onRestore(run)}
              onDelete={() => onDelete(run)} onOpen={() => onOpen(run)} />
          ))
        )}
        {more && (
          <button type="button" className="button load-more" onClick={onLoadOlder} disabled={loadingOlder}>{loadingOlder ? "Loading…" : "Load older runs"}</button>
        )}
      </section>
    </div>
  );
}
