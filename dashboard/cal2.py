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
# 3. CONFIG: COLUMNS & THAI MAPPING
# ---------------------------------------------------------
doctor_cols = [c for c in gdf.columns if c.startswith('doctors_')]
equip_cols = [c for c in gdf.columns if c.startswith('equip_')]


# *** MAPPING (ลบ Ambulance และ Beds ออกตาม Experiment) ***
disease_mapping = {
    'disease_dm': { 
        'burden': 'disease_dm', 
        'supply': [
            'doctors_surgery_general', 'doctors_ophthalmology', 'doctors_ent', 
            'doctors_family_medicine', 'doctors_public_health', 'doctors_dentist', 
            'doctors_urology', 
            'equip_ct_scanner', 'equip_mri', 'equip_ultrasound', 'equip_dialysis_machine'
        ]
    },
    'disease_heart': { 
        'burden': 'disease_heart', 
        'supply': [
            'doctors_thoracic_surgery', 'doctors_vascular_surgery', 
            'doctors_cardiothoracic_anesthesia', 'doctors_rehabilitation', 
            'doctors_diagnostic_radiology', 'doctors_advanced_imaging', 
            'equip_ct_scanner', 'equip_mri', 'equip_ultrasound'
        ]
    },
    'disease_ht': { 
        'burden': 'disease_ht',
        'supply': [
            'doctors_surgery_general', 'doctors_vascular_surgery', 
            'doctors_family_medicine', 'doctors_public_health', 
            'doctors_ophthalmology', 
            'equip_ct_scanner', 'equip_mri', 'equip_ultrasound'
        ]
    }
}

# ---------------------------------------------------------
# 4. CALCULATION: R_final Model (MATCHING EXPERIMENT)
# ---------------------------------------------------------

# 4.1 Per Capita Preparation
elderly_pop = gdf['elderly_population'].replace(0, 1)

# X1: Personnel Per Capita
gdf['X1_raw_per_capita'] = gdf[doctor_cols].sum(axis=1) / elderly_pop

# X2: Insurance Per Capita (Weight 0.3)
gdf['X2_raw_per_capita'] = gdf['insurance_uc_scheme'] / elderly_pop

# X3: Equipment Per Capita (Weight 0.2)
gdf['X3_raw_per_capita'] = gdf[equip_cols].sum(axis=1) / elderly_pop

# X4: Load IPD Per Capita (Weight 0.1)
gdf['X4_raw_per_capita'] = gdf['ipd_avg_inpatients_per_day'] / elderly_pop

# 4.2 Z-Score Calculation (Standard Z-Score)
def calculate_z_score_std(series): 
    if series.std() == 0: return series * 0
    return (series - series.mean()) / series.std()

gdf['z_X1'] = calculate_z_score_std(gdf['X1_raw_per_capita'])
gdf['z_X2'] = calculate_z_score_std(gdf['X2_raw_per_capita'])
gdf['z_X3'] = calculate_z_score_std(gdf['X3_raw_per_capita'])

# X4 Invert Logic: (Mean - X) / Std
x4_mean = gdf['X4_raw_per_capita'].mean()
x4_std = gdf['X4_raw_per_capita'].std()
gdf['z_X4'] = 0 if x4_std == 0 else (x4_mean - gdf['X4_raw_per_capita']) / x4_std

# 4.3 R_general Calculation
# Weights: X1=0.4, X2=0.3, X3=0.2, X4=0.1
gdf['R_general'] = (0.4 * gdf['z_X1']) + (0.3 * gdf['z_X2']) + (0.2 * gdf['z_X3']) + (0.1 * gdf['z_X4'])

# 4.4 Penalty Calculation
def min_max_norm(series):
    if series.max() == series.min(): return series * 0
    return (series - series.min()) / (series.max() - series.min())

total_gap_list = []

for disease, mapping in disease_mapping.items():
    # A. Burden: Normalize (Raw Count / Elderly) -> Per Capita Normalization
    if mapping['burden'] in gdf.columns:
        burden_per_capita = gdf[mapping['burden']] / elderly_pop
        burden_norm = min_max_norm(burden_per_capita)
    else:
        burden_norm = gdf.index * 0

    # B. Supply: Normalize Raw Count -> Average
    supply_norms = []
    for s_col in mapping['supply']:
        if s_col in gdf.columns:
            # Experiment ใช้ Raw Count Normalize
            supply_norms.append(min_max_norm(gdf[s_col]))
        else:
            supply_norms.append(gdf.index * 0)
    
    if supply_norms:
        supply_mean_norm = pd.concat(supply_norms, axis=1).mean(axis=1)
    else:
        supply_mean_norm = burden_norm * 0

    # C. Gap
    gap = (burden_norm - supply_mean_norm).clip(lower=0)
    total_gap_list.append(gap)

gdf['Total_Gap'] = pd.concat(total_gap_list, axis=1).sum(axis=1) if total_gap_list else 0

# Alpha default = 0.05
gdf['Penalty'] = 0.05 * gdf['Total_Gap']
gdf['R_final'] = gdf['R_general'] - gdf['Penalty']

gdf['doc'] = gdf[doctor_cols].sum(axis=1)

print(gdf[['province_name_th','doc']])