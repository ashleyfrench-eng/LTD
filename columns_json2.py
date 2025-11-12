import csv
import json
import os

# -------------------------------
# FUNCTION: Generate column JSON
# -------------------------------
def generate_columns_json(folder_path):
    """
    Reads a column_data.csv file and writes a structured columns JSON file.
    Returns the path to the JSON file.
    """
    csv_file = os.path.join(folder_path, "Revit_Data", "column_data.csv")
    output_file = os.path.join(folder_path, "columns_cleaned.json")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"❌ CSV file not found: {csv_file}")

    columns_data = []

    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                column_id = int(row["Column ID"])
                top_x = float(row["Top X (m)"])
                top_y = float(row["Top Y (m)"])
                base_level = row["Base Level"].strip()
                top_level = row["Top Level"].strip()
            except Exception:
                print(f"⚠️ Skipping malformed row: {row}")
                continue

            columns_data.append({
                "ID": column_id,
                "Top": {"X": round(top_x, 3), "Y": round(top_y, 3)},
                "BaseLevel": base_level,
                "TopLevel": top_level
            })

    output = {"Columns": columns_data}

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ JSON file saved to:\n{output_file}")
    return output_file
