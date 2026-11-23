import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useId, useRef, useState } from "react";
import { useReturnFocus } from "../hooks";
import type { VideoRun } from "../types";
import { videoFacts, videoTitle } from "../video";
import { CloseIcon, DownloadIcon } from "./icons";
import { ViewerAnnotationsButton, ViewerAnnotationsPanel, panelEscape } from "./RunAnnotations";

// The viewer of a clip (DESIGN.md §46.11): a larger player, the same facts, the words, the tags and notes button and panel, and Download. It works like the other viewers: it covers the
// page, nothing behind it can be reached, Esc closes the tags and notes panel first and the viewer on the second press, and focus goes back to the card's Open button.
//
// The player is the browser's own, so the arrow keys and Space are the player's (the viewer has none of its own to take them), and it starts nothing by itself: no autoplay, no loop.

export function VideoViewer({ run, onClose }: { run: VideoRun | null; onClose: () => void }) {
  const { props: returnFocus } = useReturnFocus();
  // The tags and notes panel (DESIGN.md §45.3): closed until its button opens it, and closed again for another clip
  const [notesOpen, setNotesOpen] = useState(false);
  const notesButton = useRef<HTMLButtonElement>(null);
  const notesPanel = useId();
  useEffect(() => {
    setNotesOpen(false);
  }, [run?.id]);
  const clip = run?.video ?? null;
  const inBin = !!run?.deleted_at;

  return (
    <Dialog.Root open={!!run && !!clip && !inBin} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay dark" />
        <Dialog.Content className="lightbox video-viewer" aria-describedby={undefined} {...returnFocus}
          onEscapeKeyDown={(event) => { panelEscape(event, notesOpen, () => { setNotesOpen(false); notesButton.current?.focus(); }); }}>
          {run && clip && (
            <>
              <div className="lightbox-bar">
                <Dialog.Title className="lightbox-title" data-viewer-title>{videoTitle(run)}</Dialog.Title>
                <div className="lightbox-actions">
                  <ViewerAnnotationsButton run={run} open={notesOpen} panelId={notesPanel} buttonRef={notesButton} onToggle={() => setNotesOpen(!notesOpen)} />
                  <a className="button small" href={clip.download_url} download data-action="download"><DownloadIcon /> Download MP4</a>
                  <Dialog.Close className="button small ghost icon-only" aria-label="Close"><CloseIcon /></Dialog.Close>
                </div>
              </div>
              <div className="vv-scroll">
                <div className="video-viewer-body">
                  <div className="video-frame large" style={{ aspectRatio: `${clip.width} / ${clip.height}` }}>
                    <video controls preload="auto" playsInline poster={clip.poster_url} src={clip.url} aria-label={`Play the clip: ${videoTitle(run)}`}>
                      Your browser cannot play this clip. Download it instead.
                    </video>
                  </div>
                  <p className="run-prompt">{run.prompt}</p>
                  {run.options.sound && <p className="run-meta video-sound">Sound: {run.options.sound}</p>}
                  <p className="run-meta" data-note="facts">{videoFacts(run)}</p>
                  {clip.note && <p className="run-note">{clip.note}</p>}
                  <p className="run-meta">Captions are not available: the model returns no transcript, so there is nothing true to caption with.</p>
                </div>
              </div>
              {notesOpen && <ViewerAnnotationsPanel run={run} panelId={notesPanel} />}
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
