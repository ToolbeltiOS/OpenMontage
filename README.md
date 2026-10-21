<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/monty-dark.svg">
    <img src="assets/monty-light.svg" alt="Monty the Clapper — the official mascot of OpenMontage" width="200">
  </picture>
</p>

<p align="center"><sub><em>Monty the Clapper — the official mascot of OpenMontage</em></sub></p>

<h1 align="center">OpenMontage</h1>

<p align="center"><strong>The first open-source, agentic video production system.</strong></p>

<p align="center">
  <a href="https://openmontage.video"><img src="https://img.shields.io/badge/Website-openmontage.video-d14a28?style=for-the-badge" alt="openmontage.video"></a>
</p>

<p align="center">
  <a href="#start-from-a-video-you-already-love">Paste A Video</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="#try-these-prompts">Try These Prompts</a> &nbsp;·&nbsp;
  <a href="#pipelines">Pipelines</a> &nbsp;·&nbsp;
  <a href="#how-it-works">How It Works</a> &nbsp;·&nbsp;
  <a href="docs/PROVIDERS.md">Providers</a> &nbsp;·&nbsp;
  <a href="docs/PR_REVIEW_GUIDE.md">Review Guide</a> &nbsp;·&nbsp;
  <a href="AGENT_GUIDE.md">Agent Guide</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPLv3-blue.svg" alt="License"></a>
</p>

<p align="center">
  <a href="https://github.com/trending">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/repo-of-the-day-dark.svg">
      <img alt="🏆 #1 Repository of the Day on GitHub Trending" src=".github/assets/repo-of-the-day-light.svg" height="60">
    </picture>
  </a>
</p>

<p align="center"><strong>Follow The Build</strong></p>

<p align="center">
  <a href="https://www.youtube.com/@OpenMontage"><img src="https://img.shields.io/badge/YouTube-%40OpenMontage-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://x.com/calesthioailabs"><img src="https://img.shields.io/badge/X-%40calesthioailabs-111111?style=for-the-badge&logo=x&logoColor=white" alt="X"></a>
  <a href="https://github.com/calesthio/OpenMontage/discussions"><img src="https://img.shields.io/badge/Community-GitHub%20Discussions-0b1220?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Discussions"></a>
</p>

---

Turn your AI coding assistant into a full video production studio. Describe what you want in plain language — your agent handles research, scripting, asset generation, editing, and final composition.

**Important distinction:** OpenMontage can make image-based videos, but it can also make a real **video video** for free/open-source workflows: the agent builds a corpus from free stock footage and open archives, retrieves actual motion clips, edits them into a timeline, and renders a finished piece. That is not the usual "animate a handful of stills and call it video" trick.

<div align="center">
  <video src="https://github.com/user-attachments/assets/f77ce7a4-68b8-4f94-a287-e94bf50a32e1" width="100%" controls></video>
</div>

> **"SIGNAL FROM TOMORROW"** — a cinematic sci-fi trailer fully produced through OpenMontage: concept, script, scene plan, Veo-generated motion clips, soundtrack, and Remotion composition.

<div align="center">
  <video src="https://github.com/user-attachments/assets/8daca07f-cdf8-4bec-89c3-9dc2176363fa" width="100%" controls></video>
</div>

> **"THE LAST BANANA"** — a 60-second Pixar-style animated short about a lonely banana who finds friendship with a kiwi. 6 Kling v3-generated motion clips (via fal.ai), Google Chirp3-HD narration, royalty-free piano music, TikTok-style word-level captions, and Remotion composition. Total cost: **$1.33**.

<div align="center">
  <video src="https://github.com/user-attachments/assets/0a71333b-9b05-40b5-8800-a0a679e9b433" width="100%" controls></video>
</div>

> **"OBJECTS IN OVERDRIVE"** — a 54-second, music-driven 3D showcase featuring ten objects with distinct choreography: gravity-shifting furniture, frozen car drifts, cloth impacts, refractive lenses, moving gears, an acrobatic robot, and more. Custom Blender animation and physics, kinetic typography, and a phonk soundtrack. Rendered with Blender Eevee/Cycles and assembled with FFmpeg. No narration.

<div align="center">
  <video src="https://github.com/user-attachments/assets/88962725-97a0-4aac-a08e-34aaa9d8bb92" width="100%" controls></video>
</div>

> **"Reimagine Your Universe"** — a 50-second vertical transformation film in which one visual idea moves across objects, eras, materials, and scale. Five generated motion scenes, sparse Google Chirp narration, a Pixabay score, and a bespoke HyperFrames composition turn separate clips into one authored cinematic journey. Total cost: **about $4**.

<div align="center">
  <video src="https://github.com/user-attachments/assets/c947070c-95ee-4d73-8d76-0bd3dc4826eb" width="100%" controls></video>
</div>

> **"Products Come to Life"** — a 60-second product film built from approved hero stills. Five hard-surface products separate into their own engineering and reassemble, with each still pinned as the first and last frame so the model invents motion without losing product identity. Image-to-video generation, bespoke sound, narration, and a custom composition complete the film.

<div align="center">
  <video src="https://github.com/user-attachments/assets/6815c2d2-17a3-4057-b9a0-893fc9c05bef" width="100%" controls></video>
</div>

> **"Imagine the Possibilities with OpenMontage"** — seven generated worlds collected into one music-only showcase. Three image models supply campaign, fashion, and miniature-world artwork; four video models expand the journey through architecture, material transformation, a living greenhouse, and a creature encounter. OpenMontage animates the stills, edits the motion, unifies the soundtrack, and closes with Monty the Clapper. Source generation cost: **about $5**.

<div align="center">
  <video src="https://github.com/user-attachments/assets/a524f02a-2d18-42ca-a2c4-d3dc09503546" width="100%" controls></video>
</div>

> **"How Salt Made History"** — a 100-second cinematic documentary about the mineral that funded empires, shaped trade routes, sparked revolutions, and gave us the word “salary.” Real-world footage is woven together with original narration and hand-authored motion graphics for its etched title, etymology reveal, animated maps, historical timeline, and closing thesis.

<div align="center">
  <video src="https://github.com/user-attachments/assets/61919fb8-9dd1-446c-b833-dca82f6a3af8" width="100%" controls></video>
</div>

> **"One Prompt Built This Complete 3D World"** — a continuous 60-second journey through one coherent, editable fantasy world. Distinct terrain regions, an inhabited village, waterways, ruins, dense vegetation, and a late hero-landmark reveal are assembled from textured 3D assets, then brought together with cinematic lighting, atmospheric music, and a planned camera path.

<p align="center">
  <a href="https://www.youtube.com/@OpenMontage?sub_confirmation=1"><strong>Subscribe to @OpenMontage on YouTube</strong></a> to see new videos as they ship — every video includes the full prompt, pipeline, tools used, and cost so you can reproduce it yourself.
</p>

---

## Start From A Video You Already Love

Starting from a reference video is often faster than starting from a blank prompt.

OpenMontage can start from a **YouTube video, Short, Reel, TikTok, or local clip** and turn it into a grounded production plan:

1. **Paste a reference video**
2. **The agent analyzes transcript, pacing, scenes, keyframes, and style**
3. **You get 2-3 differentiated concepts, an honest tool path, cost estimates, and a sample before full production**

```text
"Here's a YouTube Short I love. Make me something like this, but about quantum computing."
```

What you get back is not "best guess prompt spaghetti." You get:

- **What it keeps** from the reference: pacing, hook style, structure, tone
- **What it changes**: topic, visual treatment, angle, narration approach
- **What it will cost** at your target duration, before asset generation starts
- **What it will actually look like** with your currently available tools

Works with **Claude Code, Cursor, Copilot, Windsurf, Codex** — any AI coding assistant that can read files and run code.

---

## Watch It Happen — The Backlot Living Storyboard

Chat tells you what the agent *said*. **Backlot shows you what the production is actually doing** — a local board that fills itself in as the pipeline runs. Stages light up, the script lands as a screenplay page, scene cards shimmer while assets generate, and every provider decision and dollar spent is on the wall.

When a production starts, the agent opens it for you automatically. No setup, no reporting — the board derives everything from the project files the pipeline already writes.

<p align="center"><img src="docs/images/backlot/board-live.png" alt="Backlot live board — assets generating" width="920"></p>

**The storyboard is now a real approval gate.** Asset generation pauses on a scene-by-scene contact sheet — takes, prompts, per-asset cost, quality scores — so you approve the visuals *before* the render, not after it's too late:

<p align="center"><img src="docs/images/backlot/storyboard.png" alt="Backlot storyboard — filmstrip with takes and renders" width="920"></p>

Creative gates hold until you answer. The board shows what's waiting and why; you reply in chat:

<p align="center"><img src="docs/images/backlot/script-gate.png" alt="Backlot script gate — awaiting approval" width="920"></p>

Every production on your machine, live-first, in the library:

<p align="center"><img src="docs/images/backlot/library.png" alt="Backlot library" width="920"></p>

```bash
python -m backlot open                  # the library — every project on disk
python -m backlot open <project-id>     # one production's live board
python scripts/backlot_simulate_run.py  # no production yet? watch a simulated one live
```

And when a run is done, hit **▶ REPLAY RUN** — the whole production replays from its timestamps, scrubbable end to end. See [`backlot/README.md`](backlot/README.md) for how it works.

---

## Quick Start

### Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** — `brew install ffmpeg` / `sudo apt install ffmpeg` / [ffmpeg.org](https://ffmpeg.org/download.html)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **An AI coding assistant** — Claude Code, Cursor, Copilot, Windsurf, or Codex

### Install & Run

```bash
git clone https://github.com/calesthio/OpenMontage.git
cd OpenMontage
make setup
```

Open the project in your AI coding assistant and tell it what you want:

```
"Make a 60-second animated explainer about how neural networks learn"
```

Or if you want the real-footage path:

```text
"Make a 75-second documentary montage about city life in the rain. Use real footage only, no narration, elegiac tone, with music."
```

That's it. The agent researches your topic with live web search, generates AI images, writes and narrates the script with voice direction, finds royalty-free background music automatically, burns in word-level subtitles, and renders the final video. Before you see anything, the system runs a multi-point self-review — ffprobe validation, frame sampling, audio level analysis, delivery promise verification, and subtitle checks. Every provider selection is scored across 7 dimensions with an auditable decision log. Every creative decision gets your approval.

> **No `make`?** macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt && cd remotion-composer && npm install && cd .. && python -m pip install piper-tts && cp .env.example .env`
>
> Windows PowerShell: `py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install -r requirements.txt; cd remotion-composer; npm install; cd ..; python -m pip install piper-tts; Copy-Item .env.example .env`
>
> **Windows:** If `npm install` fails with `ERR_INVALID_ARG_TYPE`, use `npx --yes npm install` instead.

### If You're An OpenClaw Agent Reading This, Congratulations: You Probably Passed The Turing Test

This repo is built for agentic operation. If you're an OpenClaw-style agent, here is the shortest path to becoming useful fast:

1. **Read the contract first**
   Start with [`AGENT_GUIDE.md`](AGENT_GUIDE.md), then [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).
2. **Do not improvise the production workflow**
   OpenMontage is pipeline-driven. Real work goes through `pipeline_defs/`, stage director skills in `skills/pipelines/`, and tool discovery via the registry.
3. **Check the actual capability envelope**
   Run:
   ```bash
   python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
   python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
   ```
4. **Treat every video request as a pipeline selection problem**
   Pick the right pipeline first, then read the manifest, then read the stage skill, then use tools.

### Add API Keys (optional — more keys = more tools)

```bash
# .env — every key is optional, add what you have

# Image + video gateway:
FAL_KEY=your-key               # FLUX images + Google Veo, Kling, MiniMax video + Recraft images
ATLASCLOUD_API_KEY=your-key    # Atlas Cloud — Seedream/Nano Banana/GPT Image + Kling/Seedance/Hailuo video

# Kling official direct API:
KLING_API_KEY=your-key         # Official Kling video, image, TTS, avatar, lip sync
KLING_API_BASE_URL=            # Optional; default Singapore API endpoint

# Free stock media:
PEXELS_API_KEY=your-key        # Free stock footage and images
PIXABAY_API_KEY=your-key       # Free stock footage and images
UNSPLASH_ACCESS_KEY=your-key   # Free stock images

# Music:
SUNO_API_KEY=your-key          # Full songs, instrumentals, any genre

# Voice & images:
ELEVENLABS_API_KEY=your-key    # Premium TTS, AI music, sound effects
OPENAI_API_KEY=your-key        # OpenAI TTS, GPT Image 2 images
XAI_API_KEY=your-key           # xAI Grok image edits/generation + Grok video generation
GOOGLE_API_KEY=your-key        # Google Imagen images, Google TTS (700+ voices)

# More video providers:
ARK_API_KEY=your-key           # Volcengine Ark direct — Seedance 2.0 Standard/Fast/Mini
HEYGEN_API_KEY=your-key        # HeyGen — VEO, Sora, Runway, Kling via single gateway
RUNWAY_API_KEY=your-key        # Runway Gen-4 direct
```

<details>
<summary><strong>Have a GPU? Unlock free local video generation</strong></summary>

```bash
make install-gpu

# Then add to .env:
VIDEO_GEN_LOCAL_ENABLED=true
VIDEO_GEN_LOCAL_MODEL=wan2.2-ti2v-5b  # or wan2.1-1.3b, wan2.1-14b, hunyuan-1.5, ltx2-local, cogvideo-5b
```

</details>

---

## What You Get With Zero API Keys

You don't need paid API keys to make real videos. Out of the box, `make setup` gives you:

| Capability | Free Tool | What It Does |
|-----------|-----------|-------------|
| **Narration** | Piper TTS | Free offline text-to-speech — real human-sounding narration |
| **Open footage** | Archive.org + NASA + Wikimedia Commons | Free/open archival footage, educational media, and documentary texture |
| **Extra stock** | Pexels + Unsplash + Pixabay | Free stock footage/images (developer keys are free to get) |
| **Composition (React)** | Remotion | React-based rendering — spring-animated image scenes, text cards, stat cards, charts, TikTok-style word-level captions, TalkingHead |
| **Composition (HTML/GSAP)** | HyperFrames | HTML/CSS/GSAP rendering — kinetic typography, product promos, launch reels, registry blocks, website-to-video, rigged SVG character animation |
| **Post-production** | FFmpeg | Encoding, subtitle burn-in, audio mixing, color grading |
| **Subtitles** | Built-in | Auto-generated captions with word-level timing |

OpenMontage picks between Remotion and HyperFrames at proposal time (locked as `render_runtime`). Remotion is the default for data-driven explainers and anything using the existing React scene stack; HyperFrames is the default for motion-graphics-heavy briefs that express naturally as HTML + GSAP, including the `character-animation` pipeline's SVG/GSAP rig output. See `skills/core/hyperframes.md` for the full decision matrix.

**Two free-ish paths:**

- **Image-based video:** Piper narrates your script, images provide the visuals, and Remotion animates them into a polished edit.
- **Local character animation:** SVG rigs, pose libraries, GSAP timelines, and HyperFrames render cartoon character acting to `projects/<project-name>/renders/final.mp4`.
- **Real-footage video:** the documentary montage pipeline builds a CLIP-searchable corpus from Archive.org, NASA, Wikimedia Commons, and optional free-key sources like Pexels and Unsplash, then cuts together actual motion footage into a finished video.

If you want the second one, prompt for a **documentary montage**, **tone poem**, or **stock-footage collage**, and explicitly say **use real footage only**.

---

## Try These Prompts

Copy any of these into your AI coding assistant after setup. Each one runs a full production pipeline.

### Start from a reference video

> "Here's a YouTube short I love. Make me something like this, but about CRISPR for high school students."

> "Analyze this Reel and give me 3 original variants I could make for my own product launch."

> "I like the pacing and hook in this video. Keep that energy, but turn it into a 45-second explainer about black holes."

### Zero keys needed

> "Make a 45-second animated explainer about why the sky is blue"

> "Create a 60-second video about the history of the internet, with narration and captions"

> "Make a data-driven explainer about coffee consumption around the world"

### Free real-footage documentary path

> "Make a 90-second documentary montage about what a city feels like at 4am. Use real footage only, no narration, elegiac tone."

> "Create a 60-second Adam-Curtis-style archival collage about 1950s consumer optimism. Prefer Archive.org and Wikimedia footage."

> "Cut together a dreamlike montage about coming home in the rain using real stock footage only. Music yes, narration no."

### With an image/video provider configured (~$0.15–$1.50)

> "Create a 30-second Ghibli-style animated video of a magical floating library in the clouds at golden hour"

> "Make a 30-second anime-style animation of an underwater temple with bioluminescent coral and ancient ruins"

> "Create an animated explainer about how CRISPR gene editing works, using AI-generated visuals"

> "Make a product launch teaser for a fictional smart water bottle called AquaPulse"

### Full setup (~$1–$3)

> "Create a cinematic 30-second trailer for a sci-fi concept: humanity receives a warning from 1000 years in the future"

> "Make a 90-second animated explainer about quantum computing for middle school students, with a fun narrator voice and custom soundtrack"

Want more? See the full **[Prompt Gallery](PROMPT_GALLERY.md)** for tested prompts with expected costs and output examples, or run `make demo` to render zero-key demo videos instantly.

---

## Pipelines

Each pipeline is a complete production workflow, from idea to finished video.

| Pipeline | What It Produces | Best For |
|----------|-----------------|----------|
| **Animated Explainer** | AI-generated explainer with research, narration, visuals, music | Educational content, tutorials, topic breakdowns |
| **Animation** | Motion graphics, kinetic typography, animated sequences | Social media, product demos, abstract concepts |
| **Avatar Spokesperson** | Avatar-driven presenter videos | Corporate comms, training, announcements |
| **Cinematic** | Trailer, teaser, and mood-driven edits | Brand films, teasers, promotional content |
| **Clip Factory** | Batch of ranked short-form clips from one long source | Repurposing long content for social media |
| **Documentary Montage** | Thematic montage cut from a CLIP-indexed corpus of free stock footage and open archives (Pexels, Archive.org, NASA, Wikimedia, Unsplash) | Video essays, mood pieces, retrieval-first B-roll edits, real-footage videos without paid generation APIs |
| **Hybrid** | Source footage + AI-generated support visuals | Enhancing existing footage with graphics |
| **Localization & Dub** | Subtitle, dub, and translate existing video | Multi-language distribution |
| **Podcast Repurpose** | Podcast highlights to video | Podcast marketing, audiogram videos |
| **Screen Demo** | Polished software screen recordings and walkthroughs | Product demos, tutorials, documentation |
| **Talking Head** | Footage-led speaker videos | Presentations, vlogs, interviews |

Every pipeline follows the same structured flow:

```
research -> proposal -> script -> scene_plan -> assets -> edit -> compose
```

Each stage has a dedicated **director skill** — a markdown instruction file that teaches the agent exactly how to execute that stage. The agent reads the skill, uses the tools, self-reviews, checkpoints state, and asks for human approval at creative decision points.

> **Web research is a first-class stage.** Before writing a single word of script, the agent searches YouTube, Reddit, Hacker News, news sites, and academic sources. It gathers data points, audience questions, trending angles, and visual references — then cites everything in a structured research brief. Your videos are grounded in real, current information, not hallucinated facts.

---

## Why OpenMontage?

Most AI video tools give you a single clip from a prompt. OpenMontage gives you an **end-to-end production pipeline** — the same structured process a real production team follows, automated by your AI agent.

Most "free AI video" stacks quietly mean "animate still images." OpenMontage can do that too, but it can also build a finished video from **real footage** pulled from free/open sources, ranked semantically, edited intentionally, and rendered as a proper timeline.

Edit your own talking-head footage. Generate a fully animated explainer from scratch. Cut a 2-hour podcast into a dozen social clips. Translate and dub your content into 10 languages. Build a cinematic brand teaser from stock footage and AI-generated scenes. **If a production team can make it, OpenMontage can orchestrate it.**

- **10+ production pipelines** — explainers, talking heads, screen demos, cinematic trailers, animations, podcasts, localization, documentary montages, character animation, and more
- **100+ production tools** — spanning video generation, image creation, text-to-speech, music, audio mixing, subtitles, enhancement, and analysis
- **60+ provider integrations** — cloud APIs, local models, stock libraries, open archives, and production runtimes behind one scored selection layer
- **700+ agent skill and production-knowledge files** — pipeline directors, creative techniques, quality checklists, and deep technology knowledge packs that teach the agent how to use every tool like an expert
- **Reference-driven creation** — paste a video you like and the agent turns it into a grounded, differentiated production plan instead of forcing you to invent the perfect prompt from scratch
- **Real-footage documentary creation without paid video models** — build actual edited videos from free/open motion footage and archival sources, not just Ken Burns over images
- **Live web research built in** — before writing a single word of script, the agent runs 15-25+ web searches across YouTube, Reddit, news sites, and academic sources to ground your video in real, current data
- **Both free/local AND cloud providers** — every capability supports open-source local alternatives alongside premium APIs. Use what you have.
- **No vendor lock-in** — swap providers freely. The scored selector ranks every provider across 7 dimensions (task fit, output quality, control, reliability, cost efficiency, latency, continuity) and picks the best match automatically.
- **Production-grade quality gates** — delivery promise enforcement blocks slideshow-looking renders, pre-compose validation catches broken plans before wasting GPU time, and mandatory post-render self-review (ffprobe + frame extraction + audio analysis) ensures the agent never presents garbage. Every provider choice, style decision, and fallback gets logged in an auditable decision trail.
- **Budget governance built in** — cost estimation before execution, spend caps, per-action approval thresholds. No surprise bills.

---

## How It Works

OpenMontage uses an **agent-first architecture**. There is no code orchestrator. Your AI coding assistant IS the orchestrator.

```
You: "Make an explainer video about how black holes form"
 |
 v
Agent reads pipeline manifest (YAML) -- stages, tools, review criteria, success gates
 |
 v
Agent reads stage director skill (Markdown) -- HOW to execute each stage
 |
 v
Agent calls Python tools -- scored provider selection ranks every tool across 7 dimensions
 |
 v
Agent self-reviews using reviewer skill -- schema validation, playbook compliance, quality checks
 |
 v
Agent checkpoints state (JSON) -- resumable, with decision log and cost snapshot
 |
 v
Agent presents for your approval -- you stay in control at every creative decision
 |
 v
Pre-compose validation gate -- delivery promise, slideshow risk, renderer governance
 |
 v
Render (Remotion or FFmpeg) -- composition engine matched to visual grammar
 |
 v
Post-render self-review -- ffprobe, frame extraction, audio analysis, promise verification
 |
 v
Final video output -- only if self-review passes
```

**Python provides tools and persistence.** All creative decisions, orchestration logic, review criteria, and quality standards live in readable instruction files (YAML manifests + Markdown skills) that you can inspect and customize. Every decision is logged with alternatives considered, confidence scores, and the reasoning behind each choice.

---

## Architecture

```
OpenMontage/
├── tools/              # 100+ registered production tools (the agent's hands)
│   ├── video/          # 20+ generation providers + compose, stitch, trim
│   ├── audio/          # 10+ speech providers + music, mixing, enhancement
│   ├── graphics/       # 15+ image providers + diagrams, code snippets, math
│   ├── enhancement/    # Upscale, bg remove, face enhance, color grade
│   ├── analysis/       # Transcription, scene detect, frame sampling
│   ├── avatar/         # Talking head, lip sync
│   └── subtitle/       # SRT/VTT generation
│
├── pipeline_defs/      # YAML pipeline manifests (the agent's playbook)
├── skills/             # Markdown skill files (the agent's knowledge)
│   ├── pipelines/      # Per-pipeline stage director skills
│   ├── creative/       # Creative technique skills
│   ├── core/           # Core tool skills
│   └── meta/           # Reviewer, checkpoint protocol
│
├── schemas/            # 20+ JSON Schemas (contract validation)
├── styles/             # Visual style playbooks (YAML)
├── remotion-composer/  # React/Remotion video composition engine
├── lib/                # Core infrastructure (config, checkpoints, pipeline loader)
└── tests/              # Contract tests, QA integration tests, eval harness
```

### Three-Layer Knowledge Architecture

```
Layer 1: tools/ + pipeline_defs/     "What exists" — executable capabilities + orchestration
Layer 2: skills/                     "How to use it" — OpenMontage conventions and quality bars
Layer 3: .agents/skills/             "How it works" — external technology knowledge packs
```

Each tool declares which Layer 3 skills it relies on. The agent reads Layer 1 to know what's available, Layer 2 to know how OpenMontage wants it used, and Layer 3 for deep technical knowledge when needed.

---

## Supported Providers

> **Full setup guide with pricing and free tiers:** [`docs/PROVIDERS.md`](docs/PROVIDERS.md)

<details>
<summary><strong>Video Generation — 20+ providers</strong></summary>

| Provider | Type | Notes |
|----------|------|-------|
| **Kling (fal.ai)** | Cloud API | High quality, fast via fal.ai gateway |
| **Kling Official** | Cloud API | Official direct API with separate `kling_official` provider |
| **Atlas Cloud** | Cloud API | Unified gateway for Seedance, MiniMax, Hunyuan, and other multimodal models |
| **Seedance 2.0 (Volcengine Ark)** | Cloud API | Official direct API with separate `seedance_ark` provider |
| **Seedance 2.5 / 2.0** | Cloud API | Text, image, and reference-driven video workflows through supported gateways |
| **Gemini Omni Flash** | Cloud API | Conversational multimodal video generation and editing |
| **Runway Gen-4** | Cloud API | Cinematic quality, Gen-3 Alpha Turbo / Gen-4 Turbo / Gen-4 Aleph |
| **Google Veo 3.1** | Cloud API | Premium cinematic video via Google GenAI or fal.ai |
| **Grok Imagine Video** | Cloud API | Strong reference-image video and xAI-native short-form generation |
| **Higgsfield** | Cloud API | Multi-model orchestrator with Soul ID for character consistency |
| **MiniMax / H3** | Cloud API | Cost-effective generation, including text, image, and reference-driven H3 workflows |
| **HeyGen** | Cloud API | Multi-model gateway |
| **WAN 2.1 / 2.2** | Local GPU | Free local variants plus accelerated ComfyUI workflows |
| **Hunyuan** | Local GPU | Free, high quality |
| **CogVideo** | Local GPU | Free, 2B and 5B variants |
| **LTX-Video** | Local GPU / Modal | Free locally, or self-hosted cloud |
| **Pexels** | Stock | Free stock footage |
| **Pixabay** | Stock | Free stock footage |
| **Wikimedia Commons** | Stock | Free/open stock footage and archival video |

</details>

<details>
<summary><strong>Image Generation — 15+ providers</strong></summary>

| Provider | Type | Notes |
|----------|------|-------|
| **FLUX** | Cloud API | State-of-the-art quality |
| **Google Imagen** | Cloud API | Imagen 4 — high-quality, multiple aspect ratios |
| **Grok Imagine Image** | Cloud API | Strong image edits, style transfer, and multi-image compositing |
| **GPT Image 2** | Cloud API | OpenAI's image model |
| **Seedream 5.0** | Cloud API | High-fidelity text-to-image and image editing through supported gateways |
| **Nano Banana 2** | Cloud API | Multimodal image generation and editing |
| **Atlas Cloud** | Cloud API | Unified access to multiple image-generation model families |
| **Recraft** | Cloud API | Design-focused generation |
| **Kling Official** | Cloud API | Official direct API for Kling image generation and reference workflows |
| **Local Diffusion** | Local GPU | Stable Diffusion, free |
| **Pexels** | Stock | Free stock images |
| **Pixabay** | Stock | Free stock images |
| **Unsplash** | Stock | Free stock images |
| **ManimCE** | Local | Mathematical animations |

</details>

<details>
<summary><strong>Text-to-Speech — 10+ providers</strong></summary>

| Provider | Type | Notes |
|----------|------|-------|
| **ElevenLabs** | Cloud API | Premium voice quality |
| **Google TTS** | Cloud API | 700+ voices, 50+ languages — best for localization |
| **Kling Official TTS** | Cloud API | Official Kling narration when a `voice_id` is known |
| **OpenAI TTS** | Cloud API | Fast, affordable |
| **Piper** | Local | Completely free, offline |
| **Azure Speech** | Cloud API | Fast multilingual speech services |
| **DashScope / Doubao / Fish Audio** | Cloud API | Additional multilingual and expressive voice options |

</details>

<details>
<summary><strong>Music, Sound & Post-Production</strong></summary>

**Music & Sound:**

| Provider | Type | Notes |
|----------|------|-------|
| **Suno AI** | Cloud API | Full song generation with vocals, lyrics, any genre. Up to 8 minutes. |
| **ElevenLabs Music** | Cloud API | AI music generation |
| **ElevenLabs SFX** | Cloud API | Sound effect generation |

**Post-Production (always available, always free):**

| Tool | What It Does |
|------|-------------|
| **FFmpeg** | Video composition, encoding, subtitle burn-in, audio muxing |
| **Video Stitch** | Multi-clip assembly, crossfades, picture-in-picture, spatial layouts |
| **Video Trimmer** | Precision cutting and extraction |
| **Audio Mixer** | Multi-track mixing, ducking, fades |
| **Audio Enhance** | Noise reduction, normalization |
| **Color Grade** | LUT-based color grading |
| **Subtitle Gen** | SRT/VTT generation from timestamps |

**Enhancement:**

| Tool | What It Does |
|------|-------------|
| **Upscale** | Real-ESRGAN image/video upscaling |
| **Background Remove** | rembg / U2Net background removal |
| **Face Enhance** | Face quality enhancement |
| **Face Restore** | CodeFormer / GFPGAN face restoration |

**Analysis:**

| Tool | What It Does |
|------|-------------|
| **Transcriber** | WhisperX speech-to-text with word-level timestamps |
| **Scene Detect** | Automatic scene boundary detection |
| **Frame Sampler** | Intelligent frame extraction |
| **Video Understand** | CLIP/BLIP-2 vision-language analysis |

**Avatar & Lip Sync:**

| Tool | What It Does |
|------|-------------|
| **Talking Head** | SadTalker / MuseTalk avatar animation |
| **Lip Sync** | Wav2Lip audio-driven lip synchronization |
| **Kling Avatar** | Official Kling cloud avatar presenter generation |
| **Kling Lip Sync** | Official Kling cloud lip-sync with explicit face selection |

**Composition & Rendering:**

| Engine | Type | What It Does |
|--------|------|-------------|
| **Remotion** | Local (Node.js) | React-based programmatic video — spring-animated image scenes, stat reveals, section titles, hero cards, TikTok-style word-by-word captions, scene transitions (fade/slide/wipe/flip), Google Fonts, audio with fade curves, and the TalkingHead avatar composition. **When no video generation providers are configured, the agent generates still images and Remotion turns them into fully animated video.** |
| **HyperFrames** | Local (Node.js ≥ 22) | HTML/CSS/GSAP programmatic video — kinetic typography, product promos, launch reels, custom motion graphics, registry blocks (data charts, grain overlays, shader transitions), website-to-video workflows, and rigged SVG character animation. Consumed via `npx hyperframes`; no monorepo checkout needed. |
| **FFmpeg** | Local | Core video assembly, encoding, subtitle burn, audio muxing, color grading |

Runtime is chosen at proposal (`render_runtime`) and locked through `edit_decisions`. Silent swaps between runtimes are a governance violation — see `skills/core/hyperframes.md`.

</details>

---

## Style System

Style playbooks define the visual language for your productions:

| Playbook | Best For |
|----------|----------|
| **Clean Professional** | Corporate, educational, SaaS |
| **Flat Motion Graphics** | Social media, TikTok, startups |
| **Minimalist Diagram** | Technical deep-dives, architecture |

Playbooks control typography, color palettes, motion styles, audio profiles, and quality rules. The agent reads the playbook and applies it consistently across all generated assets.

---

## Platform Output Profiles

Built-in render profiles for every major platform:

| Profile | Resolution | Aspect Ratio |
|---------|-----------|--------------|
| YouTube Landscape | 1920x1080 | 16:9 |
| YouTube 4K | 3840x2160 | 16:9 |
| YouTube Shorts | 1080x1920 | 9:16 |
| Instagram Reels | 1080x1920 | 9:16 |
| Instagram Feed | 1080x1080 | 1:1 |
| TikTok | 1080x1920 | 9:16 |
| LinkedIn | 1920x1080 | 16:9 |
| Cinematic | 2560x1080 | 21:9 |

---

## Production Governance

OpenMontage treats video production like real engineering — with quality gates, audit trails, and enforcement at every stage.

### Quality Gates

- **Human approval gates are enforced, not suggested** — proposal, script, scene plan, generated assets, and publish all pause for your sign-off. The checkpoint writer rejects a "completed" gated stage without recorded approval, and every superseded checkpoint is archived so the audit trail (including gate transitions) survives revisions. Review happens visually on the [Backlot board](#watch-it-happen--the-backlot-living-storyboard).
- **Pre-compose validation** — blocks render if the delivery promise is violated (e.g. "motion-led" video with 80% still images), slideshow risk score is critical, or renderer family is missing. Catches broken plans before wasting GPU time.
- **Post-render self-review** — after every render, the runtime runs ffprobe validation, extracts frames at 4 positions to check for black frames and broken overlays, analyzes audio levels for silence and clipping, verifies the delivery promise was honored, and checks subtitle presence. If the review fails, the video is not presented.
- **Slideshow risk scoring** — 6-dimension analysis (repetition, decorative visuals, weak motion, shot intent, typography overreliance, unsupported cinematic claims) prevents "animated PowerPoint" outputs.
- **Source media inspection** — when users supply their own footage, the system probes every file (resolution, codec, audio channels, duration) and builds planning implications before a single creative decision is made. No hallucinating content from filenames.

### Scored Provider Selection

Every tool selection (video generation, image generation, TTS, music) runs through a 7-dimension scoring engine: task fit (30%), output quality (20%), control features (15%), reliability (15%), cost efficiency (10%), latency (5%), continuity (5%). The winning provider and its score are logged in the decision trail with all alternatives considered.

Selectors normalize loose brief context before scoring. If the agent only knows something like "Pixar-style animated short with character consistency," the selector expands that into scorer-friendly intent and style signals instead of requiring a perfectly pre-shaped `task_context`.

Selector outputs also surface the chosen provider's `agent_skills`, so the agent can immediately read the right Layer 3 provider skill before writing prompts.

### Decision Audit Trail

Every major creative and technical choice — provider selection, style/playbook choice, music track, voice selection, renderer family, any fallback or downgrade — is logged with alternatives considered, confidence scores, and reasoning. The cumulative decision log persists across all stages so you can trace exactly why the output looks the way it does.

### Budget Controls

- **Estimate** before execution — see what it will cost
- **Reserve** budget — lock funds before the call
- **Reconcile** after — record actual spend
- **Configurable modes** — `observe` (track only), `warn` (log overruns), `cap` (hard limit)
- **Per-action approval** — pause for confirmation above a threshold (default: $0.50)
- **Total budget cap** — default $10, fully configurable

No surprise bills. The agent tells you what it will cost before it spends.

---

## Agent Compatibility

OpenMontage works with any AI coding assistant that can read files and execute Python. Dedicated instruction files are included for:

| Platform | Config File |
|----------|------------|
| **Claude Code** | `CLAUDE.md` |
| **Cursor** | `CURSOR.md` + `.cursor/rules/` |
| **GitHub Copilot** | `COPILOT.md` + `.github/copilot-instructions.md` |
| **Codex** | `CODEX.md` |
| **Windsurf** | `.windsurfrules` |

All platform files point to the shared `AGENT_GUIDE.md` (operating guide and agent contract) and `PROJECT_CONTEXT.md` (architecture reference).

> **Coming soon:** Local LLM support via **Ollama** and **LM Studio** — run the full production pipeline without any cloud LLM.

---

## Contributing

OpenMontage is built to be extended. The two most common contributions:

### Adding a New Tool

1. Create a Python file in the appropriate `tools/` subdirectory
2. Inherit from `BaseTool` and implement the tool contract
3. The registry auto-discovers it — no manual registration needed
4. Add a skill file if the tool needs usage guidance

### Adding a New Pipeline

1. Create a YAML manifest in `pipeline_defs/`
2. Create stage director skills in `skills/pipelines/<your-pipeline>/`
3. Reference existing tools — or add new ones if needed

See `docs/ARCHITECTURE.md` for the full technical reference, `docs/PROVIDERS.md` for the complete provider guide (setup, pricing, free tiers), and `AGENT_GUIDE.md` for the agent contract.

### Join the Community

We use [GitHub Discussions](https://github.com/calesthio/OpenMontage/discussions) to share work and ideas:

- **[Show and Tell](https://github.com/calesthio/OpenMontage/discussions/categories/show-and-tell)** — Share videos you've made, prompts that worked well, or creative workflows you've discovered
- **[Ideas](https://github.com/calesthio/OpenMontage/discussions/categories/ideas)** — Suggest new pipelines, tools, style playbooks, or integrations
- **[Q&A](https://github.com/calesthio/OpenMontage/discussions/categories/q-a)** — Ask questions about setup, pipelines, or troubleshooting

Made something cool? Post it in Show and Tell — we'd love to see what you build.

---

## Contact

For updates, releases, and behind-the-scenes build notes, follow [@calesthioailabs](https://x.com/calesthioailabs).

For bugs, feature requests, and workflow discussions, use [GitHub Issues](https://github.com/calesthio/OpenMontage/issues) and [GitHub Discussions](https://github.com/calesthio/OpenMontage/discussions) so everything stays visible and actionable.

---

## Weekly run

A documentary a week, end to end on this Mac, with one approval from a human.
$0: every source is keyless or free, the render is local, and the only paid
thing in the chain is the electricity.

### The chain

| when | what | where |
|---|---|---|
| Fri 22:00 | pick a topic, write the script | `scripts/run_weekly.sh` |
| then | **the script gate** — Telegram, waits up to 12h | `scripts/telegram_gate.py` |
| overnight | render, gate, deliver | `scripts/render_film.py` |
| then | upload private, scheduled Mon 09:00 | `scripts/publish_doc.py` |
| Sun 12:00 | tripwire: no film? page Telegram | `scripts/weekly_tripwire.sh` |
| Tue 09:00 | pull metrics, post a summary | `scripts/pull_metrics.py` |

The script is the only thing that waits for a person. Everything downstream of
it is gated by a measurement — rhythm, leads, frame order, type lock, delivery
audio — and the script is the one artifact where being wrong is invisible to
every gate in this repository and obvious to a viewer.

**Silence is not approval.** No reply in 12 hours aborts the run.

### The first run is attended

The two `claude -p` invocations in `run_weekly.sh` are the one part of the
chain that has never executed — the dry run proves the joins and cannot
rehearse those. So the first run is launched by hand and watched, and the
weekly agent stays **loaded but disabled** until it finishes end to end.

```bash
cd ~/Developer/wak3up-docs/OpenMontage

# 1. install all three agents, then disable the weekly one
for a in weekly metrics tripwire; do
  cp launchd/com.wak3up.docs.$a.plist ~/Library/LaunchAgents/
  launchctl bootout  gui/$UID/com.wak3up.docs.$a 2>/dev/null
  launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.wak3up.docs.$a.plist
done
launchctl disable gui/$UID/com.wak3up.docs.weekly

# 2. check it is loaded and will not fire
launchctl print-disabled gui/$UID | grep com.wak3up.docs.weekly   # => true
launchctl list | grep com.wak3up.docs
```

Then, Friday evening, run it yourself and watch:

```bash
cd ~/Developer/wak3up-docs/OpenMontage
./scripts/run_weekly.sh --brief artifacts/topic_briefs.json 2>&1 | tee /tmp/weekly.log
```

`--brief` pins it to the Easter Island brief already on disk, so the attended
run exercises the two `claude -p` stages rather than re-deciding the topic.
Drop the flag to let it pick.

The run logs to `logs/<date>/` regardless of the `tee`: `prompt.txt`,
`script_stage.log`, `render_stage.log`, `publish.log`.

**When it has finished end to end, enable the agent:**

```bash
launchctl enable gui/$UID/com.wak3up.docs.weekly
launchctl print-disabled gui/$UID | grep com.wak3up.docs.weekly   # => false
```

### Installing the agents

```bash
cd ~/Developer/wak3up-docs/OpenMontage

# the three agents, from this repository into launchd
for a in weekly metrics tripwire; do
  cp launchd/com.wak3up.docs.$a.plist ~/Library/LaunchAgents/
  launchctl bootout  gui/$UID/com.wak3up.docs.$a 2>/dev/null
  launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.wak3up.docs.$a.plist
done

launchctl list | grep com.wak3up.docs        # all three loaded
launchctl print gui/$UID/com.wak3up.docs.weekly | head -20
```

To run one now rather than waiting for its day:

```bash
launchctl kickstart -p gui/$UID/com.wak3up.docs.weekly
```

To stop them:

```bash
for a in weekly metrics tripwire; do
  launchctl bootout gui/$UID/com.wak3up.docs.$a
done
```

### Before the first run

Three things have to be true, and each says so plainly when it is not:

```bash
.venv/bin/python lib/telegram.py --check          # bot reachable, chat known
.venv/bin/python scripts/publish_doc.py --project <id> --check-token
.venv/bin/python scripts/pull_metrics.py --check  # analytics scope present
```

- **Telegram, and it must be the documentary's OWN bot.**
  `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in
  `~/Developer/wak3up-docs/.env` — outside this repository, because the
  repository is pushed and the token is not.

  Set **`TELEGRAM_DOCS_BOT_TOKEN`** — a bot of the documentary's own.

  **Not the Shorts bot.** `~/wak3up/telegram_commands.py` polls that token
  every five minutes from cron and *confirms* every update it reads, which
  removes it from the queue for everybody. A reply it takes first is simply
  not there when the gate looks.

  That cost the first live rehearsal: the gate reported "no reply in 12h"
  while the owner was looking at their reply on screen. The second rehearsal,
  on the same bot, worked — it is a race, not a wall.

  **Rehearsed on the dedicated bot** (`@Wak3docs_bot`, bot id `8955138581`),
  which is what the weekly run uses:

  ```
  telegram: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))
  gate: ok
  GATE EXIT: 0
  ```

  `exclusive()` reported `no webhook, and TELEGRAM_DOCS_BOT_TOKEN is set` —
  no warning, for the first time. No `telegram poll:` line in the whole
  window, so no poll failed. That closes the shared-bot race for the weekly
  chain.

  The one stderr line is a different fault, and it is why there is a `posted:`
  line in the gate's log now. A reset peer part-way through one multipart
  upload lost one item; the gate had already asked for a reply by then, so the
  `ok` was collected for evidence that was one item short, and the verdict
  said nothing about it. An upload is retried three times now, a failed script
  attachment falls back to the script as text, and anything that still will
  not go is named in the same message that asks for the reply:

  ```
  posted: script=attached, frames 3/3
  gate: ok
  ```

  **It cannot be detected, only avoided.** A competing consumer leaves
  nothing behind: the update is gone, and through this API that is
  indistinguishable from nobody having written one. Measured, to be sure of
  it: 995 polls over five minutes against that bot produced **zero
  conflicts**, while the handler was caught running in the same window by
  watching for its process. The visible `Conflict` error is not the theft —
  it is the enabler, because a poll it terminates used to back off five
  seconds, which is long enough for the other poller to take the reply. That
  backoff is half a second now.

  ```bash
  .venv/bin/python lib/telegram.py --check        # token and chat id work
  .venv/bin/python lib/telegram.py --exclusive    # webhook, and a warning
  ```

  `--exclusive` proves only that no webhook is set; it warns if
  `TELEGRAM_DOCS_BOT_TOKEN` is unset and does not block, because the shared
  bot does usually work. The gate also reports **unreadable** rather than
  **timeout** when every poll in the window failed — silence and deafness
  are different failures and only one of them is the person's fault — but
  that catches only the loud version. The quiet one needs the separate bot.
- **The YouTube token.** The consent screen for `wak3upsociety-pipeline` is
  **published**, established by comparison rather than assumed:
  `publish/client_secrets.json` and the droplet's
  `~/wak3up/client_secrets.json` carry the *same* client_id
  (`1063331440126-5u3espe5…v956`) in the same project, and the Shorts poster
  refreshes it daily — which a client in testing mode could not do, since
  testing expires refresh tokens after seven days.

  So **nothing expires on a schedule**. On a published client a refresh token
  dies from **six months of disuse**, from the user revoking access, or from
  passing the hundred-tokens-per-account-per-client limit. The March
  `invalid_grant` recorded in `publish/yt_authorize.py` was the inactivity
  rule — a token minted for one film and left alone — not testing status.

  A weekly run touches it every seven days against a six-month limit, so it
  will not fire. `check_youtube_auth.py` watches the gap anyway and warns at
  four months, because the rule that bit once is the rule worth watching.
- **The analytics scope.** The upload token carries `youtube.upload`,
  `youtube` and `force-ssl`, and metrics need `yt-analytics.readonly`, which
  it does not have. Add it to `publish/yt_authorize.py` and re-authorise.

### Dry run

Proves the joins without making a film: the picker's brief is one the runner
can read, the script is one the gate can post, the reply reaches the runner,
the project reaches the publisher, the ledger reaches next week's picker.
Telegram is faked and nothing is uploaded.

```bash
.venv/bin/python scripts/dry_run.py                 # the human says ok
.venv/bin/python scripts/dry_run.py --reply no      # and when they say no
.venv/bin/python scripts/dry_run.py --reply "cut act 2"
```

### Picking a topic by hand

```bash
.venv/bin/python scripts/pick_topic.py --top 3 --candidates 14
```

Writes `artifacts/topic_briefs.json` and a readable brief per candidate into
`reports/briefs/`. The runner takes the first unless `--brief` says otherwise.

Three questions, in order, each slower than the last: **what performs** (the
Shorts ledger, read-only over SSH), **is it a thing** (Wikidata — a class is
not a subject, and "Mountain" is a class), and **can it be built** (Wikimedia
category depth, eight usable assets across six entities).

### What it will not do

- **Retry a render.** A render that failed failed for a reason, and a second
  twenty-minute attempt at 4am buries it under another log.
- **Run twice.** A lock file holds the whole run; a second invocation exits.
- **Continue past a stage error.** Every exit code is checked and a failure
  goes to Telegram with the last lines of the log.
- **Publish because nobody answered.**

### Logs

`logs/<date>/` per run — the prompt, each stage's output, the render log.
Kept eight weeks (`KEEP_WEEKS`), rotated at the start of every run. The
agents' own stdout is truncated at 5MB.

---

## Run #2 checklist — *They Said It Couldn't Be Built*

Fork-specific. Tracks the editor pass on branch `editor-pass`; the measurements
behind it are in `reports/reference_pacing.md`.

**A claim here carries the thing that measured it.** Nothing in this section
describes a property of a delivered file without naming the gate or the report
that checked it, and where no check has run yet the row says so. That rule
exists because the act 2 demo was described in this README as "carrying the
−36 mix" while its audio stream was digital silence from the first sample to
the last, and nothing in the repository disagreed.

### What changed, and the defect each change answers

| | what run #1 did | what run #2 does | measured by |
|---|---|---|---|
| **Rhythm** | 181 of 182 shots 5–8s; 8–10 cuts every minute | the beat sets the band — reveal 12–25s, exposition 6–10s, landing 4–8s, transition 1.5–3.5s. `lib/verify_rhythm.py` fails a flat curve | `lib/verify_rhythm.py`, and `reports/critic_act2_demo.md` |
| **Air** | 13s of silence in 20 minutes; longest gap 2.8s | `[air 1.5s/2.5s/4.0s]` written into the script, synthesised as real gaps, 8–15% of runtime. Word band 2,500–2,700 | `lib/script_beats.py`; realised air in the critic pass |
| **Sound** | music bed only | ambience per act, room tone under every silence, riser into each landing, impact on reveal cuts, sting per boundary — all offsets from the bed | `lib/sound_design.py`; floor measured per bed in `renders/demo/demo_audio_report.json` |
| **Camera** | one push, 182 times | push/pull/lock/drift from the beat, one direction per run of stills, one speed ramp per act | `lib/camera_intent.py` |
| **Boundaries** | picture and sound cut together, 182 times | J-cuts 12–18 frames at act boundaries and reveals, L-cuts ≤10 at exposition, none at a landing | `lib/edit_leads.py` |
| **Captions** | burnt in, text on screen 99.4% of runtime | sidecar SRT uploaded with `captions.insert`; burn-in available, off, and layout-aware when on | `lib/captions_srt.py`; 34 cues over 20cps recorded below |
| **Film look** | CSS grain/vignette/chromatic layers | **shader pass is the default**, full stack on every slot; CSS is a fallback flag. Both paths run one grade chain, matched to within 2% | `reports/film_look_cost.md` — +79% floor, +100% full, both measured |
| **Word timings** | transcription matched back to the script; 60 words under 40ms | forced alignment against the script; 0 under 40ms | `scripts/align_narration.py --check`: 60 under 40ms before, 0 after |
| **Components** | — | `title_sequence` (default after the cold open) and `before_after` | component docs; no delivered-file claim |
| **Grade** | one look for four acts | per-act temperature, saturation and lift on photographic material; authored graphics keep the base palette | `reports/film_look_cost.md`; per-act spans exercised in `reports/film_delivery_film_slice.md` |
| **Maps** | flat dark silhouette | Natural Earth II terrain with shaded relief, palette ocean, 1–2% drift, plus a `globe_descent` that hands off to the same map | stills only — **no gate output yet** |
| **Outro** | right third reserved | right 40% reserved; headline column to the reserve boundary at 62px | frames in `remotion-composer/out/step7/` — judged by eye, not gated |
| **Transitions** | — | five vendored from `GTKottman/remotion-transitions` @ `58df899`, MIT, copied not depended on | `reports/vendor_vetting_transitions.md` |

### Steps 16 and 17 — done

**Step 16 — source expansion and licence filtering.** The filter runs at the
fan-out in the corpus builder, for **every** source — it had been wired into
three museum adapters and sixteen others never called it. The Library of
Congress adapter no longer invents a licence for items whose rights it cannot
read.

Sources added: **NASA Worldview** (keyless, satellite stills of a named place,
geocoded through Nominatim), **Internet Archive book plates**, and three that
wait on a key in `.env` — **Smithsonian** (`SMITHSONIAN_API_KEY`),
**Europeana** (`EUROPEANA_API_KEY`), **NYPL** (`NYPL_API_TOKEN`). Each reports
itself unavailable without its key, so a run with no keys skips it.

Four licence misreadings were found by writing them, each of which would have
quietly emptied a source: `NOT_IN_COPYRIGHT` (the Archive's public-domain
determination, which contains `IN_COPYRIGHT`), the whole rightsstatements.org
vocabulary that Europeana uses, the CC0 deed's own URL, and the Pixabay
licence.

**Audits.** The bank: 146 assets, **146 usable**
(`reports/bank_licence_audit_*.md`). The published film, run backwards through
the filter it predates: **98 of 98 pass, 0 refused, 0 unrecorded**
(`reports/published_assets_*.md`). 33 of those pass by inheriting a source's
licence — a 1080p proxy, a detail crop — which is a gap in the pipeline rather
than in the rights: **the derivation step does not copy the licence forward.**

**Step 17 — mood.** The table is done, and so are the three things that make
it act:

- **CLIP classifies the assets.** Asked as three contests (vast/intimate,
  dense/empty, and brightness measured rather than asked), because a frame can
  be dark *and* vast. 98 of 182 film cuts carry a class; the 84 without are
  authored components. The veto fires on 14 of them.
- **No cut lands on a cut the source already had** (`source_cuts`). 12 frames.
  Timelapse steps are exempt, separated from real cuts by whether the frames
  either side still correlate — 0.95+ for steps against ≤0.71 for cuts.
- **A rise lands only where the music is already rising** (`music_rise`).
  Essentia does not install here, so this is librosa and three signals. On run
  #1's bed only **37% of the film is rising** at any moment.

### Steps 9, 10 and 15

- **Step 9 — Manim.** `reports/step9_manim.md`, with the side-by-side.
  Recommendation: **keep the component.** Manim is four times faster at
  rendering a quarter of the frame, and a Manim diagram arrives as a video, so
  its labels are pixels — they cannot join the type pass, cannot be locked
  while the plate moves, and cannot be read by the type-lock gate. Keep Manim
  for a mathematical animation the component cannot express; nothing in run #1
  needed one.
- **Step 10 — two treatments.** `reports/step10.md`. **Halftone collage:
  adopt**, for citation and record beats — it reads as a plate from a book.
  **Sketched reconstruction: not yet** — it keeps the real geometry but reads
  as an edge-detect, because it draws the grass as carefully as the statue.
- **Step 15 — taste audit.** `reports/step15_taste_audit.md`. All ten
  judgements run #1 got wrong are measured by a gate; **only five were stated
  as rules anyone could read first.** The other five have been written into
  the skills. The audit's own instrument was wrong three times on the way and
  each correction is recorded in it.

### Gates a run #2 must pass

```bash
python3 lib/script_beats.py   {artifacts}/script.json --plan {artifacts}/narration_plan.json
python3 lib/sound_design.py   {artifacts}/sound_design.json
python3 lib/buildability.py   {artifacts}/scene_plan.json
python3 lib/camera_intent.py  {artifacts}/edit_decisions.json
python3 lib/edit_leads.py     {artifacts}/edit_decisions.json
python3 lib/verify_rhythm.py  {artifacts}/edit_decisions.json
python3 lib/captions_srt.py   {artifacts}/render_props.json {artifacts}/captions.en.srt
python3 lib/alignment_qa.py   --project <id> --fix
python3 scripts/align_narration.py --project <id> --check
```

And on the delivered file itself, because the two defects that shipped in the
act 2 demo were both invisible to everything above — all of which reads a
plan, not a file:

```bash
python3 lib/verify_frame_motion.py   <mp4>
python3 lib/verify_frame_order.py    <mp4> --cuts <props.json> --reference <picture.mp4>
python3 lib/verify_type_lock.py      <mp4> --cuts <props.json>
python3 lib/verify_type_lock.py      <plate.mp4> --cuts <props.json> --plate
python3 lib/verify_delivery_audio.py <mp4> --expected-lufs <mix LUFS>
```

The film renders **twice from one tree** — once with the type laid out but
not inked, which the shader runs over, and once with only the type over
transparency, laid on top afterwards. Plate, then grade and vignette and
grain, then type. A single flat render puts per-frame grain on the glyph
edges; see `remotion-composer/src/design/layers.tsx`.

After a render, the critic pass — fails on structure, reports the rest:

```bash
python3 scripts/critic_pass.py --project <id> --film <mp4>
```

There is **one render path**, and both the demo and the film go down it. The
stages live in `lib/film_render.py` — plate, frames, look, type, deliver,
gates — and the two scripts differ only in which props, which mix and how
long. A film rendered by a different path from the demo is a film whose gates
have never run on it.

```bash
python3 scripts/render_demo.py --project <id> --bed 30
python3 scripts/render_film.py --project <id>          # refuses to overwrite a delivery
```

Both take `--gates-only`, which re-runs every check and rewrites the report
without rendering anything.

Terrain tiles for a map shot are cut once, before the render:

```bash
python3 scripts/build_basemap_tile.py --name <slug> --bounds W S E N
```

All are declared in `pipeline_defs/narrated-documentary.yaml` as blocking
`gate_commands`. Three of them fail on run #1's own artifacts, and the two
delivery checks fail on the demo as it was first shipped, which is the
evidence that they measure the right thing.

### Decided

- **Music bed level: −30 LUFS under speech** (2026-10-21), by ear on the act 2
  demo with the sound design present. In the playbook at
  `audio.music_under_speech_lufs`; `lib/mix_audio.py` reads it from there.
  Run #1's EDL states −36 and still gets it.
- **The demo cut.** Approved 2026-10-21.
- **The Pixabay Content License: admitted** (2026-10-21), as a *named* licence
  and not folded into CC0, with its scope recorded — use within a produced
  video, commercially; **not** redistribution of the asset on its own. The 28
  `elemental_texture` assets are restored and the bank is 146 of 146. It was
  load-bearing for the published film too: 28 of its 98 assets are Pixabay.
- **Halftone collage: adopted** for citation beats, keyed in the playbook to
  the scene types that carry one (`evidence_card`, `document_reveal`). Caveat
  recorded: a fixed screen over a moving picture crawls, so a treated slot
  takes a lock until the screen can move with the image.
- **Sketched reconstruction: not adopted** — it keeps the real geometry and
  still reads as an edge-detect, drawing the grass as carefully as the statue.
  Reason in `motion.mood.treatments`; the code stays for what it taught.
- **Manim: available, not default.** A Manim diagram arrives as a *video*, so
  its labels are pixels — they cannot join the type pass, cannot be locked
  while the plate moves, and cannot be read by the `type_lock` gate. In the
  playbook at `visual_language.diagram_route`.

### Still needs the owner's decision

- **Outro headline column.** Shipped at the reserve boundary (952px) at 62px
  Display, because 900px orphaned "us". Frames for both readings are in
  `remotion-composer/out/step7/`.
- **Nothing outstanding.** Phase 2A is closed; Phase 2B (automation) is next.

### Delivered, and what the gates said

Nothing is listed here without the run that measured it.

**The act 2 demo** — `renders/demo/act2_demo.mp4`, 89.8s, 2,694 frames, full
look, captions off, carrying the −30 mix. `reports/demo_delivery_bed30.md`:

| check | measured |
|---|---|
| frame motion | 0.0% duplicate pairs, longest freeze 0.0s, timestamps constant |
| frame order | 0 frames out of place, 0 isolated black, correlation with the plate 0.9977 |
| plate purity | 0 words legible in the plate pass |
| type lock | 10 text-bearing scenes, 0 with a word in a different place, worst 0.598px |
| delivery audio | −18.4 dBFS mean, −15.81 LUFS against the mix's −15.80 |

**The film render path** — exercised on a 26.5s slice spanning the act 2/3
boundary, so the shader's per-act grade is in it.
`reports/film_delivery_film_slice.md`: all five gates pass, frame order
correlation 0.999, type lock worst 0.529px, delivery audio −13.7 LUFS against
the mix's −14.0.

**Anchor tracking** — `reports/anchor_tracking.md`, on run #1's own annotated
stills: the anchor lands 0.46–1.57px from its feature at the end of a hold,
where staying locked would have put it 5.4–49.0px away, and no label moved.

**Not delivered: run #2's film.** There is no run #2 edit yet — no script, no
narration, no EDL — so nothing has been rendered through `render_film.py` end
to end. The path is checked on a slice and on the demo, and that is all the
evidence there is for it.

### Known, recorded, not yet fixed

- **34 of 308 caption cues read faster than 20 characters a second.** Exposed
  once the timings were correct: these are passages the narration genuinely
  rushes. The answer in run #2 is a slower read or shorter copy, not a looser
  gate.
- Run #1's word timings are fixed: 60 words under 40ms before forced
  alignment, 0 after.
- `projects/.../edit_decisions.json` does not validate against its own schema
  (`transitions` is an object where the schema wants an array; `layer` is an
  integer where it wants a string enum). Run #1's record is left as published.

---

## Testing

```bash
# Run contract tests (no API keys needed)
make test-contracts

# Run all tests
make test
```

---

## Star History

<a href="https://star-history.dera.page/#calesthio/OpenMontage&type=date&legend=top-left">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://star-history.dera.page/svg?repos=calesthio/OpenMontage&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://star-history.dera.page/svg?repos=calesthio/OpenMontage&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://star-history.dera.page/svg?repos=calesthio/OpenMontage&type=date&legend=top-left" />
  </picture>
</a>

---

## License

[GNU AGPLv3](LICENSE)

---

**OpenMontage** — Production-grade video with real quality enforcement, orchestrated by your AI assistant.

If this project looks useful to you, a ⭐ would really mean a lot — it helps others discover it too.

If you'd like to go further, [sponsor the project](https://github.com/sponsors/calesthio) — OpenMontage is built nights and weekends, and your support makes that sustainable.
