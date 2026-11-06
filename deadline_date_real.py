import csv, re
from datetime import datetime

path = "datasets/run_2026-10-27T17-50-29/labels.csv"

with open(path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

for r in rows:
    m = re.search(r"Prazo:\s*(\d{2}/\d{2}/\d{4})", r["observacao"])
    r["deadline_date_real"] = datetime.strptime(m[1], "%d/%m/%Y").date().isoformat() if m else ""

fields = ["id", "url", "title", "is_listing_real", "is_edital_real", "is_relevant_real",
          "deadline_real", "deadline_status_real", "deadline_date_real", "observacao"]

with open(path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(sum(1 for r in rows if r["deadline_date_real"]), "datas preenchidas")
