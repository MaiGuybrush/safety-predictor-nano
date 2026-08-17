# Issue tracker: Gitea

Issues for this repo are tracked on the internal Gitea server.

## Repository Information
- **Server**: `http://tncimweb.cminl.oa/git-server` (or `http://tnvcimweb1.cminl.oa/git-server`)
- **Repository Slug**: `guy.mai/safty-predictor-nano`
- **CLI Tool**: `tea` CLI (login: `guy.mai`)

## Conventions
- **List issues**: `tea issues list --login guy.mai --repo guy.mai/safty-predictor-nano`
- **View issue**: `tea issues <index> --login guy.mai --repo guy.mai/safty-predictor-nano`
- **Create issue**: `tea issues create --login guy.mai --repo guy.mai/safty-predictor-nano --title "<title>" --description "<description>" --labels "ready-for-agent,Kind/Feature"`
- **Edit issue**: `tea issues edit <index> --login guy.mai --repo guy.mai/safty-predictor-nano ...`
- **Close issue**: `tea issues close <index> --login guy.mai --repo guy.mai/safty-predictor-nano`
- Feature specs are also archived locally in `.scratch/<feature-slug>/spec.md`.

## Triage Labels
Uses standard roles (`ready-for-agent`, `Kind/Feature`, `Kind/Bug`, `Kind/Enhancement`, etc.).

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` — the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
