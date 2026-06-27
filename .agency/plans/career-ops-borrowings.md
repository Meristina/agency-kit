# Adaptations career-ops → agency-kit

Source analysée : `santifer/career-ops` (740 évaluations, Go dashboard, batch asynchrone, PDF Playwright).
Analyse multi-agents : 9 agents, 299 913 tokens, 396s — 2026-06-27.

---

## Ce que career-ops fait mieux (top 5)

1. **Rate-limit detection + pause propre** — batch-runner.sh détecte `session limit|resets [0-9:]+[ap]m` dans stderr, sauvegarde l'état, `--resume-paused` repart exactement là. Agency-kit : exception non catchée = mission perdue.
2. **Batch asynchrone avec isolation des workers** — N workers headless en parallèle (`claude -p --dangerously-skip-permissions`). Un crash = 1 mission perdue, les autres continuent.
3. **Export PDF via Playwright** — `generate-pdf.mjs` : placeholders `{{...}}` dans HTML, fonts inlinées en base64, ATS normalization pass, `page.pdf()`. Production-ready.
4. **Single-entry router avec dispatch de sous-modes** — un SKILL.md, table de routing, `modes/{mode}.md` + `modes/_shared.md` injecté.
5. **TUI Go dashboard (Bubble Tea)** — 3 écrans : pipeline table (8 filtres, 7 tris) / viewer inline / analytics. Zéro dépendance sur le CLI AI.

## Ce qu'agency-kit fait mieux (top 3)

1. **Pipeline avec état accumulé inter-départements** — dossier vivant, chaque département lit tous les `dept_outputs` précédents.
2. **Inspector avec VETO** — verdict ternaire PASS/PASS-WITH-FIXES/VETO + re-génération forcée.
3. **Schema de sortie explicite et versionné** — `dossier-template.md` + `deliverable-template.md`.

---

## HAUTE priorité — implémentées ✓ 2026-06-27

### ✓ 1. Rate-limit detection + pause propre (`mission.py`)
**Emprunté :** pattern grep de `batch-runner.sh`.
**Implémentation :** `_QUOTA_PAT` + `_is_quota_error()` dans `mission.py`. Deux `Runner.run_sync` wrappés dans `_mission_loop` (commander + inspector). Sur détection : `dossier["status"] = "paused_rate_limit"`, `store.save()`, print des instructions de reprise, `return dossier`.
**Effort réel :** ~20 lignes.
**Note :** `parallel.py` a ses propres appels `Runner.run_sync` qui bénéficieraient du même traitement.

### ✓ 2. Métadonnées structurées dans `deliverable.md` (`store.py`)
**Emprunté :** champs boldés `**Archetype:**`, `**TL;DR:**` en tête de rapport career-ops.
**Implémentation :** bloc YAML front-matter en tête de `deliverable.md` au moment du `save()` : `mission_id`, `route`, `departments`, `iteration`, `verdict`, `delivered`. Parsable par regex.
**Effort réel :** 10 lignes dans `store.py`.

### ✓ 3. `--dry-run` (`cli.py` + `router.py`)
**Emprunté :** flag `--dry-run` de `batch-runner.sh` + bloc "no args" de SKILL.md.
**Implémentation :**
- `_keyword_classify(goal)` extrait de `classify()` dans `router.py` (pas d'appel API).
- `_cmd_dry_run()` dans `cli.py` : appelle `_keyword_classify`, affiche la route + statut installed/missing pour chaque département, propose la commande `pip install` pour les manquants.
- `agency run --dry-run "goal"` — aucun appel API.
**Effort réel :** ~35 lignes.

---

## HAUTE priorité — implémentées ✓ 2026-06-27 (suite)

### ✓ 4. Mission queue + batch-state (`agency batch add/run/status`)
**Emprunté :** `batch-input.tsv` + `batch-state.tsv` de career-ops.
**Implémentation :** `agency_cli/batch_runner.py` — TSV queue + state, lock mkdir, add/run/status/clear. Sous-commande `agency batch add/run/status/clear`. `--resume-paused` et `--retry-failed` supportés.
**Effort réel :** ~215 lignes.

### ✓ 5. Atomic mission number reservation (`store.py`)
**Emprunté :** `reserve-report-num.mjs` avec `O_CREAT|O_EXCL` de career-ops.
**Implémentation :** `_agency_dir() / ".mission-id.lock"` avec `mkdir(exist_ok=False)` + retry 20× × 5ms dans `new_mission_id()`. Lock toujours relâché dans `finally`.
**Effort réel :** ~20 lignes.

---

## MOYENNE priorité

### 6. Export PDF via WeasyPrint
**Emprunté :** pipeline `generate-pdf.mjs` mais stack Python pure.
**Comment adapter :** `deliverable.md` → `markdown` lib → HTML → `weasyprint` → PDF. Template HTML dans `templates/deliverable-template.html`. Nouvelle sous-commande `agency export <mission_id>`. Pas de contrainte ATS = WeasyPrint suffit.
**Effort estimé :** ~1 jour.

### 7. Python Textual TUI
**Emprunté :** architecture 3 écrans du dashboard Go (pipeline table / viewer / analytics).
**Comment adapter :** `store.list_missions()` retourne déjà tout. Écran 1 : table missions (ID, GOAL, ROUTE, ITER, VERDICT). Écran 2 : viewer `deliverable.md`. Écran 3 : analytics (taux VETO par dept, itérations moyennes). Source : `dossier.json` — plus simple à parser que la markdown table career-ops.
**Effort estimé :** ~3-5 jours.

### 8. `_shared.md` par famille de département
**Emprunté :** pattern `modes/_shared.md` de career-ops.
**Comment adapter :** `_shared-finance.md`, `_shared-product.md`, etc. factorisant le contexte répété dans les 100+ fichiers officer/soldier.
**Effort estimé :** ~2-3 jours (audit + refactoring).

### 9. Variants juridictionnels (pattern locale career-ops)
**Emprunté :** `modes/de/`, `modes/fr/` de career-ops — mais pour compliance, pas langue.
**Comment adapter :** `modes/eu/` (GDPR, NIS2, AI Act), `modes/us/` (SOC2, CCPA), `modes/fr/` (RGPD + droit du travail FR) pour les départements ops, tech, comms.
**Effort estimé :** ~3-5 jours par département.

---

## Ce qu'on ne copie PAS

| Pattern career-ops | Raison |
|---|---|
| Scoring numérique ATS (0–10, seuil 4.5) | VETO/PASS d'agency-kit est déjà meilleur |
| `match-star.mjs` (token-overlap) | Spécifique CV/story-bank, aucun équivalent business |
| Liveness gate HTTP | Spécifique offres d'emploi qui expirent |
| 11 variantes locale (langue) | Ce qui est utile : variants juridictionnels, pas langue |
| APIs ATS (Greenhouse/Ashby/Lever) | Domaine emploi uniquement |

---

## Roadmap synthétique

```
Semaine 1  ✓ rate-limit detection  ✓ front-matter deliverable  ✓ --dry-run
Semaine 2  ✓ atomic mission lock + agency batch add/run/status/clear
           ✓ quota handling in parallel.py (dept/synthesis/inspect) + tests
Semaine 3  ✓ agency export (WeasyPrint PDF)
Mois 2     ✓ Python Textual TUI (3 onglets : Pipeline / Viewer / Analytics)
Mois 3     ✓ _shared-agency.md + departments.py (source unique — 9 depts)
             → suivant : variants juridictionnels EU/US/FR (ops/tech/comms)
```
