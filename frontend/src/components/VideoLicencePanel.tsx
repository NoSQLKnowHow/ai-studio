import { useId, useState } from "react";
import type { VideoLicence } from "../types";

// The licence panel (DESIGN.md §46.7, criterion 466): what the person must acknowledge before the first clip. It shows the model card's own summary, marked as a summary and not as the
// binding text, a link to the binding text, the sentence the person confirms, and a box that starts unticked and is never ticked for them. Accept is greyed until it is ticked.
// There is no way to accept except this panel: no setting and no default accepts it.

export function VideoLicencePanel({ licence, busy, problem, onAccept }: { licence: VideoLicence; busy: boolean; problem: string | null; onAccept: () => void }) {
  const [ticked, setTicked] = useState(false); // always starts unticked
  const box = useId();
  return (
    <section className="music-form video-licence" aria-labelledby={`${box}-title`}>
      <h2 id={`${box}-title`}>The licence</h2>
      {licence.outdated && <p className="run-note" data-note="licence-changed">The licence has changed since you last acknowledged it, so it is asked for again.</p>}
      <p>
        The weights of this video model are under the <strong>{licence.name}</strong>. The studio asks for your acknowledgement once, before it makes the first clip.
      </p>
      <blockquote className="video-licence-summary">
        <p className="field-hint">A summary, from the model's card (not the licence's own words):</p>
        <p>{licence.summary}</p>
      </blockquote>
      <p>
        <a href={licence.url} target="_blank" rel="noreferrer noopener">Read the binding text of the {licence.name}</a>. The studio cannot tell you whether your use is covered by it: the binding text decides.
      </p>
      <label className="choice" htmlFor={box}>
        <input id={box} type="checkbox" checked={ticked} onChange={(e) => setTicked(e.target.checked)} />
        {licence.statement}
      </label>
      <div className="prompt-row">
        <p className="prompt-help">Until it is acknowledged the form below is switched off and no clip is made.</p>
        <div className="prompt-row-end">
          <button type="button" className="button primary" data-action="accept-licence" disabled={!ticked || busy} onClick={onAccept}>{busy ? "Saving…" : "Accept"}</button>
        </div>
      </div>
      {problem && <p className="form-error" role="alert">{problem}</p>}
    </section>
  );
}
