import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
from django.shortcuts import render
from sqlalchemy import create_engine
import google.generativeai as genai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import SimulationHistory
from django.views.decorators.http import require_http_methods

@csrf_exempt
def delete_simulation(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            history_id = body.get('id')
            SimulationHistory.objects.filter(id=history_id).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@csrf_exempt
def save_simulation(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            
            # สร้าง Record ใหม่
            history = SimulationHistory.objects.create(
                province_name=body.get('province_name', 'Unknown'),
                data=body.get('data'), # ก้อน JSON ข้อมูลทั้งหมด
                ai_response=body.get('ai_response', '')
            )
            return JsonResponse({'success': True, 'id': history.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})

def get_history_list(request):
    # ดึง 20 รายการล่าสุด
    history = SimulationHistory.objects.all().order_by('-created_at')[:20]
    data = [{
        'id': h.id, 
        'province': h.province_name, 
        'time': h.created_at.strftime('%d/%m/%Y %H:%M'),
        # ส่ง data กลับไปด้วยเลย จะได้ไม่ต้อง fetch อีกรอบตอนกดเลือก (เพื่อความเร็ว)
        'full_data': h.data,
        'ai_msg': h.ai_response
    } for h in history]
    return JsonResponse({'history': data})

GENAI_API_KEY = "...."  
genai.configure(api_key=GENAI_API_KEY)

@csrf_exempt
def analyze_readiness(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("---- AI REQUEST ----")
            for key, value in data.items():
                print(key, ":", value)
            print("---------------------")
            # -------------------------------
            # 1) สร้าง Context ที่ตีความสเกลถูกต้อง
            # -------------------------------
            context_info = f"""
            บริบทข้อมูลจังหวัด \"{data.get('province_name')}\":

            - R_final = {data.get('R_final')}  (ช่วงค่าตั้งแต่ -1.7 = แย่มาก ถึง +1.7 = ดีมาก)
            - Penalty = {data.get('Penalty')}
            - จำนวนผู้สูงอายุ = {data.get('elderly_population')}

            ระดับ Gap รายโรค (ค่ามาก = ภาระโรคสูง/ระบบรองรับไม่พอ):
            - เบาหวาน (DM) = {data.get('gap_dm')}
            - หัวใจ (Heart) = {data.get('gap_heart')}
            - ความดัน (HT) = {data.get('gap_ht')}

            เกณฑ์การตีความ Gap:
            - Gap < 0.5 = ภาระโรคต่ำ
            - 0.5 ≤ Gap ≤ 2.0 = ภาระโรคปานกลาง
            - Gap > 2.0 = ภาระโรคสูงผิดปกติ (ควรตรวจเชิงลึก)

            เกณฑ์การตีความ R_final:
            - R_final < -1.0 = ความพร้อมต่ำมาก
            - -1.0 ถึง +0.5 = ความพร้อมปานกลาง
            - 0.5 ถึง 1.2 = ความพร้อมดี
            - > 1.2 = ความพร้อมดีมาก
            """

            # -------------------------------
            # 2) แยกกรณีถามครั้งแรก vs มี history
            # -------------------------------
            chat_history = data.get('chat_history', [])
            user_question = data.get('user_question', '')

            if not chat_history and not user_question:
                # ----------- รอบแรก -----------
                prompt = f"""
                {context_info}

                ในฐานะผู้เชี่ยวชาญด้านนโยบายสุขภาพจังหวัด:

                1. ระบุ Pain Point หลักของจังหวัด โดยให้ความสำคัญกับ Gap ที่ > 2.0 เท่านั้นว่าเป็น "สูงจริง"
                2. ประเมินความพร้อมของจังหวัดจากค่า R_final โดยเทียบกับช่วง -1.7 ถึง +1.7
                3. เสนอ 1 มาตรการเร่งด่วนที่สุดที่เหมาะกับจังหวัดนี้ แบบสั้น กระชับ ปฏิบัติได้จริง
                4. ถามผู้ใช้กลับว่าต้องการเจาะลึกด้านใด เช่น งบประมาณ, การเพิ่มบุคลากร, การลดภาระโรค

                ตอบทั้งหมดไม่เกิน 5 บรรทัด ชัดเจน เข้าใจง่าย
                """
            else:
                # ----------- คุยต่อ (มี history) -----------
                history_text = "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in chat_history]
                )

                prompt = f"""
                    {context_info}

                    ประวัติการสนทนาก่อนหน้า:
                    {history_text}

                    คำถามล่าสุดจากผู้ใช้: "{user_question}"

                    ให้ตอบโดย:
                    - ใช้ข้อมูลจังหวัดด้านบนเป็นฐานหลัก
                    - ตีความ Gap ตามสเกล (0.5–2.0 = ปานกลาง, >2.0 = สูงจริง)
                    - ตีความ R_final ตามสเกล -1.7 ถึง +1.7 อย่างถูกต้อง
                    - ให้คำตอบสั้น กระชับ ชัดเจน ตรงคำถาม
                    """

            # -------------------------------
            # 3) เรียก Model
            # -------------------------------
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            response = model.generate_content(prompt)
            
            return JsonResponse({'success': True, 'analysis': response.text})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid method'})


def map_view(request):
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

    # ---------------------------------------------------------
    # 5. PREPARE OUTPUT DATA
    # ---------------------------------------------------------
    total_elderly = int(gdf["elderly_population"].sum())
    mean_R_final = float(gdf["R_final"].mean())
    sorted_df = gdf[["province_name_th", "R_final"]].sort_values("R_final", ascending=False)
    
    top10_best = sorted_df.head(10).iloc[::-1]
    top10_worst = sorted_df.tail(10).iloc[::-1]

    # Map Visualization
    geojson = json.loads(gdf.to_json())
    fig_map = px.choropleth_mapbox(
        gdf, geojson=geojson, locations="province_name_th", featureidkey="properties.province_name_th",
        color="R_final", color_continuous_scale="RdYlGn", range_color=(-1.5, 1.5),
        mapbox_style="carto-positron", zoom=5, center={"lat": 13.5, "lon": 100.6}, opacity=0.8,
        hover_name="province_name_th",
        # hover_data={"R_final": ':.3f', "R_general": ':.3f', "Penalty": ':.3f'}
    )
    fig_map.add_trace(go.Scattermapbox(lat=[], lon=[], mode="lines", line=dict(color="black", width=2), hoverinfo="skip", name="highlight"))
    fig_map.update_layout(margin=dict(r=0, l=0, t=0, b=0), height=550, hovermode="closest")

    # Bar Charts
    fig_best = px.bar(top10_best, x="R_final", y="province_name_th", orientation="h", title="Top 10 จังหวัดความพร้อมสูงสุด", text_auto='.2f')
    fig_best.update_traces(marker_color='#2ca02c')
    fig_best.update_layout(margin=dict(r=10, l=100, t=40, b=10), height=300, yaxis=dict(title=""), xaxis=dict(title="Score"))

    fig_worst = px.bar(top10_worst, x="R_final", y="province_name_th", orientation="h", title="Top 10 จังหวัดความพร้อมต่ำสุด", text_auto='.2f')
    fig_worst.update_traces(marker_color='#d62728')
    fig_worst.update_layout(margin=dict(r=10, l=100, t=40, b=10), height=300, yaxis=dict(title=""), xaxis=dict(title="Score"))

    # JSON Data
    province_data = {}
    for _, r in gdf.iterrows():
        p_data = {
            "province_name": r["province_name_th"],
            "R_final": round(float(r["R_final"]), 4),
            "R_general": round(float(r["R_general"]), 4),
            "Penalty": round(float(r["Penalty"]), 4),
            "elderly_population": int(r["elderly_population"]),
            "insurance_uc_scheme": float(r["insurance_uc_scheme"]),
            "ipd_avg_inpatients_per_day": float(r["ipd_avg_inpatients_per_day"]),
            "disease_dm": float(r.get("disease_dm", 0)),
            "disease_heart": float(r.get("disease_heart", 0)),
            "disease_ht": float(r.get("disease_ht", 0)),
        }
        for col in doctor_cols: p_data[col] = float(r.get(col, 0))
        for col in equip_cols: p_data[col] = float(r.get(col, 0))
        province_data[r["province_name_th"]] = p_data

    boundaries = {}
    for _, row in gdf.iterrows():
        geom = row.geometry
        coords = []
        if geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords.extend(list(poly.exterior.coords)); coords.append([None, None])
        else:
            coords.extend(list(geom.exterior.coords))
        boundaries[row["province_name_th"]] = coords

    context = {
        "total_elderly": f"{total_elderly:,}",
        "mean_R_final": f"{mean_R_final:.2f}",
        "map_html": fig_map.to_html(full_html=False, include_plotlyjs=False),
        "bar_best_html": fig_best.to_html(full_html=False, include_plotlyjs=False),
        "bar_worst_html": fig_worst.to_html(full_html=False, include_plotlyjs=False),
        "province_data": json.dumps(province_data),
        "province_order": json.dumps(list(gdf["province_name_th"].values)),
        "boundaries": json.dumps(boundaries),
        "doctor_cols": json.dumps(doctor_cols),
        "equip_cols": json.dumps(equip_cols),
        "thai_map": json.dumps(THAI_COLUMN_MAP),
    }
    return render(request, "dashboard/map.html", context)