"""PDF client report (ported from Aceestver-3.1.2, export_pdf_report)."""
from datetime import date

from flask import Blueprint, Response, g
from fpdf import FPDF

from .auth import login_required
from .clients import _client_row, _error
from .db import get_db
from .programs import PROGRAMS
from .tracking import bmi_category, calculate_bmi
from .version import __version__

bp = Blueprint("reports", __name__, url_prefix="/api/clients")


def _latin1(value):
    """Core PDF fonts are Latin-1 only; replace anything else instead of crashing."""
    return str(value).encode("latin-1", "replace").decode("latin-1")


def _show(value, unit=""):
    return "-" if value in (None, "") else f"{value}{unit}"


def build_report(client, progress, workouts, generated_by):
    pdf = FPDF()
    pdf.set_title(_latin1(f"ACEest Client Report - {client['name']}"))
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _latin1(f"ACEest Client Report - {client['name']}"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, _latin1(f"Generated {date.today().isoformat()} by {generated_by} "
                           f"(ACEest v{__version__})"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    def section(title, rows):
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for label, value in rows:
            pdf.cell(0, 7, _latin1(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    program = PROGRAMS.get(client["program"], {})
    section("Profile", [
        ("Name", client["name"]),
        ("Age", _show(client["age"])),
        ("Height", _show(client["height"], " cm")),
        ("Weight", _show(client["weight"], " kg")),
        ("Program", program.get("name", client["program"])),
        ("Calories", _show(client["calories"], " kcal/day")),
    ])

    bmi_text = "-"
    if client["height"] and client["weight"]:
        bmi = calculate_bmi(client["weight"], client["height"])
        bmi_text = f"{bmi} ({bmi_category(bmi)[0]})"
    section("Goals & Health", [
        ("Target weight", _show(client["target_weight"], " kg")),
        ("Target adherence", _show(client["target_adherence"], " %")),
        ("BMI", bmi_text),
    ])

    weeks, avg = progress
    section("Progress", [
        ("Weeks logged", weeks),
        ("Average adherence", f"{round(avg, 1) if avg else 0} %"),
    ])

    section("Recent workouts", [
        (w["date"], f"{w['workout_type']} - {w['duration_min']} min") for w in workouts
    ] or [("None", "no workouts logged yet")])

    return bytes(pdf.output())


@bp.get("/<name>/report.pdf")
@login_required()
def client_report(name):
    client = _client_row(name)
    if client is None:
        return _error("Client not found", 404)
    db = get_db()
    progress = db.execute(
        "SELECT COUNT(*), AVG(adherence) FROM progress WHERE client_name = ?", (name,)
    ).fetchone()
    workouts = db.execute(
        "SELECT date, workout_type, duration_min FROM workouts WHERE client_name = ? "
        "ORDER BY date DESC, id DESC LIMIT 5",
        (name,),
    ).fetchall()
    pdf_bytes = build_report(client, tuple(progress), workouts, g.user["username"])
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in name)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_report.pdf"},
    )
