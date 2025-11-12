import json
import os
import math
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def group_columns_by_alignment(voronoi_json_path, match_radius=0.5):
    with open(voronoi_json_path, "r") as f:
        data = json.load(f)

    def floor_sort_key(level):
        if level.upper().startswith("RF"):
            return 999
        if level.upper().startswith("LB"):
            return -1
        try:
            return int(level)
        except:
            return 0

    ordered_floors = sorted(data.keys(), key=floor_sort_key, reverse=True)

    # --- Collect per-floor data ---
    floors_data = {
        floor: [
            {
                "X": c["X"],
                "Y": c["Y"],
                "Area": c.get("Area", 0),
                "WeightedArea": c.get("WeightedArea", 0),
                "Type": c.get("Type", "Unknown")
            }
            for c in data[floor].get("columns", [])
        ]
        for floor in ordered_floors
    }

    column_groups = []
    column_id = 1

    # --- Group by proximity ---
    for floor in ordered_floors:
        for col in floors_data[floor]:
            x, y, area, w_area, ctype = col["X"], col["Y"], col["Area"], col["WeightedArea"], col["Type"]

            matched_group = None
            for group in column_groups:
                _, last_x, last_y, *_ = group["points"][-1]
                if math.dist((x, y), (last_x, last_y)) <= match_radius:
                    matched_group = group
                    break

            if matched_group:
                matched_group["points"].append((floor, x, y, area, w_area, ctype))
            else:
                column_groups.append({
                    "id": f"C{column_id:03d}",
                    "points": [(floor, x, y, area, w_area, ctype)]
                })
                column_id += 1

    # --- Build results ---
    results = []
    for group in column_groups:
        floors = [p[0] for p in group["points"]]
        weighted_areas = [p[4] for p in group["points"]]
        total_sls = round(sum(weighted_areas), 2)

        # Pair weighted areas
        weighted_pairs = [weighted_areas[i:i+2] for i in range(0, len(weighted_areas), 2)]
        perm_loads = [pair[0] for pair in weighted_pairs if len(pair) > 0]
        imposed_loads = [pair[1] for pair in weighted_pairs if len(pair) > 1]
        total_perm = round(sum(perm_loads), 2)
        total_imposed = round(sum(imposed_loads), 2)

        unique_floors = list(dict.fromkeys(floors))

        for i, floor in enumerate(unique_floors):
            w1 = weighted_pairs[i][0] if i < len(weighted_pairs) and len(weighted_pairs[i]) > 0 else None
            w2 = weighted_pairs[i][1] if i < len(weighted_pairs) and len(weighted_pairs[i]) > 1 else None

            ftype = None
            for p in group["points"]:
                if p[0] == floor:
                    ftype = p[5]
                    break
            if ftype is None:
                ftype = "Unknown"


            results.append({
                "Column ID": group["id"],
                "X": round(group["points"][0][1], 2),
                "Y": round(group["points"][0][2], 2),
                "Floor": floor,
                "Type": ftype,
                "Area m²": round(next(p[3] for p in group["points"] if p[0] == floor), 2),
                "Permanent Load (kN)": round(w1, 2) if w1 else None,
                "Imposed Load (kN)": round(w2, 2) if w2 else None,
                "Total Permanent Load (kN)": total_perm if i == 0 else "",
                "Total Imposed Load (kN)": total_imposed if i == 0 else "",
                "Total SLS Load (kN)": total_sls if i == 0 else ""
            })
    df = pd.DataFrame(results)
    return df





def plot_columns_by_floor(floor_df):
    if floor_df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data for selected floor")
        return fig

    # 🟩 Create a text label column — only show ID if it's a Column
    floor_df["Label"] = floor_df.apply(
        lambda r: r["Column ID"] if r["Type"] in ["Column", "Foundation"] else "",
        axis=1
    )

    # 🟦 Create scatter plot
    fig = px.scatter(
        floor_df,
        x="X",
        y="Y",
        color="Type",
        text="Label",
        title=f"Column Layout — Floor {floor_df['Floor'].iloc[0]}",
        labels={"X": "X (m)", "Y": "Y (m)"},
        color_discrete_sequence=px.colors.qualitative.Safe,
        hover_data={
            "X": False,  # 🚫 hide X
            "Y": False,  # 🚫 hide Y
            "Type": False,
            "Label": False,  # 🚫 hide Type
            "Area m²": True,  # ✅ show Area
            "Permanent Load (kN)": True,  # ✅ show Permanent Load
            "Imposed Load (kN)": True,  # ✅ show Imposed Load
        },
    )

    # 🎨 Styling
    fig.update_traces(
        textposition='top center',
        marker=dict(size=8, line=dict(width=1, color='black'))
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    fig.update_layout(template="plotly_white", legend_title_text="Type", height=600)

    return fig


