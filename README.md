# EchoWorld

**A memory-driven browser RPG where villagers remember conversations, form attitudes, gossip overnight, forgive selectively, and hold the player to their promises.**

EchoWorld explores a simple question: what changes when RPG dialogue is backed by persistent, evolving memory instead of isolated chat completions? The village turns player choices into durable social consequences while keeping recalled facts separate from an NPC's current attitude and tone.

## Core demo flow

1. Treat Gareth fairly so the blacksmith remembers a respectful customer.
2. Bargain aggressively with Petra and create a negative merchant memory.
3. Deny causing trouble when Captain Mira questions you.
4. End the day so memories consolidate, gossip spreads, and attitudes resolve.
5. Ask Elder Voss what the village has heard.
6. Confess to Mira, promise not to cause more trouble, then break that promise with Petra.
7. End another day and return to Mira for a specific broken-promise callout.

The built-in guided tutorial walks judges through this sequence with an original mascot, objective panel, and directional waypoints.

## How Cognee is used

- **`recall()`** retrieves relevant NPC memory before a response. The temporary Recall notification makes the supporting evidence visible during the demo.
- **`remember()`** stores new conversations and structured interaction analysis for later continuity.
- **`improve()`** runs at End Day to consolidate session memory before attitudes and overnight gossip are resolved.
- **`forget()`** powers Bribe / Forget. If Cognee Cloud deletion fails, EchoWorld rotates that NPC to a fresh dataset as an isolation fallback.
- **Memory-backed behavior** combines verified current-run evidence, recalled context, attitudes, hearsay, confessions, and promise state without allowing tone to invent facts.

## Game mechanics

- Persistent, per-NPC conversation memory
- Warm, neutral, suspicious, and hostile attitudes
- Overnight village gossip and Elder hearsay
- A separate Confess interaction pathway
- Promise creation, violation detection, and specific consequences
- Bribe / Forget with fresh-dataset fallback
- Visible Recall traces and Night Reports
- A complete guided judge tutorial

## Architecture

```text
Pygame/Pygbag browser frontend
        |
        | same-origin /api/* requests
        v
FastAPI backend
        |
        +-- Cognee memory lifecycle
        +-- OpenAI dialogue + semantic analysis
        +-- local event/attitude/promise state
```

- [game_app.py](game_app.py) contains the responsive Pygame game and desktop entrypoint.
- Pygbag packages the browser-safe frontend from `web_build/` into `web_dist/`.
- [backend_api.py](backend_api.py) serves both the static game and FastAPI endpoints.
- Cognee and OpenAI execute only on the server; browser code never receives API keys.
- [render.yaml](render.yaml) defines the single-service Render deployment.

## Local setup

PowerShell examples:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/build_web.py
uvicorn backend_api:app --host 127.0.0.1 --port 8787
```

Open <http://127.0.0.1:8787/>. The health endpoint is available at <http://127.0.0.1:8787/api/health>.

Native desktop mode remains available:

```powershell
python game_app.py
```

## Render deployment

Push the repository to GitHub, create a Render Blueprint/Web Service, and configure these server-side environment variables:

- `OPENAI_API_KEY`
- `COGNEE_API_KEY`
- `COGNEE_SERVICE_URL`
- `USE_COGNEE_CLOUD=true`
- Optional model overrides from [.env.example](.env.example)

Build command:

```text
pip install -r requirements.txt && python scripts/build_web.py
```

Start command:

```text
uvicorn backend_api:app --host 0.0.0.0 --port $PORT
```

Never commit `.env` or place secrets in browser/Pygbag code. See [DEPLOYMENT.md](DEPLOYMENT.md) for the detailed deployment checklist and troubleshooting notes.

## Limitations

- Free hosting may cold-start slowly before the first backend interaction.
- Local JSON event, tutorial, promise, and attitude state may reset during a redeploy unless Render persistent storage is configured.
- Cognee Cloud `forget()` can fail because of provider constraints; dataset rotation then isolates a fresh NPC memory instead.
- The current demo uses lightweight local files and is intended for a guided judging session rather than concurrent production users.

## Hackathon

Built for the **WeMakeDevs x Cognee Hackathon**.
