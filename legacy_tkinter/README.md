# Legacy Tkinter versions (reference only)

These are the original desktop (Tkinter) versions of the ACEest app that were provided
for the assignment. They are kept here, unchanged except for the file names
(normalised to `Aceestver-X.Y.Z.py`), as the functional specification for each release.

The deployable product is the Flask web application in [`aceest/`](../aceest). Each Git tag
(`v1.0` … `v3.2.4`) re-implements the features of the matching file below as a web
service, so it can be containerised, tested over HTTP and deployed to Kubernetes.

| Tkinter file | Flask tag | Main features |
|---|---|---|
| Aceestver-1.0.py   | v1.0   | Static program catalogue (FL / MG / BG): workout + diet |
| Aceestver-1.1.py   | v1.1   | Client profile form, calorie estimation per program |
| Aceestver-1.1.2.py | v1.1.2 | Multiple clients, client table, CSV export, adherence chart |
| Aceestver-2.0.1.py | v2.0.1 | SQLite persistence for clients + weekly progress |
| Aceestver-2.1.2.py | v2.1.2 | (identical to 2.0.1) - Flask release adds validation + JSON errors |
| Aceestver-2.2.1.py | v2.2.1 | Weekly adherence progress chart |
| Aceestver-2.2.4.py | v2.2.4 | Extended profile, goals, workouts/exercises, body metrics, BMI, summary |
| Aceestver-3.0.1.py | v3.0.1 | (identical to 2.2.4) - Flask release adds readiness probe, logging, gunicorn |
| Aceestver-3.1.2.py | v3.1.2 | Login, AI-style program generator, PDF client report |
| Aceestver-3.2.4.py | v3.2.4 | Membership tracking, role-based users |
