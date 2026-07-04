# EchoWorld one-link web deployment

EchoWorld's browser build is a Pygbag/Pygame frontend. Cognee, OpenAI, the
event log, attitudes, and promise state run inside the FastAPI service. The
browser calls same-origin `/api/*` routes, so no API key is included in the
downloaded game.

## A. Local browser test

1. Activate the virtual environment:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Build the Pygbag bundle:

   ```powershell
   python scripts/build_web.py
   ```

4. Start the all-in-one FastAPI host:

   ```powershell
   uvicorn backend_api:app --host 127.0.0.1 --port 8787
   ```

5. Open <http://127.0.0.1:8787/>. Health is available at
   <http://127.0.0.1:8787/api/health>.

For live Pygbag development, run `scripts\dev_web.ps1`. It prepares only the
safe frontend files, starts the API at port 8787, and runs
`python -m pygbag web_build`. The browser client automatically uses port 8787
when Pygbag is served from another localhost port.

Desktop mode remains available:

```powershell
python game_app.py
```

## B. Deploy to Render

1. Push the repository to GitHub. Confirm `.env` is not tracked.
2. In Render, create a Blueprint from the repository and select
   `render.yaml`, or create one Python Web Service manually.
3. Use this build command:

   ```text
   pip install -r requirements.txt && python scripts/build_web.py
   ```

4. Use this start command:

   ```text
   uvicorn backend_api:app --host 0.0.0.0 --port $PORT
   ```

5. Add server-side environment variables in the Render dashboard:

   - `OPENAI_API_KEY`
   - `COGNEE_API_KEY`
   - `COGNEE_SERVICE_URL`
   - `USE_COGNEE_CLOUD=true`
   - `OPENAI_MODEL` or the project's existing `NPC_MODEL`/`LLM_MODEL` values,
     if you override their defaults
   - `LLM_API_KEY` and `EMBEDDING_API_KEY` if the deployed Cognee setup reads
     those aliases (they can use the same OpenAI key)

6. Deploy and open the generated Render URL. The root URL serves the game and
   the same process handles `/api/talk`, `/api/bribe`, `/api/endday`, promise,
   reset, events, and health routes.

Actual secret values belong only in Render's environment settings or a local
untracked `.env`; never put them in `render.yaml`, `.env.example`, JavaScript,
or the Pygbag source folder.

## C. Common issues

- **Cold start:** a free web service can take tens of seconds to wake. The game
  draws its title screen while the first API connection waits.
- **Missing variables:** inspect Render logs and `/api/health`. Health can be
  green even when an individual model call lacks credentials.
- **`web_dist` missing:** run `python scripts/build_web.py`. If no build exists,
  `/` deliberately says `Web build missing. Run scripts/build_web.ps1 first.`
- **Pygbag import error:** use the build script so it copies only
  `game_app.py`, `pixel_assets.py`, `tutorial_system.py`, `backend_adapter.py`,
  and `web_backend_client.py` into `web_build` before packaging.
- **Browser API failure:** use a same-origin deployed URL. In local Pygbag dev,
  keep FastAPI on port 8787; localhost CORS is enabled for development only.
- **Cognee Cloud forget failure:** the existing backend's dataset-rotation
  fallback still isolates a fresh NPC memory when direct Cloud deletion fails.

## Demo persistence limitations

Judges use one browser link and do not run a local backend. Cognee/OpenAI still
execute server-side, so secrets are not inspectable in browser code. The local
JSON event, attitude, promise, and tutorial files can reset on a Render
redeploy/restart unless a persistent disk or external state store is added.
That is acceptable for a disposable judge demo, but not for durable multi-user
production state. A free host can also cold-start slowly.
