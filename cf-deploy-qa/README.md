# QA deploy files (beat-tool-qa)

These files deploy the `qa` branch to Cloudflare Containers as `beat-tool-qa`.
They are versioned here on the `dietram` branch because `qa` belongs to GFA-DIU.

Usage: `git worktree add /tmp/heat-alcbt-qa origin/qa`, copy these three files in
(cf-worker-index.mjs → cf-worker/index.mjs, plus the repo root Dockerfile.cloudflare
gets REPLACED by the one here — qa needs the Node asset build stage), `npm install
@cloudflare/containers --no-save`, then `wrangler deploy`.

Key differences vs main: two-stage build (node:22 `npm run build` for Tailwind/icons/esbuild
before collectstatic) and the shim passes SUPABASE_DATABASE_URL (qa settings read that var).
Full stack doc: kb 01-PROJECTS/01.1-ACTIVE/IKI-GLO-ALCBT/02-DELIVERABLES/beat-cloudflare-supabase-stack.md
