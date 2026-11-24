import * as Dialog from "@radix-ui/react-dialog";
import { useId, useRef, useState } from "react";
import type { StartPicture, VideoPictureChoice } from "../video";
import { coverCrop } from "../video";
import { CloseIcon, PlusIcon, TrashIcon } from "./icons";

// The start picture of an Image to video clip (DESIGN.md §46.11): three ways in (from the history, by paste on this tab, and by uploading a file), and the preview of how it will be cut.
// The model wants the clip to be a shape (a multiple of 64 on each side), and a picture of another shape has to become that shape somehow, so the server cuts it from the middle
// to the clip's shape (a cover crop, never a stretch) and the preview shades the part that goes, so the person sees it before the clip is made.

interface Props {
  picture: StartPicture | null;
  clipWidth: number;
  clipHeight: number;
  choices: VideoPictureChoice[]; // the pictures of the history that can be chosen
  busy: boolean; // a file is being sent
  problem: string | null; // why a file was refused, in the server's words
  disabled?: boolean;
  onChoose: (choice: VideoPictureChoice) => void;
  onFile: (file: File) => void;
  onRemove: () => void;
}

export function VideoPicture({ picture, clipWidth, clipHeight, choices, busy, problem, disabled, onChoose, onFile, onRemove }: Props) {
  const [picking, setPicking] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const help = useId();
  const keep = picture ? coverCrop(picture.width, picture.height, clipWidth, clipHeight) : null;
  const cut = !!keep && (keep.width < 0.9999 || keep.height < 0.9999);
  return (
    <div className="field video-picture" role="group" aria-labelledby={`${help}-label`} data-video-picture>
      <span className="field-label" id={`${help}-label`}>Start picture</span>
      {picture && keep ? (
        <div className="video-picture-chosen">
          <div className="video-crop" style={{ aspectRatio: `${picture.width} / ${picture.height}` }}>
            {picture.thumbUrl && <img src={picture.thumbUrl} alt={`The start picture: ${picture.label}`} />}
            {/* the part that stays is the clear window; the box-shadow shades everything round it, and the container hides what spills out */}
            <span className="video-crop-keep" aria-hidden="true" style={{ left: `${keep.x * 100}%`, top: `${keep.y * 100}%`, width: `${keep.width * 100}%`, height: `${keep.height * 100}%` }} />
          </div>
          <p className="field-hint" data-note="crop">
            {cut
              ? `The clear part is what the clip uses: the picture is cut to ${clipWidth}×${clipHeight} from the middle (never stretched). The shaded edge is left out.`
              : `The picture is the clip's shape, ${clipWidth}×${clipHeight}: all of it is used.`}
          </p>
          {picture.hasAlpha && (
            <p className="field-hint" data-note="transparency">This picture has transparency, which a video does not: it is laid on white for the clip.</p>
          )}
          <button type="button" className="button small ghost danger" data-action="remove-picture" disabled={disabled} onClick={onRemove}><TrashIcon /> Remove the picture</button>
        </div>
      ) : (
        <p className="field-hint" id={help}>Choose a picture from your history, paste one here (Ctrl+V) or upload a file. It becomes the first frame; the clip takes its shape from it.</p>
      )}
      <div className="video-picture-actions">
        <button type="button" className="button small" data-action="pick-from-history" disabled={disabled} onClick={() => setPicking(true)}>From your history</button>
        <button type="button" className="button small" data-action="upload-picture" disabled={disabled || busy} onClick={() => file.current?.click()}><PlusIcon /> {busy ? "Sending…" : "Upload a picture"}</button>
        <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" tabIndex={-1} aria-label="Upload a start picture"
          onChange={(e) => {
            const chosen = e.target.files?.[0];
            e.target.value = ""; // so that the same file can be chosen again
            if (chosen) onFile(chosen);
          }} />
      </div>
      {problem && <p className="field-error" role="alert">{problem}</p>}

      <Dialog.Root open={picking} onOpenChange={setPicking}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="confirm video-picker" aria-describedby={undefined}>
            <Dialog.Title>Choose a start picture</Dialog.Title>
            {choices.length === 0 ? (
              <p>There are no pictures in your history yet. Make one on the Images tab, or upload a file.</p>
            ) : (
              <ul className="video-picker-grid" aria-label="Pictures from your history">
                {choices.map((choice) => (
                  <li key={choice.imageId}>
                    <button type="button" className="video-picker-item" data-image-id={choice.imageId} title={choice.label} aria-label={choice.label}
                      onClick={() => { setPicking(false); onChoose(choice); }}>
                      {choice.thumbUrl && <img src={choice.thumbUrl} alt="" loading="lazy" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="confirm-actions">
              <Dialog.Close className="button"><CloseIcon /> Close</Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
