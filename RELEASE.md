# Release Process

**Last updated:** 2026-05-24

This document covers the two-repo distribution strategy, the authoritative public file manifest, and the step-by-step release procedure. The release is automated via `scripts/release.sh`.

---

## Two-repo strategy

**Private repo** (this repo) — where all development happens. Contains everything: design docs, roadmap, eval pipeline, database schema, test corpus, internal tooling. Never made public.

**Public repo** — what users clone from GitHub. Contains only the files a user needs to run a scan. No design docs, no roadmap, no eval infrastructure, no internal history. This repo is a release artifact: it gets updated when you push a release, not continuously.

The two repos have no git relationship. No shared history, no branches in common, no submodules. The public repo starts fresh at v1 and accumulates only release commits.

**Why not a branch or fork?** A GitHub fork maintains a link back to the source repo, which would expose the private repo's existence. A `public` branch within this repo would share history and make private commits reachable. Two independent repos is the only clean separation.

---

## Public file manifest

This is the authoritative list of files that ship in the public repo. `scripts/release.sh` uses this list — update both together if files are added or removed.

```
prompt.md
prompt-analysis-only.md
prompt-standalone.md
rubric.md
schema.json
report-template.md
render.py
install.sh
LICENSE
examples/01-sql-injection.md
examples/02-exposed-secret.md
examples/03-missing-authz.md
examples/04-vulnerable-dep.md
rules/README.md
COMPATIBILITY.md
README.public.md  → published as README.md
.gitignore.public → published as .gitignore
```

**Not shipped:**
- `design-doc.md`, `ROADMAP.md`, `RELEASE.md` — internal docs
- `eval/` — entire directory
- `ops-checklist.md`, `t4-playbook.md` — internal reference
- `demo-project/`, `demo-output/` — internal test assets
- `test-targets/` — gitignored locally, not tracked
- `README.md` — this is the private dev README; public gets `README.public.md` renamed

---

## Pre-release checklist

Before running the release script, verify:

- [ ] All public files pass a final read-through — nothing internal leaked into prompt.md, rubric.md, etc.
- [ ] `schema.json` `$id` URL matches the version being released
- [ ] `README.public.md` is written and accurate (size limits, quick-start CTA, compatibility link)
- [ ] `COMPATIBILITY.md` reflects actual tested status (no `⬜ Not yet tested` for the primary target tools)
- [ ] `render.py` runs cleanly against a known-good `findings.json`
- [ ] Private repo is on a clean commit (no staged or unstaged changes)
- [ ] Public repo URL is set correctly in `scripts/release.sh`

---

## Running a release

```bash
# From the private repo root:
./scripts/release.sh v1.0
```

The script will:
1. Clone the public repo to a temp directory
2. Copy all files from the public manifest (renaming README.public.md → README.md)
3. Commit with message "Release v1.0"
4. Tag the commit as `v1.0` in the public repo
5. Push main and the tag to the public repo
6. Tag the private repo commit as `public-v1.0` for traceability

If there are no changes (the files are identical to the last release), the script exits cleanly without creating an empty commit.

---

## After a release

- Announce wherever appropriate (none, for now)
- Update `ROADMAP.md` changelog with the release date and what shipped
- Start a new internal milestone if warranted

---

## Setting up the public repo (first time only)

Before the first release, create the public repo on GitHub:

```bash
gh repo create <name> --public --description "<one-line description>"
```

Then set the URL in `scripts/release.sh` (the `PUBLIC_REPO_URL` variable at the top of the file). The first run of `release.sh` will populate it.

---

## Release schedule

TBD — to be decided once v1 is validated and the public repo is live. Current expectation: milestone-based releases tied to meaningful feature or quality improvements, not a fixed calendar cadence.
