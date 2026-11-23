// The Video tab's calls to the server (DESIGN.md §46.10): making a clip, and the licence. Everything else about a clip (Keep, Delete, projects, tags, Cancel) is the same call as for
// every other run, in api.ts.

import { request } from "./api";
import type { CreateVideoBody, VideoLicence, VideoRun, WithPromptRef } from "./types";

export const videoApi = {
  /** Queue a clip. A refusal is an ApiError: 422 with the field's words, 409 `licence_not_accepted` or `video_unavailable` (with a hint), 507 `storage_full`, 429 `queue_full`. */
  createClip: (body: WithPromptRef<CreateVideoBody>) => request<VideoRun>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  /** Acknowledge the licence: the revision is the one the person saw (the server refuses another: the words may have changed). */
  acceptLicence: (revision: string) => request<VideoLicence>("/api/video/licence", { method: "POST", body: JSON.stringify({ accept: true, revision }) }),
  /** Withdraw the acknowledgement; clips already made are untouched. */
  withdrawLicence: () => request<VideoLicence>("/api/video/licence", { method: "DELETE" }),
};
