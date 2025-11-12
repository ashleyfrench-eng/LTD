import pandas as pd
import matplotlib.pyplot as plt
import os
import re
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union, polygonize
import json


def parse_boundary_string(boundary_str):
    """Extract line segments from '(x1, y1)-(x2, y2)' style text."""
    lines = []
    if not isinstance(boundary_str, str):
        return lines

    boundary_str = boundary_str.replace("\n", " ").replace("\r", " ").strip()
    segments = re.split(r"[;|]", boundary_str)

    for seg in segments:
        seg = seg.strip()
        matches = re.findall(r"\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)", seg)
        if len(matches) == 2:
            try:
                (x1, y1), (x2, y2) = matches
                line = ((float(x1), float(y1)), (float(x2), float(y2)))
                if line[0] != line[1]:
                    lines.append(line)
            except Exception:
                continue

    # Remove duplicates
    return list(set(tuple(sorted(line)) for line in lines))


def extract_level_prefix(level_name):
    """Extract short prefix (e.g., '00', 'B1', 'LB')."""
    if not isinstance(level_name, str):
        return "Unknown"
    match = re.match(r"^([A-Za-z0-9]{1,2})", level_name.strip())
    return match.group(1) if match else level_name[:2]


def generate_foundation_json(folder_path):
    """
    Process foundation_data.csv:
    - Groups geometries by level prefix
    - Merges touching polygons
    - Exports PNG plots + centroid JSON file
    """
    csv_file = os.path.join(folder_path, "Revit_Data", "foundation_data.csv")
    output_folder = os.path.join(folder_path, "foundation_plots_cleaned_data")
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"❌ CSV file not found: {csv_file}")

    df = pd.read_csv(csv_file, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    if "Boundary Lines (m)" not in df.columns:
        raise ValueError("❌ Column 'Boundary Lines (m)' not found in CSV.")

    df["LevelGroup"] = df["Level"].apply(extract_level_prefix)
    centroid_data = []

    for group_name, group in df.groupby("LevelGroup"):
        fig, ax = plt.subplots(figsize=(8, 8))
        plotted = False

        for _, row in group.iterrows():
            boundary_lines = parse_boundary_string(row["Boundary Lines (m)"])
            if not boundary_lines:
                continue

            shapely_lines = [LineString(line) for line in boundary_lines]
            merged = unary_union(MultiLineString(shapely_lines))
            polygons = list(polygonize(merged))

            # Merge touching or overlapping polygons
            if polygons:
                polygons = [unary_union(polygons)]

            if polygons:
                for poly in polygons:
                    polys = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]

                    for p in polys:
                        area = p.area
                        if area > 20.0:  # skip large polygons
                            continue

                        x, y = p.exterior.xy
                        ax.fill(x, y, alpha=0.6, facecolor="skyblue", edgecolor="black", linewidth=1.2)
                        plotted = True

                        cx, cy = p.centroid.x, p.centroid.y
                        if 0.5 < area < 5.5:
                            centroid_data.append({
                                "Level": group_name,
                                "X": round(cx, 3),
                                "Y": round(cy, 3)
                            })
                            ax.plot(cx, cy, "ro", markersize=5)

        ax.set_title(f"Foundation Boundaries – {group_name}", fontsize=12)
        ax.set_aspect("equal", "box")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.grid(True, linestyle=":", linewidth=0.4)
        plt.tight_layout()

        output_path = os.path.join(output_folder, f"{group_name}.png")
        if plotted:
            plt.savefig(output_path, dpi=300)
            print(f"✅ Saved plot for: {group_name} → {output_path}")
        else:
            print(f"⚠️ No valid geometry found for group: {group_name}")

        plt.close(fig)

    # Save centroids
    json_path = os.path.join(output_folder, "foundation_points.json")
    with open(json_path, "w") as f:
        json.dump({"Foundations": centroid_data}, f, indent=2)

    print(f"\n✅ All grouped plots and centroid data saved in:\n{output_folder}")
    print(f"🟢 JSON saved to: {json_path}")

    return json_path, output_folder
