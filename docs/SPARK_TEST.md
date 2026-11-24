# AI Studio on the DGX Spark: first run and release checks

This is the checklist for what only your Spark can show: building the image, running the real models on its
GPU, and judging by eye and ear what comes out. The automated tests run against a fake pipeline with no GPU
(the README's Status table says so), so everything here is yours to try, on the Spark.

The file is cumulative. It began as the first-run checklist and gained one section for each release since,
and **a section number never changes**: the README, `docs/DESIGN.md`, `.env.example` and the code cite sections by
number ("section 34 (f)"), and so does the numbered list at the end. A new section is added at the end of the
numbered ones, whatever release it belongs to.

**How to use it.** **Part 1** (sections 1 to 13) is the first run: clone, build, start, make a first image, measure
the memory. Do it once, in order. **Part 2** (sections 14 to 39) is one section per release: after an update, do the
sections for the releases you have not checked yet. Run everything on the Spark, as your normal user (not `sudo`,
not root), in a terminal or over SSH. For where the project itself stands (what is built, what is only specified),
read "Status at a glance" at the top of `docs/DESIGN.md`.

> Never paste tokens, passwords or SSH keys into a chat. Put `HF_TOKEN` in `.env` on the Spark if
> it's ever needed, and nowhere else.

### Status of each section

The status column is only what you told me: on 2026-11-17 sections 1 to 36 you had tried; section 37 you have run in part (2026-11-19 to
11-23, below), and sections 38 and 39 have not been run. It records no results; the numbers you measure are the ones the "What to send back" list at the end asks for.

| § | Section | Release | What it checks | Status |
|---|---|---|---|---|
| 1 | Get the code | 1.0 | cloning the repository | Tried by you (your word, 2026-11-17) |
| 2 | Check Docker and the GPU | 1.0 | Docker without `sudo`; the GB10 is visible to containers | Tried by you (your word, 2026-11-17) |
| 3 | Note the memory picture before anything loads | 1.0 | free memory, and what else is running | Tried by you (your word, 2026-11-17) |
| 4 | Prepare the settings and folders | 1.0 | `.env`; who owns `data/` and the model cache | Tried by you (your word, 2026-11-17) |
| 5 | Build the image | 1.0 | the build and its `check_image` self-check | Tried by you (your word, 2026-11-17) |
| 6 | Start it | 1.0 | a healthy container; the start-up log | Tried by you (your word, 2026-11-17) |
| 7 | Open the page | 1.0 | the page loads; the model pill names the GB10 | Tried by you (your word, 2026-11-17) |
| 8 | First image: small and quick | 1.0 | first model download and load; one image | Tried by you (your word, 2026-11-17) |
| 9 | Measure the memory footprint | 1.0 | what the loaded model costs; sets `STUDIO_MIN_FREE_GB` | Tried by you (your word, 2026-11-17) |
| 10 | The everyday features | 1.0 | batch, Reuse, transparency, queue, phone | Tried by you (your word, 2026-11-17) |
| 11 | Idle unload gives the memory back | 1.0 | memory returns after the idle timeout | Tried by you (your word, 2026-11-17) |
| 12 | The memory check fails fast | 1.0 | too little free memory fails at once, with a way out | Tried by you (your word, 2026-11-17) |
| 13 | History survives the container | 1.0 | history after `down` and `up` | Tried by you (your word, 2026-11-17) |
| 14 | Cancel, Keep and automatic clean-up | 1.1 | Cancel, Keep, expiry | Tried by you (your word, 2026-11-17) |
| 15 | Editing with several images, through the API | 1.2 | the first real-model edits, from a terminal | Tried by you (your word, 2026-11-17) |
| 16 | Scale, Draft and thumbnails | 1.3 | scale picker, Draft, thumbnails | Tried by you (your word, 2026-11-17) |
| 17 | Regenerate larger | 1.4 and 1.5 | Regenerate larger, on the card and in the viewer | Tried by you (your word, 2026-11-17) |
| 18 | Editing on the page, and the Spark test for edits | 1.6 | edit times and memory; "image N"; masks | Tried by you (your word, 2026-11-17) |
| 19 | Load model and Unload model | 1.7 | the header buttons; load time; memory given back | Tried by you (your word, 2026-11-17) |
| 20 | Music: the model, from a terminal and through the API | 1.8 and 1.9 | the real music model; its speed and memory; the Music tab | Tried by you (your word, 2026-11-17) |
| 21 | Make 4K, and the upscaler probe | 1.10 | Make 4K; whether an upscaler runs on the GPU | Tried by you (your word, 2026-11-17) |
| 22 | Enlarge: the same picture, bigger and sharper | 1.11 | Enlarge with a model file; waiting for the GPU | Tried by you (your word, 2026-11-17) |
| 23 | The Kept view, and Enlarge waiting its turn | 1.12 | the Kept filter | Tried by you (your word, 2026-11-17) |
| 24 | The bin | 1.13 | Deleted, Restore, Empty bin; database schema 4 | Tried by you (your word, 2026-11-17) |
| 25 | Project folders | 1.14 | projects; database schema 5 | Tried by you (your word, 2026-11-17) |
| 26 | Deleting one picture | 1.15 | one picture to the bin; database schema 6 | Tried by you (your word, 2026-11-17) |
| 27 | The default size, 16:9 | 1.16 | the new default; time and memory against the old square | Tried by you (your word, 2026-11-17) |
| 28 | Vector | 1.17 | the Vector tab on real pictures; the laser software; schema 7 | Tried by you (your word, 2026-11-17) |
| 29 | Vector versions, the stack view, and pictures by paste | 1.18 | versions, depth stack, paste; eight-picture edits; schema 8 | Tried by you (your word, 2026-11-17) |
| 30 | The Prompt builder, with your Ollama | 1.19 | the builder with your Ollama; schema 9 | Tried by you (your word, 2026-11-17) |
| 31 | The Speech tab: four voice engines, on your Spark | 1.20 | the four real voice engines; schema 10 | Tried by you (your word, 2026-11-17) |
| 32 | Load progress: watch a real download | 1.21 | the download and load progress shown | Tried by you (your word, 2026-11-17) |
| 33 | Reorder the queue | 1.22 | dragging queued jobs; a thumb on a phone | Tried by you (your word, 2026-11-17) |
| 34 | More like this, compare, and the experiment for variations of a picture | 1.24 | More like this; compare; the variations experiment; schema 11 | Tried by you (your word, 2026-11-17) |
| 35 | Audiobook polish for Speech | 1.25 | respellings, several voices, chapter marks, the M4B; schema 12 | Tried by you (your word, 2026-11-17) |
| 36 | Search and tags across history | 1.26 | search, filters, Suggest with your Ollama; schema 13 | Tried by you (your word, 2026-11-17) |
| 37 | LTX-2.5 on your Spark: the experiment before the Video tab | 1.27 | whether LTX-2.5 runs here, how long a clip can be | Partly run by you (2026-11-19 to 11-20): a to d done, e first-frame run made and judged "it looks fine" (2026-11-23), f to i and the seed/chunked script not yet run |
| 38 | Vector quality: thin lines are kept and widened | 1.23 | the Vector clean-up keeps thin lines | Not yet run (added 2026-11-17) |
| 39 | The Video tab, through the studio, on your Spark | 1.27 | the two settings; the `Video:` check and the tab's words at each step; a 5 s clip, image to video, Cancel, the estimate, memory next to the other models, backup, the HD and Scope sizes (n) | Not yet run (added 2026-11-24) |

**Keeping this file current.** When a release adds a section, give it the next unused number (do not insert it in
the middle and do not renumber), add a row for it to the table above with the release and "Not yet run", and add its
item at the end of "What to send back". When you tell me you have tried a section, change that row's status to
"Tried by you (your word, <date>)" and nothing stronger; numbers you send back are not recorded in the status column.

---

# Part 1: First run (sections 1 to 13)

**How to read a section.** Each step says what "Good" looks like. Where it says "note" or "write down", write the
number down: it goes into the report at the end ("What to send back"). Where a step says "see Troubleshooting", the
table is [at the end of the file](#troubleshooting).

**Settings you may want.** Everything is set in `.env` (copied from `.env.example` in step 4), and `docker compose up -d`
applies a change. The defaults below are the ones in `.env.example`. The last column says which step or section
needs the setting. The rest of the file's settings are limits and file locations that have good defaults, and each is explained
next to its line in `.env.example`. Vector has no setting in `.env`: its options are on the form, for each run.

| Setting | Default | What it does | Used in |
|---|---|---|---|
| `STUDIO_UID`, `STUDIO_GID` | 1000, 1000 | The user the container runs as. Set them to `id -u` and `id -g`, so that `./data` and the model cache stay yours | step 4 |
| `STUDIO_BIND` | `0.0.0.0` | The address the page listens on. `127.0.0.1` keeps it off your LAN (an SSH tunnel or NVIDIA Sync only) | steps 4 and 7 |
| `STUDIO_PORT` | `8081` | The port on the Spark that you open in the browser; the container's own `8080` never changes. A `.env` from before 1.20 may still say `8080`: change it | step 7, Troubleshooting |
| `STUDIO_ALLOWED_HOSTS` | empty (accept any) | A guard against DNS-rebinding: the names or addresses you browse to, comma-separated (`spark-1a2b.local,192.168.1.20`); `localhost` always works. A request for any other name is refused | step 4 |
| `HF_CACHE_DIR` | not set (`~/.cache/huggingface`) | The folder on the Spark that holds the Hugging Face cache; the container sees it as `/models` | steps 4 and 8 |
| `HF_TOKEN` | empty | Only if a model repository is gated or private | Troubleshooting |
| `NGC_TAG` | `25.10-py3` | Which NVIDIA PyTorch release the image is built on; change it only if the self-check or the GPU says to | step 5, Troubleshooting |
| `STUDIO_MIN_FREE_GB` | 40 | Refuse to load the image model unless this many GB are free (`MemAvailable`). 40 is an estimate: replace it with your number. 0 = no check | steps 9 and 12 |
| `STUDIO_IDLE_TIMEOUT_MIN` | 30 | Unload the model after this many idle minutes. 0 = right away | steps 11 and 19 |
| `STUDIO_MUSIC_MIN_FREE_GB` | 40 | The same check for the music model (it needs about 24 GB; 40 is an estimate) | section 20 |
| `STUDIO_SPEECH_MIN_FREE_GB` | empty (each engine's own estimate) | The same check for a speech engine | section 31 |
| `STUDIO_LOCAL_FILES_ONLY` | `auto` | `auto` uses the local cache and touches the network only for files that are missing; `true` never contacts Hugging Face; `false` asks the hub on every load | sections 20 and 31 |
| `STUDIO_CPU_OFFLOAD` | `false` | Keep parts of the image model in CPU memory between uses: slower, and rarely useful on the Spark | none |
| `STUDIO_RETENTION_DAYS` | 30 | Finished runs you did not Keep move to the bin after this many days. 0 = never | section 14 |
| `STUDIO_BIN_DAYS` | 30 | How long a deleted run stays in **Deleted** before it goes for good. 0 = no bin: Delete is for good at once | sections 14 and 24 |
| `STUDIO_QUEUE_CAP` | 10 | How many jobs may wait; one more is refused with "The queue is full" | section 33 |
| `STUDIO_OLLAMA_URL` | empty | Where your Ollama is, for the Prompt builder (and Suggest in section 36). For an Ollama on the Spark itself: `http://host.docker.internal:11434`. Empty: the tab says how to set it up. The address stays in `.env` and is left out of the page and the logs | sections 30 and 36 |
| `STUDIO_OLLAMA_MODEL` | empty | The Ollama model, as `ollama list` names it, with its tag | sections 30 and 36 |
| `STUDIO_OLLAMA_VISION_MODEL` | empty | Only if that model cannot look at pictures: another one that can, for messages with a picture | section 30 (h) |
| `STUDIO_OLLAMA_KEEP_ALIVE`, `STUDIO_OLLAMA_NUM_CTX`, `STUDIO_OLLAMA_THINK`, `STUDIO_OLLAMA_TIMEOUT_S`, `STUDIO_OLLAMA_MAX_REPLY_S`, `STUDIO_BUILDER_AT_ONCE` | `5m`, 32768, `on`, 120, 900, 1 | How long Ollama keeps its model loaded, the conversation window, whether it thinks first, how long a silence or a reply may last, and how many chats may wait on it | section 30 (j) |
| `STUDIO_MAX_UPLOAD_MB` | 20 | The largest single picture you may upload, in MB (a picture may also have at most 16 megapixels): the photos of editing and of Upscale a picture | sections 15, 18 and 21 (c3) |
| `STUDIO_MUSIC_MAX_SECONDS` | 300 | The longest track you may ask for (10 to 360) | section 20 (d) |
| `STUDIO_SPEECH_ENGINES` | empty (all four) | Which voice engines to offer, as a list of ids: `qwen3-tts`, `voxtral`, `kokoro`, `piper` | section 31 |
| `SPEECH_VOXTRAL` | 0 | Set to 1 for a build that includes Voxtral's server (large, optional): `SPEECH_VOXTRAL=1 docker compose build` | section 31 |
| `STUDIO_SPEECH_GPU_FRACTION` | 0.2 | The share of the GPU's memory that Voxtral's server may take (0.05 to 0.9) | section 31 (j) |
| `STUDIO_VIDEO_LTX_DIR` | empty | **Video (1.27).** Your `LTX-2` clone on the Spark, with its `.venv`: `/home/YOU/ltx-experiment/LTX-2` (`YOU` is your user name). Shared into the container read-only at the same path. Empty: the Video tab says nothing is set up | section 39 (a) |
| `STUDIO_VIDEO_MODELS_DIR` | empty | The folder that holds `diffusion_models`, `text_encoders`, `vae`, `latent_upscale_models` and `model_patches`: `/home/YOU/ltx-experiment/models`. Shared read-only; nothing is downloaded | section 39 (a) |
| `STUDIO_VIDEO_MIN_FREE_GB` | 60 | Refuse a clip unless this many GB are free (the measured peak for 30 s is 55.6 GB, and 4 is added). 0 = no check | section 39 (i) |
| `STUDIO_VIDEO_MAX_SECONDS` | 30 | The longest clip the form offers | section 39 (e) |

`compose.yaml` passes each of these to the container by name, except the ones compose itself uses (`STUDIO_UID`, `STUDIO_GID`,
`STUDIO_BIND`, `STUDIO_PORT`, `HF_CACHE_DIR`, `NGC_TAG`, `SPEECH_VOXTRAL`), which shape how the container is built, run or published.
Sections 14 to 39 name a few more where they use them (`STUDIO_MAX_INPUT_IMAGES`, `STUDIO_EDIT_WARN_UNITS`, `STUDIO_DRAFT_SIZE`,
`STUDIO_VARIATIONS_FROM_PICTURE`, `STUDIO_TAG_SUGGESTIONS` and others).

---

## 1. Get the code

The repository is private, so the Spark needs your GitHub credentials (an SSH key or a personal
access token, set up the way you normally do).

```bash
git clone https://github.com/NoSQLKnowHow/ai-image-studio.git
cd ai-image-studio                     # main has everything; no branch to switch to
```

The app is called AI Studio; the repository and its folder are still named `ai-image-studio`.

## 2. Check Docker and the GPU

```bash
docker ps                              # must work without sudo
docker run --rm --runtime=nvidia --gpus=all nvcr.io/nvidia/cuda:13.0.1-base-ubuntu24.04 nvidia-smi
```

Good: `docker ps` lists containers (perhaps those of an LLM server you run), and `nvidia-smi` prints a table naming the
**GB10**. Memory columns may say "Not Supported"; that's normal on the Spark.

- `permission denied ... docker.sock`: add yourself to the docker group, then log out and in:
  `sudo usermod -aG docker $USER`
- `unknown or invalid runtime name: nvidia`: see [Troubleshooting](#troubleshooting).

## 3. Note the memory picture before anything loads

```bash
grep MemAvailable /proc/meminfo
docker ps --format '{{.Names}}\t{{.Image}}'
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}'
```

Note: `MemAvailable` (in kB; divide by 1048576 for GB), and which containers run, especially a
vLLM one (or an Ollama with a model loaded: `ollama ps`), and how much it uses: the studio shares the Spark's memory with it.

## 4. Prepare the settings and folders

```bash
cp .env.example .env
sed -i "s/^STUDIO_UID=.*/STUDIO_UID=$(id -u)/; s/^STUDIO_GID=.*/STUDIO_GID=$(id -g)/" .env
mkdir -p data ~/.cache/huggingface
ls -ld data ~/.cache/huggingface ~/.cache/huggingface/hub 2>/dev/null
```

Good: every folder listed is owned by **you**. If one shows `root` (a container that ran as root
created it), take it back: `sudo chown -R $(id -u):$(id -g) ~/.cache/huggingface` (and/or `data`).
Root-run containers such as vLLM can still use it afterwards.

Optional now, or later in `.env`: `STUDIO_ALLOWED_HOSTS` (the name or address you browse to) and
`STUDIO_BIND=127.0.0.1` if the page should not be reachable from the LAN. The table of settings at the top of Part 1 lists the others you may want.

## 5. Build the image

```bash
docker compose build --progress=plain 2>&1 | tee build.log
grep check_image build.log
```

The first build downloads NVIDIA's PyTorch image (the README gives it as an 8.3 GiB download, compressed, and it unpacks to
considerably more), so give it time. It also builds the web page and installs the Python packages and the optional Vector,
music and speech libraries, one Dockerfile step for each.

The last step of the build runs `docker/check_image.py`. It prints one line for each thing it checked, every one starting
`check_image:`, and the `grep` finds them (and the Dockerfile's own `RUN` line that starts it). In order, with your versions
in place of mine:

- `check_image: Python …; installed: torch==…, …`: first, up front: the Python version and the versions of the libraries it
  names (torch, transformers, diffusers, accelerate and the others it finds).
- `check_image: torch … (CUDA …), diffusers …, transformers …`, then `check_image: pipeline features: {…}`.
- `check_image: GPU visible now: no (expected during a build)`: Docker gives a build no GPU, so "no" is right here.
- `check_image: music worker: diffusers … from /opt/music-libs`: the music model's own copy of diffusers.
- `check_image: Enlarge: spandrel …`: what Enlarge (section 22) needs.
- `check_image: Vector: vtracer …, shapely … made a …-layer SVG from a test picture`: a tiny picture was really run through the
  Vector clean-up (section 28).
- Several `check_image: Speech: …` lines: the first line of `ffmpeg -version`, whether that ffmpeg has an AAC encoder
  (the audiobook file, section 35), and one for each engine (`qwen3-tts`, `voxtral`, `kokoro`, `piper`): `can run (…)` or
  `not available here: <the reason>`. Voxtral says it is not available unless you built it with `SPEECH_VOXTRAL=1`.
- `check_image: OK`, last.

Good: those lines, ending in `check_image: OK`. Note them. The `Enlarge:`, `Vector:` and `Speech:` lines are notes, never
failures: whatever cannot run is reported with its reason (the page shows the same reason), and the build goes on. The log
also holds a few `NOTE:` lines from Dockerfile steps that are allowed to fail; one is normal: `NOTE: Voxtral is not built
into this image (add --build-arg SPEECH_VOXTRAL=1 to build it); its engine will say so`.

If the build stops, the last lines are `check_image: PROBLEM: ...` (the root cause; there may be several) and
`check_image: FAILED`, and the lines above them hold the installed versions and, for an import failure, the full traceback.
Send me all of it, from the first `check_image:` line to the end of the file:

```bash
sed -n '/check_image: Python/,$p' build.log
```

## 6. Start it

```bash
docker compose up -d
docker compose ps                      # STATUS: "health: starting", then "healthy" within ~1-2 min
docker compose logs -f studio          # Ctrl+C stops following; the server keeps running
```

Good, in the log:

- `serving the web UI from /app/static`
- `AI Studio <version> ready (pipeline=real, data=/data)`, where `<version>` is the version of this build: the number in the page's
  title, and in `curl -s localhost:8081/api/health`
- `capability check passed: {... 'name': 'NVIDIA GB10', 'capability': '12.1' ...}` (this can take
  a minute: it imports PyTorch and diffusers in a separate process), and next to it
  `music capability check passed: {...}` for the music model, whose start-up check runs at the same time
- for a voice engine that cannot run here, such as Voxtral when you did not build it, a warning that starts `speech engine <id>:`
  and gives the reason: expected, not a failure (section 31 (a))

If it says `capability check failed: ...` instead, the message says why; see [Troubleshooting](#troubleshooting).

## 7. Open the page

From your laptop or phone on the same network: `http://<spark-address>:8081` (on the Spark,
`hostname -I` shows its addresses).

Good: the page loads with the light or dark theme following your system, and a row of tabs (Images, Music, Vector, Prompt builder and Speech; Part 1 uses
Images). The model pill in the top-right says **Model not loaded**; click it and the panel's GPU line names the GB10.

## 8. First image: small and quick

1. **Options**: Size **Custom 1024 × 1024**, **Steps 20**. Close the drawer.
2. Prompt: `a lighthouse at dusk, oil painting`. Press **Generate**.

The first run downloads the model into `~/.cache/huggingface` (31 GiB, says the README; watch
`docker compose logs -f studio`), then loads it. The pill shows **Loading image model…**, then the card
shows step progress.

Note: how long the download took, how long the load took (the log says `pipeline real ready in Ns`),
and how long the image took (shown on the card).

Good: a card with the image, the prompt, the settings and the seed. **Download** gives a file named
like `generate_lighthouse-dusk-oil-painting_1024x1024_s<seed>_<time>.png`.

## 9. Measure the memory footprint (sets `STUDIO_MIN_FREE_GB`)

In a second terminal on the Spark:

```bash
watch -n1 "grep MemAvailable /proc/meminfo"
```

Then, in the page: **Options**, reset to defaults (**2752 × 1536, which is 16:9, and 40 steps**; before 1.16 the default was 2048 × 2048, and the two cost the same: step 27 checks that), and generate one image.

Note:

- `MemAvailable` before you click (the model not loaded): **A**
- the lowest `MemAvailable` while it generates: **B**
- the worker's own memory while loaded:
  `curl -s localhost:8081/api/status | python3 -c 'import json,sys; print(json.load(sys.stdin)["memory"])'`
  (`worker_rss_gb`)

The footprint is about **A − B**. Set `STUDIO_MIN_FREE_GB` in `.env` to that plus 10–20% headroom,
then apply it with `docker compose up -d`.

## 10. The everyday features

- **Batch:** Options, Images per click **2**: one card, two images, seeds *n* and *n*+1.
- **Reuse** on a card: prompt and options come back with the seed locked; Generate again gives the
  same image.
- **Transparent background:** turn it on and try `a red apple, product shot, transparent background`.
  The card shows the image on a checkerboard if it really has alpha; note whether it did.
- **A second click while one is running** queues it with a position (`Queued · #1`).
- On your phone: no sideways scrolling, and Options opens as a bottom sheet.

## 11. Idle unload gives the memory back

```bash
sed -i 's/^STUDIO_IDLE_TIMEOUT_MIN=.*/STUDIO_IDLE_TIMEOUT_MIN=2/' .env && docker compose up -d
```

Generate one image, then wait. The pill says **Image model ready · unloads in 2 minutes**, then **Model
not loaded**.

Good: `MemAvailable` rises by about the footprint from step 9, and
`curl -s localhost:8081/api/status | python3 -m json.tool` shows the worker `"state": "unloaded"`.
The next Generate loads it again (faster this time: the files are cached).

Put the timeout back afterwards (`30` is the default, or whatever suits you) and `docker compose up -d`.

## 12. The memory check fails fast

```bash
sed -i 's/^STUDIO_MIN_FREE_GB=.*/STUDIO_MIN_FREE_GB=1000/' .env && docker compose up -d
```

Generate. Good: the card fails **immediately** with `Not enough free memory to load the model: …`
plus what to do. Put your number from step 9 back, `docker compose up -d`, and click **Retry** on
that card: it runs.

## 13. History survives the container

```bash
docker compose down && docker compose up -d
```

Good: the page (after a reload) shows all earlier runs with their images. Stopping it while an
image is generating marks that run failed with `Interrupted because the server was stopped.` (or
`Interrupted by a server restart.` if the container was killed outright); the next run works.

# Part 2: Release checks (sections 14 to 38)

**How to read a section.** Each one says what "Good" looks like; where it says to write something down, do, and send
back what the section's "Send back" line and the list at the end ask for. A section was written when its release came,
so three things in it are true of that day and not necessarily of today: "Update first ... the title should read
**v1.3**" names the version of that release (a later number in the title is fine, and `git pull` on `main` brings every
release); a sentence such as "tried in unit tests ... **not with your models**" says how much had been tried when the
section was written; and the pill and button names are the ones of that release, corrected here where a later release
renamed them. The status table at the top is the current word. Section 37 has been run in part and section 38 has not been run.

## 14. Cancel, Keep and automatic clean-up (new in 1.1)

Update first: `git pull && docker compose up -d --build` (the unchanged layers come from the cache).

One thing to know before you do: from 1.1 on, a run is cleaned up **30 days after it was made** (and you
get a warning on its card in the last 7 days). Since 1.13 the clean-up moves it to **Deleted** (section 24) and it
is deleted for good 30 days after that. Yours are only days old, so nothing goes today. If you
want to be sure some are never touched, press **Keep** on them (below), or set
`STUDIO_RETENTION_DAYS=0` in `.env` to turn the clean-up off. A backup (`scripts/backup.sh`) first is
cheap insurance.

**a) Cancel a queued job.** Click Generate twice. The second card says `Queued · #1`. Click
**Cancel** on it: it turns **Canceled** at once, with no question asked, and the first job carries on.

**b) Cancel a running job, and time it.** Options: the **1:1** preset (2048 × 2048), 2 images per click. Generate, wait
until the card shows `step N of 40`, click **Cancel**, then **Stop generating**. Start a stopwatch at
the click.

Good: the card says `Stopping` and then **Canceled** within about one step (a 2K step is a few
seconds: 40 steps take around 4 minutes). If the first image was already finished the card says
`Canceled. 1 of 2 images finished and kept.` and you can open it; if not, `Canceled before any image
was finished.` The pill still says **Image model ready** (the model was not unloaded), and the next
Generate starts straight away with no `Loading the model…`. **Write down the seconds from click to
Canceled**; the log has the same moment: `docker compose logs studio | grep -i cancel`.

**c) No memory is left behind.** Note `free -h` (and `nvidia-smi`) after a normal finished image, then
cancel three runs in a row and look again. Good: no steady rise.

**d) (Optional) Cancel during the first load.** `docker compose restart studio`, Generate, and Cancel
straight away. Good: the card says `Stopping… (a model that is still loading finishes loading
first)`, becomes **Canceled** once the load is done, and the model stays loaded for the next run.

**e) Keep.** Click **Keep** on a card: a **Kept** badge appears and the button shows as pressed. Reload
the page, then `docker compose down && docker compose up -d`: it is still kept.

**f) (Optional) See the warning and a real expiry.** This changes the date on **one run**, so use a
throwaway. It ages the newest run by 27 days:

```bash
RUN=$(curl -s 'localhost:8081/api/runs?limit=1' | python3 -c 'import sys, json; print(json.load(sys.stdin)["runs"][0]["id"])')
docker compose exec -T studio python - "$RUN" 27 <<'PY'
import datetime as d, sqlite3, sys
t = (d.datetime.now(d.timezone.utc) - d.timedelta(days=float(sys.argv[2]))).isoformat(timespec="milliseconds").replace("+00:00", "Z")
c = sqlite3.connect("/data/studio.sqlite", timeout=10)
c.execute("UPDATE runs SET created_at=? WHERE id=?", (t, sys.argv[1]))
c.commit()
PY
```

Reload the page. Good: that card says `Will be deleted in 2 days. Press Keep to save it.` Press
**Keep** and the warning goes; press it again and the warning is back. Now run the same command with
`40` instead of `27` on a run that is **not** kept, then `docker compose restart studio`. Good: a few
seconds after start-up the card has left the history and is in **Deleted** (since 1.13; its files are still
there: `ls data/images | grep "$RUN"` still lists them). To see the files go too, press **Delete forever** on it
in **Deleted** (or set `STUDIO_BIN_DAYS=0` first, so that the clean-up deletes for good): then `ls data/images | grep "$RUN"` prints
nothing.

## 15. Editing with several images, through the API (new in 1.2)

This is the same thing as section 18, through the API with `curl` instead of the page. The page has had an
Edit mode since 1.6, so section 18 is the one to do; this one stays for checking the API from a terminal. It
was the first time the **real model** was asked to edit. You need two or three pictures:
say a photo of an object or pet, and a scene. Any JPEG, PNG or WebP.

**Before you update:** this version changes the database layout. The first start upgrades it and keeps a
copy of the old one as `data/studio.sqlite.before-schema-2`. That copy is also the way back to version 1.1
(an older studio refuses a database a newer one has touched, with a message saying so). To go back: check
out the 1.1 code and rebuild, then `docker compose stop`, delete `data/studio.sqlite-wal` and
`data/studio.sqlite-shm` if they exist, copy `data/studio.sqlite.before-schema-2` over
`data/studio.sqlite`, and `docker compose up -d`. The history is then as it was at the upgrade: anything
made since is gone from the page (its image files stay in `data/images`). I tried exactly this with a
database written by the real 1.1 code. A backup (`scripts/backup.sh`) first is still the better safety net.

```bash
git pull && docker compose up -d --build
docker compose logs studio | grep -i "schema"        # "upgrading the database from schema 1 to 2 ..."
curl -s localhost:8081/api/health                    # {"ok":true,"version":"<the version of this build>"}
```

**a) A first edit** (the first run after a quiet spell loads the model, which takes a while):

```bash
scripts/edit_via_api.sh "put the object from image 1 into the scene from image 2" thing.jpg scene.jpg
```

It prints the upload sizes, the progress, and where it saved the result. **Write down:** the seconds from
`running` to `done` (excluding the model load if it had to load), the result's size (`file edit-*.png`),
and whether the result obeys the numbers. Whether a prompt can say "image 1" and "image 2" is not
confirmed by Qwen's documentation, so also try the same edit **without** numbers ("put the object from the
first picture into the second") and say which worked better.

**b) Resolution.** `scripts/edit_via_api.sh --resolution 2048 ...` is about four times the pixels for every
image. Write down the time, and `free -h` while it runs. If it runs out of memory the card says so and
suggests 1K or fewer images; that is a finding too, not a failure of the test.

**c) More images, and the shape.** Try three or four images at 1K. Then `--shape-from 1` (the result follows
image 1's shape instead of the last image's) and `--size 1024x768` (an explicit size). Good: the result
size changes as described, and the images are used in the order you gave them.

**d) Transparency.** With a PNG that has a transparent background as one input, and `--transparent`, ask
for something like "put the subject of image 1 on a transparent background". Open the result in an image
viewer that shows transparency (or the web page, which shows a checkerboard). **Write down** whether the
result has real transparency, and whether it also did without `--transparent`.

**e) The page shows these runs.** They appear in the history with an **Edit** badge (the source
thumbnails come with the page's editing support), and **Cancel**, **Keep** and **Delete** work on them.
Deleting one removes its input pictures too: `ls data/inputs` has one folder per edit run still in the
history, plus `staged` for uploads that no run has used yet (those are removed after 24 hours).

**f) The limits.** `scripts/edit_via_api.sh` with five images should be refused with `at most 4 images` (set
`STUDIO_MAX_INPUT_IMAGES` in `.env` and `docker compose up -d` to change it, up to 10). **If you have time,
raise it and try more images at 1K while watching the memory: that number sets the default cap.**

## 16. Scale, Draft and thumbnails (new in 1.3)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.3** (reload with
Ctrl+Shift+R). There is no database change this time.

**a) The scale picker, and what it saves.** Keep one prompt and **Lock seed** on (Options). Generate the
same prompt at **100%**, **50%** and **25%** and **write down the three times**. Good: 50% takes roughly a
quarter of the time of 100% (a quarter of the pixels) and 25% roughly a sixteenth, plus the same model
load if it had to load. Look at the three pictures side by side: they will **not** be the same picture
with different sizes, even with the seed locked. That is expected (§22.1), and it is worth knowing how
different they are.

**b) Draft.** Type a prompt and click **Draft** (or Ctrl+Shift+Enter). Good: a card with a **Draft**
badge, one image, 512 px on the long side, 12 steps. **Write down** the time, and whether the picture is
good enough to tell whether the prompt works. If 12 steps looks too rough or too slow, say so: both
numbers are settings (`STUDIO_DRAFT_SIZE`, `STUDIO_DRAFT_STEPS` in `.env`, then `docker compose up -d`).

**c) A draft jumps the queue.** Click Generate twice (two full-size runs), then **Draft**. Good: the draft
card says `Queued · #1`, the second full run `Queued · #2`, and the draft finishes before it starts.
The run already in progress is never interrupted.

**d) Reuse on a draft.** Click **Reuse** on the draft's card. Good: the prompt comes back, and your own size,
steps and seed stay as they were, so **Generate** makes the full-size image.

**e) Thumbnails.** On a card with one image, click **Thumbnail**; for several images, open the viewer and
use **Thumbnail** there. Good: you get a `..._thumb.webp` file, 512 px on its long side. With a transparent
image, check that the thumbnail kept its transparency.

---

## 17. Regenerate larger (new in 1.4)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.5** (reload with
Ctrl+Shift+R). There is no database change. Only runs made with 1.4 or later can have the button.

**a) From a smaller scale.** Turn **Lock seed** on (Options) and set the prompt bar's **Scale** to **50%**.
Generate. Good: when the card says Done it has **Regenerate larger** (hover it: it names the size and steps,
for example "Regenerate at 2752×1536, 40 steps" at the default size). (1.4 and 1.5 also showed a greyed **Upscale** beside it; 1.10 removed it and
put Make 4K, section 21, and Enlarge, section 22, in its place.)
Click **Regenerate larger**. Good: a toast says it is queued at that size, and a second card appears at the
full size with the **same seed** and prompt, and no button of its own. **Write down both times.** Then look
at the two pictures: with the same seed they are **not** expected to be the same picture (§23.1). **Write
down how different they are** (same subject? same layout? nothing alike?), because that decides how much
Make 4K and Enlarge (sections 21 and 22) matter.

**b) From a draft.** Select several images in Options (say 3), then click **Draft**. When it is Done, click
**Regenerate larger** on its card. Good: one full-size image at the size and steps you had selected (not the
draft's 12), using the seed the draft picked (it is on the draft's card and on the new one).

**c) Where there is no button.** Good: none on the full-size card from (a), none on a failed or canceled run
(those have Retry), none on runs made before the update, and none when Scale is 100% (a normal run).

**d) Through the API** (optional). A run can say what size it stands in for. Good: this is accepted, and the
run's JSON has an `options.full`; the second command is refused with a 422 because the "full" size is not
larger:

```sh
curl -s -X POST localhost:8081/api/runs -H 'Content-Type: application/json' -H 'X-Studio-Client: 1' \
  -d '{"prompt": "a lighthouse", "options": {"width": 512, "height": 512, "steps": 20, "full": {"width": 1024, "height": 1024, "steps": 40}}}'
curl -s -X POST localhost:8081/api/runs -H 'Content-Type: application/json' -H 'X-Studio-Client: 1' \
  -d '{"prompt": "a lighthouse", "options": {"width": 1024, "height": 1024, "steps": 20, "full": {"width": 512, "height": 512, "steps": 40}}}'
```

**e) In the viewer (new in 1.5).** Generate three images at 50% (Lock seed on, **3 images** in Options). When
it is Done, click the second image to open the viewer. Good: the top bar has **Regenerate larger** (same
tooltip as the card). Click it. Good: a note inside the viewer says "Queued this image at …" (no toast), the
viewer stays open, and a **new card at the top of the history makes one image** at the full size, with the
second image's seed (the viewer's title shows it, one more than the run's first). **Write down** that it is
one image and not three, and, as in (a), how it compares with the small one.

---

## 18. Editing on the page, and the Spark test for edits (new in 1.6)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.6** (reload with
Ctrl+Shift+R). There is no database change. This is the Spark test for edits that `docs/DESIGN.md` lists as M5c (§21.11). The **Edit** switch should be enabled; if it is greyed out,
hover it for the reason (the pipeline reports it cannot edit; `docker compose logs studio` says why).

You need a few pictures: a photo of an object or pet, a scene, a PNG with a transparent background, and (for
part f) a black-and-white mask the size of one of the photos (white where a change should go). Keep a
notebook: **times and memory** are what this section is for. Watch memory with `docker stats` or `free -h`
in a second terminal while an edit runs. The first edit after a quiet spell includes loading the model, so do
one throw-away edit first and time the ones after it.

**a) One picture.** Click **Edit**, add one photo (the **Add images** tile), type "Make it look like a
watercolour painting." and click **Generate**. Good: a card with an **Edit** badge, a numbered source
thumbnail (1) above the result, and a meta line like "1 image · 1024×1024 · 1K · 40 steps". **Write down the
time.** Is the subject still recognisably the same?

**b) Several pictures, and "image N".** Add the object and the scene. Click the **1** badge on the object:
"image 1" appears in the prompt where the cursor was. Finish it: "Put the object from image 1 into the scene
from image 2." and send. **Write down whether the result follows the numbers.** (Nobody knows yet: §21.2.)
Then use the arrows to swap the two pictures and send the same prompt again: does "image 1" now mean the
other one?

**c) The shape.** Leave Size on **Auto** and, with two pictures of different shapes, use **Result follows
image** to pick each one in turn. Good: the result takes that picture's shape, about 1 megapixel at 1K.

**d) Resolution, cost and memory (the important one).** In Options choose **Resolution**; the line under it
gives the cost in units (images × (resolution ÷ 1024)²) and a warning above `STUDIO_EDIT_WARN_UNITS` (8).
Make a table of **time and peak memory** for: 1 picture at 1K and 2K; 2 pictures at 1K and 2K; 4 pictures at
1K and, if memory allows, 2K. Good: each completes, or fails with a card that says what to do (use 1K or fewer
pictures) while the server stays up. **Then tell me:** where it really starts to struggle (the number that
should replace 8: set `STUDIO_EDIT_WARN_UNITS` in `.env` and `docker compose up -d`), and whether 4 pictures is
the right default (`STUDIO_MAX_INPUT_IMAGES`, up to 10).

**e) Transparency.** Add the transparent PNG: Options shows a hint that its transparency is kept. Edit it with
Transparent off, then on. Then try the **Extract the subject** starter on a photo of an object. **Write down**
whether the background comes back transparent (the viewer shows a checkerboard) and whether the Transparent
switch was needed when the input already had transparency (§21.2 [unconfirmed]).

**f) A mask** (so local edits can be designed, §21.5). Add the photo as image 1 and the black-and-white mask as
image 2, and write the prompt "Change the area marked in white in image 2 to ...". **Write down which colour the model
treats as "edit here"**: try with white where you want the change, then a mask with the colours swapped; and
whether a mask the same size as the photo matters (try one of a different size).

**g) Edit this.** On a finished single-image card click **Edit this**: the picture is added as image 1 and
the page switches to Edit. For a card with several images, open one in the viewer (it has **Edit this** for any
image, and for an edit's source pictures too).

**h) Reuse and Retry.** **Reuse** an edit's card: the prompt, the options and all its pictures come back, in
order, with the seed locked. If you can make one fail (a picture of 4 at 2K, say), **Retry** sends the same
pictures again.

**i) A phone.** Open the page on a phone: the tray is three pictures across, **Add images** opens the photo
picker, and nothing scrolls sideways.

---

## 19. Load model and Unload model (new in 1.7)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.7** (reload with
Ctrl+Shift+R). There is no database change. You need a second terminal for `free -h` (or `docker stats`), and
the idle timeout at its normal value (30), not the 2 minutes of step 11.

**a) Load without a run.** Start from **Model not loaded** (restart the container if it isn't:
`docker compose restart`). Write down `free -h`. Click **Load model** beside the pill. Good: the button goes
away, the pill says **Loading image model…**, focus is on the pill, and **no run card appears**. **Write down how long
until the pill says Image model ready** (this is the real load time, first time and then with the files cached, if you
unload and load again) and `free -h` once it is ready: the difference is what Load takes. Then type a prompt and
generate: it should start at once, with no loading pause.

**b) The countdown starts when the load finishes.** Right after the pill says Image model ready it should say about
**unloads in 30 minutes**, not 29 or 28 (the load itself does not eat into it).

**c) A run sent while it loads.** Unload, click Load model, and send a Generate straight away. Good: the card
waits, then runs when the load is done, and the model is loaded **once** (one worker; `docker compose logs studio`
shows one "pipeline ... ready" line for that pair).

**d) Unload.** With the model ready, click **Unload model**. Good: the pill says Model not loaded **at once** and
`free -h` shows the memory coming back within a few seconds. **Write down how much comes back** and compare it with
the figure from step 9. While a run is going the button is not shown (the pill says Generating).

**e) The memory check.** Make memory scarce (the way step 12 does) and click Load model. Good: nothing starts, a
message appears on screen, the pill says **Image model problem** with the reason (open it for the hint), and **Load
model** is still there to try again once memory is free.

**f) The idle timeout still works.** Load the model with the button and leave it alone. After the idle timeout
(set it to 2 for this, then put it back) the pill goes back to Model not loaded and the memory is returned.

**g) A phone.** On a phone the button is an icon, the pill says one word (Unloaded, Loading…, Ready), and the
header does not scroll sideways.

---

## 20. Music: the model, from a terminal and through the API (new in 1.8)

When this section was written it was the first time the **real MiniMax-Music3 model** would run anywhere: everything before it was checked against
a stand-in and, for the pipeline's own code, against a tiny random-weight copy on a CPU. Expect surprises, and write
down what you see. The Music tab (1.9) is checked at the end of this section; the model, its speed and its memory come first, with
`scripts/minimax_music.py`, which uses the very same pipeline class the studio uses.

Update first: `git pull && docker compose up -d --build`; the title should read **v1.8** or later. Look at the build's check
lines: `docker compose build 2>&1 | grep check_image` should include **`music worker: diffusers 0.40.0 from
/opt/music-libs`** and end with `check_image: OK`. If it says PROBLEM, that message is the first thing to send back.
**Free disk:** the music model is about 29 GB (up to 57 GB if the whole repository is fetched). Check
`df -h ~/.cache/huggingface` (or your `HF_CACHE_DIR`) has 60 GB.

**a) Download it ahead of time (optional, about 29 GB).** Press **Load model** later and the download happens then
(the pill says *Loading…* for its whole length); or do it now, only the parts the pipeline loads:

```bash
docker compose exec studio hf download MiniMaxAI/MiniMax-Music3 --include "modular_model_index.json" "config.json" \
  "condition_encoder/*" "language_model/*" "rvq_depth_decoder/*" "scheduler/*" "tokenizer/*" "transformer/*" "vocoder/*"
```

**Write down:** how long it took and `du -sh ~/.cache/huggingface/hub/models--MiniMaxAI--MiniMax-Music3`. (If the
first load later downloads *more*, the pipeline fetches the whole repository: tell me, and how big.)

**b) See what would be sent, loading nothing.**

```bash
docker compose exec studio python /app/scripts/minimax_music.py --genre "acoustic pop" --bpm 96 --key "C major" \
  --mood "warm and intimate, building gently" --instruments "fingerpicked guitar and soft piano" --dry-run
```

Good: the description in the three-section layout, the lyrics `[Instrumental]`, and no model loaded.

**c) A short real track (the important one).** Open a second terminal with `watch -n 2 free -h` (or `docker stats`):

```bash
docker compose exec studio python /app/scripts/minimax_music.py --genre "ambient" --mood "slow, spacious" \
  --instruments "soft pads and a piano" --duration 15 --seed 7 --out /data/try15.wav
```

The file appears at `./data/try15.wav` on the Spark. Good: it prints *loaded in N s*, then *composing*, *rendering*,
*finishing*, then *made N s of music in N s* and the licence reminder. **Write down:** the load time, the time to make 15
seconds (so the seconds of work per second of music), and the **lowest "available" memory** you saw in the other
terminal. The design's guess is at least 1.5 s of work per second of music and about 24 GB loaded (§26.7); say how far off it is.
Then **listen**: does it sound like music, with no singing? **Is the length 15 s?** (It is only an upper bound.)

**d) Longer.** The same with `--duration 60`, and if you are patient `--duration 180`. **Write down** the times: is the
cost per second steady? How long would the 5-minute maximum take? The page shows no estimate until you tell me one.

**e) Instrumental, and what helps.** Listen for any vocals in (c) and (d). Then run the same seed with your own
description text that *leaves out* "Instrumental, no vocals." (`--prompt-file`, with the lyrics still `[Instrumental]`),
and once more with `--lyrics "[Verse]\nla la la\n[Chorus]\nla la la"` to hear what a vocal track is. **Write down**
whether the `[Instrumental]` tag alone is enough, whether the extra sentence changes anything, and whether the same seed
with the same text gives the same track twice (run (c) again and compare the files with `cmp`).

**f) Cancel.** Start a 60-second track and press **Ctrl+C** while it says *composing*, then while it says *rendering*.
Good: it stops within a second or two and exits (code 130), and the next run works. **Write down** how fast it stopped.

**g) No more downloading.** Run (c) again with `--hub offline`: it must work with no network use (it only reads the
cache). Then the same through the studio, which loads from the cache by default (`STUDIO_LOCAL_FILES_ONLY=auto`):
unplug the Spark's network (or block Hugging Face) and press the studio's load below. Good: it loads. If you
can, watch `docker compose logs studio` for anything that looks like a download.

**h) Through the studio's API (the Music tab does exactly this).**

```bash
curl -s -X POST localhost:8081/api/model/load -H 'X-Studio-Client: 1' -H 'Content-Type: application/json' -d '{"model":"music"}'
curl -s localhost:8081/api/status | python3 -m json.tool | grep -E '"state"|"model"|"detail"'   # until state is "ready", model "music"
curl -s -X POST localhost:8081/api/runs -H 'X-Studio-Client: 1' -H 'Content-Type: application/json' \
  -d '{"mode":"music","prompt":"Global Metadata\nBasic Attributes: ambient.\nInstrumental, no vocals.","options":{"duration":15,"tracks":1}}'
# then poll   curl -s localhost:8081/api/runs/<id>   until "status" is "done", and fetch the track:
curl -s -o /tmp/api.wav 'localhost:8081/api/audio/<track id>?download=1' && strings /tmp/api.wav | grep machine-generated
```

Good: the music model loads, the image model is **not** loaded at the same time (`free -h` shows only one), the run
finishes with a track, and the WAV carries the note that it is machine-generated. Then make a picture (Generate): the
music model is unloaded first (`"model": "image"` in the status afterwards) and the memory comes back. **Write down** how
long the switch takes in each direction.

**i) The memory check.** With the music model's check at 40 GB (the default), make memory scarce as in step 12 and press
Load for the music model: nothing starts, the message says *music model*, and nothing is left loaded.

**j) The page (new in 1.9).** Update (`git pull && docker compose up -d --build`; the title should read **v1.9**) and
open the page. **Good:** the tabs *Images* and *Music* (later releases added Vector, Prompt builder and Speech after them); the arrow keys switch between them and the choice is still
there after a reload; the Music tab has the boxes, the description below them (try changing a box, then the
description by hand, then *Rebuild from fields*), *Add lyrics* (off), the length shortcuts, and under the form the
note naming MiniMax-Music3 and its licence. If the tab says *Music isn't available*, the reason and hint it shows are
the first thing to send back.

**k) A track from the page.** On the Music tab: genre *ambient*, mood *slow, spacious*, instruments *soft pads and a
piano*, length **15 s**, then **Make music**. **Good:** the pill says *Loading music model…* (the first load is long), then
the card shows **Composing** and **Rendering** bars in turn, then a player. **Write down** the same numbers as in (c),
now through the page, and whether the card's *Track · 0:15* is the length you got. Play it **on the Spark's browser
and on your phone** (the page is on your network): it should play and seek. Press *Download WAV* and check the name
(`music_ambient_..._15s_s<seed>_<date>.wav`).

**l) Cancel from the page.** Make a 60 s track and press **Cancel** while the *Composing* bar moves, then (another
track) while *Rendering* does. **Good:** a dialog asks first; *Stop making music* turns the card to *Canceled* within a
second or two, the model is **not** unloaded (the pill still says *Music model ready*), and the next track starts at once.
**Write down** how long the stop took in each phase.

**m) The buttons on each tab.** With the music model loaded: the Music tab offers **Unload model**, the Images tab
offers **Load model**, whose tooltip says the music model is unloaded first. Press it. **Good:** the pill goes
*Loading image model…* then *Image model ready*, and the memory of the music model comes back (`free -h`). Then the Music
tab's **Load music model** swaps them back. **Write down** the time of each swap and the free memory before and after.

**n) A phone.** Open the page on your phone. **Good:** the tabs, the form, the length shortcuts and a finished track
fit the screen with no sideways scrolling, and the player and *Download WAV* are reachable. A screenshot of anything
that does not is the most useful thing you can send.

---

## 21. Make 4K, and the upscaler probe (new in 1.10)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.10** (reload with Ctrl+Shift+R).
There is no database change. You need a 16:9 picture: Options, size **16:9** (2752×1536), generate one at the usual
steps. A 4K copy is a file next to the picture, so `ls -l data/images/<run>/` shows it.

**a) Make 4K.** On the card of a 16:9 picture press **Make 4K**. Good: the button says *Making 4K…* for a few
seconds, a note says *The 4K copy is ready: 3840×2160, N MB*, and the button becomes **Download 4K**. **Write down how
many seconds it took** (the Spark's CPU, not mine) **and the file size**. `ls -l` shows `0.png` and `0-4k.png`.

**b) Look at it.** Download the 4K copy and the original. Open the 4K copy at 100% and the original at 140% in a
viewer you trust. **Good:** the same picture, trimmed by a sliver at the sides (about 21 pixels of the 2752 wide, taken
equally from both sides), with nothing stretched (circles stay round). It will be **softer than a real 4K picture**:
no detail was added. **Write down what you think**: fine for how you will use it, or soft enough that an upscaler
(step i) is worth building. Faces, text and fine textures are where it shows.

**c) Other shapes, and where it is not offered.** Make a **1:1** picture (choose the 1:1 preset in Options: 2048×2048, which was the default until 1.15) and press Make 4K: the
tooltip says *3840×3840* and **Good** is a 3840×3840 file with nothing cut off (it is big: about 15 MP; **write down the
seconds and the file size**). A 4:3 or 3:2 picture works too (3840 wide, in proportion). A **Draft**, or any picture
that would need more than a doubling (anything under 1920×1080 or 1920×1920), has no Make 4K, and neither has one
that is already 4K. A run with several pictures has no button on its card; open one in the viewer and it is there,
for that picture only. **Pictures you made before updating** have the button too, if they qualify (open an old one).

**c2) An edit's source images.** Open an edit run's card and click one of its source thumbnails: the viewer has **Make 4K**
for it (if it is big enough), and the copy is for the source, not the result. Use the arrow keys to see that the result has
its own button.

**c3) A picture from your computer.** Press **Upscale a picture…** above your runs and choose a PNG, a JPEG and a WebP
in turn (try a **phone photo**: it should come back upright, whatever way it was held). **Good:** a download starts at once,
named `upscale_<file name>_<size>_<time>.png`, and no card appears. Try a tiny picture and a 4K one: each is refused with
the reason, in words. Try a PNG with transparency: the copy is still transparent. **Write down** the time for a
photo of about 12 MP (the server's CPU does the work).

**d) While a picture is being made.** Start a long run, and press Make 4K on an older picture while it runs.
**Good:** it works at once. **Write down** whether the running job slowed down (the steps per second in the logs).

**e) It stays.** Reload the page: **Download 4K** is still there. `docker compose restart`: still there. Delete the
run: `ls data/images/` no longer has its folder, and the 4K file went with it.

**f) Transparency.** Make a 16:9 picture with **Transparent** on and press Make 4K. **Good:** the 4K copy is still
transparent (open it on a coloured background).

**g) A phone.** In the viewer on your phone the buttons wrap onto a second row; nothing runs off the screen.

**h) The numbers.** The model cannot make 3840×2160 itself (2160 is not a multiple of 32), so there is nothing to
compare this against. If you want to try **making a bigger picture directly** (route C in `docs/DESIGN.md` §27.6), tell me:
that needs a setting for the pixel limit, which I have not built.

**i) The upscaler probe (route B, optional but it decides what comes next).** It checks that an ESRGAN-class model
runs on the Spark's GPU, and it makes two 4K files to compare. Nothing in the studio uses it.

1. On the Spark, download the model into the cache folder the container sees as `/models`:
   `mkdir -p ~/.cache/huggingface/upscalers && curl -L -o ~/.cache/huggingface/upscalers/RealESRGAN_x2plus.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth`.
   It is 67,061,725 bytes. When I downloaded it (2026-10-09) its SHA-256 was `49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb` (`sha256sum` it); the project does not publish a checksum that I found, so
   a different one means only that the file has changed. The code is BSD-3-Clause; read the model's terms yourself.
2. `docker compose cp scripts/upscale_probe.py studio:/tmp/upscale_probe.py`. (From version 1.11 `spandrel` is in the image; in 1.10 you also had to run `docker compose exec studio pip install --user spandrel`.)
3. A quick check: `docker compose exec studio python /tmp/upscale_probe.py --model /models/upscalers/RealESRGAN_x2plus.pth --crop 512x288`. **Good:** it prints the GPU, `ESRGAN, x2`, a tile time and `PROBE OK`.
4. The real one, on a 16:9 picture the studio made: `... --image /data/images/<run>/0.png --out /data/upscale-probe`.
   Then try `--dtype bf16`. The results are in `data/upscale-probe/`: put `4k-lanczos.png` (what Make 4K makes) and
   `4k-from-model.png` side by side at 100%.

**Send back:** the whole output of the probe, including the last line and the **GPU** line (it says whether it used the
GPU and which compute capability), the tile times, the peak GPU memory and the memory figures; whether the same run
with `--dtype bf16` was faster and looked the same; and above all **which of the two 4K files looks better to you and
where** (faces, text, foliage). If `pip install` or the run fails, paste the error: that is the answer I am looking for.

---

## 22. Enlarge: the same picture, bigger and sharper (new in 1.11)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.12** (reload with Ctrl+Shift+R). The build log
has a line `check_image: Enlarge: spandrel 0.4.x`; if it says spandrel cannot be imported, send me that line (everything else still
works, and Enlarge says why it is off). There is no database change. Enlarge uses **a model file you download once** and a **separate
short-lived process**, so the image model does not have to be loaded. If it is generating, Enlarge **waits for the picture to finish** and then runs (g): the two do not fit on the GPU together.

**a) The model file.** Before you download anything: generate any 16:9 picture (Options, size **16:9**, 2752×1536). Its card has
**Make 4K** and **Enlarge**, and Enlarge is **dimmed**. Hover it: the tooltip says the model file is not there and says what to do. Press
it: the same words appear as a message. **Good:** nothing is made, and Make 4K still works. Then, on the Spark:
`mkdir -p ~/.cache/huggingface/upscalers && curl -L -o ~/.cache/huggingface/upscalers/RealESRGAN_x2plus.pth https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth`
(67,061,725 bytes; the code is BSD-3-Clause; the model has its own terms, which are yours to read), reload the page: **Enlarge is no longer dimmed**.

**b) Enlarge a picture.** Press **Enlarge** on the 16:9 card. **Good:** the button says *Enlarging…*, a note then says *Enlarged to 3840×2160, N MB.
Use Download 4K.*, **Enlarge and Make 4K are gone** and **Download 4K** is there. **Write down how long it took and the file size.** The log
says it too: `docker compose logs studio | grep ENLARGED` shows a line like `ENLARGED 3840x2160 in 12.3 s on cuda with ESRGAN ×2 (RealESRGAN_x2plus.pth)`:
**send me that line**, especially the *device* (it should say `cuda`; `cpu` means the GPU was not used, which is minutes per picture). `ls -l data/images/<run>/`
shows `0.png` and `0-4k-enlarged.png`.

**c) Look at it, against the plain resize.** On a second picture of the same size press **Make 4K**, **Download 4K** and save it as `plain.png`; then press **Enlarge**
(it replaces the plain copy; that is expected), download it again as `enlarged.png`. Open both at 100%. **Write down what you think, and where**
(faces, hair, text, foliage, skies, flat colour): is Enlarge **sharper**? Does it look **natural**? Things to look for: skin that is too smooth or plastic; grain or texture
on flat colour and gradients (I saw some of that on a synthetic gradient with the real model); faint lines at regular spacing across the picture (seams where tiles meet; they would be
every 512 source pixels, so about every 700 pixels of the 4K copy for a 2752-wide picture); small text that got worse. This is the main thing I need from you.

**d) A 50% picture.** Scale **50%** (1376×768) and generate. **Make 4K is not offered** (it would be a 2.8× enlargement); **Enlarge is**, and its tooltip says 3840×2160.
Press it. **Write down the time and how it looks** next to the picture you would get from regenerating at full size (it is the same picture, which is the point).

**e) Two passes.** A custom size of **960×544**: Enlarge runs the model twice (×4) and then reduces. **Write down the time**, and whether it looks worse than a one-pass picture (a second pass can over-smooth).

**f) A square.** The 1:1 preset, 2048×2048 (choose it in Options): Enlarge makes **3840×3840** (the model's 4096×4096 is reduced). **Write down the time**, and the memory while it runs (`free -g` in another terminal).

**g) While a picture is being made.** (This is the check that failed in the first trial, with *CUDA error: out of memory*.) Start a long run (several pictures, many steps),
and press Enlarge on an older picture while it runs. Queue a second run behind it. **Good:** the button says **Waiting…** and is dimmed (that is not an error; hover it for why); the running
picture is not stopped or slowed; **when that run finishes** the button says *Enlarging…* **before the second run starts**, and then the note *Enlarged to 3840×2160…* appears and the second run goes on.
Open the page in a second browser tab while it waits: its button says *Waiting…* too, and shows Download 4K when it is done. **Write down** how long it waited, how long it then took, and whether the log's
`ENLARGED …` line says `cuda`. If you get *Not enough memory for the upscaler right now…* instead, something other than the studio is holding the GPU (the LLM server?): send me `nvidia-smi` and `free -g` taken at that moment.
Also try **Load model** and, while it is loading, Enlarge: it should wait for the load to finish.

**h) When it goes wrong.** (1) Rename the model file, reload: Enlarge is dimmed again, with the reason. (2) Put a file that is not a model in its place (`echo x > ~/.cache/huggingface/upscalers/RealESRGAN_x2plus.pth`):
pressing Enlarge says the model could not be loaded, naming the file. Restore the real file afterwards. (3) Press Enlarge twice quickly: one request, one copy.

**i) The CPU, for the record.** Set `STUDIO_UPSCALER_DEVICE=cpu` in `.env`, `docker compose up -d`, and Enlarge one picture. **Write down the time.** Set it back to `auto`.

**j) A phone.** On your phone the card's buttons and the viewer's bar, with **Enlarge** in them, wrap onto more rows; nothing runs off the screen.

**Send back:** the `ENLARGED …` lines; the times and file sizes from (b), (d), (e), (f), (i); your verdict from (c), (d) and (e): **where Enlarge looks better than the plain resize and where it looks worse**;
the memory and slowdown figures from (f) and (g); and anything that did not match "Good". If Enlarge looks worse than Make 4K on your pictures, say so plainly: that decides whether
the model, the settings (`--dtype bf16`, the tile overlap) or the whole idea needs another look, and whether Qwen redrawing (`docs/DESIGN.md` §28.5) is worth trying.

---

## 23. The Kept view, and Enlarge waiting its turn (new in 1.12)

Update first: `git pull && docker compose up -d --build` (on `main`); the title should read **v1.12** (reload with Ctrl+Shift+R).
There is no database change. The Enlarge part is §22(g) above; this section is the Kept view, which needs no GPU but is worth looking at with your own history.

**a) The filter bar.** Above your runs: **Show**, **All**, **Kept N**. Press **Keep** on two cards. **Good:** the number beside **Kept** goes up by itself;
choose **Kept** and only those two cards remain; choose **All** and everything is back; reload with **Kept** chosen and it is still chosen. The arrow keys move between the two options.

**b) Both tabs.** With **Kept** chosen on **Images**, open **Music**: the bar there says **Kept** too, with that tab's own count, and shows only kept tracks.

**c) Older kept runs.** If you have more than twenty runs, keep an old one: in **Kept**, it is found without scrolling through everything (*Load older runs* appears only when
there are more than twenty kept). Back in **All** it is not shown out of order.

**d) Generating while Kept is chosen.** Press **Generate**. **Good:** your job appears **at the top** with the note *Shown while it works. It stays in this view only if you Keep it.*;
when it finishes (not kept) it leaves and a toast says *"…" is done. It is not kept, so it is not in this view.* with **Show all**. Do it again and press **Keep** on the working card:
the note goes away and the card stays when the job is done.

**e) Stopping to keep.** In **Kept**, press **Keep** on a kept card. **Good:** the card goes; a toast says *No longer kept: "…". It will be deleted around <date>, in N days, unless you Keep it again.*
with **Undo**; **Undo** brings the card back in its place. A run older than your retention (30 days) says it will go *at the next daily clean-up*. With the keyboard, focus lands on the filter bar.

**f) A phone.** The bar fits, and the toast with **Undo** can be pressed.

**Send back:** anything that did not match "Good", and whether the date in (e) matched the date you expected from the run's age.

## 24. The bin (new in 1.13)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.13** (reload with Ctrl+Shift+R). **This release upgrades the database**
(schema 4): the first start makes a copy beside it, so check, before anything else: `ls -l data/studio.sqlite*` shows `studio.sqlite.before-schema-4`, and your
runs are all there. (If anything is missing, stop and send me the log; the copy is the way back, with an older studio.)

**a) The first clean-up.** Runs older than 30 days that you did not Keep used to be deleted at the first start and then daily; now they are **moved to Deleted**.
Open **Deleted**: if you had such runs they are there, each saying when it will be deleted for good (30 days from today). **Good:** nothing you cared about is gone.

**b) Delete, Undo.** Press **Delete** on a recent card. **Good:** the question says it moves to Deleted and stays 30 days; the card goes; a toast says so with **Undo**; **Undo** brings
the card back where it was. Do it again and this time let the toast go: the run is in **Deleted** (the count beside it went up), with its pictures still opening.

**c) Restore.** In **Deleted** press **Restore** on a run you had kept: the toast says *It is still kept*. On one you had not: *It has a fresh 30 days*. Both are back in All.

**d) Delete forever, Empty bin.** **Delete forever** asks first and then removes the run and its files (`ls data/images/<run id>` is gone). **Empty bin** (top right of the bar) asks,
saying how many on Images and on Music, and then empties both. **Good:** `du -sh data` falls by what was in the bin.

**e) A waiting run.** Start a long run, queue another, and press **Delete** on the waiting one: the question says it cannot be undone, and it does not appear in Deleted.

**f) The setting.** In `.env` put `STUDIO_BIN_DAYS=0` and `docker compose up -d`: Delete is for good again (the old question), and the next clean-up empties whatever is in the bin. Set it back to `30`.

**g) A phone.** The bar with **Deleted** and **Empty bin**, a card in the bin and the questions fit the screen.

**Send back:** the `ls -l data/studio.sqlite*` line, what (a) showed, anything that did not match "Good".

## 25. Project folders (new in 1.14)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.14** (reload with Ctrl+Shift+R). **This release upgrades the database**
(schema 5): the first start makes a copy beside it, so check, before anything else: `ls -l data/studio.sqlite*` shows `studio.sqlite.before-schema-5`, and your
runs are all there, **none of them in a project yet**. (If anything is missing, stop and send me the log; the copy is the way back, with an older studio.)
This step needs no GPU work: use runs you already have.

**a) The drop-down.** Open the **Project** drop-down above your runs. **Good:** it says **Any project** and **No project**, and no projects yet; **Manage** is beside it.

**b) File a run.** On a card you like press **Add to project ▾**, choose **New project…**, type a name and press **Create**. **Good:** the card shows the project's name and a chip, a toast
says *Filed … in … It is kept.* with **Undo**, and the card's **Keep** is pressed and does nothing when you press it (hover it: it says why). Press **Undo**: the run is back as it was,
and if it was not kept before it is not kept now.

**c) Move, take out.** File two runs in one project and a third in another. On one press its project's name and choose the other project: *Moved … from … to …*. Press it again and choose
**Take out of project**: *Taken out of … It is still kept.*, and now **Keep** works again (and is on).

**d) Browse.** Choose a project in the drop-down above your runs. **Good:** only its runs are shown, the number beside it is for this tab, and the numbers beside **Kept** and **Deleted**
are the project's. Choose **No project**, then a project and **Kept**: the project stays chosen. Reload the page: the choice is still there. Open the **Music** tab: the same projects, with their
counts for music.

**e) Manage.** Press **Manage**: make a project, rename one, try a name that is taken (even in other capitals): refused with the reason. Delete a project that holds runs: it asks first and says the runs
are **not deleted**; afterwards they are still in the list, kept, and in no project.

**f) Delete, Restore.** Press **Delete** on a filed run: the question names the project. In **Deleted** the card shows the project as a chip (and has no Project button); **Restore** puts it back in the project, kept.

**g) A phone.** The **Project** button's drop-down on a card, the filter bar with its two controls and the **Manage** dialog fit the screen with no sideways scroll.

**Send back:** the `ls -l data/studio.sqlite*` line, and anything that did not match "Good".

## 26. Deleting one picture (new in 1.15)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.15** (reload with Ctrl+Shift+R). **This release upgrades the database**
(schema 6): the first start makes a copy beside it, so check, before anything else: `ls -l data/studio.sqlite*` shows `studio.sqlite.before-schema-6`, and your
runs are all there with every picture still on its card. (If anything is missing, stop and send me the log; the copy is the way back, with an older studio.)
This step needs no GPU work: use runs you already have.

**a) Delete a picture.** Open a run with several pictures, press the second one, and press **Delete picture**. **Good:** the question names it (*image 2 of 4, seed …*), says it moves to **Deleted**
for 30 days and that its 4K and Enlarge copies go with it; after **Delete** the viewer shows the next picture, the card has one picture fewer (the rest numbered again, with their own seeds),
and a toast says so with **Undo**. Press **Undo**: the picture is back between its neighbours.

**b) The Deleted view.** Delete a picture again and open **Deleted**. **Good:** the run is **one card** (*From a run made on …*) listing the picture with its place, seed and *In the bin since … It will be deleted
for good around …*; the number beside **Deleted** went up by one; pressing the thumbnail opens it, and the viewer has **Download** but no **Delete picture** or **Make 4K**. **Restore** puts it back.

**c) Its copies go with it.** On a picture press **Make 4K** (or **Enlarge**), wait, then delete the picture and **Delete forever** it from **Deleted**. **Good:** `ls data/images/<run id>` no longer has `<n>.png`, `<n>-4k.png` or
`<n>-4k-enlarged.png` of that picture (and `ls data/thumbs/<run id>` has no thumbnail of it), and the run's other pictures are all there.

**d) The last picture.** Delete a run's pictures one by one. **Good:** the last question says *the whole run moves to Deleted*, and after it the run is in **Deleted** as an ordinary card with its pictures, and **Undo** brings the run back.

**e) A music run.** Make a track with 2 or 3 versions. **Good:** each row has **Delete track** (a single track has none); deleting one renumbers the others (*Version 1 of 2*); in **Deleted** the track is on a card with a player and the same **Restore** and **Delete forever**.

**f) Empty bin.** With a run and some pictures in the bin, press **Empty bin**. **Good:** the question says how many runs and how many pictures (*Delete 1 run and 2 pictures for good …*), and afterwards `du -sh data` fell by what was in the bin.

**g) A phone.** The viewer's **Delete picture**, its question and the card in **Deleted** fit the screen.

**Send back:** the `ls -l data/studio.sqlite*` line, what (c) showed, and anything that did not match "Good".

## 27. The default size, 16:9 (new in 1.16)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.16** (reload with Ctrl+Shift+R). There is no database change.
**(c) is the one check this release needs the Spark for** (criterion 184 of `DESIGN.md` §34.6); the rest takes a minute each and needs no GPU work.

**a) A browser with nothing saved.** Open the studio in a **private window**. **Good:** the Options button reads **2752×1536 · 40 steps …**; in Options the **16:9** preset is selected and
**Custom** starts at **2752 × 1536**; **Reset to defaults** gives the same; and no note is shown.

**b) Your own browser (the one you have used before).** Reload it with Ctrl+Shift+R. **Good, if it was on the 1:1 preset:** a toast says *The default size is now 16:9, and your saved 1:1 was changed to it.
Choose 1:1 in Options to go back.* and Options is on **16:9** (a saved scale such as 50% is kept). Reload again: **no** note. Choose **1:1** in Options and reload: it **stays** 1:1, with no note.
If it was on another preset or a Custom size, **nothing** is moved and no note is shown. Edit's size is not touched either way.

**c) One run at the default size, and one at the old square: time and memory (criterion 184).** This needs the real model. In a second terminal on the Spark:

```bash
watch -n1 "grep MemAvailable /proc/meminfo"
```

In the page turn **Lock seed** on, set **Images per click** to 1 and **Steps** to 40, and use the same prompt for both runs. First choose **16:9** (the default; **Reset to defaults** does it) and generate one image;
then choose **1:1** (2048 × 2048) and generate one more. If the model has to load for the first, wait for it to be ready before you start counting, so that both runs are measured loaded. For each run **write down**:

- the time on the card (the seconds of the run, without the model load);
- `MemAvailable` before you click (**A**) and the lowest it reached while the run was going (**B**), so the footprint is **A − B**;
- the worker's own memory while it was loaded: `curl -s localhost:8081/api/status | python3 -c 'import json,sys; print(json.load(sys.stdin)["memory"])'` (`worker_rss_gb`).

**Good:** the 16:9 run takes about as long as the square (it has 0.9% more pixels: 4.23 MP against 4.19) and its **A − B** is no more than the square's, within the noise between two runs.
**If it is larger, send me both sets of numbers:** the default would have to be thought about again, and `STUDIO_MIN_FREE_GB` (step 9) may need raising.

**d) The command-line script.** `./scripts/qwen_image.py generate "test" --dry-run` (it needs nothing installed) prints `size : 2752x1536` and an output file name with `2752x1536` in it;
`./scripts/qwen_image.py generate --help` says *generate defaults to 2752x1536 (16:9)*; and `--aspect-ratio 1:1` with `--dry-run` says `2048x2048`. Only if you use the script for real: one image without a size is **2752 × 1536**.

**e) The API with no size.** The request below names no size. **Good:** the answer's `options` has `"width": 2752` and `"height": 1536`, and the finished picture is 2752 × 1536
(`file` on the downloaded PNG, or the size on the card). A request that names a size (`"width": 1024, "height": 1024`) gets that size.

```bash
curl -s -X POST localhost:8081/api/runs -H 'Content-Type: application/json' -H 'X-Studio-Client: 1' -d '{"prompt": "a lighthouse at dusk", "options": {"steps": 20}}'
```

**f) What does not change.** Turn **Edit** on: Size is still **Auto** (*from your images*), and **Reset to defaults** leaves it there. Press **Reuse** on a card made before the update (a square):
Options go to that run's own size (**1:1**), not to 16:9; the same with **Retry** on a failed one.

**Send back:** from (c) the two times and the two sets of memory numbers (and `worker_rss_gb` for each); from (b) whether the note appeared and what it said; and anything that did not match "Good".

## 28. Vector (new in 1.17)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.17** (reload with Ctrl+Shift+R). **Back up first: the first start of 1.17 upgrades the database to schema 7.**
A copy is made before it (`data/studio.sqlite.before-schema-7`; if you start straight from 1.13 you also get the copies for schemas 5 and 6). Nothing here needs a second GPU job at the same time:
a Vector run is an image run (the model draws) followed by a short clean-up on the CPU.

**a) The start-up.** In the build output, the line `check_image: Vector: …` (from `check_image.py`; it is a note and never fails the build): copy it if it says `unavailable` or `cannot make a test file here`.
`ls -l data/studio.sqlite*` shows the `.before-schema-7` copy. **Good:** a third tab **Vector** is there. If it says the libraries are missing instead, send me the line from the build and `docker compose logs studio | grep -i vector`.

**b) A first real run, black and white.** On the Vector tab: prompt *a simple fox head, bold*, Kind **Silhouette**, Colours **2**, size 100 × 100 mm, then **Make vector**.
**Good:** the card says *drawing* and then *tracing*; the preview is the shape in one colour on white; the card says **2 colours, 1 layer**. **Write down** the seconds of the drawing and of the tracing
(the clean-up is on the CPU: the card or `docker compose logs studio` says), `MemAvailable` before and the lowest while it ran, and the `worker_rss_gb` of step 27 (c).

**c) Does the clean-up like real Qwen pictures?** This was the first time the clean-up saw one (until then it had only been tried on constructed pictures). On the card look at the **notes** and the **paths** count; download the SVG and open it in a browser.
**Good:** the shape matches the preview, with no grey fringe and no texture. **Send me** the notes (`specks_removed`, `small_feature`, `hanging_island`, `coarse_drawing`) and a screenshot if the drawing came out with shading,
gradients or text in it (that would mean the model is ignoring the negative words; guidance `4.0` is a guess for this model).

**d) Four colours.** Colours **4**, name **red** and **green** as inks, leave the third to the picture, Kind **Flat**, prompt *a simple flag with three wide bands*. **Good:** the line under Colours says **3 layers**;
the layers are exactly your red and green and one more colour; white has no layer; the table on the card lists each layer's colour, paths and cut length.

**e) The laser software (the reason for all this).** Download the **SVG** and the **layers ZIP** from (d). Open the SVG in **xTool Creative Space** (P2) and in **LightBurn** (G3 Ultra).
**Good:** it measures **100 × 100 mm**; the layers (or colours) appear, one per colour, named like *Layer 2 (red)*; each can be given its own cut or engrave setting; nothing is missing or the wrong colour.
Then the same with a layer's own SVG from the ZIP: it sits at the same place and size, so stacked layers register. **Also do §31.9 item 1 if you have not:** open `docs/laser_test_sheet.svg` in both and answer its six questions
(measures 100 mm? what layers? separate settings? holes and circles right? are outlines taken as lines and fills as areas, and which looks right for cutting? anything missing or joined?). It decides whether shapes are written filled or as outlines.

**f) Side by side and stacked.** Lock the seed, Colours **3**, make one run **Side by side** and one **Stacked** (bleed 0.5). **Good:** side by side, the layers do not overlap; stacked, each lower layer also contains what is above it,
grown by the bleed, so pieces cut from separate sheets would glue up with no gap. Look at both in the laser software.

**g) By shape.** Layers by **Shape** with a picture of several separate pieces: each piece is a numbered layer (*Layer 1 (piece-1)* …) in a distinct colour, up to 30 (more than that: the card says the cap was reached), and *Arrangement* is greyed.

**h) A big sheet.** Press the **xTool P2 bed** preset (600 × 307 mm) and make one run. **Good:** the SVG says `width="600mm" height="307mm"`; the preview has the sheet's shape; a feature smaller than the smallest feature is flagged,
and if the drawing is too coarse for it the card says so (`coarse_drawing`: 1536 pixels over 600 mm is 0.4 mm a pixel).

**i) Housekeeping.** Keep, then Delete: the run goes to **Deleted** with its files (`ls data/vector/` shows its folder); Restore brings it back; Delete forever removes the folder. File it in a Project (step 25): it is kept and locked as any run.

**Send back:** the `Vector:` line from (a); from (b) the two times and the memory numbers; from (c) the notes and any screenshot; from (e) what the P2's software and LightBurn showed (**and the test sheet's six answers**);
the verdict of (f), and anything that did not match "Good".

## 29. Vector versions, the stack view, and pictures by paste (new in 1.18)

Update first: `git pull && docker compose up -d --build`; the title should read **v1.18** (reload with Ctrl+Shift+R). **Back up first: the first start of 1.18 upgrades the database to schema 8**
(one new column, `vectors.deleted_at`, so a single version of a Vector run can go to the bin). A copy is made before it (`data/studio.sqlite.before-schema-8`); `ls -l data/studio.sqlite*` shows it.
Nothing here is a new kind of GPU work, except (k), which is the edit measurement that sets the picture limit.

**a) A Vector run as one card.** Make a Vector run with **Versions 3** (Flat, Colours 4). **Good:** one compact card with a small grid of three previews at the left and one row of buttons
(Reuse, Keep, Project, Delete, **Download…**), about the height of an Images card of three pictures, not three full blocks. Press a preview.

**b) The viewer and the drawing.** **Good:** a large view opens with **The drawing** at the left (*What Qwen-Image drew, 1536 × 1536 px*) and **The vector** at the right, the same size, so you can judge the trace
against what it was traced from; under them the colours line, the layer table, the notes and the downloads; **Escape** closes it, the arrow keys move between the versions, and focus returns to the preview.
**Write down** whether the trace is a fair copy of the drawing. If the drawing is gone (it is not, on a fresh run) the panel says *The drawing is no longer on the disk*.

**c) Delete version.** In the viewer press **Delete version** on version 2. **Good:** a question, then a toast with **Undo**; the card now has two previews, numbered 1 and 2 again (the seeds do not change);
the **Deleted** view shows one card for the run with *version 2, seed N* and **Restore** and **Delete forever**; Restore puts it back **in its own place** (version 2 again). Delete the versions one at a time down to the last:
**good:** the last one sends the whole run to Deleted and says so. Then **Delete** on a card with several versions: **good:** its question says *It has 3 versions. All of them move to Deleted …*.

**d) Stacked (depth), and the Back sheet.** Lock the seed, Colours **4**, **Stacked (depth)**, **Back sheet: The colour with the most ink**, Bleed **0**. **Good:** the viewer has a **Height** column (1, 2, 3) and a
**Stack view** with a **Sheets shown** slider; sliding it peels the sheets off from the front. Make the same run with **The colour with the least ink** and again with **The first ink in my list**.
**Good:** the back sheet is a different colour each time and the heights follow it. **Send me** which of the three you would use, and whether the stack view reads as depth to you.

**e) The laser software.** Download the **layers ZIP** of (d) (most ink at the back) and open the SVG in **xTool Creative Space** and **LightBurn**. **Good:** the back layer is the whole design, each layer in front of it holds less,
and cut from separate sheets they glue up into relief. **Send me** whether the sheets register and whether 0 bleed gave you flush edges or the 0.5 you would rather have.

**f) A run made in 1.17.** Open a Vector run from before the update. **Good:** it opens in the viewer with its drawing and its Height column (each layer as high as its number); **Reuse** fills Back sheet with *The colour with the most ink*.

**g) Pictures by paste.** On the Images tab (all of these on your own browser, on the Spark's address over plain `http`): (1) take a **screenshot** and press **Ctrl+V** (⌘+V) with the cursor in the prompt box, then again
with the cursor on the bare page, then on a button; (2) **Copy image** on a web page and paste it on the bare page; (3) copy a **range from a spreadsheet** and paste it in the prompt box, then in the Options drawer's negative
prompt (don't: the drawer blocks paste, and that is the point; try the history's project name field in the Manage dialog instead); (4) paste **text** only, in the prompt box. **Good:** (1) and (2) add a picture to the tray, once each
(in Edit; in Generate see (h)); (3) the picture wins in the prompt box and the text wins in the other field; (4) pastes as text and nothing else happens.

**h) Generate pastes.** Switch to **Generate**, write a prompt, and paste a screenshot. **Good:** the card turns into **Edit** with your prompt kept, and a toast says *Switched to Edit: 1 picture added. Refer to it as image 1.*
with **Undo**; Undo takes the picture out and returns to Generate. Drop two pictures on the card: the toast counts two.

**i) On a phone.** Long-press the prompt box and choose **Paste**, with a screenshot and with a photo from the gallery. **Good:** as (g). **Send me** whether your phone's keyboard offers the picture at all: that is the browser's doing.

**j) Upscale a picture….** Click **Upscale a picture…**, close the file chooser, press **Ctrl+V** with a screenshot on the clipboard. **Good:** a 4K PNG downloads. Drop a picture on the button (it lights up while it is over it).
Drop two: **good:** it uses the first and says so. Paste a picture on the bare page afterwards: **good:** it goes to the tray, and no upscale starts.

**k) Eight pictures (the measurement).** Set `STUDIO_MAX_INPUT_IMAGES=8` in `.env`, restart, and make **Edit** runs with **6** and then **8** pictures at **1K** (and 4 at 2K if the memory allows), with your LLM server loaded (the other models that share the memory).
**Good:** the tile reads *8 of 8* and is switched off; a ninth is skipped and counted; the run finishes. **Write down** the seconds, `MemAvailable` before and the lowest while it ran, and whether it ran out of memory (the failure card should
say so and suggest 1K or fewer pictures, and the server should stay up). **Send me** whether the model follows **"image 7"** and **"image 8"** in a prompt as it does "image 1" and "image 2", and what to set
`STUDIO_MAX_INPUT_IMAGES` (shipped 4) and `STUDIO_EDIT_WARN_UNITS` (shipped 8; eight pictures at 1K are 8 units and do not warn) to.

**Send back:** the `ls -l data/studio.sqlite*` line; from (b) your judgement of the trace; from (d) the three back-sheet results and your verdict; from (e) what the laser software showed; from (g) to (j) anything that did not match
"Good" and which browser and device; from (k) the times, memory and the numbers you suggest.

## 30. The Prompt builder, with your Ollama (new in 1.19)

**Load it.** 1.19 began on the branch `prompt-builder` and is merged (pull request #41, in the repository's history), so `git pull` on `main` is all you need.

```bash
cd ~/ai-image-studio                                  # your checkout
mkdir -p ~/backups && scripts/backup.sh --no-model ~/backups   # first: the first start of 1.19 upgrades the database to schema 9 (without the models: about 10 GB, and a minute or two)
git checkout main && git pull
```

Then put your Ollama in `.env` (the address stays in this file and nowhere else: the page, the logs and every message leave it out):

```bash
STUDIO_OLLAMA_URL=http://host.docker.internal:11434   # Ollama on the Spark itself; or its address, if it is on another machine
STUDIO_OLLAMA_MODEL=qwen3.8:27b
# leave the rest at their defaults for now: KEEP_ALIVE 5m, NUM_CTX 32768, THINK on, TIMEOUT 120 s, MAX_REPLY 900 s, AT_ONCE 1
```

For a container to reach an Ollama on the same machine, Ollama must listen beyond `127.0.0.1`: on the Spark, `OLLAMA_HOST=0.0.0.0` in Ollama's service (then restart Ollama), and the model must be pulled (`ollama pull qwen3.8:27b`).
`compose.yaml` already maps `host.docker.internal` to the Spark. Then:

```bash
docker compose up -d --build                          # builds this release and reads .env; reload the page with Ctrl+Shift+R: the title shows the version (1.19 or later)
ls -l data/studio.sqlite*                             # note the line: studio.sqlite.before-schema-9 is the copy made before the upgrade
docker compose logs studio | grep -i "schema\|builder" | head
```

**a) The connection.** Open **Prompt builder** (the fourth tab). **Good:** *Ollama is ready: qwen3.8:27b*. Press **Test connection**. **Good:** it lists Ollama's version and its models, says yours is among them, and says whether it can look at pictures
(Ollama's library says `qwen3.8:27b` can). **Check** that the address appears nowhere on the page, and that `curl -s http://localhost:8081/api/capabilities | grep -c -e host.docker.internal -e 11434` (use the port in your `.env`) prints `0`; the capabilities say only whether the builder is `configured`, `reachable` and which `model`.
With `STUDIO_OLLAMA_URL` empty, **good:** the tab says *The Prompt builder needs an Ollama server…* and Saved prompts, Preferences and Projects still work.

**b) A first chat.** Type **a lighthouse in a storm** and Send. **Good:** the chat is in the list at once; a card says *Thinking…* with the seconds and a **Show thinking** fold; then the reply streams, with at most **three questions**, each with 3 to 5 chips.
Tap two chips, add a few words of your own, press Send. Press **Write it now**. **Good:** **The prompt so far** (right) shows the words with the changed ones marked, an editable box, a length meter, the negative prompt, and the settings that fit as chips you can switch off.
Press **Stop** in the middle of a reply: **good:** what was written stays, marked *stopped*, and the prompt so far does not change. **Write down** the time to the first word, the words per second, and how long the thinking took for a plain, a vague and a detailed idea.

**c) Speed while an image is being made.** Start an image run, and while it works send a message. **Good:** the reply card says *An image is being made, so replies may be slower.* and it still arrives. **Write down** the times with the image model loaded and idle, and while it works.
Open a second chat and send while the first is writing: **good:** *Waiting for another reply…*, then it goes.

**d) Does the model keep to the structure?** Put twenty different ideas through the builder (new chat each). For each, note whether the reply came at once, showed *Asking again…* (the studio asked a second time, with thinking off), or came as plain words with no questions and no change to the prompt
(the plain-text fallback). Do ten with **Think: On** (the default) and ten with **Think: Off** (the switch beside Send). **Check** that with Off no *Show thinking* appears. **Send me** the counts. A model that falls back often is the first thing to change.

**e) Do the questions help?** With ten ideas, a plain one, a vague one and a detailed one, judge: are the questions the right ones, are the chips different from each other, is the finished prompt better than what you would have typed? **Send me** what you would change; this decides how much the instruction files (`backend/studio/builder/instructions/*.md`, written by me as a first draft) need.

**f) Save, versions, compare.** Press **Save as prompt**, accept or change the title and the tags, choose a project. Ask for a change (*make it moodier*) and press **Save as new version**; press it again without changing anything. **Good:** version 2, then *Nothing changed.*
Open it in **Prompts**: **good:** both versions, newest first; tick two and **Compare**: the changed words are marked as removed (struck through) and added (underlined), the settings table says what changed; **Make this the current one** on version 1 adds version 3, a copy.
**Flesh out**: **good:** a chat linked to the prompt whose first reply says what it has and what is missing.

**g) Use it in the other tabs.** On a saved prompt (and on The prompt so far): **Use in Images** fills the prompt box, goes to Images, and says what it set (*Filled the prompt, set 16:9, guidance 4 and a negative prompt.*) with **Undo**; the chip *From Prompt builder: "title" v1* shows beside the box.
**Generate now** queues a run at once without changing the Images form; **Quick try** makes a Draft and its picture appears on the version, without leaving the tab. **Good:** the run's card says *From "title" v1* and the line opens the prompt; **Reuse** brings the chip back.
**Send me** whether prompts the builder wrote give pictures you like better than your own (use the Draft quick try, side by side), and what the quick try costs in time.
For **Vector** and **Music**: make a chat **For Vector** and one **For Music**, then **Use in Vector** / **Use in Music**: **good:** the idea, kind, colours, inks and size, or the fields, lyrics and length, are filled, and what the form cannot take is named in the toast.

**h) Pictures.** Attach a photo to a chat (choose, drop, paste on the tab, or **Pick from my history**) and press **Describe as a prompt**. **Good:** a prompt for Images that describes it. **Send me** whether it is sensible. On a finished picture press **Refine in Prompt builder**
(on its card and in the viewer): **good:** a chat opens with the words in the prompt box and the picture attached; say what is wrong (*too dark*) and the reply proposes a new version. In **Edit**, with two pictures in the tray, press **Help me write this**: **good:** the builder opens
*For Edit* with both pictures, numbered, and writes a prompt that refers to *image 1* and *image 2*.

**i) Preferences.** Add *photographic, natural light* in **Preferences**, start a chat. **Good:** the chat says *Using 1 preference* and the prompts follow it; switch it off and it stops. A suggestion (*Remember "…"?*) is added only when you press **Add**.

**j) Memory with everything loaded** (Ollama is on the Spark): run `free -h`, `nvidia-smi` and `ollama ps` with Ollama's model (about 18 GB) **and** Qwen-Image both loaded. **Good:** both fit; if the image model's pre-flight refuses, its message now also says to press **Unload from memory** on the Prompt builder tab.
Press **Unload from memory**: **good:** `ollama ps` shows nothing loaded and `MemAvailable` rises. **Write down** `MemAvailable` before and after, and whether `STUDIO_OLLAMA_NUM_CTX=32768` fits next to Qwen-Image (if not, how much `16384` saves), and what `STUDIO_OLLAMA_KEEP_ALIVE` you want (`5m` ships).

**k) The bin and the backup.** Delete a chat and a prompt; **good:** each asks, moves to **Deleted** (30 days), and **Restore** brings it back; the pictures made from a deleted prompt say *From "title" v1, deleted*. Run `scripts/backup.sh --no-model ~/backups` and check that it says it is packing your history, images, prompts and chats; `tar -tzf` the data piece and look for `data/builder/` (a chat's pictures).

**l) On a phone.** Open the tab on your phone. **Good:** the tab bar does not scroll sideways, *Prompt builder* wraps onto two lines, and a switch (*Chat | Prompt | Library*) shows one column at a time. Send a message, and switch away to *Library* while it is being written: **good:** the reply carries on.

**Send back:** the `ls -l data/studio.sqlite*` line; from (a) what Test connection showed; from (b) and (c) the times; from (d) the counts; from (e) your judgement of the questions; from (g) your verdict on the pictures and from (h) on the description; from (j) the memory numbers; and anything that did not match "Good", with the browser and device.

## 31. The Speech tab: four voice engines, on your Spark (new in 1.20)

When this section was written, nothing here had run on a Spark. The fake engines (a tone for a voice) and a real browser had tried the plumbing; **no real engine had made a sound, and nobody had judged one**. So this section is mostly *listening*, and the notes you send back are about how it sounds and what it costs.

**Load it.** 1.20 began on the branch `speech` and is merged (pull request #43, in the repository's history), so `git pull` on `main` is all you need.

```bash
cd ~/ai-image-studio                                  # your checkout
mkdir -p ~/backups && scripts/backup.sh --no-model ~/backups   # first: the first start of 1.20 upgrades the database to schema 10 (without the models: about 10 GB, and a minute or two)
git checkout main && git pull
docker compose up -d --build                          # builds this release and reads .env; reload the page with Ctrl+Shift+R: the title shows the version (1.20 or later)
ls -l data/studio.sqlite*                             # note the line: studio.sqlite.before-schema-10 is the copy made before the upgrade
grep check_image build.log | grep -i speech          # if you built with a log, as in step 5; else: docker compose logs studio | grep -i "speech" | head -20
```

**What is downloaded, and when.** The engines' *libraries* (Kokoro, Piper, Qwen3-TTS) go into the image when it is built; Voxtral's server is an optional extra (`SPEECH_VOXTRAL=1 docker compose build`, large) and is left out unless you ask. The voice **models are downloaded by the studio itself, the first time each engine loads** (your first **Load speech model**, **Play sample** or **Make reading** with that engine), into the Hugging Face cache that `compose.yaml` mounts (`~/.cache/huggingface`, or `HF_CACHE_DIR`). After that nothing is fetched again (`STUDIO_LOCAL_FILES_ONLY=auto`, as for the other models). **A backup does not hold these models**: it holds your readings and voices, and a restore on a new machine downloads the models again on first use. To avoid waiting in the page, you may fetch a repository beforehand with `hf download <repo>`.

**a) The engines.** Open **Speech** (the fifth tab, after Prompt builder). **Good:** each engine has a pill (*Ready*, *Not installed*, *Needs more memory*) with its reason; the build's `Speech:` lines say the same. **Write down** which engines say *Ready* and the exact reason on any that do not. **Check** that Voxtral says it is not built into the image, unless you built it. **Qwen3-TTS and torchaudio.** On the first Spark run the Qwen3-TTS pill said *not installed* with `No module named 'torchaudio'` (Kokoro and Piper were *Ready*; Voxtral was not built). `qwen-tts` imports torchaudio at the top of a module that only its old 25 Hz tokenizer uses, and NVIDIA's image has none for the Spark. The build now makes that one import optional in its own copy of the library (`docker/patch_qwen_tts.py`; DESIGN section 38.18, item 72), so after a rebuild the pill says *Ready* (confirmed on the first Spark that had the patch): `grep patch_qwen_tts build.log` shows `patched` (or `already patched`). **If it still says *not installed*** and the reason names a package, send me the pill's exact words, the build's `Speech: qwen3-tts:` line, and the last lines of `docker compose exec studio env PYTHONPATH=/opt/speech-libs/qwen3-tts python -c "import qwen_tts"`, which name the next thing that is missing.

**b) The first load of each engine.** For each engine in turn (Kokoro, Piper, Qwen3-TTS): choose it, press **Load speech model** (or **Play sample** on a voice). **Good:** the pill says *Loading…* for as long as the download takes, then the engine is loaded; `docker compose logs -f studio` shows no error. **Write down** the time to download and to load, and the size added to the cache (`du -sh ~/.cache/huggingface/hub/models--*` before and after). Then press **Unload** and **Load** again: **good:** quick, with no download.

**c) Voices and samples.** In Kokoro, press **Play sample** on a few voices. **Good:** the first press makes the fixed sentence (*"Good evening. This is how I will sound when I read to you."*) and plays it; the second plays the kept file at once. **Check** that every voice says its accent where its source states one, and *Accent not stated* where it does not, and that no voice is called American, British or Irish by its name alone. In **Piper**, the **Jenny** voice is the one you asked about: **write down** what accent you hear.

**d) A reading.** Paste two or three pages and press **Prepare text**. **Good:** the review shows the parts, with their length in minutes; **Make reading** says what it will do (*"3 parts, about 11 min of audio, about 30 MB. Kokoro-82M, Heart."*). Press it. **Good:** a card appears at once with a bar (*Part 1 of 3 · paragraph 4 of 40 · 2 min made*), and after the engine has run once, *about N min to go*. **Press Listen while it is being made.** **Good:** the text opens paragraph by paragraph, the spoken paragraph is marked and kept in view, it plays what is made and, if you catch up with the maker, says *Waiting for the next paragraph to be made…* and carries on by itself. **Listen at each paragraph boundary: is there a gap, a click, or a change of pitch?** (This is the one thing no stand-in could tell us.) **Write down** how many seconds of work each second of audio takes (the card's minutes made against the clock), for each engine, and the lowest `MemAvailable` (`free -h`) while it works.

**e) Playing it.** On the finished card press **Listen**. Try: Pause and Play; the **15-second** buttons; **Previous** and **Next paragraph** (and `J`, `K`, Space and the arrow keys when focus is in the player); the **speed** at 0.75×, 1.5× and 2× (**good:** the voice does not go up in pitch); the four **text sizes** and **Wider line spacing**; **Follow along** off and on; a click on any paragraph. **Drag the slider into the middle of a part of half an hour or more** (make one from a long text): **good:** it plays from there within a second or two (this is a WAV the server builds as it sends it, and seeking into it is by range request: **write down** how long a seek takes).

**f) A book.** Prepare an **EPUB** with chapters, and a long **PDF** (with bookmarks, and one that is only scanned images). **Good:** the EPUB is cut into parts by chapter and the review lets you **Include**, **Rename**, **Merge with next** and edit a paragraph; a scanned PDF is refused with *no text layer*. **Check** the summary for the book (*"12 parts, about 11 h 20 min of audio, about 2 GB"*) and, if you can, make the whole book. **Write down** the time, the disk it used, and whether the page stayed usable. **Good:** stop the container halfway (`docker compose restart studio`) and open the page: the reading says it failed because the worker stopped, keeps every finished piece, and **Retry** carries on from the piece after.

**g) The place, on two devices.** Listen for a minute on the computer and press Pause. Open the studio on your phone. **Good:** the card says **Continue listening from 1:12 in part 1** (or where you stopped), and plays from there. Listen on the phone, then look at the computer: **good:** the same place.

**h) On a phone.** Open the tab on your phone. **Good:** the tab bar does not scroll sideways, the Source box, the voice list, the cards and the player fit, and the player's buttons stay on screen. **Lock the screen while a reading plays.** **Good:** the lock screen shows the reading's title, the part and the voice, with play, pause, back, forward, previous and next. **Write down** what your phone and browser are, whether Safari asks you to press **Play** (*"Your browser wanted a press before it would play sound"*), and whether the sound stops when the screen locks.

**i) Qwen3-TTS: a style, a designed voice, your own voice.** Choose Qwen3-TTS. **Style:** type *calm and warm, like an audiobook narrator* and make a short reading; then another with no style. **Write down** whether the style is audible. **Design a voice:** *a warm Irish woman in her forties, unhurried, clear* → **Make three samples**. **Good:** three clips of the same passage that differ from each other. **Write down** whether any sounds Irish (nothing is promised: it is an open question). Save one and use it for a short reading. **Add my voice:** read the passage aloud on your phone, upload the file. **Good:** a recording that is too short or silent is refused in the server's words; a good one can be heard back, can be heard speaking (*Hear it speak*), and is saved only after you tick the statement and give a name. **Write down** how close the cloned voice is, the time to make a reading in it, and which file kinds your phone's chooser offered (WAV, MP3, M4A…). **Rename** and **Delete** a voice: **good:** Delete asks first and says readings already made keep their audio.

**j) Voxtral** (only if you built it with `SPEECH_VOXTRAL=1`). **Good:** its pill says *Ready*; the first load downloads about 8 GB, and its server starts with a share of the GPU's memory (`STUDIO_SPEECH_GPU_FRACTION`, 0.2 by default: an estimate). **Write down** the download time, whether the server started at that share (if not, the log line and what happened), the memory, and the quality against Kokoro. **Check** that its licence badge says non-commercial.

**k) Sharing the Spark.** While a reading is being made, press **Generate** on Images and **Play sample** on another voice. **Good:** the sample goes ahead of waiting readings but never ahead of the part being made; the image waits its turn in the queue; the reading carries on afterwards from the next part. **Write down** how long the model swaps take each way (speech to image to speech), and `free -h` and `nvidia-smi` with each engine loaded alone and after **Unload**.

**l) Downloads and the file's note.** On a finished reading press **Download**. **Good:** a ZIP of the parts with a `playlist.m3u`; open it in a player on your phone. Download one part's WAV from the player's parts list. **Check** its name (`reading_the-title_part03_af-bella_20261108.wav`) and that `ffprobe` shows a note in its file information naming the engine and the voice (a cloned voice says it was made with the speaker's agreement).

**m) The bin, projects and the backup.** **Delete** a reading: **good:** it asks, goes to **Deleted** for 30 days, **Restore** brings it back, and it can be **filed in a project**. A reading is always kept (there is no Keep button). Run `scripts/backup.sh --no-model ~/backups` and look inside the newest one: `tar -xOf "$(ls -t ~/backups/ai-image-studio-backup-*.tar | head -1)" data.tar.gz | tar -tz | grep "data/speech" | head` (a backup is one `.tar` that holds `data.tar.gz`). **Good:** it lists readings and voices. The speech models that you have downloaded **are** in a backup (the studio decides which from `STUDIO_SPEECH_ENGINES` and the `STUDIO_SPEECH_<ID>_MODEL` settings). Check it without making a backup of tens of GB: `scripts/backup.sh --dry-run ~/backups`. **Good:** the `models:` summary lists each speech model you have used, for example `Qwen3-TTS CustomVoice: hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice`, and one line names those not downloaded yet (*each downloads the first time its engine is used*). **Write down** the total it gives for `models:` and how long a real backup with the models takes.

**Send back:** the `ls -l data/studio.sqlite*` line; from (a) the pills and any reasons; from (b) the download and load times and the cache sizes; from (c) the accent you hear in Jenny; from (d) the seconds of work per second of audio for each engine, the lowest `MemAvailable`, and **whether there was any gap, click or pitch change between paragraphs**; from (e) how long a seek in a long part took; from (f) the book's time and disk use and what the restart showed; from (g) and (h) your phone, whether the place and the lock screen worked, and whether Safari wanted a press; from (i) your judgement of the style, the designed voices, the clone and the file kinds your chooser offered; from (j) the Voxtral numbers; from (k) the swap times and memory; from (l) whether the ZIP and the note were right; and anything that did not match "Good", with the message the page or the log showed.

## 32. Load progress: watch a real download (new in 1.21)

The server says how far a model's load has got, and the page shows it (the header pill, the cards, the Speech tab, the voice dialogs). Items a to g read it from a terminal; item h is the page. When this section was written, **nothing here had been seen on a Spark**: the watcher had been tried with fake downloads and against the real downloaders in a sandbox, not with your models. This is where that is checked.

**Watch it.** In one terminal, leave this running:
```bash
watch -n 1 "curl -s localhost:8081/api/status | python3 -c 'import json,sys; w=json.load(sys.stdin)[\"worker\"]; print(w[\"state\"], w[\"model\"], w[\"engine\"], w[\"variant\"]); print(w[\"progress\"])'"
```
In another, `du -sh ~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-*` (or whichever model is loading) shows what is really on disk.

**a) A first download.** Pick a checkpoint you have never used (for example **Design a voice**, which needs `…-VoiceDesign`; **Make three samples**). **Good:** the `progress` line goes from `phase: starting` to `phase: downloading` with `done_bytes` rising and `total_bytes` set (the Hub's size), then to `phase: loading` with only `elapsed_s` rising, then the state is `ready` and `progress` is `None`. **Write down:** the `total_bytes` it gave, and the size of that model's folder on disk when it was done (`du -sb`): **are they the same?** If the total is bigger than the folder, the Hub lists files the library does not fetch, and I will drop the total for that model.
**b) The pattern of the download.** **Write down** whether `done_bytes` rose steadily or in big steps (the default downloader, `hf_xet`, writes in bursts), and whether `phase` ever said `loading` in the middle of the download. It should not: a file that is arriving counts as a download however slowly it grows.
**c) A model that is already downloaded.** Unload it (**Unload model**) and load it again. **Good:** `phase: loading` from the start, `done_bytes` at its full size, `elapsed_s` rising. **Write down** how long a load from disk takes for each kind of voice (preset, designed or cloned, **Design a voice**): this is the reload you asked about.
**d) What made room.** Load a preset voice, then use a voice you designed. **Good:** `progress.after` says `speech:qwen3-tts:custom` while the `clone` checkpoint loads, and is `None` once it is ready.
**e) The other models.** Load the **image model** and the **music model** once each (`Load model` on each tab). **Good:** the same line. **Write down** whether the image model's `total_bytes` matches its folder (about 31 GiB), and the same for music (about 29 GB).
**f) Kokoro and Piper.** Load each if you have not: **Good:** `downloading` with `done_bytes` and **`total_bytes` None** (no size is offered for them).
**g) Voxtral** (only if built). **Good:** `downloading` while its server fetches the model, then `loading` for as long as the server takes to start. **Write down** whether `done_bytes` rises (the server writes into the same cache).

**h) The page.** While (a) is running, look at the page. **Good:** the header pill says `Loading speech model… · 2.1 GB of 4.5 GB` (and `· 40 s` while it loads into memory); the pill's panel and the Speech tab say *Downloading Qwen3-TTS for designing a voice* with a bar that fills; **Design a voice** says the same under *Making three samples…*; where another checkpoint was in memory, *Qwen3-TTS for preset voices was unloaded to make room.* is there. Then load the image model (or make a track) from a cold start: its card says the same instead of *the first load takes a while*. On a phone nothing runs off the screen. **Write down** anything wrong, unclear or too busy, and whether the number rises often enough to look alive.

**Send back:** from (a) the two sizes; from (b) steady or in steps, and any wrong `loading`; from (c) the load times; from (d) the `after` it showed; from (e) and (f) the sizes and any `total_bytes` that was wrong or missing; from (g) whether it rose; from (h) what the page showed.

## 33. Reorder the queue (new in 1.22)

When this section was written it had been tried in unit tests, in a real browser with the fake pipeline, and with a finger sent through the browser's protocol; **not with your models, and not with a real thumb.** This is where that is checked. You need a job that takes long enough for others to wait behind it: a full-size image run of several pictures does it.

**a) Drag.** Start a long image run (for example 4 pictures at full size). While it goes, make three more jobs, one of them a **Draft**, one a **music** track and one a plain image (they wait behind the first). The header shows **Queue** and a count. Open it. **Good:** the job that is going is at the top with a lock; the three waiting jobs are listed with their place, their kind (**Image**, **Music**, **Drawing**, **Speech** or **Voice**) and their words, and the draft is first (a draft jumps the line when it arrives). Drag the last job by its grip to the top. **Good:** a line shows where it will land; when you let go it is first; the cards' **Queued · #n** change to match, **and the cards on the Images tab move too**: the job that is going first, then the waiting jobs in queue order, then your history. A job you make now goes to the end of the waiting cards, not to the top.
**b) The order they are worked on.** Let the long run finish. **Good:** the jobs start in the order the panel showed. **Write down:** whether anything started out of that order.
**c) Your order wins over drafts.** Drag a full-size job above the draft. **Good:** it stays there, and runs first. Make another draft. **Good:** the new draft goes to the very **front** of the line, and the job you placed is still ahead of the first draft.
**d) What cannot be moved.** **Good:** the job that is going has no grip and no arrows. A **reading** that has made a part and is waiting for its next turn shows a lock and cannot be dragged, but another job can be dropped before or after it. If a job starts while the panel is open, its grip and arrows are gone within a moment; if you were dragging it, nothing happens when you let go.
**e) The arrows and the keyboard.** Use **Tab** to reach a job's *Move up* arrow and press **Enter**. **Good:** it moves, focus stays on a working arrow, and a screen reader (if you use one) says *Moved “…” to place 1 of 3.*
**f) Two screens.** Open the Queue on your phone and on a computer. Move a job on one. **Good:** the other shows it within a second or two, without you touching it.
**g) Your thumb.** On your phone, drag a job by its grip. **Good:** it drags instead of the page scrolling, and nothing runs off the screen at the width of your phone. **Write down:** whether the grip is easy to hit and whether you reached for the arrows instead.
**h) A model swap.** Put a **music** track ahead of an **image** job and let them run. **Good:** the studio swaps models (the pill says it is loading the other one), and the Queue panel keeps the order you made. **Write down:** how long the swap took.

**Send back:** from (a) to (c) whether anything was in an order you did not expect; from (d) what a started reading looked like; from (g) your thumb's verdict; from (h) the swap time and anything surprising.

## 34. More like this, compare, and the experiment for variations of a picture (new in 1.24)

When this section was written it had been tried in unit tests, in a real browser with the fake pipeline (whose pictures are plain patterns) and against the real server code; **not with your models.** Parts a to g need only the model you already use. **Part h is the experiment** that decides whether *Variations of this picture* is ever switched on: it is off until you do. The database is upgraded on first start, with a copy made first: after the first start, `ls -l data/studio.sqlite*` should show **`studio.sqlite.before-schema-11`** next to the database.

**a) More takes, from a card.** Make a picture you like (any size you normally use). Press **More like this** on its card. **Good:** a dialog opens with **More takes of the prompt** chosen, **Variations of this picture** greyed with the words *Not tried on this machine yet*, **Pictures** at 4, your own words in the **Words** box, and a line saying what will be made (the size and steps of that run). Press **Make**. **Good:** the dialog closes, a toast says it is queued, and a **new card** appears with 4 pictures: each different from the first picture and from each other, in the same subject and style because the words are the same. Its first chip reads **Variation of “…your words…”**; the original card now has a chip **Variations (1)**. **Write down:** the time for the 4 pictures, whether they look like takes of the same idea, and whether any was a copy of the original (none should be: the seeds are new).
**b) From the viewer.** Open one of the original's pictures in the viewer and press **More like this** there. **Good:** the same dialog and the same request as (a); the new run is linked to the original in the same way (its chip says the same). Change the **Words** (add a colour, say) and make 2 pictures. **Good:** the 2 pictures follow the changed words; the original's words on its card are untouched.
**c) The family.** Press the **Variations (2)** chip on the original. **Good:** the history shows only the original and the two runs made from it, and a pill **Variations of “…”** with a close button; a Kept filter you had on is cleared inside it (the view is the whole family, not only its kept runs). Press the pill's button: the whole history is back. Press the chip again and **reload the page**: **Good:** the page opens on the whole history (a family is a place you went to, not a setting).
**d) The source goes away.** Send the original to the **bin** (Delete on its card). **Good:** the variations stay, and their chip now reads **Variation of a run in the bin**; **More like this** is not offered on the original in the bin. Restore it: the chips read as before and the original's count comes back. Delete a variation: **the original's count goes down** (on this page and on any other you have open). **Write down:** anything that stayed wrong until you reloaded (a count may lag a moment after the daily clean-up of the bin or **Empty bin**, which can remove many runs at once, and a reload fixes it).
**e) Two screens.** Open the page on your phone and on a computer. Make a variation on one. **Good:** the other shows the new card and the **Variations (n)** chip on the original within a second or two, without a reload.
**f) Compare.** Open one picture in the viewer and press **Add to compare**; close the viewer; a bar **Compare · 1 chosen** is at the foot of the page. Open a picture from **another run** and add it too. **Good:** the bar says **Compare · 2 chosen** and its **Compare** button works. Try to add a third: **good:** the viewer says in words that the basket holds two and offers **Replace the first**. Press **Compare**. **Good:** the two pictures side by side, each labelled with its words, seed and size; **Slider** lays one over the other, and the divider moves with the mouse, with a finger and with **← →** (5% at a time), **Page Up/Down** (10%) and **Home/End**; **Fit** and **100%** zoom both pictures together and panning one moves the other; **Swap sides** swaps them. Press **Keep this one** on the picture you prefer. **Good:** it says **Kept** and that run is Kept (check its card); the other picture's run is as it was. **Write down:** whether you could tell the two pictures apart at 100% with the slider better than side by side, and whether anything was hard to hit with your thumb.
**g) Your phone.** On your phone (or a window 360 px wide), open the **More like this** dialog, the compare bar and the compare view. **Good:** nothing runs off the screen; side by side stacks one above the other; the slider works by touch. **Write down:** what did not fit, with a screenshot.

**h) The experiment: variations of a picture.** Do this only if you want the second choice at all. In `.env` set `STUDIO_VARIATIONS_FROM_PICTURE=true`, then `docker compose up -d` again. **Good:** the dialog now offers **Variations of this picture** for the picture on the screen in the viewer (from a card it is offered only for a run with a single picture, and says so otherwise). It makes an **edit** run with that picture as its only input and the words in the box, at the picture's own size. Do this on **five of your own pictures**, four variations each, and look at them side by side with the original (use compare). **Write down for each:** are the variations recognisably the same subject and style, and **not four copies of the original**; does the composition change; how long one took, and whether a model swap was needed (the pill says so); and what happens when the words name a change ("the same, at night"). If the results are poor, switch it back off (`false`) and say so: I will either tune what is sent with the picture and the number of steps, or leave the choice off for good.

**Send back:** the `ls -l data/studio.sqlite*` line; from (a) the time and your verdict on the takes; from (c) and (d) anything that did not match "Good"; from (e) whether the other screen followed; from (f) your verdict on side by side against the slider, and your thumb's; from (g) a screenshot of anything that did not fit; and from (h), if you ran it, the five pictures' verdicts and the times.

## 35. Audiobook polish for Speech: respellings, several voices, chapter marks (new in 1.25)

When this section was written it had been tried in unit tests, in the server's tests with a **real ffmpeg**, and in a real browser with the fake speech engines (which make tones); **no real engine had spoken any of it**, so every question about sound is yours. The database is upgraded on first start, with a copy made first: after the first start, `ls -l data/studio.sqlite*` should show **`studio.sqlite.before-schema-12`** next to the database. Use the engine you like best for a, b and c, and a second for d. **Rebuild the image first** (`docker compose build`): the build's `check_image:` lines now include one that says whether ffmpeg has an AAC encoder; **Good:** the line `check_image: Speech: ffmpeg has an AAC encoder (the audiobook file can be made)` (after the `Speech:` line that gives ffmpeg's version). Write down the line if it says anything else.

**a) The pronunciation list.** On the Speech tab press **Pronunciation list**. Add `Nguyen` → `win`, then **Try it** with *"Nguyen's winter was long."* **Good:** the words below say *"win's winter was long."* (the whole word only, and `winter` is left alone). Add `US` with **Match capitals exactly** ticked, as `you ess`, and try *"Tell us about the US."* **Good:** only the second is changed. **Write down:** nothing yet; now the sound.
**b) How respellings sound.** Prepare a short text that has your own hard names in it (a person's, a place's, a medicine's: five of them). With **no entries**, make the reading in your favourite voice and listen: **write down which words were wrong**. Add one entry for each as a respelling in plain letters (the way you would say it to a child: `win`, `nuh-GWEN`, `kuh-NEE-tuh`), make the reading again, and listen. **Good:** the words are now said as you spelled them, and **the text you read along with is still the original spelling**. **Write down:** for each word, **which spellings worked and which did not**, in this engine (hyphens, capitals and doubled letters are what to try). **Then make the same reading with another engine** and write down which of the respellings that worked in the first still work. That is the question the list cannot answer from here: it is one list for every engine, and plain respellings are not the engines' own phonemes.
**c) The list is kept by the reading.** With a reading that is made, change one entry's respelling and press **Make reading** again on the same text. **Good:** the new reading uses the new respelling, the old reading's audio is untouched when you play it, and the card of each says how many entries it used.
**d) Several voices.** Paste a short script with three names, two of them speaking at least twice and some lines with no name at all:

```
It was a quiet night at the lighthouse.

Alice: Did you hear that?
Bob: Hear what? The wind?
Carol: I heard it too, down by the door.
Alice: No, a knock, three times.
Bob: Then go and open the door yourself.
Carol: Not me, I am not going.
The sea went on without them.
```

Press **Prepare text**. **Good:** a **Speakers** list names **Alice, Bob and Carol** with their line counts (2, 2 and 2), each ticked and set to **Main voice**; the text shows the names beside their lines, and the two lines with no name stay the narrator's. (A name needs two lines before it is offered, which is why the script has no `Narrator:` line.) Give Alice and Bob each a voice you can tell apart from the main one, leave Carol on the main voice, and make the reading. **Good:** the lines are read in the voices you chose, the line with no name in the main voice, and the names themselves are not spoken. **Write down:** **whether the voices change cleanly between lines** (any click, gap, change of loudness or hurry at a change of voice), **whether the pause between two speakers feels right** (too slow, too quick; this is the only pause that has never been heard), the time it took compared with the same text in one voice (the first use of each voice may cost something), and how the engine's voices were offered (Qwen3-TTS should offer only its presets, or only your own voices, matching the main voice, with a line saying why; Piper should say it has one voice).
**e) False alarms.** Prepare a text that is not a script: an article with one *Note:* line, a time (`The meeting is at 10:30`), a web address, and a line that starts `Remember: lock the door`. **Good:** no Speakers list appears (one name, or a label from the list of labels, is not a speaker). Then prepare a text where one name wrongly looks like a speaker (a recipe whose two steps start `Sauce:`, with a second repeated label such as `Dough:`): **Good:** the list shows them, and **unticking a name makes its lines read as written, label and all**. **Write down:** any ordinary text of yours that got a Speakers list it should not have, and the names.
**f) Chapter marks in the ZIP.** Make a reading of your own book (or a long text) in at least four parts and let it finish. Press **Download** on its card and open the ZIP. **Good:** beside the part files and `playlist.m3u` there are **`chapters.txt`** (one `HH:MM:SS.mmm Title` line per part, the first at `00:00:00.000`) and **`chapters.ffmetadata`**. Play the parts one after another in a player that shows the time (or join them: `for f in …; do echo "file '$f'"; done > list.txt; ffmpeg -f concat -safe 0 -i list.txt -c copy joined.wav`) and **write down whether each chapter starts where chapters.txt says** (by ear, at two or three places).
**g) The M4B.** On the reading's card (and in the player) press **Make audiobook (M4B)**. **Good:** the button shows progress (the share made, and the part it is in), then a **Download audiobook (M4B)** link with the size. **Write down: how long it took for the whole book** and the file's size (about 29 MB an hour at the default 64 kbit/s), and whether the studio was slow to answer meanwhile. Open the file in **every player you use** (the Books app on a phone, Audiobookshelf, VLC, your car) and **write down: does it show the chapters with the part titles, do they jump to the right place, does it resume where you stopped, does it sound as good as the WAV** (try `STUDIO_SPEECH_AUDIOBOOK_KBPS=96` in `.env` if not). Press the button again straight away: **Good:** the same file is offered at once, with no second build. Start a long reading, press it while parts are still being made: **Good:** it says *"n of m parts so far"* and the file has those parts.
**h) Without the encoder.** (Only if you want to see the words.) In `.env` set `STUDIO_SPEECH_FFMPEG=/nonexistent`, `docker compose up -d`: **Good:** the audiobook button is greyed and says in words that the file needs ffmpeg with an AAC encoder, and **the ZIP still downloads with its chapter lists**. Put the setting back.
**i) Tidy up.** `ls -l data/speech/audiobooks/` shows the M4B you made; **Good:** it is gone a day after you last took it (or, to see it sooner, `STUDIO_SPEECH_TEMP_HOURS=1` and wait an hour); the next backup (`scripts/backup.sh`) does **not** contain it.
**j) Your phone.** On your phone (or a window 360 px wide) open the **Pronunciation list** dialog, the **Speakers** list in a review and the audiobook button. **Good:** nothing runs off the screen and every control can be pressed with a thumb.

**Send back:** the `check_image:` ffmpeg line and the `ls -l data/studio.sqlite*` line; from (b) the table of which respellings worked in which engine; from (d) your verdict on the voice changes and the pause, and the times; from (e) any false alarm; from (f) whether the chapter times matched by ear; from (g) the build time, the size, and for each player whether the chapters and the resume worked; and a screenshot of anything on the phone that did not fit.

## 36. Search and tags across history, with your Ollama and your real history (new in 1.26)

When this section was written it had been tried in unit tests, against a fake Ollama that answers in the right shape, and in a real browser with the fake pipeline and a scripted model; **not with your Ollama, your models or your real history.** Parts a, c to g and i need only what you already run; **part b needs your Ollama** (the Prompt builder's `STUDIO_OLLAMA_URL` and `STUDIO_OLLAMA_MODEL`, section 30). The database is upgraded on first start, with a copy made first: after the first start, `ls -l data/studio.sqlite*` should show **`studio.sqlite.before-schema-13`** next to the database, and the log should say the runs were indexed (`indexed N runs for search`).

**a) Your real history is found.** Open the page, pick any tab, and type a word you know is in an old prompt (one from a month ago, say) into the **Search** box. **Good:** the old runs that have the word come up, newest first, and the number beside **All** is the number of runs found (it says *12 results* beside the box); **Load older runs** reads more if there are more than a page. Try a word from a **music** run's lyrics on the Music tab, and the **file name** or the **web address** of a reading on the Speech tab. **Write down:** any run you expected and did not get (with its words), and how long the first search took to answer (the page says nothing; count the seconds). Then type a few odd things: `"fox`, `fox*`, `fox AND hen`, `-fox`, `a:b`, and a single `(`. **Good:** each answers with a list or *No runs match*; **none shows an error**.
**b) Suggest, with your Ollama.** Open the **Tags and notes** editor on a picture you know well and press **Suggest**. **Good:** the button says *Asking…* for a few seconds and then a row of up to **5 suggested tags**, each a button with a +; **none is added by itself**; pressing one adds it and it leaves the row; **Dismiss** clears the row. Try a run of each kind (a picture, a track with lyrics, a drawing, a reading). **Write down:** the seconds a press takes with the image model **loaded and idle**, and with a picture **being made**; whether the tags are ones you would use (say how many of five); whether it reused the spelling of your own tags; and whether anything it suggested was a word that is not in the run at all. Then check `free -h` / `nvidia-smi` and `ollama ps`: **write down** whether Ollama's model is now loaded next to the image model, and whether the image model's next load refused for memory (the message points to **Unload from memory** on the Prompt builder tab; the studio never unloads Ollama's model itself).
**c) Suggest says why it cannot.** Stop Ollama (or set a wrong address in `.env` and restart) and open the editor. **Good:** **Suggest** is **greyed with the reason beside it** (*Ollama can't be reached…*), and **typing a tag still works**. Remove `STUDIO_OLLAMA_URL` altogether: **good:** it says *Needs the Prompt builder's Ollama…*. Set `STUDIO_TAG_SUGGESTIONS=0` with Ollama running: **good:** it says Suggest is switched off.
**d) Tags and notes on every kind of card.** Tag a picture, a track, a drawing and a reading (type `fox, winter`; use the autocomplete for a tag you used before), and write a note on one. **Good:** the chips and the note show on the card, **survive a reload**, and show on a second screen within a second or two; the same editor is in the **picture viewer** and the **Vector viewer** (button **Tags and notes**), and **Esc closes the panel before the viewer**. Search for one of the tags and for a word of the note: **good:** that run is found. Delete a run (to the bin): **good:** its tags and note stay visible there but cannot be edited; **Restore** it and edit again.
**e) The filters.** With a search on, press **Filters**. **Good:** **Model** lists the models of this tab's history with counts; **Size** (Images only) lists the sizes with counts and names the shape where it is one of the studio's; **From** and **To** take dates. Choose a model, a size and a range together with a word: **good:** each narrows the others, and the numbers beside **All**, **Kept** and **Deleted** follow (they count what matches). **Clear filters** puts everything back.
**f) Your time zone.** On the page, choose **From** and **To** as the same day, one on which you know you made runs late in the evening (after 8 p.m. your time) and one early in the morning. **Good:** the runs you made that day, by your clock, are all there, none from the evening before or after; and the same on the phone if it is in another zone. **Write down** the time zone of the Spark, of the computer and of the phone, and any run that was on the wrong side of midnight (with its time as the card's tooltip shows it).
**g) What is remembered.** Set a search, a model and a range, then reload. **Good:** they are gone (the history shows everything), while the **Show** choice and the **Project** you had are as you left them. Open another tab with the search on: **good:** the words and the dates are still there; the Model and Size are that tab's own.
**h) Search while you work.** With a search on, make a new picture whose words do not match it. **Good:** its card appears at the top with *Shown while it works. It stays in this view only if it matches.*, and a toast says it does not match when it finishes. Remove the tag a run was found by, while it is in the results: **good:** the card leaves with a toast and **Undo**.
**i) Your phone.** On the phone (or a window 360 px wide) open the filter bar's **Search** and **Filters**, the editor on a card and in the viewer, and the suggestion row. **Good:** nothing runs off the screen, and every control is reachable with a thumb. **Write down:** what did not fit, with a screenshot.
**j) Speed with a big history.** If you have more than a few thousand runs: search for a common word and for a rare one and flip between **All**, **Kept** and **Deleted**. **Write down:** whether the list and the counts feel quick (the counts are one query for each tab and Show choice over the index; the page asks 250 ms after you stop typing).

**Send back:** the `ls -l data/studio.sqlite*` line and the log's indexing line; from (a) any run that was not found and the odd inputs that gave anything but a list; from (b) the seconds, your verdict on the tags, and the memory numbers; from (c) the three greyed messages; from (d) and (e) anything that did not match "Good"; from (f) the time zones and any run on the wrong side of midnight; from (g) and (h) anything that did not match "Good"; from (i) a screenshot of anything that did not fit; and from (j) your feel for the speed.

## 37. LTX-2.5 on your Spark: the experiment before the Video tab (new in 1.27)

**When this section was written nothing of the Video tab was built** (it is built now, in 1.27: section 39 runs it; this section stays what it was, the measurement of the model by itself, outside the studio). There was no tab, no route and no database change; what you had was a design (`DESIGN.md` §46) that **could not be settled until the model itself had been measured on your machine.** So this section is a measurement of LTX-2.5 **by itself, outside the studio**, in a folder of its own, and what you send back decides the design: whether one clip can be about 30 seconds long in one pass (design A), or whether a long clip has to be several shorter clips chained and stitched (design B), or neither (`DESIGN.md` §46.5). **I am not telling you it will work.** Lightricks' model card does not say whether the model runs on a DGX Spark (arm64), how much memory it needs, how long a clip it can make, or how large its files are; every one of those was an **UNKNOWN** that this section turns into a number or a word.

**Status (2026-11-23): you have run most of it, and the commands below are now the ones that really worked.** Each lettered step ends with a line *Run by you* or *Not yet run* saying what was done; the numbers are in `DESIGN.md` §46.18 and are not repeated here. **Done:** (a), (b) warm, (c), (d) the three lengths, (e) the first-frame clip. **Not yet run:** (f), (g), (h) with speech, (i), (k) (`step4b.sh`), strength 0.6 and start-plus-end in (e), the options of (d), a cold load. **No result is claimed here for a step marked *Not yet run*.**

What the model card does say (and that I used to write the commands below; `DESIGN.md` §46.3 has the full table with sources): LTX-2.5 is a 22-billion-parameter open-weights model from Lightricks that makes video **and its sound in one pass**, from text or from one or more pictures; the card says width and height must be **multiples of 32**, **but the program's own `--help` says "divisible by 64"; use 64** (every multiple of 64 is also one of 32), and the number of frames must be **8n + 1** (so 121, 241, 481 and 721 are all allowed: 8×15+1, 8×30+1, 8×60+1, 8×90+1). The card's examples use 121 frames at 24 frames a second, which is a little over 5 seconds (120 ÷ 24 = 5). **720p is 1280×720, and 720 is not a multiple of 64** (11.25 × 64), so **1280×704** is used below; it is the nearest allowed size under 720 (11 × 64 = 704), and it is the size every long run used.

**Rules for the whole experiment**

* **Check each flag with `--help` first; flags change.** `uv run python -m ltx_pipelines.distilled --help` on your Spark shows: required `--prompt`, `--output-path`, `--spatial-upsampler-path`, and either one monolith (`--distilled-checkpoint-path` and `--gemma-root`) or **the split layout used below** (`--transformer-path`, `--text-encoder-path`, `--video-vae-path`, `--audio-vae-path`; `--duration-head-path` is optional). Others: `--seed` (default 10), `--frame-rate` (default 24.0), `--num-frames` (8\*k+1), `--auto-duration MIN MAX`, `--width` and `--height` (divisible by 64; defaults 1536 × 1024; **they are the final size of the file**), `--image PATH FRAME_IDX STRENGTH [BINDING] [CRF]`, `--quantization {fp8-cast, fp8-scaled-mm, nvfp4-cast, nvfp4-prequant}`, `--offload {none, cpu, disk}`, `--chunked` (with `--chunk-pixel-frames`, `--chunk-carry-frames`, `--chunk-blend-frames`), `--lora`, `--enhance-prompt`, `--hdr`, `--compile`, `--diffvae-optimization` and more. **Write down the exact command you ran for every measurement.**
* **Run it all on the Spark, as your normal user, in a folder of its own** (`mkdir -p ~/ltx-experiment`), **not inside the studio's container and not in the studio's folder.** Stop the studio while you measure (`docker compose stop` in the studio's folder) so that its models do not hold memory; part (i) is the one place where it runs on purpose. **Harmless noise:** every `uv run` prints "Uninstalled 1 package ... Installed 1 package", and the program prints `nanobind: leaked ... OpenImageIO` warnings when it exits; neither is an error. The DiffVAE also warns that `natten` is not installed and falls back to a slower backend; that was left as it is.
* **Time and memory come from `scripts/measure_run.sh`** (the repository's measuring script, used as `"$MR" -o FILE.csv -- COMMAND ...`; `"$MR" --help` says the rest). It runs the command, records the seconds, the command's exit status and, every 2 seconds, the memory in use on the whole machine, the lowest memory still available (`MemAvailable`; the Spark's CPU and GPU share one pool of memory, `DESIGN.md` §9a) and, where `nvidia-smi` can say, the GPU memory, and prints one paragraph at the end. **A figure it cannot read it writes as "not available"**; do not fill it in. Ctrl-C stops the command and still prints the summary. For the times of things that are not one command (a download you start by hand, a step you do by eye) **write down the time with `date '+%F %T'` before and after; do not remember it.**
* **Your settings file.** All the commands below read `~/ltx-experiment/env.sh`; make it once, after (a) has fetched the files:

```bash
# ~/ltx-experiment/env.sh  (read with: source ~/ltx-experiment/env.sh)
MR=~/ai-image-studio/scripts/measure_run.sh   # the measuring script, on main since the 1.27 spec
M=~/ltx-experiment/models                      # the folder the files were downloaded into (--local-dir)
FLAGS=(
  --transformer-path "$M/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors"             # distilled transformer, bf16
  --text-encoder-path "$M/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"               # Gemma 4 12B with projection, bf16
  --video-vae-path "$M/vae/ltx-2.5-video-vae-bf16.safetensors"                            # video VAE, bf16
  --audio-vae-path "$M/vae/ltx-2.5-audio-vae-bf16.safetensors"                            # audio VAE, bf16
  --spatial-upsampler-path "$M/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"  # spatial upscaler x2, bf16
)
PROMPT="A woman in a yellow raincoat walks along a stone pier at dusk. Waves break against the wall, gulls call, and the wind blows."
```

* **Everything goes in your notes as words as well as numbers.** "It said `CUDA error: no kernel image`" is worth more than "it failed".
* **The model is gated and has a licence.** On https://huggingface.co/Lightricks/LTX-2.5 accept the terms with your own Hugging Face account. The weights are under the *LTX-2.x Community License Agreement*: the card says commercial use is free for an entity under 10 million dollars of annual revenue and needs a paid agreement above that, and that passing on fine-tunes may need a paid licence. **I have not read the licence itself; its binding text is https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x: read it before you use the output for anything but trying it.** Give your token to the download tool in your own shell (`export HF_TOKEN=...` in that terminal, or the tool's own login), **never in a chat, never in a file in the repository.** **If a download says `Error: Access denied. This repository requires approval.`, your account has not been approved yet:** open the model page, request access with that account, wait for the approval, and run the download again (that is what happened to you, and the download worked after the approval). The listing of the files (`list_repo_files`) works without approval.

**a) Can it be installed at all?** First write down what the machine is: `uname -m` (expect `aarch64`), `python3 --version`, `nvidia-smi` (the CUDA version is in its header), `uv --version`, `df -h ~` (free disk) and `free -g`. The card's own stack, **ltx-pipelines**, says it needs Python 3.12 or newer, CUDA 12.7 or newer and PyTorch 2.7; **whether those exist as arm64 builds for the Spark's GPU is exactly what this step finds out.** Then, in `~/ltx-experiment`:

```bash
MR=~/ai-image-studio/scripts/measure_run.sh      # the checkout of step 1 (the script is on main)
date '+%F %T'
"$MR" -o ~/ltx-experiment/a_install.csv -- bash -c 'git clone https://github.com/Lightricks/LTX-2.git && cd LTX-2 && uv sync'
date '+%F %T'
cd LTX-2 && uv run python -m ltx_pipelines.distilled --help     # read it: the flags for this machine are here
```

**Run by you, 2026-11-19 to 11-20: it works.** `git clone` and `uv sync` worked on aarch64, and `--help` printed (its flags are summarised at the top of this section). The Python version `uv sync` chose was not written down: **write it down now** (`cd ~/ltx-experiment/LTX-2 && uv run python --version`).

**Good:** `uv sync` finishes and `--help` prints. **If anything fails, that is the result:** write down the first error message in full, the step it came from (Python version, CUDA version, a wheel for aarch64 that does not exist, `ltx-kernels` that does not build), and what you tried. The card names two other stacks: **ComfyUI** (it has official LTX-2.5 workflow templates) and **diffusers** (installed from `main`: `pip install git+https://github.com/huggingface/diffusers`, the classes `LTX2ImageToVideoPipeline` and `LTX2LatentUpsamplePipeline`, with `pipe.enable_model_cpu_offload()` and `vae.enable_tiling()`). **If ltx-pipelines cannot be installed, try one of those and write down which one worked**, because which stack runs here decides how the studio would drive it (`DESIGN.md` §46.6). Everything below is written for ltx-pipelines; for another stack, do the same measurements with its own commands.

Then fetch the files the distilled pipeline asks for (`--help` and the repository's README say which: the card lists the **distilled DiT**, the **text encoder** (Gemma 4 12B with its projection), the **video VAE** (there are two: *DiffVAE*, higher quality and heavier, and *Conv VAE*, faster and lighter; take the one the pipeline asks for first), the **audio VAE and vocoder**, and the **x2 latent spatial upscaler**), with the download tool of the environment `uv sync` made. **The command that worked** (after your access to the model was approved; the file names are printed by the first line, which works without approval):

```bash
cd ~/ltx-experiment/LTX-2
uv run python -c "from huggingface_hub import list_repo_files; print('\n'.join(list_repo_files('Lightricks/LTX-2.5')))"   # the exact file names
uv run hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
  vae/ltx-2.5-video-vae-bf16.safetensors vae/ltx-2.5-audio-vae-bf16.safetensors \
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors model_patches/ltx-2.5-duration-head-bf16.safetensors \
  --local-dir ~/ltx-experiment/models
```

(The sixth file is the optional duration head, needed only for (g).) Put it under `"$MR" -i 10 -o ~/ltx-experiment/a_download_N.csv --` and `date '+%F %T'` before and after, so that the time is measured: **the start time was not written down, so the download time is not known.** **The card gives no file sizes, so this is where they are found out:** after each download `du -sh` the file or folder, and write down **each size, the total, the seconds, and `df -h` before and after.** **Good:** a list of files with sizes, and enough disk left over for everything that follows (if the disk is nearly full, stop and write that down; the sizes you found are the answer to "can it live on this machine").

**Run by you, 2026-11-19 to 11-20: done.** Before access was approved the download stopped with `Error: Access denied. This repository requires approval.`; after it, the six files came down (71.1 GB together; 449 GB used before and 515 GB after, 3.0 TB free). The sizes and the download seconds are in `DESIGN.md` §46.7 and §46.18.

**b) The first load: time and memory.** The model is large, so loading is a cost of its own. Make the smallest clip the rules allow, so that the time is nearly all loading: **9 frames (8×1+1) at 512×320** (both multiples of 64: 8 × 64 and 5 × 64).

```bash
source ~/ltx-experiment/env.sh
cd ~/ltx-experiment/LTX-2
free -g
"$MR" -o ~/ltx-experiment/b_tiny_1.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/b_tiny_1.mp4 --width 512 --height 320 --num-frames 9
"$MR" -o ~/ltx-experiment/b_tiny_2.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/b_tiny_2.mp4 --width 512 --height 320 --num-frames 9
```

**Good:** both finish with exit status 0 and an MP4 file. **Write down:** the seconds of the **first** run (the files are read from disk, or downloaded if part (a) left something out) and of the **second** (the same, with the files probably still in the kernel's cache), the lowest `MemAvailable` of each, the peak memory used, and whether the program's own log says how long loading took (copy the lines). If the first run is much slower than the second, say by how much. **If it runs out of memory or the Spark stops answering, that is the result of this step:** write down what you saw, restart the Spark if you must, and go to (d)'s options (`--quantization fp8-cast`, `nvfp4-prequant`, `--offload cpu`) before anything else.

**Run by you, 2026-11-19 to 11-20: done, but only a warm load.** Both runs finished (exit 0) in about 45 s, nearly all of it loading, **with the model files still in the kernel's page cache from the download**, so **a cold load from disk was not measured: to measure it, restart the Spark and run the tiny clip once more under the script.** The numbers are in `DESIGN.md` §46.18.

**c) The distilled model, text to video, 5 seconds, 720p.** One clip: **121 frames at 24 fps, 1280×704**. Use this prompt, so that your result can be compared with the later ones: *"A woman in a yellow raincoat walks along a stone pier at dusk. Waves break against the wall, gulls call, and the wind blows."* (The frame rate is `--frame-rate`, default 24.0, so nothing needs to be passed.)

```bash
source ~/ltx-experiment/env.sh
cd ~/ltx-experiment/LTX-2
"$MR" -o ~/ltx-experiment/c_5s.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/c_5s.mp4 --width 1280 --height 704 --num-frames 121
ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration -of default=nw=1 ~/ltx-experiment/c_5s.mp4
```

**Good:** exit status 0; `ffprobe` shows **a video stream and an audio stream** (the model makes sound with the picture; if there is no audio stream, write that down, it is the answer); the duration is about 5 seconds. **Write down:** the seconds, the peak memory used and the lowest `MemAvailable` from the script's summary, the file size (`ls -l`), the ffprobe lines (**including whether the file's width and height are the 1280×704 you asked for or something else**: the card's examples are "two-stage" and the diffusers example makes a smaller picture first and then doubles it, so `--width` and `--height` might have meant the first stage: **they did not, the file had exactly the size asked for**), and **the seconds of work per second of video** (seconds ÷ about 5). **Then play it with sound** (copy the file to your computer if the Spark has no speakers): does the picture look like the prompt, does the sound match it (waves, gulls, wind), is the sound **stereo**, and is it **silence, noise or something that sounds like what you asked for?** Say it in words.

**Run by you, 2026-11-19 to 11-20: done.** Exit 0; the file has a video stream (H.264, 24 fps) and a stereo AAC audio stream at 48 kHz; you watched and listened and said the picture looks like the text, the sound matches it, and it is stereo. The numbers are in `DESIGN.md` §46.18.

**d) Longer clips, and what the options change.** The same prompt and size, with more frames at 24 fps: **241 frames (10 s, 8×30+1), 481 frames (20 s, 8×60+1)** and the longest the machine allows: **721 frames (30 s, 8×90+1).** One at a time, each under the script. **A 30 second clip takes about 17 minutes, so run them in the background** with a small script of your own (this is its shape; your `step4.sh` may differ), and read its log:

```bash
#!/usr/bin/env bash
# ~/ltx-experiment/step4.sh: the 10, 20 and 30 second clips, one after the other, each under the measuring script
source ~/ltx-experiment/env.sh
cd ~/ltx-experiment/LTX-2 || exit 1
for pair in "10s 241" "20s 481" "30s 721"; do
  set -- $pair                                  # $1 is the name, $2 the number of frames
  echo "=== $1 start $(date '+%F %T')"
  "$MR" -i 5 -o ~/ltx-experiment/d_$1.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/d_$1.mp4 --width 1280 --height 704 --num-frames "$2"
  rc=$?
  echo "=== $1 end $(date '+%F %T') exit $rc"
done
```

```bash
nohup bash ~/ltx-experiment/step4.sh > ~/ltx-experiment/step4.log 2>&1 &     # starts it and keeps it running if the terminal closes
grep -E '^===|measure_run:' ~/ltx-experiment/step4.log                       # the start and end lines and the script's summaries
# the peak memory used and the lowest MemAvailable (MiB) from a CSV, if you want them without the summary:
awk -F, 'NR > 1 && $3 ~ /^[0-9]+$/ { if ($3 > m) m = $3 } END { print "peak used MiB:", m }' ~/ltx-experiment/d_30s.csv
awk -F, 'NR > 1 && $4 ~ /^[0-9]+$/ { if (min == "" || $4 < min) min = $4 } END { print "lowest MemAvailable MiB:", min }' ~/ltx-experiment/d_30s.csv
```

**The card does not state a longest clip for 2.5. A hosted service has been reported to offer 20 seconds in its fast tier; that is a limit of that service and may not apply to the weights (`DESIGN.md` §46.3).** So this is the place to find the real limit. **Good:** a clip of the length you asked for, with sound that lasts as long as the picture. **Write down for each:** the exit status, the seconds, the peak memory and the lowest `MemAvailable`, **the exact error if it stopped** (out of memory? a limit the program names? a clip shorter than asked for?), and whether the **picture and the sound hold together over the length** (does the scene drift, repeat, or fall apart after some seconds; does the sound go on, loop, or stop). If a run has not finished after an hour, press Ctrl-C and write that down (an hour is my suggestion for how long to wait, not a number from the model; the 30 second clip took about 17 minutes). **Stop trying longer lengths once one fails** and write down the longest that worked; *that* number decides design A against design B. **Nothing above 30 seconds has been tried.**

Then **what the options change**, on the 5 second clip of (c) (121 frames), one option at a time: add **`--quantization fp8-cast`**; then **`--quantization nvfp4-prequant`** (the card says this needs the distilled NVFP4 checkpoint and `ltx-kernels`, on Blackwell GPUs, which the Spark's is; if it will not run, write down why); then **`--offload cpu`**. For each: **write down the seconds and the peak memory next to (c)'s, and whether the picture or the sound looks different.** (A third-party blog reported that an NVFP4 variant of an earlier model, LTX-2.3, used less memory but was no faster, because video is limited by computing and not by memory; that was a different version, so it is a thing to check and not a fact to rely on.) Also, **once, if the repository has a pipeline for the full "dev" checkpoint** (it is the one that is not distilled, and would be what a "Final" quality means; the card names only `ltx_pipelines.distilled` and `ltx_pipelines.dfr_pipeline`, so look in the repository's README for the other), **run the 5 second clip with it and write down the seconds, the memory and whether it looks better than the distilled one.** If you cannot find how to run it, write that down.

**Run by you, 2026-11-19 to 11-20: the three lengths are done.** 10, 20 and 30 s all finished with exit 0 and no error (the 30 s clip, 721 frames, came out in one pass); you watched them: 10 s good; 20 s good except one "inhuman" turn; 30 s good but the person's arms keep appearing and disappearing. All used the same prompt and the default seed 10, so **length or seed is not yet known: that is what (k) is for.** **Not yet run, and no result was reported: `--quantization fp8-cast`, `nvfp4-prequant`, `--offload cpu`, and the dev checkpoint.** The numbers are in `DESIGN.md` §46.18.

**e) From a picture of yours: first frame, and first and last frame.** Make a picture you know well in the studio's Images tab (start the studio again for this; stop it when you are done, or use part (i)'s way) and download it. Make it the size the video needs: `ffmpeg -i pic.png -vf "scale=1280:704:force_original_aspect_ratio=increase,crop=1280:704" pic_720.png`. **Image to video, first frame:** `--image pic_720.png 0 STRENGTH` (frame 0 is the first frame; **the `--help` example uses 1.0; run 1.0 first, then once a lower value such as 0.6, and write down both**), with a prompt that says what should happen (*"the camera slowly moves in; the person turns and smiles"*), 121 frames, 1280×704, under the script. **Good:** the clip starts looking like your picture (the same subject, colours and composition) and then moves. **Write down:** how like your picture its first frame is (put the picture and the clip's first frame side by side: `ffmpeg -i c_clip.mp4 -frames:v 1 first.png`), whether the strength changes that, whether the subject stays the same person or thing to the end, the seconds and the memory next to (c)'s, and whether the sound still matches. **Start and end frame:** the card says the flag can be given more than once; make a second picture (the same subject in another pose or place, also scaled to 1280×704) and run `--image pic_720.png 0 1.0 --image pic2_720.png 120 1.0 guide` (the last of 121 frames has index 120 **if the indexes count from 0, as the card's 0 for the first frame suggests; the `--help` examples are `--image start.jpg 0 1.0` and `--image end.jpg 160 1.0 guide`, and with the binding `auto` an index after 0 guides as a keyframe**). **Good:** the clip begins at the first picture and ends at the second. **Write down:** whether it does, whether the ending is **reached smoothly or the picture jumps in the last second**, and whether the sound has a cut near the end. If you have the time, also try **a start picture at 0 and a second at the middle (index 60)**: does the clip pass through it?

**Run by you, 2026-11-19 to 11-20, and watched on 2026-11-23: the first-frame clip only.** `--image 3-2.png 0 1.0` (a 1376×768 RGBA PNG made in the studio, scaled and cropped by ffmpeg to 1280×704; it was still RGBA and the program accepted it) made a 5 s clip, exit 0, at the same cost as the text-only clip. **You watched it on 2026-11-23 and said "it looks fine"**; you did not say how like the picture its first frame is or whether the subject stays the same, so **that comparison (picture and first frame side by side, as described above) is still to do**. **Not yet run: strength 0.6, start and end frame, start and middle.** A picture with transparent parts was not tried either.

**f) The chain: two clips made one after the other, stitched.** This is design B's whole idea, tried by hand. **Clip A** is the 5 second clip of (c) or (e). Take its **last frame**:

```bash
ffmpeg -sseof -0.1 -i A.mp4 -frames:v 1 last.png            # a frame about 0.1 s before the end: close enough
# the exact last frame (keeps overwriting the file until the last one): ffmpeg -sseof -1 -i A.mp4 -update 1 last.png
```

**Clip B** uses it as its first frame with **the same prompt** (so that nothing else changes): `--image last.png 0 STRENGTH`, the same size, 121 frames, under the script. **Stitch** them (this re-encodes; it keeps both pictures and both sounds):

```bash
ffmpeg -i A.mp4 -i B.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" AB.mp4
```

B's first frame is A's last, so one frame is shown twice at the join (about 0.04 s at 24 frames a second); leave it, and say if you see it. Watch **AB.mp4** at the join, several times, and with sound. **Good** means all of: **no jump in colour or brightness** at the join; **the same face, clothes and place** before and after; **motion that carries on** (a person walking keeps walking, in the same direction); and **the sound does not cut, click or change character** (the waves go on as waves, the same voice if there was a voice). **Bad** is any of: a **jump in colour** or in light; **a face or an object that changed** (the person is another person); the motion stopping and starting again; **a cut in the sound**: a hole, a click, music that starts over, a voice that changes. **Write down in words what you saw and heard at the join, for each of those, and how many seconds before and after the join the problem is audible or visible.** Then **make a third clip C from B's last frame** and stitch A+B+C: **does it get worse with each link** (the face drifting a little more each time)? That is the question a 30 second clip made of six 5 second links depends on, and I cannot answer it from here. (Under the flags above, clip B is `uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path B.mp4 --width 1280 --height 704 --num-frames 121 --image last.png 0 1.0`.)

**Not yet run.**

**g) What the model decides about length.** Omit `--num-frames` altogether. The card says that without it the model's **duration head** **predicts the clip length from the prompt**; `--help` says the same (`--auto-duration MIN MAX`, default 1.0 to 20.0 seconds, "only available for LTX-2.5 / gemma4 onward"; read `--help` to see whether `--auto-duration` must be given too, and add `--duration-head-path` with the sixth file you downloaded). Run it for three prompts of different kinds: one that is a moment (*"A door slams shut in an empty house."*), one that is a short scene (*"A man walks across a kitchen, picks up a kettle, pours tea into two cups and sits down."*), and one with speech (the prompt of (h)). Afterwards `ffprobe -v error -select_streams v -show_entries stream=nb_frames,r_frame_rate,duration -of default=nw=1 out.mp4`. **Write down for each prompt: the number of frames and the seconds it chose, and the seconds the run took.** **Good:** a length that fits the prompt and is a number the rules allow (8n + 1). Is it ever longer than what you managed in (d)? Is a given prompt's length steady when you run it again? **The card also says the model can make several connected shots in one pass ("native multi-shot") but gives no way to write them in what I read; if the repository's README shows how, make one two-shot clip with it and write down what it did, because a long clip made of shots in one pass would be a third way to a long clip.**

**Not yet run.**

**h) The sound.** Use a prompt that **names dialogue and ambience**: *"In a small lighthouse kitchen, an old keeper says, in a calm voice, 'The storm will pass by morning.' Rain taps on the window and a kettle begins to whistle. Soft piano music plays in the background."* — 121 frames, 1280×704, under the script. Then `ffprobe -v error -select_streams a -show_entries stream=codec_name,sample_rate,channels,channel_layout,duration -of default=nw=1 out.mp4` and `ffmpeg -i out.mp4 -af volumedetect -vn -f null - 2>&1 | grep -E "mean_volume|max_volume"`. **Write down:** the audio codec, **sample rate**, **number of channels** (mono or stereo), the duration of the audio against that of the video, and the two volume lines (a clip you know is silent, such as `ffmpeg -f lavfi -i anullsrc -t 2 silent.wav`, gives you the figure to compare them with). **Listen, and say in words:** **is there speech, and does it say what you wrote? Is it intelligible? Do the rain, the kettle and the piano come out? Do any of them come out when you did not ask for them?** Does the **voice match the mouth** (lip-sync), if the person is on screen? **Then the same prompt with a different seed:** is it **the same voice**? (The card says the voice stays consistent across shots of one generation; whether it stays across two generations is not stated, and design B depends on it.) The card gives no way to give the model **your own audio**; do not look for one here beyond reading `--help` for an option, and **write down any option about audio that `--help` lists.**

**Run by you, in part:** the sound of the 5 s clip of (c) (AAC, stereo, 48 kHz, 31 ms shorter than the video at 5 s and at 30 s) and your verdict that it matched. **Not yet run: the speech prompt above, the volume lines, and the same prompt with a different seed (`--seed`).**

**i) The studio's other models, side by side.** Only if (c) worked. The studio and Ollama keep models in the same unified memory (`DESIGN.md` §9a). **Running out of memory on a machine like this can make it stop answering: save your work and be ready to restart it.** Start the studio (`docker compose up -d`), press **Load model** in its header so that the image model is loaded, and if you use the Prompt builder make Ollama load its model too (`ollama ps` shows it). Write down `free -g` and `nvidia-smi`. **Then run the 5 second clip of (c) again under the script, with all of that loaded.** **Good:** it finishes. **Write down:** whether it ran, the seconds against (c)'s, the lowest `MemAvailable`, **`free -g` during the run (in a second terminal) and after**, whether the studio's page stayed usable, and what happens if you then press **Generate** in the studio while the clip is being made (the studio's own memory check may refuse; write down what it says). Then **press Unload model in the studio, and Ollama's `ollama stop <model>`, and run the clip again:** how much faster is it, and how much more memory was left? That tells us whether the Video tab must unload the other models before it runs (as Speech and Music do) or whether they can stay. (For scale: the 30 s clip needed a peak of about 55.6 GiB machine-wide, `DESIGN.md` §46.18.)

**Not yet run.**

**j) The decision table.** From what you found, this is how the design is chosen (the same table is in `DESIGN.md` §46.5, which has more rows since the first results; **the provisional choice so far is design A with a 10 second default and a warning under long lengths, PROPOSED, not yet decided**):

| What the experiment showed | Design |
|---|---|
| **(d)** reaches about 30 seconds (721 frames) in one pass, picture and sound holding together, and the time is something you can live with | **A: one clip, in one pass**, up to the length that worked |
| **(d)** stops at about 10 seconds (or at any length below 30), **and** the chain **(f)** looks right (no jump in colour, the same face, sound without a cut, and it does not get worse with each link) | **B: chained segments**, each as long as the model manages, stitched |
| **(d)** reaches about 20 seconds and the chain is right | **B** with long segments, or **A** at 20 seconds: the choice is yours (`DESIGN.md` §46.16) |
| **(d)** stops short **and** the chain **(f)** is not right (faces change, sound cuts, drift) | **Neither**: the Video tab offers only what is possible (the longest single clip; no chaining), and **we talk** about what to do |
| **(a)** failed on every stack, or **(b)** or **(c)** ran out of memory with every option | **No Video tab on this machine** for now; we talk |
| **(c)** works but **(i)** does not (it cannot live next to the other models) | The Video tab works only **after unloading the others**, and says so before it starts |

**k) The seed, and the pipeline's own long-clip mode (added after the first results, 2026-11-23).** The 20 and 30 second clips showed body-motion flaws, but only with one prompt and one seed (10). This step asks whether that is the length or the seed, and whether `--chunked` ("generate long clips in overlapping temporal windows": 97-frame windows, a 25-frame carry, a crossfade over the whole overlap) does better. It is the same prompt and size as (d), run in the background like `step4.sh`; the shape of `~/ltx-experiment/step4b.sh` is:

```bash
#!/usr/bin/env bash
# ~/ltx-experiment/step4b.sh: 20 s and 30 s with another seed, then 30 s with --chunked (the default seed)
source ~/ltx-experiment/env.sh
cd ~/ltx-experiment/LTX-2 || exit 1
run() {   # run NAME FRAMES [extra flags...]: one clip under the measuring script
  local name=$1 frames=$2; shift 2
  echo "=== $name start $(date '+%F %T')"
  "$MR" -i 5 -o ~/ltx-experiment/k_$name.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/k_$name.mp4 --width 1280 --height 704 --num-frames "$frames" "$@"
  local rc=$?
  echo "=== $name end $(date '+%F %T') exit $rc"
}
run 20s_seed11 481 --seed 11
run 30s_seed11 721 --seed 11
run 30s_chunked 721 --chunked
```

```bash
nohup bash ~/ltx-experiment/step4b.sh > ~/ltx-experiment/step4b.log 2>&1 &
grep -E '^===|measure_run:' ~/ltx-experiment/step4b.log
```

The three runs together take at least about 27 minutes (the 20 and 30 second clips of (d) took 604 s and 1,036 s; the time of a `--chunked` run is not known). **Write down:** for each clip the exit status, the seconds, the peak memory and the lowest `MemAvailable`; **for the `--chunked` clip the program's own `Plan: N chunks` line** (every single-pass run printed `Plan: 1 chunks`) **and the real length** (`ffprobe -v error -select_streams v -show_entries stream=nb_frames,duration -of default=nw=1 k_30s_chunked.mp4`; `--help` says the stitched clip floors `--num-frames` to the causal grid when it is off-grid, 240 becoming 233, so 721 may come out shorter). **Watch and listen**, and say in words: **with seed 11, do the 20 and 30 second clips show the same kind of flaw as with seed 10** (a turn where the upper body and the legs disagree; arms appearing and disappearing), **or are they good?** **Good** (flaws belong to the seed): both seed-11 clips are good. **If both seeds show flaws at 20 and 30 seconds, they belong to the length** (one more seed, `--seed 12`, makes it firmer). **For `--chunked`:** is the 30 second clip better or worse than the single-pass one, **is there a visible or audible seam where one window hands over to the next** (a window is 97 frames, about 4 seconds at 24 frames a second, my arithmetic), and does the sound go on without a cut? What it decides: whether the long-clip design is A (with a warning), C (`--chunked`, design C of `DESIGN.md` §46.5) or B (`DESIGN.md` §46.5, step (f)).

**Not yet run: written, not reported as run.**

**Send back:** from (a) the machine's facts (`uname -m`, Python, CUDA, `uv`), which stack worked or the first error of each that did not, and the file sizes and the download seconds; from (b) the two load times and the memory; from (c) the script's summary, the ffprobe lines and your verdict on the picture and the sound; from (d) the table of lengths (exit status, seconds, peak memory, lowest `MemAvailable`, the error if any, and whether it held together), what each option changed, and whether the full "dev" checkpoint could be run and how it compared; from (e) your verdicts on the first frame, the strength values you tried and the end frame; from (f) what you saw and heard at each join, in words, and whether it got worse with the third link; from (g) the lengths the duration head chose; from (h) the audio's format and your verdict on speech, ambience, music and the voice across seeds; from (i) the `free -g` lines and what happened; from (k) the three clips' table and your verdicts (seed, `--chunked`, seams); and the **CSV files** (`~/ltx-experiment/*.csv`) if you want me to read the curves. No tokens or passwords, please. **What you have already sent (2026-11-19 to 11-23) is not asked for again: (a), (b) warm, (c), the lengths of (d), the first-frame clip of (e) with your verdict "it looks fine".**

## 38. Vector quality: thin lines are kept and widened (new in 1.23)

*Why 38: this section belongs to release 1.23, which is older than sections 34 to 37, but every number from 1 to 37 is cited by
other files and none may move, so it takes the next free one. The status table at the top says which release each section came with.*

Nothing in this section has been run on your Spark. It was added on 2026-11-17 from `docs/DESIGN.md` §41 and from reading the code; the
steps below say only what the code does.

**What changed.** The Vector tab gave you a result that kept the outline and the hair of a pencil drawing and lost the rest of the face. Two
causes: the clean-up deleted everything narrower than the **smallest feature** (0.5 mm by default; on a 100 mm sheet drawn at 1536 pixels a
pencil line 3 to 5 pixels wide is under it), and a stroke whose width wandered across that limit came back as dashes. Since 1.23 the clean-up
**keeps thin lines and widens them to just over the smallest feature** (between 1 and 3 drawing pixels more, about 0.07 to 0.2 mm on a 100 mm sheet),
so a thin stroke stays one unbroken line. A shape that is already wide enough does not move, and specks (noise) are still removed first, so noise
does not become blots. The option is `thin_lines`: `thicken` (what a run gets when it does not say) or `drop` (the earlier behaviour: thin parts are
removed). The colour step also reads thin dark strokes now, where it used to drop them as in-between grey.

**What is not built**, so do not look for it: the **Engrave or Cut** choice, the form's **Thin lines**, **Shading** and **Dot spacing** controls,
the **tone dots** (shading turned into a layer of dots) and the Engrave wording of the drawing's recipe. The page has no control for thin lines; the
one related field is **Smallest feature (mm)**. Soft shading is still left out, and the studio still asks the model for flat, shadeless artwork, so how
much fine line the model draws depends on your prompt. This section checks what the clean-up does with the lines that are there.

**What §41 says was not tried:** your own source PNG (the test picture was cut from a screenshot and shrunk to about 60%, so its lines were softer
than yours), any picture from a real Qwen run through the new clean-up, and the Spark.

Update first: `git pull && docker compose up -d --build`; the title should read **v1.23** or later. There is no database change. The clean-up is on the
CPU, so there is no new GPU work: the memory figures of section 28 (b) still apply.

**a) The picture that failed, again.** On the Vector tab open a Vector run you made before 1.23 whose result lost the lines of its drawing (in the
viewer, **The drawing** is at the left and **The vector** at the right). Press **Reuse** (the prompt, the options and the seed come back), check that **Smallest
feature (mm)** says 0.5 (set it if not) and press **Make vector**. **Good:** the new vector keeps the fine lines of the drawing (in a face: eyes, brows, nose, lips,
creases) as unbroken lines and not as dashes, where the old result had only the outline and the solid areas; the lines are a little bolder than in the
drawing and never thinner than the smallest feature. The drawing itself should be the same as before, because the seed is the same; if it is not, say so,
because that is the model and not the clean-up. **Write down** whether the vector is now a fair copy of the drawing, and what is still missing (the soft
shading is expected to be missing).

**b) What the check says it did.** Open the new version's notes (the viewer shows them under the layer table; a card with one version shows them too).
**Good:** a note that reads like *"12 thin lines narrower than 0.5 mm were widened to 0.5 mm, so they stay one line each and the drawing keeps its
detail."* (the number is yours). If the drawing had noise, also *"N specks smaller than 0.5 mm were removed."* The same is in the run's JSON:

```bash
RUN=$(curl -s 'localhost:8081/api/runs?limit=1' | python3 -c 'import sys, json; print(json.load(sys.stdin)["runs"][0]["id"])')
curl -s localhost:8081/api/runs/$RUN | python3 -c 'import sys, json; c = json.load(sys.stdin)["vectors"][0]["check"]; print(c["thin_lines"], c["widened"], c["removed"]); print([n["code"] for n in c["notes"]])'
```

**Good:** it prints `thicken`, a `widened` above 0 and the counts of removed `specks` and `thin_parts`, then the note codes (`thin_widened` among them;
`specks_removed` if there were specks).

**c) Thicken against drop.** The page cannot switch it, so use the API: the same prompt and seed twice, once with each setting (use your own prompt if you like).
Wait for each to finish, then look at both in the viewer and read the check as in (b) with each run's id.

```bash
for MODE in thicken drop; do
  curl -s -X POST localhost:8081/api/runs -H 'Content-Type: application/json' -H 'X-Studio-Client: 1' \
    -d "{\"mode\": \"vector\", \"prompt\": \"a pencil drawing of a face\", \"options\": {\"seed\": 7, \"thin_lines\": \"$MODE\"}}" \
    | python3 -c 'import sys, json; r = json.load(sys.stdin); print(r["id"], r["options"].get("thin_lines"))'
done
```

**Good:** the `thicken` run says `thicken` with a `widened` above 0 and keeps the fine lines; the `drop` run says `drop`, has `widened` 0, and loses
or breaks them as the Vector tab did before 1.23 (DESIGN.md says the `drop` result is byte for byte what the earlier engine made; that was tested on constructed
pictures only). **Write down** which you prefer on this picture, and the `svg_bytes` of each (in the same `check`).

**d) The smallest feature.** On the form set **Smallest feature (mm)** to **0.15**, press **Reuse** on the run of (a) and make it; then **1**; then **3** (100 × 100 mm).
**Good:** at 0.15 the lines are widened only to that width, so the vector follows the drawing more closely, and the note says 0.15 mm; at 1 the lines are bolder.
At 3 mm the smallest feature is wider than about 30 pixels of the drawing (about 2 mm on a 100 mm sheet, whose drawing is 1536 pixels on its long side), too wide to
widen to, so **good** is a note that reads *"Thin lines were not widened: 3 mm is too wide to widen them to on this drawing (more than 32 of its pixels), so parts
narrower than that were removed."* and a result like the old one. **Write down** which setting gives you the best vector for the lines you care about.

**e) Time.** The tracing time of each run is in the log: `docker compose logs studio | grep traced`, one line for each version (*"run … version 1 traced in 1.2s …"*).
**Write down** it for 0.5, 0.15 and 3 mm. (DESIGN.md §41.8 reports about a second at 0.5 mm and at 0.15 mm, and about 2.5 s at the largest feature that is still widened, for a picture cut from your
screenshot and measured without a GPU; it is not a figure for your Spark.)

**f) The laser software.** Download the SVG of (a) and open it in **xTool Creative Space** and **LightBurn**, as in section 28 (e). **Good:** it measures what you asked
for, and the thin lines are there. **Write down** whether anything looks wrong in either program that did not in the viewer.

**g) An older run.** Open a Vector run from before 1.23 in the viewer. **Good:** it opens as it did before; nothing is traced again, and its check has no thin-line
note (it was cleaned up as `drop`).

**Send back:** from (a) whether the vector keeps the fine lines of its drawing and what is still missing; from (b) the note and the numbers it printed; from (c) which of
`thicken` and `drop` you prefer and the two `svg_bytes`; from (d) the notes and your verdict at 0.15, 1 and 3 mm; from (e) the tracing seconds; from (f) what the laser
programs showed; and anything that did not match "Good".

## 39. The Video tab, through the studio, on your Spark (new in 1.27)

**This is the first time the Video tab meets your Spark.** When this section was written the tab had been tried in unit tests, in a real browser with a **fake engine** (it writes a real MP4 with sound, and speaks the real program's protocol), and with a stand-in for the LTX-2 folder; **no clip has been made through the studio with the real LTX-2.5, and the real program has not been started from inside the studio's container.** The experiment of section 37 is what you ran by hand; this section is the same program, run by the studio. Do the steps in order: each says what the tab and `check_image` should say, so that when one fails you know which one. `docs/DESIGN.md` §46.19 says what was built and what was not.

**What you need first:** the LTX-2 folder and the model files from section 37 (a) to (c) (`~/ltx-experiment/LTX-2` with its `.venv`, made by `uv sync`, and `~/ltx-experiment/models` with `diffusion_models`, `text_encoders`, `vae`, `latent_upscale_models` and `model_patches`), about **60 GB of free memory** (the studio checks, and says so if not), and the studio's other models **not** loaded for the first clip (step (g) is the one that tries them together). **Nothing is downloaded.**

**a) The two settings.** Put these two lines in `.env` (they are in `.env.example`, commented out; **replace `YOU` with your user name and write the full path, not `~`**, which a `.env` file does not expand; the command under them prints both lines with your real home folder):

```
STUDIO_VIDEO_LTX_DIR=/home/YOU/ltx-experiment/LTX-2
STUDIO_VIDEO_MODELS_DIR=/home/YOU/ltx-experiment/models
```

To get them with your real home folder, run this and copy the two lines it prints into `.env` (replacing any `STUDIO_VIDEO_LTX_DIR=` and `STUDIO_VIDEO_MODELS_DIR=` lines already there):

```bash
printf 'STUDIO_VIDEO_LTX_DIR=%s\nSTUDIO_VIDEO_MODELS_DIR=%s\n' "$HOME/ltx-experiment/LTX-2" "$HOME/ltx-experiment/models"
```

Check what the container will see before you build:

```bash
readlink -f ~/ltx-experiment/LTX-2/.venv/bin/python        # Good: /usr/bin/python3.12 or /usr/bin/python3: the system Python, which the container has too
ls -ln ~/ltx-experiment/LTX-2/.venv/bin/python ~/ltx-experiment/models   # the owner's numbers, and whether "others" can read and enter: r-x
id -u; id -g                                                # the container runs as STUDIO_UID:STUDIO_GID (section 4): the studio must be able to read both folders
```

**Good:** the link ends at a system Python (**not** under `~/.local/share/uv`, which the container does not have: the tab says so, step (c)), and the studio's user can read both folders. If not, `chmod -R a+rX` on the folder, or set `STUDIO_UID` and `STUDIO_GID` to the folder's owner. **Write down** the output of the three commands.

**b) Rebuild and start.**

```bash
docker compose up -d --build        # --build, so that compose.yaml's two read-only mounts and the Video pieces are in the image
docker compose config | grep -B1 -A3 ltx-experiment     # Good: the two folders, each as "source", "target" (the SAME path) and read_only: true
docker compose logs studio | grep -i video              # the start-up check's line (it is run once and remembered)
docker compose exec studio python /app/docker/check_image.py | grep Video     # the same check, now with the folders in place
```

**What the `Video:` lines should say, in order** (this is the build's own self-check run in the running container; in the build itself nothing is mounted, so the build prints *no program is set up in this build*, which is fine and **not** a failure):

1. `Video: measured working on the Spark (2026-11-19/20): LTX-2 commit daa6b16, ... torch 2.13.0+cu132 (CUDA 13.2), ... natten 0.21.7+torch2130cu132`: what was measured. Nothing to check.
2. `Video: this image's own PyTorch is 2.9.0a0+145a3a7bda.nv25.10 (CUDA 13.0), which the program cannot use: it runs in an environment of its own (...)`. Nothing to check.
3. `Video: /usr/bin/python3 is Python 3.12.3 (as measured: the host's environment can run here)`. **If it says another version**, the host's environment may not run in the container: paste that line.
4. `Video: the LTX program can be started: Python 3.12.3, torch 2.13.0+cu132 (CUDA 13.2), ...; as measured`. **Good:** `as measured`, or a **difference** in a package (shown, not refused: for example `natten not found`). **Not good:** `Video: not available here: ...`, with the reason and what to do; **paste the whole line** (step (c) lists the messages).
5. `Video: all five model files were found in /home/YOU/ltx-experiment/models` (with your own path).
6. `Video: ffmpeg has an H.264 encoder (libx264): the HD and Scope sizes can be trimmed to size`. **If it says there is none**, HD and Scope cannot be made (the other sizes can): paste the line.

(An exec'd check runs without a GPU being demanded; whether PyTorch sees the GPU is reported, and `Video: ... cannot see the GPU` is the one to take seriously.)

**c) What the tab says at each step, when something is wrong.** Open the **Video** tab. **Good:** a form (if it asks you to acknowledge the licence first, step (d)). **If not**, the tab says **Video isn't available on this server**, gives the reason, then what to do, and has a **Check again** button; put it right on the Spark and press **Check again**: the studio looks again (at most once in 10 seconds, and not while a clip is being made; it says so) **without restarting the container**. A line you changed in `.env` needs `docker compose up -d` first. The steps are checked in this order and the first that fails is the one shown; **the words of the reason are**:

| Step | The tab says (the start of the reason) | What to do |
|---|---|---|
| ffmpeg | `ffmpeg is not installed, and a clip cannot be read or made playable without it.` | the image has it; it means a broken build: paste the line |
| Program not set up | `Video is not set up: no program is named to make clips.` (or `no LTX-2 folder is named, and the program is not built into this image`) | the two lines of (a), then `docker compose up -d` |
| LTX-2 folder | `The LTX-2 folder is not there: <path>.` / `... is not a folder` / `has no Python environment: <path>/.venv/bin/python is not there` / `has no packages/ folder` | the path in `.env` must be the clone itself; `uv sync` in it |
| Python link | `The LTX-2 environment's Python is a link to <path>, which is not in the container.` | make the environment with the system Python: `uv sync --python 3.12` (on the host) |
| Permissions | `The studio cannot read the LTX-2 folder <path>: it runs as <user> (uid, gid).` / `cannot run the LTX-2 environment's Python` | `chmod -R a+rX`, or `STUDIO_UID`/`STUDIO_GID`, as the hint says |
| Model files | `The folder of model files is not set.` / `is not there: <path>` / `holds none of diffusion_models, text_encoders, vae or latent_upscale_models: <path> (it holds: ...)` / `No file for the <text encoder, sound VAE, ...> was found in <folder> (it holds: ...)` / `More than one file could be the distilled model in <folder>: a, b` / `cannot read the <file>` | the folder must **contain** those four folders; name the file in `STUDIO_VIDEO_TRANSFORMER` (or `_TEXT_ENCODER`, `_VIDEO_VAE`, `_AUDIO_VAE`, `_UPSAMPLER`) if the choice is not clear; an "Also wrong:" line lists the rest |
| Python of the program | `The video program's Python is 3.x; LTX-2 needs 3.12 or newer.` / `PyTorch does not import in the video program's environment (<error>)` / `The LTX-2 program (ltx_pipelines) is not installed in that environment.` / `does not import (<error>)` | `uv sync` in the LTX-2 folder on the host, then **Check again** |
| GPU | `PyTorch in the video program's environment cannot see the GPU.` | `docker exec ai-image-studio nvidia-smi` must show the GB10 (section 2); the hint asks for `docker exec ai-image-studio env \| grep -i -E 'cuda\|triton\|ld_library'`: **paste it** |
| It did not answer | `The video program's Python did not answer: <what it printed>` | run the command in the hint by hand and paste what it prints |

**What to paste back for any of these:** the tab's reason and hint word for word (a screenshot is fine), the `Video:` lines of (b), and the output of `docker exec ai-image-studio env | grep -i -E 'cuda|triton|ld_library|python|torch'`. **Write down** which step first failed and whether **Check again** moved it on after you put it right.

**d) The licence.** The first time, the tab shows the licence's summary (the model card's words, with a revision) and a button to acknowledge it; **the form is switched off until you do**. **Good:** acknowledge it; the form opens; reload the page: it **stays** acknowledged (it is stored in the database with the licence's revision, never in a setting). **Write down** whether the summary matches what you read on the model's page: the binding text has not been read by whoever wrote the summary.

**e) A first clip: 5 seconds from text.** In **What happens** write something plain, in **What you hear** a sound (for example *a quiet room, rain on the window*), choose **5 s**, leave the size at 1280×704, the seed blank, and press **Make clip**. **Good, in order:** the card is queued and then working; the line under the form before you pressed said **About N min** with **the table's source named** (*measured on one Spark setup, 2026-11-19/20 (no natten)*); the card then says, one after another, *Starting the video program*, *Reading your words*, *Making the picture and sound (first pass): step n of 8*, *Getting ready to sharpen*, *Sharpening to full size (second pass): step n of 3*, *Decoding the picture and sound*, *Writing the file*, with the seconds so far and about how long to go; the clip then appears, plays **with its sound**, shows the facts line (*5.0 s · 1280×704 · 24 fps · Draft · with sound · seed N · 3 min 12 s*) and a download. **Write down:** the seconds it took (the card's last number), whether every stage name appeared, whether the estimate's *to go* was near the truth, and `docker compose logs studio | grep -i video | tail -30`. **If it fails**, the card says why and gives a hint: *the program stopped*, *not enough memory*, *out of memory*, *the disk is full*, *the licence*: **paste the card's words and the log's last 60 lines of the clip's run**. If the card sits on *Starting the video program* and after two minutes says **Working: the program does not say which step it is on**, the program is running but its lines were not recognised: **paste the log** (this is the one case where the studio cannot tell progress from silence).
  **Then check the file itself.** Open the clip on the Spark and **on your phone** (the tab's download, or the page itself over the LAN): **Good:** it plays, the sound is there and in step with the picture, and you can seek in it. `ffprobe -v error -show_entries stream=codec_name,width,height,avg_frame_rate,duration data/video/*/clip.mp4` should say H.264 1280×704 24 fps and AAC stereo, picture and sound within about 0.1 s; a longer gap shows as a **note on the card** (*The sound and the picture differ by N ms: the sound stops early.*).

**f) Image to video.** Press **Animate this** on a picture of Images (or switch the form to **Image to video** and choose a picture). **Good:** the picture becomes the **start picture**, the size follows its shape (1280×704 for a 16:9 picture), a preview shows **what is cut off** (the picture is cropped to the clip's shape from the middle, never stretched), and a picture with transparency says it is **laid on white**. Make a 5 s clip. **Good:** it starts from the picture; it takes about as long as (e). **Write down** the seconds and whether the first frame is your picture; in section 37 the same thing "looks fine".

**g) Cancel in the middle.** Start a 10 s clip, wait until the card says *Making the picture and sound (first pass)*, press **Cancel**. **Good:** the card says *Stopping the video program…* and then **Canceled** within a few seconds (the studio ends the program and everything it started, not just the first process); `nvidia-smi` and `free -g` show the memory **back**; `ls data/video` has nothing left of that clip; the next clip starts normally. **Write down:** the seconds from pressing Cancel to *Canceled*, `free -g` before the clip, in the middle of it and after Cancel, and `ps aux | grep -i ltx_pipelines` in the container (`docker compose exec studio ps aux | grep ltx_pipelines`), which should print **nothing** after Cancel.

**h) The estimate against reality.** After (e), (f) and a 10 s clip, look at the line under the form for 5 s and 10 s. **Good:** it names **the clips made on this machine** (*About 4 min, from the 2 clips of about 5 s made on this machine*) and is near what the clips took; before any clip it named the table and said it was one setup's, **without natten**. The table was measured without natten; with natten every clip took about 30 s longer (a fixed part), so **the first estimate may be 30 s too small**: **write down** by how much, and the estimate after the second and the fifth clip.

**i) Memory next to the other models.** With the **image model loaded** (make a picture first) press **Make clip**. **Good:** only one model is in memory, so the studio swaps: the image model goes and the video program runs (the model pill names the video model while the clip is made); the next picture loads the image model again (a swap each time). Then, with the **free memory at about 60 GB or less** (`free -g`, section 3, with another model server or Ollama holding some), press **Make clip**. **Good:** it is refused at once with the numbers (*Not enough free memory to load the video model: N GB available, 60 GB required (STUDIO_VIDEO_MIN_FREE_GB).*) and what to do. **Write down** the pill's words, the seconds the swap took each way, and the memory numbers.

**j) The folders and the files.** `ls -la data/video` and `du -sh data/video data/video-cache`. **Good:** each clip is in its own folder with `clip.mp4`, `poster.jpg` and a thumbnail; the program's caches are in `data/video-cache` (not in the LTX-2 folder, which is read-only); `ls -l data/studio.sqlite*` shows **`studio.sqlite.before-schema-14`** next to the database after the first start. **Keep**, a **tag**, **Delete** (to the bin) and **Restore** work on a clip as on a picture; **search** finds a clip by its words. **A clip has no captions**: the viewer says why.

**k) Backup.** `scripts/backup.sh --no-image --no-model --dry-run ~/backups`. **Good:** the summary names **the video clips** and what they weigh, says that the unfinished clips' work folders and `data/video-cache` are left out, and says **the video model files are your own and are not copied**: **back up `~/ltx-experiment/models` and the LTX-2 folder yourself.**

**l) Your phone.** On the phone (or a window 360 px wide) open the Video tab, make nothing, and look at the form, a card and the viewer. **Good:** nothing runs off the screen; the video plays; the controls are reachable with a thumb. **Write down** what did not fit, with a screenshot.

**m) The second way (optional, a long build; not tried).** Only if you want the program **inside the image** and need not the host's folder: `VIDEO_LTX=1 docker compose build` (the commit pinned in the Dockerfile is the one measured, `daa6b16f...`; the build runs `uv sync --frozen`, and downloads several GB), leave `STUDIO_VIDEO_LTX_DIR` empty, and set `STUDIO_VIDEO_MODELS_DIR` as before. **Good:** the same steps pass. **Write down:** whether the build finished, how long it took, and the `Video:` lines.

**n) HD 1920×1080 and Scope 2.40:1 · 1920×800 (added 2026-11-24; nothing about them has been measured on your Spark).** Two buttons in the **Size** row. The program only makes multiples of 64, so it is asked for **1920×1088** and **1920×832**, and the studio **cuts the clip to the size on the button from the middle** (4 rows off the top and bottom for HD, 16 for Scope), which converts the picture once more and copies the sound. Do (e) first, so that you have the 1280×704 numbers to compare with, and do not run these while a clip is being made.
  1. **By hand first**, for the time and the memory peak (the card gives the time only). The same command as section 37 (c), with the size changed (`--width 1920 --height 1088`; for Scope `--width 1920 --height 832`):
```bash
source ~/ltx-experiment/env.sh
cd ~/ltx-experiment/LTX-2
"$MR" -i 5 -o ~/ltx-experiment/n_hd_5s.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/n_hd_5s.mp4 --width 1920 --height 1088 --num-frames 121
"$MR" -i 5 -o ~/ltx-experiment/n_scope_5s.csv -- uv run python -m ltx_pipelines.distilled "${FLAGS[@]}" --prompt "$PROMPT" --output-path ~/ltx-experiment/n_scope_5s.mp4 --width 1920 --height 832 --num-frames 121
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,r_frame_rate,duration -of default=nw=1 ~/ltx-experiment/n_hd_5s.mp4
```
  **Good:** exit status 0 for both and the sizes `ffprobe` says are 1920×1088 and 1920×832. If the program refuses a size or runs out of memory, **that is the answer**: paste its last lines.
  2. **In the tab:** choose **HD 1920×1080**, **5 s**, and press **Make clip**. **Good:** before you press it, the line under Size says *the program makes 1920×1088 … and the studio trims the picture to 1920×1080*, and the line above Make clip gives an estimate (it counts 1920×1088 and scales the 1280×704 table by the pixels, **a guess that is probably short**); the clip appears with **1920×1080** in its facts line; `ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,duration data/video/*/clip.mp4` says **h264, 1920, 1080, yuv420p** and AAC stereo; the sound is there and in step; the first frame is **not squashed or shifted** (the same picture as (1) with nothing cut but a few rows at the top and bottom); **the picture is not visibly softer than the 1280×704 clip's**.
  3. **The same for Scope** (*1920×800*: a very wide, flat picture).
  4. **Write down:** the seconds, by hand and in the tab, for HD and Scope against (e); the memory peak from `measure_run.sh`; **the extra seconds the trim took** (the card's *Writing the file* stage); **the file sizes** (`ls -l ~/ltx-experiment/n_hd_5s.mp4 data/video/*/clip.mp4`: the program's own file and the studio's, for HD, Scope and the 1280×704 clip of (e)); whether the estimate was near; whether anything ran out of memory; and what you think of how the two look.

**Send back:** from (a) the three commands' output; from (b) the `Video:` lines; from (c) the first failing step's words, the `env` lines and whether **Check again** worked; from (d) whether the summary matches the licence; from (e) the seconds, the stage names, the estimate against the truth, the `ffprobe` line and whether it played on the phone, with any failure's card and log; from (f) the seconds and whether the first frame is your picture; from (g) the seconds to *Canceled*, the memory numbers and the `ps` output; from (h) the estimates; from (i) the pill's words, the swap seconds and the memory numbers; from (j) the `ls`/`du` lines; from (k) the summary's words; from (l) a screenshot of anything that did not fit; from (m) the build's result; from (n) the by-hand times, memory peaks and `ffprobe` lines, the tab's seconds, the trim's extra seconds, the file sizes, the estimate against the truth, and what the two sizes look like.

## Troubleshooting

This is the table the steps and sections point to ("see Troubleshooting"). It is at the end because it serves every part of the file.

| You see | What to do |
|---|---|
| `unknown or invalid runtime name: nvidia` | Register NVIDIA's runtime with Docker: `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`. Or delete the `runtime: nvidia` line from `compose.yaml`: the GPU reservation below it is the `--gpus all` equivalent and may be enough. |
| `could not select device driver "nvidia"` | The NVIDIA Container Toolkit isn't set up for Docker. It ships with DGX OS; check step 2. |
| `check_image: PROBLEM: ...` (the build stops) | The line names the cause; the lines above it hold the installed versions and any traceback. Send them as step 5 says: `sed -n '/check_image: Python/,$p' build.log`. |
| `The data directory /data is not writable by this process (uid …)` | The message ends with the exact `sudo chown` to run on `./data`. |
| `capability check failed: ...` in the log | The message says why; the rows above and below (the runtime, the GPU, no kernels for the GB10) are the usual causes. |
| Model pill: **Image model unavailable**, `No CUDA GPU is visible` | The container didn't get the GPU. Step 2 must work first. |
| `no kernels for the Spark's GPU (GB10)` | Try a newer NVIDIA PyTorch release: set `NGC_TAG` in `.env` (for example `25.11-py3`), then `docker compose build`. |
| `diffusers is installed, but QwenImage21Pipeline is only a placeholder` | transformers didn't import. `docker compose exec studio python -c 'import transformers'` shows why; send me the output. |
| A tab or an engine says "not installed" or "unavailable", with a reason | The build's `check_image: Enlarge:`, `Vector:` and `Speech:` lines say the same thing (they are notes, never a failed build). Sections 22, 28 and 31 (a) say what to send back. |
| The Video tab says **Video isn't available on this server**, or **Check again** does not clear it | The reason and the hint on the tab name the step that failed; section 39 (c) lists every message and what to do, and what to paste back (the `Video:` lines of `docker compose exec studio python /app/docker/check_image.py` and the `env` lines it names). |
| Download fails with 401/403 or "gated" | Accept the model's terms on Hugging Face if it asks, then set `HF_TOKEN` in `.env` and `docker compose up -d`. |
| `Not enough free memory to load the model` | Another model server on the Spark probably holds the memory (a vLLM container, or a model loaded in Ollama): lower its `--gpu-memory-utilization` or stop it (for Ollama, `ollama stop <model>`, or **Unload from memory** on the Prompt builder tab), then flush the page cache: `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'`. Then **Retry**. |
| Out of memory while loading or generating | Same as above; also try a smaller size or fewer images per click. |
| `port is already allocated` | Something else uses 8081 (the studio's port on the Spark since 1.20; it was 8080): set another `STUDIO_PORT` in `.env`, and if your `.env` still says `STUDIO_PORT=8080`, change it to 8081. |
| The page loads but never updates live | Check `docker compose logs studio`; the connection banner at the top says if the live stream is down. |

To update later: `git pull && docker compose up -d --build`.

## What to send back

Paste these into the chat (no tokens or passwords; check before pasting). The numbers are fixed, because other files cite them; the groups only help you find your place.

**Part 1, the first run (items 1 to 5)**

1. The `check_image:` lines from step 5.
2. The first ~30 lines of `docker compose logs studio` after step 6.
3. The timings from step 8 and the numbers **A**, **B** from step 9.
4. Anything that didn't match "Good", with the message the page or the log showed.
5. Whether transparent output really had transparency (step 10).

**Part 2, releases 1.1 to 1.7 (items 6 to 11)**

6. The numbers from step 14: seconds from clicking **Stop generating** to the card saying **Canceled**, and the memory before and after.
7. The numbers and observations from step 15 (edits through the API).
8. The numbers from step 16: the time of a draft and of a run at each scale, and how the draft looks.
9. From step 17: the two times, and how different the small and the regenerated pictures are.
10. From step 18 (the Spark test for edits, M5c): the times and memory for each case, whether the model followed "image 1" and "image 2", what it did with a transparent picture, which mask colour worked, and the numbers you suggest for the cap and the cost warning.
11. From step 19: how long Load model takes (first time and cached), how much memory it takes and how much Unload gives back, and anything that did not match "Good".

**Part 2, releases 1.8 to 1.15 (items 12 to 19)**

12. From step 20 a) to i) (the music model, the first real run): the download size and time, the load time, the seconds of work per second of music at 15, 60 and (if you can) 180 seconds, the lowest available memory, whether the track was instrumental with the tag alone, whether the same seed repeats, how fast Ctrl+C stopped it, whether anything downloaded after the first time, and anything that did not match "Good".
13. From step 20 j) to n) (the Music tab on the Spark): the numbers from (k), (l) and (m), whether the track played and seeked on your phone, and a screenshot of anything on the phone that did not fit.
14. From step 21 (Make 4K): the seconds and the file size from (a) and for a square in (c), what you thought of the picture in (b), whether the rotation of a phone photo and the refusals in (c3) were right, the time for a 12 MP photo in (c3), whether a running job slowed down in (d), and anything that did not match "Good". From (i), if you ran it: the whole probe output and which of the two 4K files looks better to you, and where.
15. From step 22 (Enlarge): the `ENLARGED …` log lines (time, device, model), the times and sizes from (b), (d), (e), (f) and (i), your verdict on **where Enlarge looks better or worse than Make 4K** from (c) to (e), the memory and slowdown figures from (f) and (g), and anything that did not match "Good".
16. From step 23 (the Kept view): anything that did not match "Good", and whether the date in (e) was the date you expected.
17. From step 24 (the bin): the `ls -l data/studio.sqlite*` line, what the first clean-up put in Deleted, and anything that did not match "Good".
18. From step 25 (project folders): the `ls -l data/studio.sqlite*` line, and anything that did not match "Good".
19. From step 26 (deleting one picture): the `ls -l data/studio.sqlite*` line, what (c) showed, and anything that did not match "Good".

**Part 2, releases 1.16 to 1.22 (items 20 to 26)**

20. From step 27 (the default size): the time and the memory numbers (A, B, `worker_rss_gb`) for one run at 2752 × 1536 and one at 2048 × 2048 from (c), whether the note in (b) appeared, and anything that did not match "Good".
21. From step 28 (Vector): the `Vector:` line from (a), the seconds of the drawing and of the tracing and the memory numbers from (b), the notes from (c) with a screenshot if the drawing had shading or gradients, what XCS and LightBurn showed in (e) (and the laser test sheet's six answers, `DESIGN.md` §31.9 item 1), your verdict on side by side against stacked in (f), and anything that did not match "Good".
22. From step 29 (Vector versions, the stack view, pictures by paste): the `ls -l data/studio.sqlite*` line, your judgement of the trace against the drawing in (b), the three back-sheet results and your verdict in (d), what XCS and LightBurn showed of the stacked layers in (e), which browsers and devices did and did not take a pasted picture in (g) to (j), and from (k) the times, the memory numbers, whether eight pictures ran, whether the model follows "image 7" and "image 8", and the numbers you suggest for the limit and the cost warning.
23. From step 30 (the Prompt builder): the `ls -l data/studio.sqlite*` line, what Test connection showed, the times to the first word and the thinking times from (b) and (c), the counts from (d) (first time, asked again, plain text; thinking on and off), your judgement of the questions from (e), your verdict on the Quick try pictures from (g) and on the description from (h), the memory numbers and the settings you suggest from (j), and anything that did not match "Good".
24. From step 31 (the Speech tab): the `ls -l data/studio.sqlite*` line, the engine pills and the download and load times from (a) and (b), the accent you hear in Jenny, the seconds of work per second of audio and the lowest memory for each engine from (d), **whether there was any gap, click or pitch change between paragraphs when a reading was played as it was made**, the seek time from (e), the book's time and disk use and what the restart showed from (f), whether the place and the lock screen worked on your phone from (g) and (h), your judgement of the style, the designed voices and the clone from (i), the Voxtral numbers from (j), the swap times and memory from (k), and anything that did not match "Good".
25. From section 32 (load progress): the two sizes of a first download (the `total_bytes` and the folder on disk), whether `done_bytes` rose steadily or in steps, the load times from disk, any `total_bytes` that was wrong, and what the page showed (h).
26. From section 33 (reordering the queue): whether the jobs ran in the order the Queue panel showed (b) and (c), what a reading that had started looked like (d), whether the other screen followed (f), your thumb's verdict on the grip (g), and the model swap time (h).

**Part 2, releases 1.24 to 1.27 (items 27 to 30)**

27. From section 34 (More like this, compare, and the experiment): the `ls -l data/studio.sqlite*` line, the time and your verdict on the takes from (a), anything that did not match "Good" in (c) and (d), whether the other screen followed (e), your verdict on side by side against the slider and your thumb's from (f), a screenshot of anything that did not fit from (g), and, if you ran the experiment (h), the five pictures' verdicts and the times.
28. From section 35 (audiobook polish for Speech): the `check_image:` ffmpeg line and the `ls -l data/studio.sqlite*` line, the table of which respellings worked in which engine from (b), your verdict on the voice changes and on the pause between speakers and the times from (d), any false alarm from (e), whether the chapter times matched by ear in (f), the M4B's build time and size and, for each player, whether the chapters and the resume worked from (g), and a screenshot of anything on the phone that did not fit.
29. From section 36 (search and tags): the `ls -l data/studio.sqlite*` line and the indexing line from the log, the runs that were not found in (a), the seconds and your verdict on the tags and the memory numbers from (b), the three greyed messages from (c), the time zones and any run on the wrong side of midnight from (f), a screenshot of anything on the phone that did not fit, and anything that did not match "Good".
30. From section 37 (LTX-2.5, the experiment before the Video tab): **already sent (2026-11-19 to 11-23): (a), (b) warm, (c), the lengths of (d) and your verdicts, and the first-frame clip of (e) with "it looks fine"**. **Still to send:** the Python version `uv sync` chose, a cold load time (b), what `--quantization fp8-cast`, `nvfp4-prequant`, `--offload cpu` and the dev checkpoint did (d, if you run them), your comparison of the first frame with your picture, strength 0.6 and the end frame (e), what you saw and heard at each join and whether the third link was worse (f), the lengths the duration head chose (g), the audio format and your verdict on speech, ambience, music and the voice across seeds (h), the `free -g` lines and what happened next to the studio and Ollama (i), and the three clips of (k) (`step4b.sh`: seed 11 at 20 and 30 s, and 30 s with `--chunked`) with your verdicts and the `Plan: N chunks` line, and the CSV files if you want the curves read.

**Part 2, release 1.27 (item 32, added 2026-11-24)**

32. From section 39 (the Video tab through the studio): the three commands of (a), the `Video:` lines of (b) (and `docker compose config | grep -B1 -A3 ltx-experiment`), the first failing step's words from (c) with the `env` lines and whether **Check again** moved it on, whether the licence summary of (d) matches the model's page, from (e) the seconds, whether each stage name appeared, the estimate against the truth, the `ffprobe` line and whether the clip played with sound on the phone (and the card's words and the log's last 60 lines if it failed), from (f) the seconds and whether the first frame was your picture, from (g) the seconds from Cancel to *Canceled*, the memory numbers and the `ps` output, from (h) the estimates after the first, second and fifth clip, from (i) the pill's words, the swap seconds and the memory numbers, from (j) the `ls` and `du` lines and the `before-schema-14` file, from (k) the backup summary's words, from (l) a screenshot of anything that did not fit, from (m) the build's result if you tried it, and from (n) the by-hand times and memory peaks of HD and Scope, the tab's seconds, the trim's extra seconds, the file sizes (the program's and the studio's), the estimate against the truth, and what the two sizes look like.

**Part 2, release 1.23 (item 31, added 2026-11-17)**

31. From section 38 (Vector, thin lines kept and widened): whether the vector of (a) keeps the fine lines of its drawing and what is still missing, the note and the numbers from (b), which of `thicken` and `drop` you prefer and the two `svg_bytes` from (c), the notes and your verdict at 0.15, 1 and 3 mm from (d), the tracing seconds from (e), what the laser programs showed in (f), and anything that did not match "Good".
