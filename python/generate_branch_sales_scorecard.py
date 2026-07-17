from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "generated_data"
OUTPUT_DIR.mkdir(exist_ok=True)

random.seed(42)

PROVINCES_AND_CITIES = {
    "Ontario": ["Toronto", "Ottawa", "Hamilton", "London", "Mississauga", "Markham", "Brampton", "Kitchener", "Windsor", "Kingston"],
    "Quebec": ["Montreal", "Quebec City", "Laval", "Gatineau", "Sherbrooke", "Trois-Rivieres", "Longueuil"],
    "British Columbia": ["Vancouver", "Victoria", "Surrey", "Burnaby", "Richmond", "Kelowna", "Abbotsford"],
    "Alberta": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Grande Prairie"],
    "Manitoba": ["Winnipeg", "Brandon", "Portage la Prairie"],
    "Saskatchewan": ["Regina", "Saskatoon", "Prince Albert"],
    "Nova Scotia": ["Halifax", "Dartmouth", "Sydney"],
    "New Brunswick": ["Fredericton", "Moncton", "Saint John"],
    "Newfoundland and Labrador": ["St. John's", "Corner Brook"],
    "Prince Edward Island": ["Charlottetown", "Summerside"],
    "Northwest Territories": ["Yellowknife"],
    "Nunavut": ["Iqaluit"],
    "Yukon": ["Whitehorse"],
}

FIRST_NAMES = [
    "Aiden", "Ava", "Benjamin", "Chloe", "Daniel", "Emma", "Ethan", "Grace", "Hannah",
    "Isaac", "Jasmine", "Liam", "Mia", "Noah", "Olivia", "Owen", "Parker", "Ruby", "Sophia",
    "Thomas", "Victoria", "William", "Zara", "Mason", "Ella", "Lucas", "Amelia", "Henry",
    "Harper", "Jack", "Charlotte", "Leo", "Lily", "Nora", "Sam", "Aria", "Theo", "Mila",
    "Julian", "Sienna", "Aaron", "Aaliyah", "Colin", "Faith", "Dylan", "Brooke"
]

LAST_NAMES = [
    "Brown", "Campbell", "Davis", "Edwards", "Foster", "Garcia", "Hughes", "Johnson",
    "Kim", "Lee", "Mitchell", "Nguyen", "Owen", "Patel", "Quinn", "Roberts", "Sanchez",
    "Turner", "Underwood", "Vargas", "Walker", "Xu", "Young", "Zhang", "Adams", "Bennett",
    "Clark", "Diaz", "Evans", "Fisher", "Gonzalez", "Harris", "Irwin", "James", "Khan"
]

TIERS = [
    ("Small", {"Manager": 1, "Advisor": 2, "Teller": 3}),
    ("Medium", {"Manager": 1, "Advisor": 3, "Teller": 4}),
    ("Large", {"Manager": 1, "Advisor": 4, "Teller": 5}),
]

ROLE_ORDER = ["Manager", "Advisor", "Teller"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def month_factor(month_index: int) -> float:
    seasonal = 1 + 0.06 * math.sin((month_index - 1) / 12 * 2 * math.pi)
    return seasonal


def pick_location() -> tuple[str, str]:
    province = random.choice(list(PROVINCES_AND_CITIES.keys()))
    city = random.choice(PROVINCES_AND_CITIES[province])
    return province, city


def generate_name() -> tuple[str, str]:
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def build_dimensions() -> tuple[list[dict], list[dict], list[dict]]:
    branches: list[dict] = []
    employees: list[dict] = []
    role_weights: list[dict] = []

    for tier_name, staffing in TIERS:
        for branch_index in range(100):
            branch_id = len(branches) + 1
            province, city = pick_location()
            branch_code = f"{tier_name[:3].upper()}{branch_id:03d}"
            branch_name = f"{tier_name} Branch {branch_id:03d}"
            branch = {
                "branch_id": branch_id,
                "branch_code": branch_code,
                "branch_name": branch_name,
                "tier": tier_name,
                "province": province,
                "city": city,
                "manager_count": staffing["Manager"],
                "advisor_count": staffing["Advisor"],
                "teller_count": staffing["Teller"],
                "employee_count": sum(staffing.values()),
                "opening_year": random.randint(2008, 2024),
            }
            branches.append(branch)

            role_sequence = [
                ("Manager", staffing["Manager"]),
                ("Advisor", staffing["Advisor"]),
                ("Teller", staffing["Teller"]),
            ]
            for role, count in role_sequence:
                for _ in range(count):
                    first_name, last_name = generate_name()
                    employee_id = len(employees) + 1
                    employee = {
                        "employee_id": employee_id,
                        "branch_id": branch_id,
                        "branch_code": branch_code,
                        "tier": tier_name,
                        "province": province,
                        "city": city,
                        "role": role,
                        "first_name": first_name,
                        "last_name": last_name,
                        "hire_date": f"{random.randint(2015, 2024)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                    }
                    employees.append(employee)

    role_weights.extend(
        [
            {"role": "Advisor", "metric_name": "Lending", "weight_pct": 35},
            {"role": "Advisor", "metric_name": "Investing", "weight_pct": 35},
            {"role": "Advisor", "metric_name": "Banking units", "weight_pct": 15},
            {"role": "Advisor", "metric_name": "LEI customer score", "weight_pct": 15},
            {"role": "Teller", "metric_name": "Banking units", "weight_pct": 70},
            {"role": "Teller", "metric_name": "LEI customer score", "weight_pct": 30},
            {"role": "Manager", "metric_name": "Lending", "weight_pct": 30},
            {"role": "Manager", "metric_name": "Investing", "weight_pct": 30},
            {"role": "Manager", "metric_name": "Banking units", "weight_pct": 15},
            {"role": "Manager", "metric_name": "LEI customer score", "weight_pct": 10},
            {"role": "Manager", "metric_name": "Compliance / Risk", "weight_pct": 15},
        ]
    )

    return branches, employees, role_weights


def build_targets(employees: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for employee in employees:
        tier = employee["tier"]
        role = employee["role"]
        base_targets = {
            "Small": {
                "Advisor": {"lending": 1800, "investing": 1400, "banking": 420, "lei": 78},
                "Teller": {"banking": 560, "lei": 76},
                "Manager": {"lending": 2500, "investing": 1800, "banking": 600, "lei": 80, "compliance": 88},
            },
            "Medium": {
                "Advisor": {"lending": 2400, "investing": 1800, "banking": 560, "lei": 80},
                "Teller": {"banking": 740, "lei": 78},
                "Manager": {"lending": 3200, "investing": 2300, "banking": 740, "lei": 82, "compliance": 90},
            },
            "Large": {
                "Advisor": {"lending": 3200, "investing": 2400, "banking": 740, "lei": 82},
                "Teller": {"banking": 920, "lei": 80},
                "Manager": {"lending": 4200, "investing": 3000, "banking": 920, "lei": 84, "compliance": 92},
            },
        }[tier][role]

        for month_index in range(1, 13):
            monthly_factor = month_factor(month_index)
            row = {
                "employee_id": employee["employee_id"],
                "branch_id": employee["branch_id"],
                "branch_code": employee["branch_code"],
                "role": role,
                "tier": tier,
                "month_number": month_index,
                "month_name": date(2025, month_index, 1).strftime("%B"),
                "target_lending": round(base_targets.get("lending", 0) * monthly_factor * random.uniform(0.95, 1.05), 2),
                "target_investing": round(base_targets.get("investing", 0) * monthly_factor * random.uniform(0.95, 1.05), 2),
                "target_banking_units": round(base_targets.get("banking", 0) * monthly_factor * random.uniform(0.95, 1.05), 2),
                "target_lei": 4.0,
                "target_compliance": round(base_targets.get("compliance", 0) * monthly_factor * random.uniform(0.97, 1.03), 2),
            }
            rows.append(row)
    return rows


def read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_sales(target_rows: list[dict], employee_rows: list[dict]) -> list[dict]:
    employee_lookup = {row["employee_id"]: row for row in employee_rows}
    rows: list[dict] = []

    for target_row in target_rows:
        employee_id = target_row["employee_id"]
        employee = employee_lookup[employee_id]
        role = target_row["role"]
        tier = target_row["tier"]

        lending_actual = 0.0
        investing_actual = 0.0
        if role in {"Advisor", "Manager"}:
            lending_actual = round(float(target_row["target_lending"]) * random.uniform(0.95, 1.05), 2)
            investing_actual = round(float(target_row["target_investing"]) * random.uniform(0.95, 1.05), 2)

        banking_units_actual = round(float(target_row["target_banking_units"]) * random.uniform(0.95, 1.05), 2)
        lei_actual = round(clamp(float(target_row["target_lei"]) / 20.0 * random.uniform(0.95, 1.05), 1.0, 5.0), 2)

        rows.append(
            {
                "employee_id": employee_id,
                "branch_id": employee["branch_id"],
                "branch_code": employee["branch_code"],
                "role": role,
                "tier": tier,
                "month_number": target_row["month_number"],
                "month_name": target_row["month_name"],
                "lending_actual": lending_actual,
                "investing_actual": investing_actual,
                "banking_units_actual": banking_units_actual,
                "lei_actual": lei_actual,
            }
        )

    return rows


def build_lei_survey(target_rows: list[dict], employee_rows: list[dict]) -> list[dict]:
    employee_lookup = {row["employee_id"]: row for row in employee_rows}
    rows: list[dict] = []

    for target_row in target_rows:
        employee_id = target_row["employee_id"]
        employee = employee_lookup[employee_id]
        baseline_lei = clamp(float(target_row["target_lei"]) / 20.0, 1.0, 5.0)
        lei_score = round(clamp(baseline_lei + random.gauss(0, 0.25), 1.0, 5.0), 2)
        survey_response_count = random.randint(4, 15)

        rows.append(
            {
                "employee_id": employee_id,
                "branch_id": employee["branch_id"],
                "month_number": target_row["month_number"],
                "month_name": target_row["month_name"],
                "survey_response_count": survey_response_count,
                "lei_score": lei_score,
            }
        )

    return rows


def build_compliance(branches: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for branch in branches:
        tier = branch["tier"]
        base = {"Small": 88, "Medium": 90, "Large": 92}[tier]
        for month_index in range(1, 13):
            monthly_factor = month_factor(month_index)
            compliance_score = round(clamp(base * monthly_factor + random.gauss(0, 1.1), 80, 100), 2)
            risk_score = round(clamp(100 - compliance_score + random.gauss(0, 1.2), 0, 25), 2)
            exceptions_count = random.randint(0, 4)
            rows.append(
                {
                    "branch_id": branch["branch_id"],
                    "branch_code": branch["branch_code"],
                    "month_number": month_index,
                    "month_name": date(2025, month_index, 1).strftime("%B"),
                    "tier": tier,
                    "province": branch["province"],
                    "city": branch["city"],
                    "compliance_score": compliance_score,
                    "risk_score": risk_score,
                    "exceptions_count": exceptions_count,
                }
            )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    employees = read_csv_rows(OUTPUT_DIR / "dim_employee.csv")
    targets = read_csv_rows(OUTPUT_DIR / "fact_targets.csv")
    sales = build_sales(targets, employees)
    lei_survey = build_lei_survey(targets, employees)

    sales_fields = ["employee_id", "branch_id", "branch_code", "role", "tier", "month_number", "month_name", "lending_actual", "investing_actual", "banking_units_actual", "lei_actual"]
    lei_fields = ["employee_id", "branch_id", "month_number", "month_name", "survey_response_count", "lei_score"]

    write_csv(OUTPUT_DIR / "fact_sales.csv", sales_fields, sales)
    write_csv(OUTPUT_DIR / "fact_lei_survey.csv", lei_fields, lei_survey)

    print(f"Regenerated {len(sales)} employee-month sales rows and {len(lei_survey)} employee-month survey rows.")
    print(f"Files written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
