import geopandas as gpd
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from shapely.geometry import mapping
from django.shortcuts import render
from sqlalchemy import create_engine
import os

def map_view(request):
    DB_USER = os.getenv("DATABASE_USER", "hospital_user")
    DB_PASS = os.getenv("DATABASE_PASSWORD", "hospital_pass")
    DB_HOST = os.getenv("DATABASE_HOST", "hospital_db")
    DB_NAME = os.getenv("DATABASE_NAME", "hospital_db")
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}")

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
            a."equip_bed_total"
        FROM adequacy_geo g
        JOIN adequacy_raw a
        ON g."ProvinceKey" = a."ProvinceKey";
    """
    gdf = gpd.read_postgis(query, engine, geom_col="geometry")
    gdf = gdf.loc[:, ~gdf.columns.duplicated()]

    # Simplify Index
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
    gdf["staff_norm"] = gdf["staff_score"] / gdf["staff_score"].max()
    gdf["equip_norm"] = gdf["equipment_score"] / gdf["equipment_score"].max()
    gdf["elderly_norm"] = gdf["elderly_population"] / gdf["elderly_population"].max()
    gdf["AdequacyIndex"] = (
        0.4 * gdf["staff_norm"]
        + 0.3 * gdf["equip_norm"]
        + 0.3 * (1 - gdf["elderly_norm"])
    )

    geojson = json.loads(gdf.to_json())

    # base choropleth
    fig = px.choropleth_mapbox(
        gdf,
        geojson=geojson,
        locations="province_name_th",
        featureidkey="properties.province_name_th",
        color="AdequacyIndex",
        color_continuous_scale="YlOrRd",
        mapbox_style="carto-positron",
        zoom=4.5,
        center={"lat": 13.5, "lon": 100.6},
        opacity=0.8,
        hover_name="province_name_th"
    )

    # overlay trace (empty scatter for highlight)
    fig.add_trace(go.Scattermapbox(
        lat=[], lon=[],
        mode="lines",
        line=dict(color="cyan", width=4),
        name="highlight"
    ))

    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    # export coordinates for each province boundary
# export coordinates for each province boundary
    boundaries = {}
    for _, row in gdf.iterrows():
        geom = row.geometry
        coords = []
        if geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords.extend(list(poly.exterior.coords))
                coords.append([None, None])  # break between polygons
        else:
            coords.extend(list(geom.exterior.coords))
        boundaries[row["province_name_th"]] = coords


    return render(request, "dashboard/map.html", {
        "graph": fig.to_html(full_html=False),
        "boundaries": json.dumps(boundaries)
    })
