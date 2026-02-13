import os
import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import json
# ---------------------------------------------------------
# 1. DATABASE CONNECTION
# ---------------------------------------------------------
DB_USER = os.getenv("DATABASE_USER", "hospital_user")
DB_PASS = os.getenv("DATABASE_PASSWORD", "hospital_pass")
DB_HOST = os.getenv("DATABASE_HOST", "hospital_db")
DB_NAME = os.getenv("DATABASE_NAME", "hospital_db")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}")

# ---------------------------------------------------------
# 2. QUERY DATA
# ---------------------------------------------------------
query = """
    SELECT 
        g."ProvinceKey",
        g."ADM1_TH" AS province_name_th,
        g.geometry,
        a.*
    FROM "Readiness_geo2" g
    JOIN "Readiness2" a
    ON g."ProvinceKey" = a."ProvinceKey";
"""
gdf = gpd.read_postgis(query, engine, geom_col="geometry")
gdf = gdf.loc[:, ~gdf.columns.duplicated()]

# ---------------------------------------------------------
# 3. CONFIG & MAPPING
# ---------------------------------------------------------
doctor_cols = [c for c in gdf.columns if c.startswith('doctors_')]
equip_cols = [c for c in gdf.columns if c.startswith('equip_')]

THAI_COLUMN_MAP = {
    # --- Surgeons & Surgical Specialties ---
    "doctors_surgery_general": "ศัลยศาสตร์ทั่วไป",
    "doctors_neurosurgery": "ประสาทศัลยศาสตร์",
    "doctors_plastic_surgery": "ศัลยศาสตร์ตกแต่ง",
    "doctors_thoracic_surgery": "ศัลยศาสตร์ทรวงอก",
    "doctors_urology": "ศัลยศาสตร์ยูโรวิทยา",
    "doctors_pediatric_surgery": "กุมารศัลยศาสตร์",
    "doctors_colorectal_surgery": "ศัลยศาสตร์ลำไส้ใหญ่และทวารหนัก",
    "doctors_vascular_surgery": "ศัลยศาสตร์หลอดเลือด",
    "doctors_trauma_surgery": "ศัลยศาสตร์อุบัติเหตุ",
    "doctors_oncologic_surgery": "ศัลยศาสตร์มะเร็งวิทยา",
    "doctors_craniofacial_surgery": "ศัลยศาสตร์ตกแต่งและเสริมสร้างใบหน้า",
    "doctors_orthopedics": "ศัลยศาสตร์ออร์โธปิดิกส์",
    "doctors_pediatric_orthopedics": "ออร์โธปิดิกส์เด็ก",
    "doctors_orthopedic_oncology": "เนื้องอกกระดูกและระบบเนื้อเยื่อเกี่ยวพัน",

    # --- OB-GYN ---
    "doctors_obgyn": "สูติศาสตร์-นรีเวชวิทยา",
    "doctors_maternal_fetal_medicine": "เวชศาสตร์มารดาและทารกในครรภ์",
    "doctors_gynecologic_oncology": "มะเร็งวิทยานรีเวช",
    "doctors_reproductive_medicine": "เวชศาสตร์การเจริญพันธุ์",
    "doctors_pelvic_reconstructive_surgery": "เวชศาสตร์เชิงกรานและศัลยศาสตร์ซ่อมเสริม",
    "doctors_sexual_medicine": "เวชศาสตร์ทางเพศ",

    # --- Pediatrics ---
    "doctors_pediatrics": "กุมารเวชศาสตร์",
    "doctors_pediatric_cardiology": "กุมารเวชศาสตร์โรคหัวใจ",
    "doctors_pediatric_respiratory": "กุมารเวชศาสตร์โรคระบบการหายใจ",
    "doctors_pediatric_endocrine": "กุมารเวชศาสตร์โรคต่อมไร้ท่อและเมตาบอลิสึม",
    "doctors_pediatric_development": "กุมารเวชศาสตร์พัฒนาการและพฤติกรรม",
    "doctors_pediatric_nephrology": "กุมารเวชศาสตร์โรคไต",
    "doctors_pediatric_infectious_disease": "กุมารเวชศาสตร์โรคติดเชื้อ",
    "doctors_pediatric_gastro_hepato": "กุมารเวชศาสตร์โรคระบบทางเดินอาหารและโรคตับ",
    "doctors_pediatric_neurology": "กุมารเวชศาสตร์ประสาทวิทยา",
    "doctors_pediatric_allergy": "กุมารเวชศาสตร์โรคภูมิแพ้และภูมิคุ้มกัน",
    "doctors_pediatric_hematology": "กุมารเวชศาสตร์โรคเลือด",
    "doctors_neonatology": "กุมารเวชศาสตร์ทารกแรกเกิดและปริกำเนิด",
    "doctors_pediatric_dermatology": "กุมารเวชศาสตร์ตจวิทยา",
    "doctors_pediatric_hem_onc": "โลหิตวิทยาและมะเร็งในเด็ก",
    "doctors_pediatric_nutrition": "กุมารเวชศาสตร์โภชนาการ",
    "doctors_pediatric_sleep": "กุมารเวชศาสตร์การนอนหลับ",

    # --- ENT / Eye / Mental Health ---
    "doctors_ophthalmology": "จักษุวิทยา",
    "doctors_ent": "โสตศอนาสิกวิทยา",
    "doctors_ent_sleep": "โสตศอนาสิกวิทยาการนอนหลับ",
    "doctors_psychiatry": "จิตเวชศาสตร์",
    "doctors_child_psychiatry": "จิตเวชศาสตร์เด็กและวัยรุ่น",
    "doctors_psychiatric_sleep": "จิตเวชศาสตร์นอนหลับ",
    "doctors_geriatric_psychiatry": "จิตเวชศาสตร์ผู้สูงอายุ",
    "doctors_addiction_psychiatry": "จิตเวชศาสตร์การเสพติด",

    # --- Pathology ---
    "doctors_clinical_pathology": "พยาธิวิทยาคลินิก",
    "doctors_forensic_medicine": "นิติเวชศาสตร์",
    "doctors_general_pathology": "พยาธิวิทยาทั่วไป",
    "doctors_anatomical_pathology": "พยาธิวิทยากายวิภาค",
    "doctors_gynecologic_pathology": "พยาธิสูตินรีเวชวิทยา",
    "doctors_dermatopathology": "ตจพยาธิวิทยา",
    "doctors_hematopathology": "โลหิตพยาธิวิทยา",
    "doctors_transfusion_medicine": "เวชศาสตร์บริการโลหิต",

    # --- Radiology ---
    "doctors_radiology_general": "รังสีวิทยาทั่วไป",
    "doctors_diagnostic_radiology": "รังสีวิทยาวินิจฉัย",
    "doctors_radiation_oncology": "รังสีรักษาและมะเร็งวิทยา",
    "doctors_nuclear_medicine": "เวชศาสตร์นิวเคลียร์",
    "doctors_radiation_nuclear": "รังสีรักษาและเวชศาสตร์นิวเคลียร์",
    "doctors_neuroimaging": "ภาพวินิจฉัยระบบประสาท",
    "doctors_neuro_intervention": "รังสีร่วมรักษาระบบประสาท",
    "doctors_body_intervention": "รังสีร่วมรักษาของลำตัว",
    "doctors_advanced_imaging": "ภาพวินิจฉัยชั้นสูง",

    # --- Anesthesia ---
    "doctors_anesthesiology": "วิสัญญีวิทยา",
    "doctors_cardiothoracic_anesthesia": "วิสัญญีวิทยาผ่าตัดหัวใจหลอดเลือดและทรวงอก",
    "doctors_neuro_anesthesia": "วิสัญญีวิทยาผู้ป่วยโรคทางระบบประสาท",
    "doctors_pain_medicine": "การระงับปวด/เวชศาสตร์ความปวด",
    "doctors_pediatric_anesthesia": "วิสัญญีวิทยาสำหรับเด็ก",

    # --- Preventive & Family Medicine ---
    "doctors_family_medicine": "เวชศาสตร์ครอบครัว",
    "doctors_public_health": "เวชศาสตร์ป้องกันแขนงสาธารณสุขศาสตร์",
    "doctors_epidemiology": "เวชศาสตร์ป้องกันแขนงระบาดวิทยา",
    "doctors_clinical_preventive": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์ป้องกันคลินิก",
    "doctors_aerospace_medicine": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์การบิน",
    "doctors_occupational_medicine": "เวชศาสตร์ป้องกันแขนงอาชีวเวชศาสตร์",
    "doctors_community_mental_health": "เวชศาสตร์ป้องกันแขนงสุขภาพจิตชุมชน",
    "doctors_maritime_medicine": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์ทางทะเล",
    "doctors_travel_medicine": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์การเดินทางและท่องเที่ยว",
    "doctors_traffic_medicine": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์การจราจร",
    "doctors_lifestyle_medicine": "เวชศาสตร์ป้องกันแขนงเวชศาสตร์วิถีชีวิต",

    # --- General Medicine Tier ---
    "doctors_rehabilitation": "เวชศาสตร์ฟื้นฟู",
    "doctors_general_practice": "เวชปฏิบัติทั่วไป",

    # --- Basic health workers ---
    "doctors_physician": "แพทย์ (รวม)",
    "doctors_dentist": "ทันตแพทย์",
    "doctors_pharmacist": "เภสัชกร",
    "doctors_professional_nurse": "พยาบาลวิชาชีพ",
    "doctors_radiologic_technologist": "นักรังสีการแพทย์",
    "doctors_physical_therapist": "นักกายภาพบำบัด",
    "doctors_technical_staff": "นักเทคนิคการแพทย์",
    "doctors_psychologist": "นักจิตวิทยา",
    "doctors_public_health_officer": "นักวิชาการสาธารณสุข",
    "doctors_traditional_thai_medicine": "แพทย์แผนไทย",
    
    # --- Equipment ---
    "equip_ct_scanner": "เครื่อง CT Scan",
    "equip_mri": "เครื่อง MRI",
    "equip_ultrasound": "เครื่อง Ultrasound",
    "equip_ventilator": "เครื่องช่วยหายใจ",
    "equip_dialysis_machine": "เครื่องฟอกไต",
    "equip_beds": "เตียงผู้ป่วยรวม",
    "equip_ambulance": "รถพยาบาล",
    "equip_lithotripter": "เครื่องสลายนิ่ว",
    
    # --- Others ---
    "disease_dm": "ผู้ป่วยโรคเบาหวาน",
    "disease_heart": "ผู้ป่วยโรคหัวใจ",
    "disease_ht": "ผู้ป่วยโรคความดัน",
    "elderly_population": "จำนวนผู้สูงอายุ",
    "insurance_uc_scheme": "สิทธิบัตรทอง (UC)",
    "ipd_avg_inpatients_per_day": "ผู้ป่วยในเฉลี่ย/วัน (IPD)"
}

disease_mapping = {
        'disease_dm': { 
            'burden': 'disease_dm', 
            'supply': [
                'doctors_surgery_general',      # ศัลยศาสตร์
                'doctors_ophthalmology',        # จักษุวิทยา
                'doctors_ent',                  # โสตศอนาสิกวิทยา
                'doctors_family_medicine',      # เวชศาสตร์ครอบครัว
                'doctors_public_health',        # เวชศาสตร์ป้องกันแขนงสาธารณสุขศาสตร์
                'doctors_dentist',              # ทันตแพทย์
                'doctors_urology',              # ศัลยศาสตร์ยูโรวิทยา
                'equip_ambulance',              # equipment_รถพยาบาล
                'equip_beds',              # equipment_จำนวนเตียง
                'equip_ct_scanner',             # equipment_เครื่องเอ็กเรย์คอมพิวเตอร์
                'equip_mri',                    # equipment_เครื่องตรวจอวัยวะด้วยสนามแม่เหล็กไฟฟ้า
                'equip_ultrasound',             # equipment_เครื่องอัลตราซาวน์
                'equip_dialysis_machine'        # equipment_เครื่องล้างไต
            ]
        },
        'disease_heart': { 
            'burden': 'disease_heart', 
            'supply': [
                'doctors_thoracic_surgery',             # ศัลยศาสตร์ทรวงอก
                'doctors_vascular_surgery',             # ศัลยศาสตร์หลอดเลือด
                'doctors_cardiothoracic_anesthesia',    # วิสัญญีวิทยาเพื่อการผ่าตัดหัวใจ...
                'doctors_rehabilitation',               # เวชศาสตร์ฟื้นฟู
                'doctors_diagnostic_radiology',         # รังสีวิทยาวินิจฉัย
                'doctors_advanced_imaging',             # ภาพวินิจฉัยชั้นสูง
                'equip_ambulance',                      # equipment_รถพยาบาล
                'equip_beds',                      # equipment_จำนวนเตียง
                'equip_ct_scanner',                     # equipment_เครื่องเอ็กเรย์คอมพิวเตอร์
                'equip_mri',                            # equipment_เครื่องตรวจอวัยวะด้วยสนามแม่เหล็กไฟฟ้า
                'equip_ultrasound'                      # equipment_เครื่องอัลตราซาวน์
            ]
        },
        'disease_ht': { 
            'burden': 'disease_ht',
            'supply': [
                'doctors_surgery_general',      # ศัลยศาสตร์
                'doctors_vascular_surgery',     # ศัลยศาสตร์หลอดเลือด
                'doctors_family_medicine',      # เวชศาสตร์ครอบครัว
                'doctors_public_health',        # เวชศาสตร์ป้องกันแขนงสาธารณสุขศาสตร์
                'doctors_ophthalmology',        # จักษุวิทยา
                'equip_ambulance',              # equipment_รถพยาบาล
                'equip_beds',              # equipment_จำนวนเตียง
                'equip_ct_scanner',             # equipment_เครื่องเอ็กเรย์คอมพิวเตอร์
                'equip_mri',                    # equipment_เครื่องตรวจอวัยวะด้วยสนามแม่เหล็กไฟฟ้า
                'equip_ultrasound'              # equipment_เครื่องอัลตราซาวน์
            ]
        }
    }

# ---------------------------------------------------------
# 4. CALCULATION
# ---------------------------------------------------------
elderly_pop = gdf['elderly_population'].replace(0, 1)

gdf['X1_raw_per_capita'] = gdf[doctor_cols].sum(axis=1) / elderly_pop
gdf['X2_raw_per_capita'] = gdf['insurance_uc_scheme'] / elderly_pop
gdf['X3_raw_per_capita'] = gdf[equip_cols].sum(axis=1) / elderly_pop
gdf['X4_raw_per_capita'] = gdf['ipd_avg_inpatients_per_day'] / elderly_pop

def calculate_z_score_std(series): 
    if series.std() == 0: return series * 0
    return (series - series.mean()) / series.std()

gdf['z_X1'] = calculate_z_score_std(gdf['X1_raw_per_capita'])
gdf['z_X2'] = calculate_z_score_std(gdf['X2_raw_per_capita'])
gdf['z_X3'] = calculate_z_score_std(gdf['X3_raw_per_capita'])

x4_mean = gdf['X4_raw_per_capita'].mean()
x4_std = gdf['X4_raw_per_capita'].std()
gdf['z_X4'] = 0 if x4_std == 0 else (x4_mean - gdf['X4_raw_per_capita']) / x4_std

w1, w2, w3, w4 = 0.4, 0.3, 0.2, 0.1
gdf['R_general'] = (w1 * gdf['z_X1']) + (w2 * gdf['z_X2']) + (w3 * gdf['z_X3']) + (w4 * gdf['z_X4'])

def min_max_norm(series):
    if series.max() == series.min(): return series * 0
    return (series - series.min()) / (series.max() - series.min())

total_gap_list = []
for disease, mapping in disease_mapping.items():
    burden_norm = min_max_norm(gdf[mapping['burden']]) if mapping['burden'] in gdf.columns else gdf.index * 0
    supply_norms = []
    for s_col in mapping['supply']:
        supply_norms.append(min_max_norm(gdf[s_col]) if s_col in gdf.columns else gdf.index * 0)
    
    supply_mean_norm = pd.concat(supply_norms, axis=1).mean(axis=1) if supply_norms else burden_norm * 0
    gap = (burden_norm - supply_mean_norm).clip(lower=0)
    total_gap_list.append(gap)

gdf['Total_Gap'] = pd.concat(total_gap_list, axis=1).sum(axis=1) if total_gap_list else 0
gdf['Penalty'] = 0.05 * gdf['Total_Gap']
gdf['R_final'] = gdf['R_general'] - gdf['Penalty']

# print(gdf['province_name_th'])
# ---------------------------------------------------------
# 5. DEBUG: RAW, NORMALIZED, Z-SCORE, GAP, PENALTY, FINAL
# ---------------------------------------------------------

import pandas as pd

# ให้ print DataFrame แบบไม่ truncate
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

# ---- RAW X1, X2, X3, X4 ----
gdf['RAW_X1_sum'] = gdf[doctor_cols].sum(axis=1)
gdf['RAW_X2_uc'] = gdf['insurance_uc_scheme']
gdf['RAW_X3_sum'] = gdf[equip_cols].sum(axis=1)
gdf['RAW_X4_ipd'] = gdf['ipd_avg_inpatients_per_day']

# ---- RAW per capita ----
gdf['RAW_X1_per_capita'] = gdf['X1_raw_per_capita']
gdf['RAW_X2_per_capita'] = gdf['X2_raw_per_capita']
gdf['RAW_X3_per_capita'] = gdf['X3_raw_per_capita']
gdf['RAW_X4_per_capita'] = gdf['X4_raw_per_capita']

# ---- Z-scores ----
gdf['Z_X1'] = gdf['z_X1']
gdf['Z_X2'] = gdf['z_X2']
gdf['Z_X3'] = gdf['z_X3']
gdf['Z_X4'] = gdf['z_X4']

# ---------------------------------------------------------
# 6. STORE BURDEN / SUPPLY / GAP PER DISEASE
# ---------------------------------------------------------
for disease, mapping in disease_mapping.items():

    burden_col = mapping['burden']
    supply_cols = mapping['supply']

    # raw burden
    gdf[f'{disease}_burden_raw'] = gdf[burden_col]

    # raw supply total (sum)
    gdf[f'{disease}_supply_raw_sum'] = gdf[supply_cols].sum(axis=1)

    # raw supply mean
    gdf[f'{disease}_supply_raw_mean'] = gdf[supply_cols].mean(axis=1)

    # normalized burden (min-max)
    gdf[f'{disease}_burden_norm'] = min_max_norm(gdf[burden_col])

    # normalized supply (mean of normalized supplies)
    supply_norms = []
    for s in supply_cols:
        supply_norms.append(min_max_norm(gdf[s]))
    gdf[f'{disease}_supply_norm_mean'] = pd.concat(supply_norms, axis=1).mean(axis=1)

    # GAP = burden_norm - supply_norm_mean
    gdf[f'{disease}_gap'] = (gdf[f'{disease}_burden_norm'] - gdf[f'{disease}_supply_norm_mean']).clip(lower=0)


# ---------------------------------------------------------
# 7. BUILD FINAL DEBUG DATAFRAME
# ---------------------------------------------------------

all_debug_cols = [
    "province_name_th",

    # RAW values
    "RAW_X1_sum","RAW_X2_uc","RAW_X3_sum","RAW_X4_ipd",
    "RAW_X1_per_capita","RAW_X2_per_capita","RAW_X3_per_capita","RAW_X4_per_capita",

    # Z scores
    "Z_X1","Z_X2","Z_X3","Z_X4",

    # Readiness & Penalty
    "R_general","Total_Gap","Penalty","R_final"
]

# include disease-level details
for disease in disease_mapping:

    all_debug_cols += [
        f"{disease}_burden_raw",
        f"{disease}_supply_raw_sum",
        f"{disease}_supply_raw_mean",
        f"{disease}_burden_norm",
        f"{disease}_supply_norm_mean",
        f"{disease}_gap"
    ]


# ---------------------------------------------------------
# 8. PRINT EVERYTHING (FULL, NON-TRUNCATED)
# ---------------------------------------------------------

print("\n================= FULL DEBUG DATAFRAME =================\n")
print(gdf[all_debug_cols].to_string())
print("\n========================================================\n")

# ---------------------------------------------------------
# 9. EXPORT DEBUG DATAFRAME TO CSV
# ---------------------------------------------------------

output_path = "readiness_debug_output.csv"   # เปลี่ยน path ได้ตามต้องการ

gdf[all_debug_cols].to_csv(output_path, index=False, encoding="utf-8-sig")

print(f"\nCSV Exported Successfully → {output_path}\n")
