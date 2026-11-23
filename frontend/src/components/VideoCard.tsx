import { useState } from "react";
import { binNote, canceledText, expiryText, keepLockedTitle, workingNote, type ViewScope } from "../format";
import { RunFrom } from "../promptLinks";
import type { VideoEstimateTable, VideoRun } from "../types";
import { estimateClip, stageFraction, videoFacts, videoStatusLabel, videoTitle, workingText } from "../video";
import { timeAgo } from "../format";
import { DownloadIcon, FolderIcon, PinIcon, RestoreIcon, ReuseIcon, StopIcon, TrashIcon, VideoIcon, ZoomInIcon } from "./icons";
import { ProjectMenu, projectOf, type ProjectControls } from "./ProjectMenu";
import { RunAnnotations } from "./RunAnnotations";

// The card of a clip (DESIGN.md §46.11): the player (the browser's own, `controls`, which starts nothing by itself), the facts line, the words (what happens, and what you hear as a
// second line, so that a reader who cannot hear still has the text), the tags and the note, the state while it works, and the buttons it needs.
//
// Nothing here ever plays by itself: no `autoplay`, no `loop`, no preview that moves when the pointer is over the card. A clip may have sound, and one that starts without being
// asked is hostile; a looping muted one is the same thing under another name (§46.16 item 12).

interface Props {
  run: VideoRun;
  now: number;
  estimate: VideoEstimateTable | undefined; // how long a clip takes, for the line that says how long is left
  transient: boolean; // in a filtered view only because it is working (DESIGN.md §29.3, §32)
  viewScope: ViewScope; // which filter that is, so the note says what keeps the card there
  projects: ProjectControls; // the project folders, and what the Project button does (§32)
  onReuse: () => void;
  onRetry: () => void;
  onCancel: () => void;
  onToggleKeep: () => void;
  onRestore: () => void; // take the run out of the bin (§30)
  onDelete: () => void;
  onOpen: () => void; // open the viewer
}

export function VideoCard({ run, now, estimate, transient, viewScope, projects, onReuse, onRetry, onCancel, onToggleKeep, onRestore, onDelete, onOpen }: Props) {
  const [expanded, setExpanded] = useState(false);
  const label = videoStatusLabel(run);
  const active = run.status === "queued" || run.status === "running";
  const inBin = run.deleted_at !== null; // in the bin (DESIGN.md §30): the clip is not served from there
  const filed = run.project_id !== null;
  const project = projectOf(run, projects.projects);
  const expiry = run.pinned ? null : expiryText(run.expires_at, now);
  const long = run.prompt.length > 240;
  const clip = run.video;
  const options = run.options;
  const estimated = estimate ? (estimateClip(estimate, options.seconds, options.width, options.height, options.fps)?.seconds ?? null) : null; // from the clips made here, else the table
  const fraction = run.status === "running" ? stageFraction(run.progress) : null;
  // the player has the clip's own shape, so nothing jumps when the poster loads and nothing runs off a phone's screen
  const shape = `${clip?.width ?? options.width} / ${clip?.height ?? options.height}`;

  return (
    <article className={`run-card video-card status-${run.status}`} data-run-id={run.id} aria-label={`${label}: clip, ${videoTitle(run)}`}>
      <div className="run-body">
        <div className="run-head">
          <span className="music-mark" aria-hidden="true"><VideoIcon /></span>
          <span className={`badge badge-${run.status}`}>{label}</span>
          {run.pinned && <span className="badge badge-kept"><PinIcon /> Kept</span>}
          {filed && <span className="badge badge-project" data-project-chip><FolderIcon /> {project?.name ?? "Project"}</span>}
          {inBin && <span className="badge badge-deleted"><TrashIcon /> Deleted</span>}
          <time dateTime={run.created_at} title={new Date(run.created_at).toLocaleString()}>{timeAgo(run.created_at, now)}</time>
        </div>

        <p className={`run-prompt${long && !expanded ? " clamped" : ""}`}>{run.prompt}</p>
        {long && (
          <button type="button" className="link-button" onClick={() => setExpanded((e) => !e)} aria-expanded={expanded}>{expanded ? "Show less" : "Show full text"}</button>
        )}
        {/* what you hear, as text: the clip may not say what was written (the model is told, not obliged), and a reader who cannot hear still has the words */}
        {options.sound && <p className="run-meta video-sound" data-note="sound">Sound: {options.sound}</p>}
        <p className="run-meta" data-note="facts">{videoFacts(run)}</p>
        <RunFrom run={run} />
        <RunAnnotations run={run} />

        {run.status === "queued" && (
          <p className="run-note" data-note="queued">
            Other models are unloaded first, and the video program loads its own for every clip, which takes about 45 seconds.
          </p>
        )}
        {run.status === "running" && (
          <div className="progress" role="status" data-video-progress>
            <div className={`progress-track${fraction === null ? " indeterminate" : ""}`} role={fraction === null ? undefined : "progressbar"} aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)} aria-label="How far the clip has got">
              <span style={fraction === null ? undefined : { width: `${(fraction * 100).toFixed(1)}%` }} />
            </div>
            <p>{workingText(run, estimated, now)}</p>
          </div>
        )}

        {/* the clip, once it exists: the browser's own player, with the poster shown until it is played. preload="metadata" fetches the first bytes only. Not in the bin: it is not served from there */}
        {clip && !inBin && (
          <div className="video-frame" style={{ aspectRatio: shape }}>
            <video controls preload="metadata" playsInline poster={clip.poster_url} src={clip.url} aria-label={`Play the clip: ${videoTitle(run)}`}>
              Your browser cannot play this clip. Download it instead.
            </video>
          </div>
        )}
        {clip?.note && <p className="run-note" data-note="clip">{clip.note}</p>}

        {run.status === "canceled" && <p className="run-note">{canceledText(run)}</p>}
        {expiry && <p className="run-expiry">{expiry}. Press <strong>Keep</strong> to save it.</p>}
        {transient && <p className="run-note" data-note={`working-in-${viewScope}`}>{workingNote(viewScope)}</p>}
        {inBin && <p className="run-note" data-note="in-bin">{binNote(run, now)} A clip in the bin cannot be played: restore it first.</p>}

        {run.status === "failed" && run.error && (
          <div className="run-error" role="alert">
            <p>{run.error.message}</p>
            {run.error.hint && <p className="hint">{run.error.hint}</p>}
            {!inBin && <button type="button" className="button small" data-action="retry" onClick={onRetry}><ReuseIcon /> Retry</button>}
          </div>
        )}

        {inBin ? (
          <div className="run-actions">
            <button type="button" className="button small" data-action="restore" onClick={onRestore} title="Take this clip out of the bin">
              <RestoreIcon /> Restore
            </button>
            <button type="button" className="button small ghost" data-action="reuse" onClick={onReuse} title="Load these words and settings, with the seed locked">
              <ReuseIcon /> Reuse
            </button>
            <button type="button" className="button small ghost danger" data-action="delete" onClick={onDelete} title="Delete this clip for good">
              <TrashIcon /> Delete forever
            </button>
          </div>
        ) : (
          <div className="run-actions">
            {active && (
              <button type="button" className="button small ghost danger" data-action="cancel" aria-disabled={run.canceling || undefined} onClick={() => !run.canceling && onCancel()}
                title={run.status === "queued" ? "Take this clip out of the queue" : run.canceling ? "Stopping the video program" : "Stop making this clip (nothing of it is kept)"}>
                <StopIcon /> {run.canceling ? "Stopping…" : "Cancel"}
              </button>
            )}
            {clip && (
              <button type="button" className="button small" data-action="open" onClick={onOpen} title="Watch it larger, with its facts and notes">
                <ZoomInIcon /> Open
              </button>
            )}
            {clip && (
              <a className="button small" href={clip.download_url} download data-action="download" title="The MP4 file, with its sound">
                <DownloadIcon /> Download MP4
              </a>
            )}
            <button type="button" className="button small ghost" data-action="reuse" onClick={onReuse} title="Load these words and settings, with the seed locked">
              <ReuseIcon /> Reuse
            </button>
            <button type="button" className={`button small ghost keep${run.pinned ? " active" : ""}`} data-action="keep" aria-pressed={run.pinned}
              aria-disabled={filed || undefined} data-locked={filed || undefined} onClick={filed ? undefined : onToggleKeep}
              title={filed ? keepLockedTitle(project?.name ?? null) : run.pinned ? "Kept: this clip is never deleted automatically. Click to stop keeping it." : "Keep this clip: it will never be deleted automatically"}>
              <PinIcon /> Keep
            </button>
            <ProjectMenu run={run} controls={projects} />
            <button type="button" className="button small ghost danger" data-action="delete" onClick={onDelete} disabled={run.status === "running"}
              title={run.status === "running" ? "Can't delete while it's being made" : "Delete this clip"}>
              <TrashIcon /> Delete
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
