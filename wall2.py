import csv
import json
import os

def generate_wall_json(folder_path, min_height_mm=1800):
    """
    Process wall_data.csv to create structured JSON:
    - Skips walls shorter than min_height_mm
    - Stores start & end top coordinates, base & top levels, and height
    - Saves JSON to folder_path
    """
    csv_file = os.path.join(folder_path, "Revit_Data", "wall_data.csv")
    output_file = os.path.join(folder_path, "wall_cleaned.json")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"❌ CSV file not found: {csv_file}")

    walls_data = []

    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                height_mm = float(row.get("Unconnected Height (mm)", 0))
                if height_mm < min_height_mm:
                    continue  # skip very short walls

                wall_id = int(row["Wall ID"])
                start_top_x = float(row["Start X (m)"])
                start_top_y = float(row["Start Y (m)"])
                end_top_x = float(row["End X (m)"])
                end_top_y = float(row["End Y (m)"])
                base_level = row["Base Level"].strip()
                top_level = row["Top Level"].strip()[13:].upper()  # adjust as needed

            except Exception:
                continue  # skip malformed rows

            walls_data.append({
                "ID": wall_id,
                "Start Top": {"X": round(start_top_x, 3), "Y": round(start_top_y, 3)},
                "End Top": {"X": round(end_top_x, 3), "Y": round(end_top_y, 3)},
                "BaseLevel": base_level,
                "TopLevel": top_level,
                "Height_mm": round(height_mm, 1)
            })

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({"Walls": walls_data}, f, indent=2)

    print(f"✅ JSON file saved to:\n{output_file}")
    print(f"📊 Walls exported: {len(walls_data)}")

    return output_file, len(walls_data)
