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
print("Loading province shapefile ...")

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

print("🗺️ Uploading Readiness_geo ...")
gdf.to_sql(
    "Readiness_geo2",
    engine,
    if_exists="replace",
    index=False,
    dtype={"geometry": Geometry("MULTIPOLYGON", srid=4326)},
)
print("Uploaded Readiness_geo successfully!")

# ---------------------------------------------------------------------
# Load Excel data (Readiness Raw)
# ---------------------------------------------------------------------
print("Loading Readiness.xlsx ...")

raw_path = "../data/raw/Readiness_penalty2.xlsx"
if not os.path.exists(raw_path):
    raise FileNotFoundError(f"File not found: {raw_path}")

raw_df = pd.read_excel(raw_path)

# (Optional) Normalize column names
raw_df.columns = [c.strip().replace(" ", "_") for c in raw_df.columns]
rename_map = {
    # Province
    "จังหวัด": "province_name",

    # --- Surgeons & Surgical Specialties ---
    "doctors_original_ศัลยศาสตร์": "doctors_surgery_general",
    "doctors_original_ประสาทศัลยศาสตร์": "doctors_neurosurgery",
    "doctors_original_ศัลยศาสตร์ตกแต่ง": "doctors_plastic_surgery",
    "doctors_original_ศัลยศาสตร์ทรวงอก": "doctors_thoracic_surgery",
    "doctors_original_ศัลยศาสตร์ยูโรวิทยา": "doctors_urology",
    "doctors_original_กุมารศัลยศาสตร์": "doctors_pediatric_surgery",
    "doctors_original_ศัลยศาสตร์ลำไส้ใหญ่และทวารหนัก": "doctors_colorectal_surgery",
    "doctors_original_ศัลยศาสตร์หลอดเลือด": "doctors_vascular_surgery",
    "doctors_original_ศัลยศาสตร์อุบัติเหตุ": "doctors_trauma_surgery",
    "doctors_original_ศัลยศาสตร์มะเร็งวิทยา": "doctors_oncologic_surgery",
    "doctors_original_ศัลยศาสตร์ตกแต่งและเสริมสร้างใบหน้า": "doctors_craniofacial_surgery",
    "doctors_original_ศัลยศาสตร์ออร์โธปิดิกส์": "doctors_orthopedics",
    "doctors_original_ออร์โธปิดิส์เด็ก": "doctors_pediatric_orthopedics",
    "doctors_original_เนื้องอกกระดูกและระบบเนื้อเยื่อเกี่ยวพัน": "doctors_orthopedic_oncology",

    # --- OB-GYN ---
    "doctors_original_สูติศาสตร์-นรีเวชวิทยา": "doctors_obgyn",
    "doctors_original_เวชศาสตร์มารดาและทารกในครรภ์": "doctors_maternal_fetal_medicine",
    "doctors_original_มะเร็งวิทยานรีเวช": "doctors_gynecologic_oncology",
    "doctors_original_เวชศาสตร์การเจริญพันธุ์": "doctors_reproductive_medicine",
    "doctors_original_เวชศาสตร์เชิงกรานและศัลยศาสตร์ซ่อมเสริม": "doctors_pelvic_reconstructive_surgery",
    "doctors_original_เวชศาสตร์ทางเพศ": "doctors_sexual_medicine",

    # --- Pediatrics ---
    "doctors_original_กุมารเวชศาสตร์": "doctors_pediatrics",
    "doctors_original_กุมารเวชศาสตร์โรคหัวใจ": "doctors_pediatric_cardiology",
    "doctors_original_กุมารเวชศาสตร์โรคระบบการหายใจ": "doctors_pediatric_respiratory",
    "doctors_original_กุมารเวชศาสตร์โรคต่อมไร้ท่อและเมตาบอลิสึม": "doctors_pediatric_endocrine",
    "doctors_original_กุมารเวชศาสตร์พัฒนาการและพฤติกรรม": "doctors_pediatric_development",
    "doctors_original_กุมารเวชศาสตร์โรคไต": "doctors_pediatric_nephrology",
    "doctors_original_กุมารเวชศาสตร์โรคติดเชื้อ": "doctors_pediatric_infectious_disease",
    "doctors_original_กุมารเวชศาสตร์โรคระบบทางเดินอาหารและโรคตับ": "doctors_pediatric_gastro_hepato",
    "doctors_original_กุมารเวชศาสตร์ประสาทวิทยา": "doctors_pediatric_neurology",
    "doctors_original_กุมารเวชศาสตร์โรคภูมิแพ้และภูมิคุ้มกัน": "doctors_pediatric_allergy",
    "doctors_original_กุมารเวชศาสตร์โรคเลือด": "doctors_pediatric_hematology",
    "doctors_original_กุมารเวชศาสตร์ทารกแรกเกิดและปริกำเนิด": "doctors_neonatology",
    "doctors_original_กุมารเวชศาสตร์ตจวิทยา": "doctors_pediatric_dermatology",
    "doctors_original_โลหิตวิทยาและมะเร็งในเด็ก": "doctors_pediatric_hem_onc",
    "doctors_original_กุมารเวชศาสตร์โภชนาการ": "doctors_pediatric_nutrition",
    "doctors_original_กุมารเวชศาสตร์การนอนหลับ": "doctors_pediatric_sleep",

    # --- ENT / Eye / Mental Health ---
    "doctors_original_จักษุวิทยา": "doctors_ophthalmology",
    "doctors_original_โสตศอนาสิกวิทยา": "doctors_ent",
    "doctors_original_โสตศอนาสิกวิทยาการนอนหลับ": "doctors_ent_sleep",
    "doctors_original_จิตเวชศาสตร์": "doctors_psychiatry",
    "doctors_original_จิตเวชศาสตร์เด็กและวัยรุ่น": "doctors_child_psychiatry",
    "doctors_original_จิตเวชศาสตร์นอนหลับ": "doctors_psychiatric_sleep",
    "doctors_original_จิตเวชศาสตร์ผู้สูงอายุ": "doctors_geriatric_psychiatry",
    "doctors_original_จิตเวชศาสตร์การเสพติด": "doctors_addiction_psychiatry",

    # --- Pathology ---
    "doctors_original_พยาธิวิทยาคลินิก": "doctors_clinical_pathology",
    "doctors_original_นิติเวชศาสตร์": "doctors_forensic_medicine",
    "doctors_original_พยาธิวิทยาทั่วไป": "doctors_general_pathology",
    "doctors_original_พยาธิวิทยากายวิภาค": "doctors_anatomical_pathology",
    "doctors_original_พยาธิสูตินรีเวชวิทยา": "doctors_gynecologic_pathology",
    "doctors_original_ตจพยาธิวิทยา": "doctors_dermatopathology",
    "doctors_original_โลหิตพยาธิวิทยา": "doctors_hematopathology",
    "doctors_original_เวชศาสตร์บริการโลหิต": "doctors_transfusion_medicine",

    # --- Radiology ---
    "doctors_original_รังสีวิทยาทั่วไป": "doctors_radiology_general",
    "doctors_original_รังสีวิทยาวินิจฉัย": "doctors_diagnostic_radiology",
    "doctors_original_รังสีรักษาและมะเร็งวิทยา": "doctors_radiation_oncology",
    "doctors_original_เวชศาสตร์นิวคลียร์": "doctors_nuclear_medicine",
    "doctors_original_รังสีรักษาและเวชศาสตร์นิวเคลียร์": "doctors_radiation_nuclear",
    "doctors_original_ภาพวินิจฉัยระบบประสาท": "doctors_neuroimaging",
    "doctors_original_รังสีร่วมรักษาระบบประสาท": "doctors_neuro_intervention",
    "doctors_original_รังสีร่วมรักษาของลำตัว": "doctors_body_intervention",
    "doctors_original_ภาพวินิจฉัยชั้นสูง": "doctors_advanced_imaging",

    # --- Anesthesia ---
    "doctors_original_วิสัญญีวิทยา": "doctors_anesthesiology",
    "doctors_original_วิสัญญีวิทยาเพื่อการผ่าตัดหัวใจหลอดเลือดใหญ่และทรวงอก": "doctors_cardiothoracic_anesthesia",
    "doctors_original_วิสัญญีวิทยาสำหรับผู้ป่วยโรคทางระบบประสาท": "doctors_neuro_anesthesia",
    "doctors_original_การระงับปวด/เวชศาสตร์ความปวด": "doctors_pain_medicine",
    "doctors_original_วิสัญญีวิทยาสำหรับเด็ก": "doctors_pediatric_anesthesia",

    # --- Preventive & Family Medicine ---
    "doctors_original_เวชศาสตร์ครอบครัว": "doctors_family_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงสาธารณสุขศาสตร์": "doctors_public_health",
    "doctors_original_เวชศาสตร์ป้องกันแขนงระบาดวิทยา": "doctors_epidemiology",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์ป้องกันคลินิก": "doctors_clinical_preventive",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์การบิน": "doctors_aerospace_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงอาชีวเวชศาสตร์": "doctors_occupational_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงสุขภาพจิตชุมชน": "doctors_community_mental_health",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์ทางทะเล": "doctors_maritime_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์การเดินทางและท่องเที่ยว": "doctors_travel_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์การจราจร": "doctors_traffic_medicine",
    "doctors_original_เวชศาสตร์ป้องกันแขนงเวชศาสตร์วิถีชีวิต": "doctors_lifestyle_medicine",

    # --- General Medicine Tier ---
    "doctors_original_เวชศาสตร์ฟื้นฟู": "doctors_rehabilitation",
    "doctors_original_เวชปฏิบัติทั่วไป": "doctors_general_practice",

    # --- Basic health workers ---
    "doctors_original_แพทย์": "doctors_physician",
    "doctors_original_ทันตแพทย์": "doctors_dentist",
    "doctors_original_เภสัชกร": "doctors_pharmacist",
    "doctors_original_พยบ.วิชาชีพ": "doctors_professional_nurse",

    "doctors_original_นักรังสี": "doctors_radiologic_technologist",
    "doctors_original_นักกายภาพ": "doctors_physical_therapist",
    "doctors_original_นักเทคนิค": "doctors_technical_staff",
    "doctors_original_นักจิต": "doctors_psychologist",
    "doctors_original_นวก.สาธารณสุข": "doctors_public_health_officer",
    "doctors_original_แพทย์แผนไทย": "doctors_traditional_thai_medicine",

    # Elderly
    "elderly_จำนวนผู้สูงอายุ": "elderly_population",

    # Equipment
    "equipment_เครื่องเอ็กเรย์คอมพิวเตอร์": "equip_ct_scanner",
    "equipment_เครื่องตรวจอวัยวะด้วยสนามแม่เหล็กไฟฟ้า": "equip_mri",
    "equipment_เครื่องสลายนิ่ว": "equip_lithotripter",
    "equipment_เครื่องอัลตราซาวน์": "equip_ultrasound",
    "equipment_เครื่องล้างไต": "equip_dialysis_machine",
    "equipment_รถพยาบาล": "equip_ambulance",
    "equipment_จำนวนเตียง": "equip_beds",

    # Insurance
    "insurance_บัตรทอง": "insurance_uc_scheme",

    # Utilization
    "opd_ipd_จำนวนผู้ป่วยในเฉลี่ยต่อวัน": "ipd_avg_inpatients_per_day",

    # Diseases
    "PUSH_ดัน": "disease_ht",
    "DM_เบาหวาน": "disease_dm",
    "H_หัวใจ": "disease_heart"
}

raw_df.rename(columns=rename_map, inplace=True)
print(raw_df.columns)
# Upload Readiness
print("Uploading Readiness ...")
raw_df.to_sql(
    "Readiness2",
    engine,
    if_exists="replace",
    index=False
)
print("Uploaded Readiness successfully!")
print("All data successfully loaded to PostGIS database.")
