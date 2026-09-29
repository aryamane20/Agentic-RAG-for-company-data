# Hyperframes Composition Brief: Solstice Analytics RAG Chat

## Objective
Create a launch-style brag video for the Solstice Analytics RAG Chat internal knowledge assistant.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape, 1920x1080
- Duration: 39 seconds (a dark problem-first cold open, slower pacing throughout, no metrics/proof scene, and no raw SQL or a separate roles scene — both were cut after the user found them unclear or too technical)

## Source Material
- Project root: `/Users/aryamane/Desktop/Agentic-RAG-for-company-data`
- Primary files read: README.md, frontend/app/globals.css, frontend/app/login/page.tsx, frontend/app/chat/page.tsx
- Product name: Solstice Analytics (RAG Chat)
- Tagline / strongest claim: Role-based access control enforced inside the database query itself, not the UI
- Key UI or visual moment to recreate: the pill-shaped chat input, the "Searching..." agent state, the RBAC denial card (lock icon), the source citation tag
- Copy that must appear verbatim:
  - "Every company chatbot has the same problem."
  - "It knows too much."
  - "What's the on-call escalation process?"
  - "Searching — query 1 of 3" / "Refining — query 2 of 3"
  - "Source: on_call_runbook.md"
  - "What's the compensation band for a Senior Software Engineer?"
  - "You don't have access to that information."
  - "Each role only sees what it's allowed to see." (plain-English mechanism label, replaced a raw SQL line the user found too technical)
  - "Source: compensation_bands.md"
  - "Same question. Different role."
  - "Answers come only from documents your role can access."
  - "FastAPI · LangChain · Groq · Postgres/pgvector · Next.js"
  - "Arya Mane"

## Creative Direction
- Tone preset: app-store, with one deliberate departure for the cold open
- Creative direction: clean professional product demo, feature-highlight structure, emphasis on backend enforcement mechanics (RBAC, the agent's search loop) over chat UI chrome. Slower pacing than a typical brag cut — every beat gets a real, generous hold, not a skim.
- Angle: the same question, asked by two different roles, produces two different answers, because access control is enforced at the database level, not the UI. Open on the problem this solves before showing the solution. Explain the mechanism in plain English, not code.
- Hook: a dark, UI-free cold open stating the problem in the product's own terms — the one intentional departure from the warm-cream palette used everywhere else in the video.
- Outro / punchline: the product's own real footer line, directly answering the hook's "It knows too much."
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign
  - Any "proof"/metrics scene — explicitly excluded by the user
  - Raw code/SQL on screen — explicitly cut after the user found it too technical
  - A standalone scene whose point isn't self-evident on its own — the original "Roles" scene (stat cards + "Not every answer.") was cut for exactly this reason

## Visual Identity
- Background: #f5ead8 (light scenes); #1c1815 warm near-black (Scene H only, a deliberate one-scene departure, not a global theme change)
- Text: #201e1d (light scenes); #f5ead8 (Scene H, inverted)
- Accent: #c67139 (with #8c491a as a deeper hover/accent tone)
- Display font: Caprasimo (fetched via Google Fonts CDN link at build time, accepted lint warning for local render)
- Body font: Figtree
- Visual references from the project: the circular two-tone logo mark, the pill input bar, the RBAC denial card's lock icon, source citation tags

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Scene H (Hook) — 6.5s — dark cold open, two sequential problem-statement lines, no UI
2. Scene 1 (Search) — 11.5s — typing inside this scene, then two labeled search phases ("query 1 of 3" / "query 2 of 3"), then the sourced answer lands
3. Scene 2 (Denied) — 7.0s — RBAC denial card, then a plain-English mechanism label (no code)
4. Scene 3 (Contrast) — 6.5s — role flips to HR staff, same question, real answer lands
5. Scene 6 (Outro) — 7.5s — footer line, tech stack line, credit line

## Audio
- Audio role: warm minimal corporate bed, sparse professional accents
- Audio arc: near-silent under the dark hook's first second, bed enters low as the hook's first line appears, holds steady through the middle, small lifts at each scene's payoff moment, clean fade under the outro's three lines
- Music: happy-beats-business-moves-vol-1-by-ende-dot-app.mp3 (120 BPM), already in `composition/assets/music/`
- Music cue guidance: bundled preset at `<brag-skill-dir>/assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json`. Treat cues within the preset's original 25s planning window as real hints, use natural timing beyond it.
- Audio-reactive treatment: intentionally omitted, restraint is the point of this tone
- Audio-coupled moments:
  - Scene 1 — typing ticks, then a soft search texture under the dots, resolving to quiet on the answer's arrival
  - Scene 2 — a single quiet lock-click on the denial card
  - Scene 3 — a soft affirming chime as the answer lands
- SFX selection guidance: sparse, professional, motion-matched, no playful or comedic sounds
- Audio files: music already in `composition/assets/music/`; SFX in `composition/assets/sfx/` — only the files actually referenced by the current composition are kept (card sounds from the removed Roles scene were deleted)

## Hyperframes Instructions
Load `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`. This is a `/brag` workflow, not the generic `hyperframes` entry-point interview.

Requirements:
- Show real product UI and copy, not abstractions.
- Keep all text readable — the user explicitly asked for slower pacing and generous holds.
- Duration target is 39s, per explicit user direction (originally extended past the skill's normal 15-25s default, then trimmed back down after cutting two scenes).
- Include the planned music layer; SFX per the guidance above.
- Treat music cue metadata as optional timing hints; ignore any cue that hurts readability or pacing.
- Run `hyperframes check` before render.
