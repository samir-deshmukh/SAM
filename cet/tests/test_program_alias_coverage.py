import csv
from pathlib import Path

def test_2024_engineering_cutoff_program_names_are_recognized():
    path = Path(__file__).resolve().parents[1] / "data" / "reference" / "program_aliases.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        aliases = {row["raw_name"]: row for row in csv.DictReader(handle)}

    expected = {
        "Electrical Engg[Electronics and Power]",
        "Mechanical & Automation Engineering",
        "Printing and Packing Technology",
        "5G",
        "VLSI",
        "Architectural Assistantship",
        "Data Engineering",
        "Fire Engineering",
    }
    assert expected <= aliases.keys()
    assert aliases["Electrical Engg[Electronics and Power]"]["program_full"] == "Electrical Engineering (Electronics and Power)"
    assert aliases["Mechanical & Automation Engineering"]["program_full"] == "Mechanical and Automation Engineering"
    assert aliases["Printing and Packing Technology"]["program_full"] == "Printing and Packaging Technology"
    assert all(aliases[name]["program_family"] == "BE" for name in expected)
