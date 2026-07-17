from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "generated_data"
DB_PATH = ROOT / "scorecard.db"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def infer_sql_type(column: str) -> str:
    integer_columns = {
        "branch_id",
        "employee_id",
        "month_number",
        "manager_count",
        "advisor_count",
        "teller_count",
        "employee_count",
        "opening_year",
        "survey_response_count",
        "exceptions_count",
    }
    return "INTEGER" if column in integer_columns else "REAL"


def load_csv_into_table(conn: sqlite3.Connection, table_name: str, rows: list[dict[str, str]], numeric_fields: set[str] | None = None) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    numeric_fields = numeric_fields or set()
    column_sql = ", ".join(
        f'"{column}" {infer_sql_type(column) if column in numeric_fields else "TEXT"}'
        for column in columns
    )
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({column_sql})')

    placeholders = ", ".join(["?"] * len(columns))
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if column in numeric_fields:
                if value in (None, ""):
                    values.append(None)
                elif column in {"branch_id", "employee_id", "month_number", "manager_count", "advisor_count", "teller_count", "employee_count", "opening_year", "survey_response_count", "exceptions_count"}:
                    values.append(int(float(value)))
                else:
                    values.append(float(value))
            else:
                values.append(value)
        conn.execute(f'INSERT INTO "{table_name}" ({", ".join(f'"{c}"' for c in columns)}) VALUES ({placeholders})', values)

    conn.commit()


def build_schema(conn: sqlite3.Connection) -> None:
    dim_branch_rows = read_csv_rows(DATA_DIR / "dim_branch.csv")
    dim_employee_rows = read_csv_rows(DATA_DIR / "dim_employee.csv")
    dim_role_weights_rows = read_csv_rows(DATA_DIR / "dim_role_weights.csv")
    fact_targets_rows = read_csv_rows(DATA_DIR / "fact_targets.csv")
    fact_sales_rows = read_csv_rows(DATA_DIR / "fact_sales.csv")
    fact_lei_survey_rows = read_csv_rows(DATA_DIR / "fact_lei_survey.csv")
    fact_compliance_rows = read_csv_rows(DATA_DIR / "fact_compliance.csv")

    load_csv_into_table(
        conn,
        "dim_branch",
        dim_branch_rows,
        {"branch_id", "manager_count", "advisor_count", "teller_count", "employee_count", "opening_year"},
    )
    load_csv_into_table(
        conn,
        "dim_employee",
        dim_employee_rows,
        {"employee_id", "branch_id"},
    )
    load_csv_into_table(
        conn,
        "dim_role_weights",
        dim_role_weights_rows,
        {"weight_pct"},
    )
    load_csv_into_table(
        conn,
        "fact_targets",
        fact_targets_rows,
        {"employee_id", "branch_id", "month_number", "target_lending", "target_investing", "target_banking_units", "target_lei", "target_compliance"},
    )
    load_csv_into_table(
        conn,
        "fact_sales",
        fact_sales_rows,
        {"employee_id", "branch_id", "month_number", "lending_actual", "investing_actual", "banking_units_actual", "lei_actual"},
    )
    load_csv_into_table(
        conn,
        "fact_lei_survey",
        fact_lei_survey_rows,
        {"employee_id", "branch_id", "month_number", "survey_response_count", "lei_score"},
    )
    load_csv_into_table(
        conn,
        "fact_compliance",
        fact_compliance_rows,
        {"branch_id", "month_number", "compliance_score", "risk_score", "exceptions_count"},
    )


def create_views(conn: sqlite3.Connection) -> None:
    for view_name in ["vw_employee_monthly_score", "vw_employee_rank", "vw_employee_scorecard_long", "vw_branch_monthly_score", "vw_branch_pacing"]:
        conn.execute(f"DROP VIEW IF EXISTS {view_name}")

    conn.execute(
        """
        CREATE VIEW vw_employee_monthly_score AS
        WITH role_weights AS (
            SELECT
                role,
                MAX(CASE WHEN metric_name = 'Lending' THEN weight_pct END) AS lending_weight,
                MAX(CASE WHEN metric_name = 'Investing' THEN weight_pct END) AS investing_weight,
                MAX(CASE WHEN metric_name = 'Banking units' THEN weight_pct END) AS banking_weight,
                MAX(CASE WHEN metric_name = 'LEI customer score' THEN weight_pct END) AS lei_weight
            FROM dim_role_weights
            GROUP BY role
        )
        SELECT
            fs.employee_id,
            fs.branch_id,
            de.branch_code,
            de.role,
            de.first_name,
            de.last_name,
            fs.month_number,
            fs.month_name,
            CASE
                WHEN de.role = 'Teller' THEN NULL
                ELSE fs.lending_actual / ft.target_lending
            END AS lending_pct_to_target,
            CASE
                WHEN de.role = 'Teller' THEN NULL
                ELSE fs.investing_actual / ft.target_investing
            END AS investing_pct_to_target,
            fs.banking_units_actual / ft.target_banking_units AS banking_units_pct_to_target,
            fs.lei_actual / ft.target_lei AS lei_pct_to_target,
            (
                COALESCE(CASE WHEN de.role = 'Teller' THEN NULL ELSE fs.lending_actual / ft.target_lending END, 0) * COALESCE(rw.lending_weight, 0)
                + COALESCE(CASE WHEN de.role = 'Teller' THEN NULL ELSE fs.investing_actual / ft.target_investing END, 0) * COALESCE(rw.investing_weight, 0)
                + COALESCE(fs.banking_units_actual / ft.target_banking_units, 0) * COALESCE(rw.banking_weight, 0)
                + COALESCE(fs.lei_actual / ft.target_lei, 0) * COALESCE(rw.lei_weight, 0)
            ) / 100.0 AS weighted_total_score
        FROM fact_sales fs
        JOIN fact_targets ft
            ON ft.employee_id = fs.employee_id
           AND ft.month_number = fs.month_number
        JOIN dim_employee de
            ON de.employee_id = fs.employee_id
        LEFT JOIN role_weights rw
            ON rw.role = de.role
        ORDER BY fs.employee_id, fs.month_number
        """
    )

    conn.execute(
        """
        CREATE VIEW vw_employee_rank AS
        SELECT
            employee_id,
            branch_id,
            branch_code,
            role,
            first_name,
            last_name,
            month_number,
            month_name,
            lending_pct_to_target,
            investing_pct_to_target,
            banking_units_pct_to_target,
            lei_pct_to_target,
            weighted_total_score,
            DENSE_RANK() OVER (
                PARTITION BY role, month_number
                ORDER BY weighted_total_score DESC
            ) AS rank_within_role,
            DENSE_RANK() OVER (
                PARTITION BY branch_id, month_number
                ORDER BY weighted_total_score DESC
            ) AS rank_within_branch
        FROM vw_employee_monthly_score
        """
    )

    conn.execute(
        """
        CREATE VIEW vw_employee_scorecard_long AS
        SELECT
            employee_id,
            branch_id,
            branch_code,
            role,
            first_name,
            last_name,
            month_number,
            month_name,
            'Lending' AS pillar_name,
            lending_pct_to_target AS pct_to_target,
            weighted_total_score,
            rank_within_role,
            rank_within_branch
        FROM vw_employee_rank
        WHERE role != 'Teller' AND lending_pct_to_target IS NOT NULL

        UNION ALL

        SELECT
            employee_id,
            branch_id,
            branch_code,
            role,
            first_name,
            last_name,
            month_number,
            month_name,
            'Investing' AS pillar_name,
            investing_pct_to_target AS pct_to_target,
            weighted_total_score,
            rank_within_role,
            rank_within_branch
        FROM vw_employee_rank
        WHERE role != 'Teller' AND investing_pct_to_target IS NOT NULL

        UNION ALL

        SELECT
            employee_id,
            branch_id,
            branch_code,
            role,
            first_name,
            last_name,
            month_number,
            month_name,
            'Banking' AS pillar_name,
            banking_units_pct_to_target AS pct_to_target,
            weighted_total_score,
            rank_within_role,
            rank_within_branch
        FROM vw_employee_rank
        WHERE banking_units_pct_to_target IS NOT NULL

        UNION ALL

        SELECT
            employee_id,
            branch_id,
            branch_code,
            role,
            first_name,
            last_name,
            month_number,
            month_name,
            'LEI' AS pillar_name,
            lei_pct_to_target AS pct_to_target,
            weighted_total_score,
            rank_within_role,
            rank_within_branch
        FROM vw_employee_rank
        WHERE lei_pct_to_target IS NOT NULL
        """
    )

    conn.execute(
        """
        CREATE VIEW vw_branch_monthly_score AS
        WITH branch_sales AS (
            SELECT
                branch_id,
                month_number,
                SUM(lending_actual) AS lending_actual,
                SUM(investing_actual) AS investing_actual,
                SUM(banking_units_actual) AS banking_units_actual,
                SUM(lei_actual) AS lei_actual
            FROM fact_sales
            GROUP BY branch_id, month_number
        ),
        branch_targets AS (
            SELECT
                branch_id,
                month_number,
                SUM(target_lending) AS target_lending,
                SUM(target_investing) AS target_investing,
                SUM(target_banking_units) AS target_banking_units,
                SUM(target_lei) AS target_lei,
                SUM(target_compliance) AS target_compliance
            FROM fact_targets
            GROUP BY branch_id, month_number
        ),
        manager_weights AS (
            SELECT
                MAX(CASE WHEN metric_name = 'Lending' THEN weight_pct END) AS lending_weight,
                MAX(CASE WHEN metric_name = 'Investing' THEN weight_pct END) AS investing_weight,
                MAX(CASE WHEN metric_name = 'Banking units' THEN weight_pct END) AS banking_weight,
                MAX(CASE WHEN metric_name = 'LEI customer score' THEN weight_pct END) AS lei_weight,
                MAX(CASE WHEN metric_name = 'Compliance / Risk' THEN weight_pct END) AS compliance_weight
            FROM dim_role_weights
            WHERE role = 'Manager'
        )
        SELECT
            bs.branch_id,
            db.branch_code,
            db.branch_name,
            db.tier,
            bs.month_number,
            fc.month_name,
            bs.lending_actual / bt.target_lending AS lending_pct_to_target,
            bs.investing_actual / bt.target_investing AS investing_pct_to_target,
            bs.banking_units_actual / bt.target_banking_units AS banking_units_pct_to_target,
            bs.lei_actual / bt.target_lei AS lei_pct_to_target,
            fc.compliance_score / bt.target_compliance AS compliance_pct_to_target,
            (
                (bs.lending_actual / bt.target_lending) * mw.lending_weight
                + (bs.investing_actual / bt.target_investing) * mw.investing_weight
                + (bs.banking_units_actual / bt.target_banking_units) * mw.banking_weight
                + (bs.lei_actual / bt.target_lei) * mw.lei_weight
                + (fc.compliance_score / bt.target_compliance) * mw.compliance_weight
            ) / 100.0 AS weighted_total_score
        FROM branch_sales bs
        JOIN branch_targets bt
            ON bt.branch_id = bs.branch_id
           AND bt.month_number = bs.month_number
        JOIN dim_branch db
            ON db.branch_id = bs.branch_id
        JOIN fact_compliance fc
            ON fc.branch_id = bs.branch_id
           AND fc.month_number = bs.month_number
        CROSS JOIN manager_weights mw
        ORDER BY bs.branch_id, bs.month_number
        """
    )

    conn.execute(
        """
        CREATE VIEW vw_branch_pacing AS
        SELECT
            branch_id,
            branch_code,
            branch_name,
            tier,
            month_number,
            month_name,
            lending_pct_to_target,
            investing_pct_to_target,
            banking_units_pct_to_target,
            lei_pct_to_target,
            compliance_pct_to_target,
            weighted_total_score,
            CASE
                WHEN weighted_total_score >= 1.0 THEN 'Green'
                WHEN weighted_total_score >= 0.9 THEN 'Amber'
                ELSE 'Red'
            END AS rag_status
        FROM vw_branch_monthly_score
        """
    )

    conn.commit()


def run_validation(conn: sqlite3.Connection) -> None:
    view_names = ["vw_employee_monthly_score", "vw_employee_rank", "vw_branch_monthly_score", "vw_branch_pacing"]
    for view_name in view_names:
        count = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
        print(f"{view_name}: {count}")

    print("\nTop 3 Advisors for most recent month:")
    latest_month = conn.execute("SELECT MAX(month_number) FROM vw_employee_rank WHERE role = 'Advisor'").fetchone()[0]
    rows = conn.execute(
        """
        SELECT
            employee_id,
            branch_id,
            branch_code,
            first_name,
            last_name,
            weighted_total_score,
            rank_within_role,
            rank_within_branch
        FROM vw_employee_rank
        WHERE role = 'Advisor' AND month_number = ?
        ORDER BY weighted_total_score DESC, employee_id
        LIMIT 3
        """,
        (latest_month,),
    ).fetchall()
    for row in rows:
        print(row)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    build_schema(conn)
    create_views(conn)
    run_validation(conn)
    conn.close()
    print(f"\nSQLite database created at {DB_PATH}")


if __name__ == "__main__":
    main()
