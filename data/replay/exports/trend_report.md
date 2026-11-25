# Quality over time (Excalidraw history replay)

One row per quarter of real Excalidraw string changes, scored with today's engines.
Content drift only: engine drift is tracked from now on with the fixed regression set.

| batch | date | new | changed | gate_needs_context_% | claude_mean_sev | deepl_mean_sev | google_mean_sev | auto_ship_% | to_people_% | audit_n | audit_errors_per_100 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025Q2 | 2025-06-30 | 10 | 0 | 60.0 | 1.5 | 1.4 | 2.0 | 90.0 | 10.0 | 9 | 0.0 |
| 2025Q3 | 2025-09-30 | 6 | 1 | 42.9 | 2.0 | 2.0 | 2.14 | 57.1 | 42.9 | 4 | 0.0 |
| 2025Q4 | 2025-12-28 | 11 | 21 | 100.0 | 1.59 | 2.31 | 3.53 | 0.0 | 68.8 | 0 |  |
| 2026Q1 | 2026-03-30 | 56 | 2 | 37.9 | 1.36 | 1.67 | 2.26 | 67.2 | 32.8 | 10 | 0.0 |
| 2026Q2 | 2026-06-29 | 6 | 0 | 100.0 | 1.5 | 2.33 | 3.17 | 83.3 | 16.7 | 5 | 20.0 |
| 2026Q3 | 2026-09-30 | 33 | 1 | 32.4 | 1.79 | 2.0 | 2.44 | 64.7 | 35.3 | 10 | 0.0 |
| 2026Q4 | 2026-11-03 | 8 | 0 | 25.0 | 1.5 | 2.0 | 3.5 | 50.0 | 50.0 | 4 | 0.0 |

Audit pooled: 1 errors in 42 auto-shipped strings = 2.4 per 100 (target <= 2.0). Per-batch audits are small (<= 10); read the pooled number.
