#!/usr/bin/env python3
"""
scripts/optimize_facility_maps.py

Optimizes high-resolution official CPDDO 2026 Quezon City wall maps (28 MB, 248 MP each)
into web-friendly assets (~1.5 MB each) for the DengueSense QC interactive viewer.
Also generates authoritative metadata and frontend JS asset.
"""

import os
import sys
import json
import hashlib
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUT_IMG_DIR = os.path.join(PROJECT_ROOT, "frontend", "assets", "images", "maps")
OUT_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "authoritative", "cpdd", "facilities_metadata.json")
OUT_JS_PATH = os.path.join(PROJECT_ROOT, "frontend", "js", "facilities-data.js")

MAP_CATALOG = [
    {
        "id": "health",
        "raw_filename": "Quezon City Health Facilities 2026.jpg",
        "web_filename": "qc_health_facilities_2026.jpg",
        "title": "Health Facilities",
        "subtitle": "Quezon City Hospitals, Super Health Centers, & Barangay Health Centers",
        "icon": "🏥",
        "badge": "Priority Diagnostic Hubs",
        "legend": [
            {"label": "Health Facilities", "color": "#c53030", "shape": "Heartbeat circle icon", "description": "Tertiary hospitals, Super Health Centers, Barangay Health Centers"}
        ],
        "dengue_relevance": {
            "role": "Frontline Clinical Access & Diagnostic Testing",
            "clinical_significance": "Essential sites for early Dengue NS1 antigen rapid diagnostic testing, CBC/platelet monitoring, oral rehydration therapy (ORT), and inpatient referral.",
            "flood_compound_risk": "CDRA 2022 Section 3.7.3 identifies 12 health centers and 13 hospitals in areas subject to >0.5m flood depth during severe storms (e.g., Brgys Sienna, West Triangle, Milagrosa, Central, Damayang Lagi, Doña Imelda). Compounded monsoon flooding risks cutting off critical healthcare triage during dengue outbreaks."
        }
    },
    {
        "id": "schools",
        "raw_filename": "Quezon City Public Schools 2026.jpg",
        "web_filename": "qc_public_schools_2026.jpg",
        "title": "Public Schools",
        "subtitle": "Quezon City Public Elementary & High Schools",
        "icon": "🏫",
        "badge": "High Pediatric Exposure",
        "legend": [
            {"label": "High Schools", "color": "#dd6b20", "shape": "Orange building emblem", "description": "Public junior & senior high schools"},
            {"label": "Elementary Schools", "color": "#805ad5", "shape": "Purple building emblem", "description": "Public primary & elementary schools"}
        ],
        "dengue_relevance": {
            "role": "Pediatric Congregate Setting & Daytime Transmission",
            "clinical_significance": "Quezon City eLLCAP 2021-2050 (pp. 33-35) highlights that children under 15 comprise 30% of the city population and suffer the highest morbidity from dengue shock syndrome.",
            "diurnal_exposure": "Aedes aegypti mosquitoes are daytime biters with peak feeding between 6:00-9:00 AM and 3:00-6:00 PM, exactly coinciding with school class hours and outdoor play."
        }
    },
    {
        "id": "daycare",
        "raw_filename": "Quezon City Child Development Centers 2026.jpg",
        "web_filename": "qc_child_development_centers_2026.jpg",
        "title": "Child Development Centers",
        "subtitle": "Quezon City Barangay Day Care & Early Childhood Centers",
        "icon": "👶",
        "badge": "High Vulnerability",
        "legend": [
            {"label": "Child Development Centers", "color": "#2b6cb0", "shape": "Blue building emblem", "description": "Barangay early childhood care and development centers"}
        ],
        "dengue_relevance": {
            "role": "Early Childhood & Infant Care Cohort",
            "clinical_significance": "Toddlers and infants have underdeveloped immune systems, presenting the greatest risk of rapid dehydration and severe capillary leakage when infected with dengue.",
            "environmental_focus": "Requires rigorous daily search-and-destroy of artificial container breeding sites in center courtyards, toy bins, and plant saucers."
        }
    },
    {
        "id": "higher_ed",
        "raw_filename": "Quezon City Higher Education Institutions 2026.jpg",
        "web_filename": "qc_higher_education_2026.jpg",
        "title": "Higher Education Institutions",
        "subtitle": "State Universities, Colleges, & Higher Ed Campuses",
        "icon": "🎓",
        "badge": "Large Campuses",
        "legend": [
            {"label": "Higher Education Institutions", "color": "#2c7a7b", "shape": "Teal graduation emblem", "description": "Universities, colleges, and tertiary institutes"}
        ],
        "dengue_relevance": {
            "role": "High Daytime Foot Traffic & Expansive Campus Grounds",
            "clinical_significance": "Vast green spaces and campus waterways (such as UP Diliman and Ateneo grounds) require proactive vector control and drainage maintenance."
        }
    },
    {
        "id": "fire",
        "raw_filename": "Quezon City Fire Stations 2026.jpg",
        "web_filename": "qc_fire_stations_2026.jpg",
        "title": "Fire Stations",
        "subtitle": "Bureau of Fire Protection & Volunteer Fire Stations",
        "icon": "🚒",
        "badge": "Emergency Lifelines",
        "legend": [
            {"label": "Fire Stations", "color": "#e53e3e", "shape": "Red station emblem", "description": "BFP stations and accredited volunteer brigades"}
        ],
        "dengue_relevance": {
            "role": "Disaster Response & Vector Control Logistics",
            "clinical_significance": "Staging hubs for water dewatering in flooded barangays and mobile misting/fogging operations during post-flood dengue outbreaks."
        }
    },
    {
        "id": "police",
        "raw_filename": "Quezon City Police Stations and Jails 2026.jpg",
        "web_filename": "qc_police_jails_2026.jpg",
        "title": "Police Stations & Jails",
        "subtitle": "QCPD Police Stations, Sub-stations, & Detention Facilities",
        "icon": "🚓",
        "badge": "Security & Congregate",
        "legend": [
            {"label": "Police Stations & Jails", "color": "#1a365d", "shape": "Navy badge emblem", "description": "Police precincts and detention centers"}
        ],
        "dengue_relevance": {
            "role": "High-Density Congregate Facilities",
            "clinical_significance": "Detention cells and precincts require targeted vector management to prevent rapid institutional transmission cycles."
        }
    },
    {
        "id": "libraries",
        "raw_filename": "Quezon City Public Libraries 2026.jpg",
        "web_filename": "qc_public_libraries_2026.jpg",
        "title": "Public Libraries",
        "subtitle": "Quezon City Main Library & Barangay Branch Libraries",
        "icon": "📚",
        "badge": "Civic Centers",
        "legend": [
            {"label": "Public Libraries", "color": "#744210", "shape": "Brown book emblem", "description": "City central and barangay branch libraries"}
        ],
        "dengue_relevance": {
            "role": "Community Information & IEC Dissemination Hubs",
            "clinical_significance": "Public venues for distributing DOH 4S anti-dengue information, education, and communication materials to families and students."
        }
    }
]

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def main():
    os.makedirs(OUT_IMG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_JSON_PATH), exist_ok=True)
    
    print(f"Starting optimization of {len(MAP_CATALOG)} facilities maps...")
    
    catalog_result = []
    
    for item in MAP_CATALOG:
        raw_path = os.path.join(RAW_DIR, item["raw_filename"])
        if not os.path.exists(raw_path):
            print(f"WARNING: Raw file missing: {raw_path}", file=sys.stderr)
            continue
            
        raw_size = os.path.getsize(raw_path)
        raw_hash = sha256_file(raw_path)
        
        web_path = os.path.join(OUT_IMG_DIR, item["web_filename"])
        
        with Image.open(raw_path) as img:
            orig_w, orig_h = img.size
            # Target width 2200px maintains clean sharpness while keeping file size ~1.5MB
            target_w = 2200
            target_h = int(orig_h * (target_w / orig_w))
            
            print(f"Resizing {item['id']}: {orig_w}x{orig_h} -> {target_w}x{target_h}...")
            resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            resized.save(web_path, "JPEG", quality=85, optimize=True)
            
        web_size = os.path.getsize(web_path)
        web_hash = sha256_file(web_path)
        
        print(f"  -> Saved {item['web_filename']}: {web_size / (1024*1024):.2f} MB (was {raw_size / (1024*1024):.2f} MB)")
        
        catalog_result.append({
            "id": item["id"],
            "title": item["title"],
            "subtitle": item["subtitle"],
            "icon": item["icon"],
            "badge": item["badge"],
            "web_asset_url": f"assets/images/maps/{item['web_filename']}",
            "dimensions": {
                "web": {"width": target_w, "height": target_h, "size_bytes": web_size},
                "original": {"width": orig_w, "height": orig_h, "size_bytes": raw_size}
            },
            "sha256": {
                "web": web_hash,
                "original": raw_hash
            },
            "legend": item["legend"],
            "dengue_relevance": item["dengue_relevance"]
        })
        
    metadata = {
        "is_authoritative_reference": True,
        "is_sample": False,
        "publisher": "Quezon City Planning and Development Department (CPDDO)",
        "office_address": "4th Floor Civic Center Building D, Quezon City Hall Compound, Elliptical Road, Diliman, Quezon City",
        "publication_year": 2026,
        "geographic_coordinate_system": "GCS_PRS_1992",
        "projected_coordinate_system": "Philippines Zone III (PRS 1992)",
        "datum": "Philippine Reference System 1992",
        "total_categories": len(catalog_result),
        "categories": catalog_result
    }
    
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved metadata to {OUT_JSON_PATH}")
    
    js_content = f"""// Auto-generated by scripts/optimize_facility_maps.py
// Authoritative CPDDO 2026 Facilities Catalog for DengueSense QC
window.QC_FACILITIES_METADATA = {json.dumps(metadata, indent=2, ensure_ascii=False)};
"""
    with open(OUT_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Saved JS asset to {OUT_JS_PATH}")
    print("Optimization completed successfully!")

if __name__ == "__main__":
    main()
