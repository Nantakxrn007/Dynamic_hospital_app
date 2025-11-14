import os
import json
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from django.shortcuts import render
from sqlalchemy import create_engine

def map_view(request):
    # -----------------------------
    # 1) Connect DB
    # -----------------------------
    DB_USER = os.getenv("DATABASE_USER", "hospital_user")
    DB_PASS = os.getenv("DATABASE_PASSWORD", "hospital_pass")
    DB_HOST = os.getenv("DATABASE_HOST", "hospital_db")
    DB_NAME = os.getenv("DATABASE_NAME", "hospital_db")
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}")

    # -----------------------------
    # 2) Query geometry + raw
    # -----------------------------
    query = """
        SELECT 
            g."ProvinceKey",
            g."ADM1_TH" AS province_name_th,
            g.geometry,
            a."doctors_physician",
            a."doctors_dentist",
            a."doctors_pharmacist",
            a."doctors_registered_nurse",
            a."doctors_specialist_total",
            a."elderly_population",
            a."equip_ct_scanner",
            a."equip_mri",
            a."equip_lithotripter",
            a."equip_ultrasound",
            a."equip_dialysis_machine",
            a."equip_ambulance",
            a."equip_bed_total",
            a."insurance_uc_scheme",
            a."insurance_hospital_count",
            a."opd_avg_outpatients_per_day",
            a."ipd_avg_inpatients_per_day"
        FROM adequacy_geo g
        JOIN adequacy_raw a
        ON g."ProvinceKey" = a."ProvinceKey";
    """
    gdf = gpd.read_postgis(query, engine, geom_col="geometry")
    gdf = gdf.loc[:, ~gdf.columns.duplicated()]

    # -----------------------------
    # 3) Derive features + normalize (baseline)
    # -----------------------------
    gdf["staff_score"] = (
        gdf["doctors_physician"]
        + gdf["doctors_dentist"]
        + gdf["doctors_pharmacist"]
        + gdf["doctors_registered_nurse"]
        + gdf["doctors_specialist_total"]
    )
    gdf["equipment_score"] = (
        gdf["equip_ct_scanner"]
        + gdf["equip_mri"]
        + gdf["equip_lithotripter"]
        + gdf["equip_ultrasound"]
        + gdf["equip_dialysis_machine"]
        + gdf["equip_ambulance"]
        + gdf["equip_bed_total"]
    )
    gdf["insurance_score"] = (
        gdf["insurance_uc_scheme"] + gdf["insurance_hospital_count"]
    )
    gdf["service_load"] = (
        gdf["ipd_avg_inpatients_per_day"] + gdf["opd_avg_outpatients_per_day"]
    ) / 2.0

    def safe_norm(s):
        mx = float(s.max()) if float(s.max()) != 0 else 1.0
        return s / mx, mx

    staff_norm, staff_max = safe_norm(gdf["staff_score"])
    equip_norm, equip_max = safe_norm(gdf["equipment_score"])
    ins_norm, ins_max = safe_norm(gdf["insurance_score"])
    elderly_norm, elderly_max = safe_norm(gdf["elderly_population"])
    svc_norm, svc_max = safe_norm(gdf["service_load"])

    gdf["X1"] = staff_norm
    gdf["X2"] = equip_norm
    gdf["X3"] = ins_norm
    gdf["X4"] = 1 - svc_norm
    gdf["Xelderly_inv"] = 1 - elderly_norm

    w1, w2, w3, w4 = 0.40, 0.30, 0.15, 0.15
    gdf["A_i"] = w1 * gdf["X1"] + w2 * gdf["X2"] + w3 * gdf["X3"] + w4 * gdf["X4"]

    # -----------------------------
    # 4) KPI (Zone A scorecards)
    # -----------------------------
    total_elderly = int(gdf["elderly_population"].sum())
    mean_Ai = float(gdf["A_i"].mean())
    top10 = gdf[["province_name_th", "A_i"]].sort_values("A_i", ascending=False).head(10)

    # -----------------------------
    # 5) Base map (choropleth) + highlight layer
    # -----------------------------
    geojson = json.loads(gdf.to_json())

    fig_map = px.choropleth_mapbox(
        gdf,
        geojson=geojson,
        locations="province_name_th",
        featureidkey="properties.province_name_th",
        color="A_i",
        color_continuous_scale="RdYlGn",
        range_color=(0, 1),
        mapbox_style="carto-positron",
        zoom=4.5,
        center={"lat": 13.5, "lon": 100.6},
        opacity=0.8,
        hover_name="province_name_th",
        hover_data={
            "A_i": ':.3f',
            "X1": ':.3f',
            "X2": ':.3f',
            "X3": ':.3f',
            "Xelderly_inv": ':.3f'
        },
    )
    fig_map.data[0].name = "base"
    fig_map.add_trace(go.Scattermapbox(
        lat=[], lon=[],
        mode="lines",
        line=dict(color="black", width=3),
        hoverinfo="skip",
        name="highlight"
    ))
    fig_map.update_layout(
        margin=dict(r=0, l=0, t=0, b=0),
        height=500,
        hovermode="closest"
    )

    # -----------------------------
    # 6) Ranking bar fig
    # -----------------------------
    fig_bar = px.bar(
        top10, x="A_i", y="province_name_th",
        orientation="h",
        title="Ranking province A_i TOP 10",
        range_x=[0, 1]
    )
    fig_bar.update_layout(
        margin=dict(r=10, l=150, t=40, b=10),  # เพิ่ม l เพื่อให้ชื่อจังหวัดแสดงเต็ม
        height=380,
        yaxis=dict(
            automargin=True,
            tickfont=dict(size=12),
            title=""
        )
    )

    # -----------------------------
    # 7) Data for JS
    # -----------------------------
    province_data = {}
    for _, r in gdf.iterrows():
        province_data[r["province_name_th"]] = {
            "doctors_physician": int(r["doctors_physician"]),
            "doctors_dentist": int(r["doctors_dentist"]),
            "doctors_pharmacist": int(r["doctors_pharmacist"]),
            "doctors_registered_nurse": int(r["doctors_registered_nurse"]),
            "doctors_specialist_total": int(r["doctors_specialist_total"]),
            "equip_ct_scanner": int(r["equip_ct_scanner"]),
            "equip_mri": int(r["equip_mri"]),
            "equip_lithotripter": int(r["equip_lithotripter"]),
            "equip_ultrasound": int(r["equip_ultrasound"]),
            "equip_dialysis_machine": int(r["equip_dialysis_machine"]),
            "equip_ambulance": int(r["equip_ambulance"]),
            "equip_bed_total": int(r["equip_bed_total"]),
            "insurance_uc_scheme": float(r["insurance_uc_scheme"]),
            "insurance_hospital_count": int(r["insurance_hospital_count"]),
            "opd_avg_outpatients_per_day": float(r["opd_avg_outpatients_per_day"]),
            "ipd_avg_inpatients_per_day": float(r["ipd_avg_inpatients_per_day"]),
            "elderly_population": int(r["elderly_population"]),
            "A_i": round(float(r["A_i"]), 3),
            "baseline_A_i": round(float(r["A_i"]), 3)
        }

    boundaries = {}
    for _, row in gdf.iterrows():
        geom = row.geometry
        coords = []
        if geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords.extend(list(poly.exterior.coords))
                coords.append([None, None])
        else:
            coords.extend(list(geom.exterior.coords))
        boundaries[row["province_name_th"]] = coords

    norm_max = {
        "staff_max": staff_max,
        "equip_max": equip_max,
        "ins_max": ins_max,
        "svc_max": svc_max
    }

    context = {
        "total_elderly": f"{total_elderly:,}",
        "mean_Ai": f"{mean_Ai:.2f}",
        "map_html": fig_map.to_html(full_html=False, include_plotlyjs=False),
        "bar_html": fig_bar.to_html(full_html=False, include_plotlyjs=False),
        "boundaries": json.dumps(boundaries),
        "province_data": json.dumps(province_data),
        "norm_max": json.dumps(norm_max),
        "province_order": json.dumps(list(gdf["province_name_th"].values)),
    }
    return render(request, "dashboard/map.html", context)