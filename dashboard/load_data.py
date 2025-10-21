import os
import json
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
from geoalchemy2 import Geometry
from shapely.geometry import MultiPolygon, Polygon

# ---------------------------------------------------------------------
# Database Connection
# ---------------------------------------------------------------------
DB_USER = os.getenv("DATABASE_USER", "hospital_user")
DB_PASS = os.getenv("DATABASE_PASSWORD", "hospital_pass")
DB_HOST = os.getenv("DATABASE_HOST", "hospital_db")
DB_NAME = os.getenv("DATABASE_NAME", "hospital_db")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
)

# ---------------------------------------------------------------------
# Load shapefile (Province Geometry)
# ---------------------------------------------------------------------
print("📦 Loading province shapefile ...")

url = "https://github.com/prasertcbs/thailand_gis/raw/main/province/province_simplify.zip"
gdf = gpd.read_file(url)

# Load province_dict.json
with open("../data/raw/province_dict.json", "r", encoding="utf-8") as f:
    prov_map = json.load(f)

gdf["ProvinceKey"] = gdf["ADM1_TH"].map(prov_map)

# Check CRS (Coordinate Reference System)
if gdf.crs is None or gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

# Convert Polygon → MultiPolygon and Geometry → WKB hex
def convert_geom(geom):
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    return geom.wkb_hex if geom else None

gdf["geometry"] = gdf["geometry"].apply(convert_geom)

# Upload to PostGIS
print("🗺️ Uploading adequacy_geo ...")
gdf.to_sql(
    "adequacy_geo",
    engine,
    if_exists="replace",
    index=False,
    dtype={"geometry": Geometry("MULTIPOLYGON", srid=4326)},
)
print("✅ Uploaded adequacy_geo successfully!")

# ---------------------------------------------------------------------
# Load Excel data (Adequacy Raw)
# ---------------------------------------------------------------------
print("📊 Loading adequacy_raw.xlsx ...")

raw_path = "../data/raw/Adequecy_data.xlsx"
if not os.path.exists(raw_path):
    raise FileNotFoundError(f"File not found: {raw_path}")

raw_df = pd.read_excel(raw_path)

# (Optional) Normalize column names
raw_df.columns = [c.strip().replace(" ", "_") for c in raw_df.columns]
rename_map = {
    # 👩‍⚕️ Doctors / Staff
    "doctors_แพทย์": "doctors_physician",
    "doctors_ทันตแพทย์": "doctors_dentist",
    "doctors_เภสัชกร": "doctors_pharmacist",
    "doctors_พยบ.วิชาชีพ": "doctors_registered_nurse",
    "doctors_บุคลากรเฉพาะทางรวม": "doctors_specialist_total",

    # 👵 Elderly
    "elderly_จำนวนผู้สูงอายุ": "elderly_population",

    # ⚙️ Equipment
    "equipment_เครื่องเอ็กเรย์คอมพิวเตอร์": "equip_ct_scanner",
    "equipment_เครื่องตรวจอวัยวะด้วยสนามแม่เหล็กไฟฟ้า": "equip_mri",
    "equipment_เครื่องสลายนิ่ว": "equip_lithotripter",
    "equipment_เครื่องอัลตราซาวน์": "equip_ultrasound",
    "equipment_เครื่องล้างไต": "equip_dialysis_machine",
    "equipment_รถพยาบาล": "equip_ambulance",
    "equipment_จำนวนเตียง": "equip_bed_total",

    # 💳 Insurance
    "insurance_บัตรทอง": "insurance_uc_scheme",
    "insurance_จำนวนโรงพยาบาล": "insurance_hospital_count",

    # 🏥 Utilization
    "opd_ipd_จำนวนผู้ป่วยนอกเฉลี่ยต่อวัน": "opd_avg_outpatients_per_day",
    "opd_ipd_จำนวนผู้ป่วยในเฉลี่ยต่อวัน": "ipd_avg_inpatients_per_day",
}

raw_df.rename(columns=rename_map, inplace=True)
print(raw_df.columns)
# Upload adequacy_raw
print("🧮 Uploading adequacy_raw ...")
raw_df.to_sql(
    "adequacy_raw",
    engine,
    if_exists="replace",
    index=False
)
print("✅ Uploaded adequacy_raw successfully!")

print("🎉 All data successfully loaded to PostGIS database.")
