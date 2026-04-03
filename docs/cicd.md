# CI/CD: Vercel Deployment Gate

This repository uses Vercel Git integration for deployments and GitHub Actions for merge gating.

## Deployment Model

- Preview and production deployments are created by Vercel Git integration.
- GitHub Actions does **not** run `vercel deploy`.
- CI gate workflow: `.github/workflows/vercel-preview-gate.yml`.

## What the Gate Enforces

For every pull request targeting `main`, the workflow:

1. Reads `pull_request.head.sha`.
2. Polls GitHub commit statuses for context `Vercel`.
3. Passes only when `Vercel` is `success`.
4. Fails immediately when `Vercel` is `failure` or `error`.
5. Fails on timeout if no `Vercel` status appears.

## Required Repository Setup

1. Ensure the Vercel GitHub app is installed and the Vercel project is linked to this repository.
2. In GitHub branch protection for `main`, enable required status checks.
3. Mark this workflow job as required:
   - `Vercel Preview Gate / wait-for-vercel-status`
4. Optional double-lock: also mark native Vercel check `Vercel` as required.

## Notes

- The workflow assumes the Vercel status context is exactly `Vercel`.
- If the context name changes in the future, update `VERCEL_CONTEXT` in the workflow.
