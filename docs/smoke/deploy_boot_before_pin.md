# Deploy check — boot before pin (standing procedure)

Origin: S103i. The precision-pass image was pinned in `compose.yaml` and committed
*before* the container was confirmed to start; it crash-looped on a startup
`NameError` (wiring var-name mismatch) that the unit suite never exercised
(`_build_default_compositions` is not in the unit path). Green unit tests are not
a running app — the live-surface law applied to deployment.

The procedure, every time `make build-api` re-pins the deployed image:

1. `make build-api` — builds + rewrites the `compose.yaml` digest pin.
2. `docker compose up -d --force-recreate padhanam-api` — recreate on the new image.
3. **Verify it actually started before committing the pin:**
   - `docker compose ps padhanam-api` shows `Up … (healthy)`, not `Restarting`.
   - the app builds: `docker compose exec -T padhanam-api python -c "from apps.api.main import create_app; create_app()"` prints no traceback.
   - it serves: `docker compose exec -T caddy wget -qO- http://padhanam-api:8000/app` returns the page (`<title>Padhanam …`).
4. Only then `git add compose.yaml && git commit` the pin.

If step 3 fails, revert the pin to the prior good digest (`git show <prev-commit>:compose.yaml`), bring the container up on it, fix the code, re-verify on the synced fast-path (`make sync-code` + the `create_app` smoke), then rebuild. Do not commit a pin to an unverified image.

This is the same principle as browser-interactive-verification for UI surfaces
(CLAUDE.md) and "a proof on fakes is not a proof on the real surface"
(`charter/principles.md`), carried to the deploy step.
