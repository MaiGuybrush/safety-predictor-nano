# Domain Docs Layout & Consumer Rules

## Layout
This repository uses a **single-context** domain layout.

- **Glossary & Architecture**: Defined in `AGENTS.md` at the repo root.
- **Architecture Decision Records (ADR)**: Located in `docs/adr/`.
- **Product Requirements (PRD)**: Located in `docs/prd/`.

## Consumer Rules for Agents
1. **Read before building**: Inspect `AGENTS.md` and relevant ADRs in `docs/adr/` before designing or implementing features.
2. **Respect ADR decisions**: All new implementations must conform to accepted ADRs.
3. **Domain Vocabulary**: Use consistent domain terms defined in `AGENTS.md` and ADRs across code, commits, and tickets.
