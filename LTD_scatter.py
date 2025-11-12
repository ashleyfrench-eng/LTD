import pandas as pd
import matplotlib.pyplot as plt
import os
import re

# -------------------------------
# Extract points helper
# -------------------------------
def extract_points(boundary_str):
    """Extract all (x, y) pairs from a text string like '(-18.244,51.189)-(-22.734,51.189); ...'"""
    points = []
    if not isinstance(boundary_str, str):
        return points

    boundary_str = boundary_str.replace("\n", " ").replace("\r", " ").strip()
    matches = re.findall(r"\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)", boundary_str)

    for m in matches:
        try:
            x, y = float(m[0]), float(m[1])
            points.append((x, y))
        except Exception:
            continue

    return points


# -------------------------------
# Main function to run scatter plots
# -------------------------------
def generate_scatter_plots(folder_path):
    """Generates scatter plots for each level and saves them in a subfolder."""
    csv_file = os.path.join(folder_path, "Revit_Data", "foundation_data.csv")
    output_folder = os.path.join(folder_path, "foundation_scatter")
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"❌ CSV file not found: {csv_file}")

    df = pd.read_csv(csv_file, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    if "Boundary Lines (m)" not in df.columns:
        raise ValueError("❌ Column 'Boundary Lines (m)' not found in CSV.")

    plot_paths = []

    for level_name, group in df.groupby("Level"):
        all_points = []
        for _, row in group.iterrows():
            pts = extract_points(row["Boundary Lines (m)"])
            all_points.extend(pts)

        if not all_points:
            continue

        x_vals = [p[0] for p in all_points]
        y_vals = [p[1] for p in all_points]

        plt.figure(figsize=(8, 8))
        plt.scatter(x_vals, y_vals, s=10, c="blue", alpha=0.7, label=f"{level_name}")
        plt.title(f"Scatter of Boundary Points – {level_name}")
        plt.xlabel("X (m)")
        plt.ylabel("Y (m)")
        plt.axis("equal")
        plt.grid(True, linestyle=":", linewidth=0.4)
        plt.legend()
        plt.tight_layout()

        output_path = os.path.join(output_folder, f"{level_name.replace(' ', '_')}_scatter.png")
        plt.savefig(output_path, dpi=300)
        plt.close()

        plot_paths.append(output_path)

    return plot_paths
