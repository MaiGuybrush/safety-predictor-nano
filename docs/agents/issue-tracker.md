# Issue Tracker Configuration: Gitea Issues (via tea CLI)

Issues for this repository are tracked in **Gitea Issues** via the official `tea` CLI.

## Instance Information
- **Gitea Base URL**: `http://tnvcimweb1.cminl.oa/git-server`
- **Repository**: `guy.mai/safty-predictor-nano`
- **CLI Tool**: `tea` (already authenticated as `guy.mai`)

## Workflow & Operations

### Creating Issues (`/to-tickets`)
1. Publish tickets directly to Gitea using `tea issue create --title "<title>" --body "<body>" --labels "ready-for-agent"`.
2. Reference blocking dependencies in the issue description using `#<issue_number>`.

### Working Issues (`/implement`)
1. Query active tickets via `tea issue list --state open`.
2. Pick issues with label `ready-for-agent` whose blockers are cleared.
3. Implement and test against acceptance criteria.
4. Close the issue on Gitea via `tea issue close <index>` upon completion.
