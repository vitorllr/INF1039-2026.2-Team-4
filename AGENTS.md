# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- Repo layout: work is organized per sprint and per person, `Sprint-N/<Nome-Sobrenome>/`. `main.py` at the repo root is an unrelated leftover stub, not part of the app.
- INEA (Instituto Estadual do Ambiente) has no documented public API for its flood/rain bulletin. The real, live source is the HTML-based Sistema de Alerta de Cheias at `https://alertadecheias.inea.rj.gov.br`, with one station table per hydrographic region at `dados/<regiao>.php`. See `Sprint-3/Vitor-Rocha/poc-parsing-boletim-inea/` for a working parser and caveats (fragile HTML scraping, incomplete TLS chain on that host).

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
