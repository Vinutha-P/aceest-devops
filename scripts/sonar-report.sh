#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Export the SonarQube analysis of "aceest-fitness" to docs/evidence/sonarqube-report.md
# (SonarQube Community has no PDF export - this makes the report part of the repo).
#   SONAR_TOKEN=<token> scripts/sonar-report.sh
#   SONAR_URL defaults to http://localhost:9000
# -----------------------------------------------------------------------------
set -euo pipefail
: "${SONAR_TOKEN:?set SONAR_TOKEN (SonarQube > My Account > Security)}"
SONAR_URL="${SONAR_URL:-http://localhost:9000}"
PROJECT="${SONAR_PROJECT:-aceest-fitness}"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/evidence"
mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"

api() { curl -fsS -u "${SONAR_TOKEN}:" "${SONAR_URL}$1"; }

METRICS="alert_status,bugs,vulnerabilities,security_hotspots,code_smells,coverage,duplicated_lines_density,ncloc,tests,test_failures,sqale_rating,reliability_rating,security_rating"
api "/api/measures/component?component=${PROJECT}&metricKeys=${METRICS}" > "$TMP/measures.json"
api "/api/qualitygates/project_status?projectKey=${PROJECT}" > "$TMP/gate.json"
api "/api/project_analyses/search?project=${PROJECT}&ps=10" > "$TMP/analyses.json"

python - "$TMP" "$OUT_DIR/sonarqube-report.md" "$SONAR_URL" "$PROJECT" <<'PY'
import json, sys, datetime, pathlib
tmp, out, url, project = sys.argv[1:5]
load = lambda n: json.loads(pathlib.Path(tmp, n).read_text())
measures = {m["metric"]: m.get("value", "-") for m in load("measures.json")["component"]["measures"]}
gate = load("gate.json")["projectStatus"]
analyses = load("analyses.json")["analyses"]
rating = {"1.0": "A", "2.0": "B", "3.0": "C", "4.0": "D", "5.0": "E"}
rows = [
    ("Quality Gate", gate["status"]),
    ("Bugs", measures.get("bugs")), ("Vulnerabilities", measures.get("vulnerabilities")),
    ("Security Hotspots", measures.get("security_hotspots")),
    ("Code Smells", measures.get("code_smells")),
    ("Coverage", f'{measures.get("coverage")} %'),
    ("Duplicated lines", f'{measures.get("duplicated_lines_density")} %'),
    ("Lines of code", measures.get("ncloc")), ("Unit tests", measures.get("tests")),
    ("Test failures", measures.get("test_failures")),
    ("Reliability rating", rating.get(measures.get("reliability_rating"), "-")),
    ("Security rating", rating.get(measures.get("security_rating"), "-")),
    ("Maintainability rating", rating.get(measures.get("sqale_rating"), "-")),
]
lines = [f"# SonarQube report - {project}", "",
         f"Exported {datetime.datetime.now():%Y-%m-%d %H:%M} from {url}/dashboard?id={project}", "",
         "| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows]
lines += ["", "## Quality gate conditions", "", "| Metric | Status | Actual | Threshold |",
          "|---|---|---|---|"]
for c in gate.get("conditions", []):
    lines.append(f'| {c["metricKey"]} | {c["status"]} | {c.get("actualValue", "-")} '
                 f'| {c.get("comparator", "")} {c.get("errorThreshold", "")} |')
lines += ["", "## Recent analyses", "", "| Date | Version |", "|---|---|"]
for a in analyses:
    lines.append(f'| {a["date"]} | {a.get("projectVersion", "-")} |')
pathlib.Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
PY
rm -rf "$TMP"
echo
echo "Saved to ${OUT_DIR}/sonarqube-report.md"
