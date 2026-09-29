# Brag Plan: Solstice Analytics RAG Chat

## What is this app?
An internal AI knowledge assistant that answers employee questions strictly from company documents via an agentic search loop, with role-based access control enforced inside the database query itself, not the UI.

## The angle
Most "AI chat for your docs" demos show a pretty chat window and stop there. The actual hard, non-generic thing this project does is invisible in a screenshot: the same question, asked by two different roles, produces two different answers, because access is enforced at the database level, not the UI. Open on the problem this solves, in plain language, before showing the product at all.

## Hook (first few seconds)
A dark, UI-free cold open: "Every company chatbot has the same problem." holds, then "It knows too much." States the problem in plain English before any product UI appears.

## Key moments (the middle)
- Typing the question into the real chat UI, then the agent visibly searching and refining ("query 1 of 3" -> "query 2 of 3") before the answer lands with a real source citation tag ("Source: on_call_runbook.md"). This is the proof that it's an agent loop, not a canned response.
- The same engineer asking a compensation question and getting the RBAC denial card (lock icon, "You don't have access to that information."), with a plain-English line underneath explaining why: "Each role only sees what it's allowed to see."
- The same question, asked again as HR staff: a real answer lands this time, with its own source tag ("Source: compensation_bands.md"). Label: "Same question. Different role."

## Outro / punchline
The app's own real footer line, already sitting under the input bar in the product: "Answers come only from documents your role can access." Directly answers the hook's "It knows too much." Then the real tech stack and a credit line.

## User flow worth showing
1. Engineer types a question about on-call escalation. Agent searches, refines, answers, cites its source.
2. Engineer asks a compensation question. Denial card, plain-English reason, not an answer.
3. Same question, HR staff role this time. Real answer, real source citation.

## Tone
- Preset: app-store, with one deliberate departure for the cold open
- Creative direction: clean professional product demo, emphasis on the agent's search loop and access control over chat UI chrome
- Interpretation: smooth slides and wipes, confident holds, no jokes, no chaos, no jargon. Every technical claim gets a plain-English label, not code or a metric.

## Format: landscape - 1920x1080
## Duration: 39s (revised down from 45s after cutting two scenes the user found unclear or too technical: a standalone "roles" scene, and a raw SQL line on screen)

## Editorial history, in order
1. Started as a 20s cut: chat-only, no cold open.
2. Extended to 30s at the user's request, added a login-screen hook.
3. Rebuilt at the user's own detailed storyboard to 45s: dark cold-open, a "Roles" stat-card scene, typing restored inside the search scene, a real SQL line shown as a code chip, an extended outro with tech stack and credit. Explicitly dropped a "proof"/metrics scene the user's reference storyboard had included.
4. Cut back to 39s: removed the SQL code chip (too technical, replaced with a plain-English line) and removed the Roles scene entirely (its "Not every answer." line didn't stand on its own without more setup). This is the current cut.

## Visual identity (from the project)
- Background: #f5ead8 (warm cream); #1c1815 warm near-black for the cold-open scene only
- Accent: #c67139 (copper/terracotta), with #8c491a as a deeper accent-hover tone
- Text: #201e1d (light scenes), #f5ead8 (dark cold-open)
- Display font: Caprasimo
- Body font: Figtree
- Strongest visual element: the pill-shaped input bar with the circular two-tone logo mark, and the RBAC denial card's lock icon against the warm neutral surface

## Share copy (draft)
Every company chatbot has the same problem: it knows too much. This one enforces role-based access at the database level, not the UI, so the same question gets a different answer depending on who's asking.

## Audio direction
- Role: warm minimal corporate bed, sparse professional accents
- Music: happy-beats-business-moves-vol-1-by-ende-dot-app.mp3 (120 BPM)
- Music treatment: near-silent under the dark hold at the very start, enters low as the hook's first line appears, holds steady through the middle, small lift into the outro, clean fade on the final line
- Audio-reactive treatment: none, restraint is the point of this tone
- SFX posture: sparse, motion-matched, professional restraint
- Audio-coupled moments: typing ticks during the question, a soft search texture under the searching/refining dots, a dry quiet lock-click on the denial card's arrival, a warm soft chime on the HR answer's arrival
- Restraint rule: no playful or comedic sound design, no risers, no chaotic layering

## Storyboard

### Scene H - Hook, dark cold-open - 6.5s
Full dark screen (the one deliberate departure from the warm-cream palette used everywhere else): "Every company chatbot has the same problem." holds, fades, then large: "It knows too much." No UI yet.
Sequential/interaction: two sequential lines, each held long enough to read before the next replaces it
Audio intent: quiet, a little tense, near-silent under the first second
Transition mood: hard cut to light -> Scene 1

### Scene 1 - The engineer asks, and the agent iterates - 11.5s
The chat input pill appears, the on-call question types in character by character. The pill resolves into the question as a sent bubble, then "Searching -- query 1 of 3", then "Refining -- query 2 of 3" while the dots keep animating, then the answer lands with its source tag, "Source: on_call_runbook.md". Held generously.
Sequential/interaction: yes -- typing, then two labeled search phases, then the answer arrives
Audio intent: quiet typing, brief anticipation, a settled landing
Audio-coupled idea: typing ticks, then a soft search texture under the dots, resolving to quiet on the answer's arrival
Transition mood: smooth wipe -> Scene 2

### Scene 2 - Denied, and shown why - 7.0s
Same engineer, the compensation question. The RBAC denial card arrives, then a plain-English line underneath: "Each role only sees what it's allowed to see." No code shown -- an earlier cut showed the real SQL WHERE clause here, but it read as too technical, so this cut states the same mechanism in plain language instead.
Sequential/interaction: yes -- question, then the denial card, then the label
Audio intent: a small, dry, definitive click on the denial
Audio-coupled idea: a single lock-click as the card lands
Transition mood: slide -> Scene 3

### Scene 3 - The contrast - 6.5s
Role badge flips to HR staff. The identical question, asked again, gets a real answer this time: $135,000-$165,000, with its own source tag, "Source: compensation_bands.md". Label: "Same question. Different role."
Sequential/interaction: yes -- role badge swap, question, then the answer lands
Audio intent: warmer, the release after Scene 2's denial
Audio-coupled idea: a soft affirming chime as the answer lands
Transition mood: smooth wipe -> Scene 6

### Scene 6 - Outro - 7.5s
The product's own footer line: "Answers come only from documents your role can access." -- the direct answer to Scene H's "It knows too much." Then the real stack (FastAPI, LangChain, Groq, Postgres/pgvector, Next.js) as a small mono-type line, then the credit: Arya Mane. Music resolves.
Sequential/interaction: three sequential lines, each held before the next
Audio intent: settled, confident close
Music: fades out through this scene
Transition mood: soft hold -> end

**Music mood for this video:** clean, warm, confident corporate energy, never loud
**Audio summary:** A low, steady corporate bed carries the whole video, restrained typing and UI-adjacent SFX mark each beat, and the mix settles into a clean fade under the final line.
**Duration check:** 6.5 + 11.5 + 7.0 + 6.5 + 7.5 = 39.0s
**Not in this cut:** a "proof"/metrics scene (faithfulness/precision/test counts), a standalone "Roles" stat-card scene, and a raw SQL code chip -- all cut at the user's explicit request, the first two before ever being built, the last two after being built and reviewed.
