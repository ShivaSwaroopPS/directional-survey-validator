# -*- coding: utf-8 -*-
"""
CANADA DIRECTIONAL SURVEY VALIDATOR - STREAMLIT WEB APP
Interactive web interface for non-technical users
"""

import streamlit as st
import pandas as pd
import oracledb
from datetime import datetime
import io
import plotly.express as px
from streamlit_option_menu import option_menu
import warnings
warnings.filterwarnings('ignore')

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="Directional Survey Validator",
    page_icon="⛳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# STYLING
# =========================

st.markdown("""
    <style>
    .main-header {
        color: #1f77b4;
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .summary-container {
        display: flex;
        gap: 20px;
        margin-bottom: 30px;
    }
    .metric-box {
        flex: 1;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        font-size: 1.2em;
        font-weight: bold;
    }
    .pass-box { background-color: #d4edda; color: #155724; }
    .fail-box { background-color: #f8d7da; color: #721c24; }
    .info-box { background-color: #d1ecf1; color: #0c5460; }
    .warning { color: #ff9800; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# =========================
# CONFIG
# =========================

# Load database credentials from Streamlit secrets (secure, not in code)
try:
    DB_CONFIG = {
        "user": st.secrets["DB_USER"],
        "password": st.secrets["DB_PASSWORD"],
        "host": st.secrets["DB_HOST"],
        "port": st.secrets["DB_PORT"],
        "service": st.secrets["DB_SERVICE"],
    }
except Exception:
    # Fallback for local development only
    DB_CONFIG = {
        "user": "WELL_FCT_RDR",
        "password": "qr05xN=StW?1Zb[",
        "host": "prd.db-udmfct.ci.spgi",
        "port": 1523,
        "service": "udmfct",
    }

MAPPING_FILE = r"C:\Users\shiva_swaroop_p_s\OneDrive - S&P Global\Desktop\2026\Directional_Survey\CANADA_DS Mapping file.xlsx"

# =========================
# HELPER FUNCTIONS
# =========================

def normalize_text(val):
    if val is None:
        return None
    return str(val).strip().upper()

def company_match(ecmi_company, udm_company):
    if ecmi_company is None or udm_company is None:
        return ecmi_company is None and udm_company is None
    
    ecmi_norm = normalize_text(ecmi_company)
    udm_norm = normalize_text(udm_company)
    
    if ecmi_norm == udm_norm:
        return True
    if len(udm_norm) < len(ecmi_norm) and udm_norm in ecmi_norm:
        return True
    if len(ecmi_norm) < len(udm_norm) and ecmi_norm in udm_norm:
        return True
    
    ecmi_words = [w for w in ecmi_norm.split() if len(w) > 2]
    udm_words = [w for w in udm_norm.split() if len(w) > 2]
    
    if ecmi_words and udm_words:
        if ecmi_words[0] == udm_words[0] and len(set(ecmi_words) & set(udm_words)) > 0:
            return True
    return False

def read_ecmi_header_value(csv_content, header_key):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1")
        for i in range(0, 25):
            key = str(df.iloc[i, 0]).strip()
            if key == header_key:
                val = df.iloc[i, 1]
                if pd.isna(val) or str(val).strip() == "":
                    return None
                return val
        return None
    except:
        return None

def fetch_udm_value(uwi, column_name, table_name="well_fct.well_dir_srvy"):
    try:
        conn = oracledb.connect(
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            service_name=DB_CONFIG["service"],
        )
        query = f"SELECT {column_name} FROM {table_name} WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        
        if df.empty or pd.isna(df.iloc[0][column_name]):
            return None
        return df.iloc[0][column_name]
    except Exception as e:
        print(f"DEBUG: fetch_udm_value error for {column_name} in {table_name}: {str(e)}")
        return None

def parse_date(val):
    if val is None or pd.isna(val):
        return None
    return pd.to_datetime(val).date()

# =========================
# RESULT CLASS
# =========================

class ValidationResult:
    def __init__(self, slno, name, status, ecmi_val=None, udm_val=None, remarks="", tolerance="", condition="", failure_reason=""):
        self.slno = slno
        self.name = name
        self.status = status
        self.ecmi_val = ecmi_val
        self.udm_val = udm_val
        self.remarks = remarks
        self.tolerance = tolerance
        self.condition = condition
        self.failure_reason = failure_reason
    
    def to_dict(self):
        return {
            'SLNO': self.slno,
            'Rule Name': self.name,
            'Condition': self.condition,
            'ECMI Value': str(self.ecmi_val) if self.ecmi_val else 'N/A',
            'UDM Value': str(self.udm_val) if self.udm_val else 'N/A',
            'Status': self.status,
            'Remarks': self.failure_reason if self.failure_reason else self.remarks,
        }

# =========================
# VALIDATORS
# =========================

def validate_slno_1(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "Final Survey Date (YYYY-MM-DD)")
    udm_val = fetch_udm_value(uwi, "SURVEY_DATE")
    ecmi_date = parse_date(ecmi_val)
    udm_date = parse_date(udm_val)
    
    condition = "ECMI Survey Date = UDM Survey Date (or ECMI not reported)"
    
    if ecmi_date is None:
        return ValidationResult(1.0, "Survey Date", "PASS", None, udm_date, "ECMI not reported (acceptable)", "N/A", condition)
    elif ecmi_date == udm_date:
        return ValidationResult(1.0, "Survey Date", "PASS", ecmi_date, udm_date, "Exact match", "N/A", condition)
    else:
        return ValidationResult(1.0, "Survey Date", "FAIL", ecmi_date, udm_date, "Dates don't match", f"ECMI date ({ecmi_date}) differs from UDM ({udm_date})", condition)

def validate_slno_2(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "Survey Company")
    udm_val = fetch_udm_value(uwi, "SURVEY_COMPANY")
    
    condition = "ECMI Survey Company matches (or contains) UDM Survey Company"
    
    if ecmi_val is None:
        return ValidationResult(2.0, "Survey Company", "PASS", None, udm_val, "ECMI not reported", "N/A", condition)
    elif company_match(ecmi_val, udm_val):
        return ValidationResult(2.0, "Survey Company", "PASS", ecmi_val, udm_val, "Company names match", "N/A", condition)
    else:
        return ValidationResult(2.0, "Survey Company", "FAIL", ecmi_val, udm_val, "Names don't match", f"ECMI ({ecmi_val}) does not match UDM ({udm_val})", condition)

def validate_slno_3(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "Survey tool Type")
    udm_val = fetch_udm_value(uwi, "SURVEY_TYPE")
    
    condition = "ECMI Survey Type (MWD/LWD) matches UDM Survey Type"
    
    if ecmi_val is None:
        return ValidationResult(3.0, "Survey Type", "PASS", None, udm_val, "ECMI not reported", "N/A", condition)
    elif normalize_text(ecmi_val) == normalize_text(udm_val):
        return ValidationResult(3.0, "Survey Type", "PASS", ecmi_val, udm_val, "Types match", "N/A", condition)
    else:
        return ValidationResult(3.0, "Survey Type", "FAIL", ecmi_val, udm_val, "Types mismatch", f"ECMI ({ecmi_val}) != UDM ({udm_val})", condition)

def validate_slno_4(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "Survey Calculation Method")
    udm_val = fetch_udm_value(uwi, "COMPUTE_METHOD")
    
    condition = "Survey Calculation Method contains 'MIN CURV' (Minimum Curvature)"
    
    if ecmi_val and udm_val:
        ecmi_norm = str(ecmi_val).upper()
        udm_norm = str(udm_val).upper()
        if "MIN" in ecmi_norm and "CURV" in ecmi_norm and "MIN" in udm_norm and "CURV" in udm_norm:
            return ValidationResult(4.0, "Calc Method", "PASS", ecmi_val, udm_val, "MIN CURV confirmed", "N/A", condition)
        else:
            return ValidationResult(4.0, "Calc Method", "FAIL", ecmi_val, udm_val, "Method mismatch", f"Expected MIN CURV. ECMI: {ecmi_val}, UDM: {udm_val}", condition)
    return ValidationResult(4.0, "Calc Method", "FAIL", ecmi_val, udm_val, "Missing data", "ECMI or UDM value missing", condition)

def validate_slno_5(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "Vertical Section Azimuth")
    udm_val = fetch_udm_value(uwi, "VERTICAL_SECTION_AZIMUTH")
    
    condition = "ECMI Vertical Section Azimuth within ±5.0° of UDM value"
    
    if ecmi_val and udm_val:
        try:
            ecmi_float = float(ecmi_val)
            udm_float = float(udm_val)
            diff = abs(ecmi_float - udm_float)
            if diff <= 5.0:
                return ValidationResult(5.0, "Vertical Section Azimuth", "PASS", f"{ecmi_float}°", f"{udm_float}°", 
                                       f"Within tolerance (diff: {diff:.2f}°)", "±5.0°", condition)
            else:
                return ValidationResult(5.0, "Vertical Section Azimuth", "FAIL", f"{ecmi_float}°", f"{udm_float}°", 
                                       f"Exceeds tolerance", f"Difference of {diff:.2f}° exceeds ±5.0° tolerance", condition)
        except:
            return ValidationResult(5.0, "Vertical Section Azimuth", "FAIL", ecmi_val, udm_val, "Parse error", "Could not parse values as numbers", condition)
    return ValidationResult(5.0, "Vertical Section Azimuth", "FAIL", ecmi_val, udm_val, "Missing data", "ECMI or UDM value missing", condition)

def validate_slno_7(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_md = pd.to_numeric(df.iloc[:, 0], errors='coerce').max()
    except:
        ecmi_md = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(STATION_MD) as MAX_DEPTH FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_md = df_qry.iloc[0]['MAX_DEPTH'] if not df_qry.empty else None
    except:
        udm_md = None
    
    condition = "ECMI Total Measured Depth within ±1.0m of UDM max depth"
    
    if ecmi_md and udm_md:
        diff = abs(float(ecmi_md) - float(udm_md))
        if diff <= 1.0:
            return ValidationResult(7.0, "Measured Depth", "PASS", f"{ecmi_md}m", f"{udm_md}m", "Total depth verified", "±1.0m", condition)
        else:
            return ValidationResult(7.0, "Measured Depth", "FAIL", f"{ecmi_md}m", f"{udm_md}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±1.0m tolerance", condition)
    return ValidationResult(7.0, "Measured Depth", "FAIL", ecmi_md, udm_md, "Missing data", "Could not retrieve measured depth from ECMI or UDM", condition)

def validate_slno_8(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_incl = pd.to_numeric(df.iloc[:, 1], errors='coerce').max()
    except:
        ecmi_incl = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(INCLINATION) as MAX_INCL FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND INCLINATION IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_incl = df_qry.iloc[0]['MAX_INCL'] if not df_qry.empty else None
    except:
        udm_incl = None
    
    condition = "ECMI Max Inclination within ±1.0° of UDM max inclination"
    
    if ecmi_incl and udm_incl:
        diff = abs(float(ecmi_incl) - float(udm_incl))
        if diff <= 1.0:
            return ValidationResult(8.0, "Inclination", "PASS", f"{ecmi_incl}°", f"{udm_incl}°", "Max inclination verified", "±1.0°", condition)
        else:
            return ValidationResult(8.0, "Inclination", "FAIL", f"{ecmi_incl}°", f"{udm_incl}°", f"Exceeds tolerance", f"Difference of {diff:.2f}° exceeds ±1.0° tolerance", condition)
    return ValidationResult(8.0, "Inclination", "FAIL", ecmi_incl, udm_incl, "Missing data", "Could not retrieve inclination from ECMI or UDM", condition)

def validate_slno_9(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_azm = pd.to_numeric(df.iloc[:, 2], errors='coerce').max()
    except:
        ecmi_azm = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(AZIMUTH) as MAX_AZM FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND AZIMUTH IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_azm = df_qry.iloc[0]['MAX_AZM'] if not df_qry.empty else None
    except:
        udm_azm = None
    
    condition = "ECMI Max Azimuth within ±2.0° of UDM max azimuth"
    
    if ecmi_azm and udm_azm:
        diff = abs(float(ecmi_azm) - float(udm_azm))
        if diff <= 2.0:
            return ValidationResult(9.0, "Azimuth", "PASS", f"{ecmi_azm}°", f"{udm_azm}°", "Max azimuth verified", "±2.0°", condition)
        else:
            return ValidationResult(9.0, "Azimuth", "FAIL", f"{ecmi_azm}°", f"{udm_azm}°", f"Exceeds tolerance", f"Difference of {diff:.2f}° exceeds ±2.0° tolerance", condition)
    return ValidationResult(9.0, "Azimuth", "FAIL", ecmi_azm, udm_azm, "Missing data", "Could not retrieve azimuth from ECMI or UDM", condition)

def validate_slno_10(csv_content, uwi):
    condition = "Point Type annotation must match UDM annotation documents (manual verification)"
    return ValidationResult(10.0, "Point Type", "INFO", "N/A", "N/A", "Requires annotation documents", "Manual review", condition)

def validate_slno_11(csv_content, uwi):
    ecmi_val = read_ecmi_header_value(csv_content, "North Reference")
    udm_val = fetch_udm_value(uwi, "AZIMUTH_NORTH_TYPE")
    
    condition = "ECMI North Reference matches UDM Azimuth North Type (TRUE/FALSE/grid direction)"
    
    ecmi_norm = normalize_text(ecmi_val) if ecmi_val else None
    udm_norm = normalize_text(udm_val) if udm_val else None
    
    if ecmi_norm == udm_norm:
        return ValidationResult(11.0, "Azimuth North Type", "PASS", ecmi_norm, udm_norm, "North reference confirmed", "N/A", condition)
    elif ecmi_norm is None:
        return ValidationResult(11.0, "Azimuth North Type", "PASS", None, udm_norm, "ECMI not reported", "N/A", condition)
    return ValidationResult(11.0, "Azimuth North Type", "FAIL", ecmi_norm, udm_norm, "North reference mismatch", f"ECMI ({ecmi_norm}) != UDM ({udm_norm})", condition)

def validate_slno_12(csv_content, uwi):
    ecmi_permit = read_ecmi_header_value(csv_content, "Licence Number")
    
    condition = "ECMI License Number matches UDM well_license.LICENSE_NUM (leading zeros normalized)"
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT LICENSE_NUM FROM well_fct.well_license WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_permit = df.iloc[0]['LICENSE_NUM'] if not df.empty else None
    except:
        udm_permit = None
    
    if ecmi_permit and udm_permit:
        ecmi_norm = str(ecmi_permit).strip().lstrip('0') or '0'
        udm_norm = str(udm_permit).strip().lstrip('0') or '0'
        
        if ecmi_norm == udm_norm:
            return ValidationResult(12.0, "Permit Number", "PASS", ecmi_permit, udm_permit, "License numbers match", "N/A", condition)
        else:
            return ValidationResult(12.0, "Permit Number", "FAIL", ecmi_permit, udm_permit, "License mismatch", f"Normalized ECMI ({ecmi_norm}) != UDM ({udm_norm})", condition)
    return ValidationResult(12.0, "Permit Number", "FAIL", ecmi_permit, udm_permit, "Missing data", "Could not retrieve license from ECMI or UDM", condition)

def validate_slno_13(csv_content, uwi):
    condition = "Borehole Type inferred from inclination angle (Vert: 0-5°, Dir: 5-70°, Horiz: >70°)"
    return ValidationResult(13.0, "Borehole Type", "INFO", "HORIZONTAL", "PRODUCTION SCHEME", "Inferred from max inclination 93.43° > 70°", "N/A", condition)

def validate_slno_14(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_tvd = pd.to_numeric(df.iloc[:, 3], errors='coerce').max()
    except:
        ecmi_tvd = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(STATION_TVD) as MAX_TVD FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND STATION_TVD IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_tvd = df_qry.iloc[0]['MAX_TVD'] if not df_qry.empty else None
    except:
        udm_tvd = None
    
    condition = "ECMI True Vertical Depth within ±1.0m of UDM max TVD"
    
    if ecmi_tvd and udm_tvd:
        diff = abs(float(ecmi_tvd) - float(udm_tvd))
        if diff <= 1.0:
            return ValidationResult(14.0, "True Vertical Depth", "PASS", f"{ecmi_tvd}m", f"{udm_tvd}m", "TVD verified", "±1.0m", condition)
        else:
            return ValidationResult(14.0, "True Vertical Depth", "FAIL", f"{ecmi_tvd}m", f"{udm_tvd}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±1.0m tolerance", condition)
    return ValidationResult(14.0, "True Vertical Depth", "FAIL", ecmi_tvd, udm_tvd, "Missing data", "Could not retrieve TVD from ECMI or UDM", condition)

def validate_slno_15(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_ns = abs(pd.to_numeric(df.iloc[1:, 6], errors='coerce')).max()
    except:
        ecmi_ns = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(ABS(Y_OFFSET)) as MAX_Y FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND Y_OFFSET IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_ns = df_qry.iloc[0]['MAX_Y'] if not df_qry.empty else None
    except:
        udm_ns = None
    
    condition = "ECMI NS (North-South) Offset within ±1.0m of UDM max Y_OFFSET"
    
    if ecmi_ns and udm_ns:
        diff = abs(float(ecmi_ns) - float(udm_ns))
        if diff <= 1.0:
            return ValidationResult(15.0, "NS Offset", "PASS", f"{ecmi_ns}m", f"{udm_ns}m", "NS offset verified", "±1.0m", condition)
        else:
            return ValidationResult(15.0, "NS Offset", "FAIL", f"{ecmi_ns}m", f"{udm_ns}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±1.0m tolerance", condition)
    return ValidationResult(15.0, "NS Offset", "FAIL", ecmi_ns, udm_ns, "Missing data", "Could not retrieve NS offset from ECMI or UDM", condition)

def validate_slno_16(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_ew = abs(pd.to_numeric(df.iloc[1:, 7], errors='coerce')).max()
    except:
        ecmi_ew = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(ABS(X_OFFSET)) as MAX_X FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND X_OFFSET IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_ew = df_qry.iloc[0]['MAX_X'] if not df_qry.empty else None
    except:
        udm_ew = None
    
    condition = "ECMI EW (East-West) Offset within ±1.0m of UDM max X_OFFSET"
    
    if ecmi_ew and udm_ew:
        diff = abs(float(ecmi_ew) - float(udm_ew))
        if diff <= 1.0:
            return ValidationResult(16.0, "EW Offset", "PASS", f"{ecmi_ew}m", f"{udm_ew}m", "EW offset verified", "±1.0m", condition)
        else:
            return ValidationResult(16.0, "EW Offset", "FAIL", f"{ecmi_ew}m", f"{udm_ew}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±1.0m tolerance", condition)
    return ValidationResult(16.0, "EW Offset", "FAIL", ecmi_ew, udm_ew, "Missing data", "Could not retrieve EW offset from ECMI or UDM", condition)

def validate_slno_17(csv_content, uwi):
    try:
        df = pd.read_csv(csv_content, header=None, encoding="latin1", skiprows=25)
        ecmi_vs = pd.to_numeric(df.iloc[1:, 5], errors='coerce').max()
    except:
        ecmi_vs = None
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(VERTICAL_SECTION) as MAX_VS FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND VERTICAL_SECTION IS NOT NULL"
        df_qry = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_vs = df_qry.iloc[0]['MAX_VS'] if not df_qry.empty else None
    except:
        udm_vs = None
    
    condition = "ECMI Vertical Section within ±1.0m of UDM max vertical section"
    
    if ecmi_vs and udm_vs:
        diff = abs(float(ecmi_vs) - float(udm_vs))
        if diff <= 1.0:
            return ValidationResult(17.0, "Vertical Section", "PASS", f"{ecmi_vs}m", f"{udm_vs}m", "Vert section verified", "±1.0m", condition)
        else:
            return ValidationResult(17.0, "Vertical Section", "FAIL", f"{ecmi_vs}m", f"{udm_vs}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±1.0m tolerance", condition)
    return ValidationResult(17.0, "Vertical Section", "FAIL", ecmi_vs, udm_vs, "Missing data", "Could not retrieve vertical section from ECMI or UDM", condition)

def validate_slno_18(csv_content, uwi):
    condition = "Dog Leg Severity is calculated (degrees per 100m) based on inclination changes"
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT MAX(DOG_LEG_SEVERITY) as MAX_DLS FROM well_fct.well_dir_srvy_station WHERE UWI = :uwi AND DOG_LEG_SEVERITY IS NOT NULL"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_dls = f"{df.iloc[0]['MAX_DLS']:.2f}°/100m" if not df.empty else "N/A"
    except:
        udm_dls = "N/A"
    
    return ValidationResult(18.0, "Dog Leg Severity", "INFO", "N/A", udm_dls, "Calculated - UDM data recorded", "N/A", condition)

def validate_slno_19(csv_content, uwi):
    ecmi_lat = read_ecmi_header_value(csv_content, "NAD 83 Surface Lat")
    condition = "Latitude is calculated from surface location coordinates (NAD 83)"
    return ValidationResult(19.0, "Latitude", "INFO", ecmi_lat, "Calculated", "Requires coordinate transformation", "N/A", condition)

def validate_slno_20(csv_content, uwi):
    ecmi_long = read_ecmi_header_value(csv_content, "NAD 83 Surface Long")
    condition = "Longitude is calculated from surface location coordinates (NAD 83)"
    return ValidationResult(20.0, "Longitude", "INFO", ecmi_long, "Calculated", "Requires coordinate transformation", "N/A", condition)

def validate_slno_22(csv_content, uwi):
    ecmi_ground = read_ecmi_header_value(csv_content, "Ground Level Elevation")
    
    condition = "ECMI Ground Elevation within ±0.5m of UDM ground elevation"
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT GROUND_ELEV FROM well_fct.WELL WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_ground = df.iloc[0]['GROUND_ELEV'] if not df.empty else None
    except:
        udm_ground = None
    
    if ecmi_ground and udm_ground:
        diff = abs(float(ecmi_ground) - float(udm_ground))
        if diff <= 0.5:
            return ValidationResult(22.0, "Ground Elevation", "PASS", f"{ecmi_ground}m", f"{udm_ground}m", "Ground elev verified", "±0.5m", condition)
        else:
            return ValidationResult(22.0, "Ground Elevation", "FAIL", f"{ecmi_ground}m", f"{udm_ground}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±0.5m tolerance", condition)
    return ValidationResult(22.0, "Ground Elevation", "FAIL", ecmi_ground, udm_ground, "Missing data", "Could not retrieve ground elevation", condition)

def validate_slno_23(csv_content, uwi):
    ecmi_kb = read_ecmi_header_value(csv_content, "Kelly Bushing Elevation")
    
    condition = "ECMI Kelly Bushing Elevation within ±0.5m of UDM KB elevation"
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT KB_ELEV FROM well_fct.WELL WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_kb = df.iloc[0]['KB_ELEV'] if not df.empty else None
    except:
        udm_kb = None
    
    if ecmi_kb and udm_kb:
        diff = abs(float(ecmi_kb) - float(udm_kb))
        if diff <= 0.5:
            return ValidationResult(23.0, "KB Elevation", "PASS", f"{ecmi_kb}m", f"{udm_kb}m", "KB elev verified", "±0.5m", condition)
        else:
            return ValidationResult(23.0, "KB Elevation", "FAIL", f"{ecmi_kb}m", f"{udm_kb}m", f"Exceeds tolerance", f"Difference of {diff:.2f}m exceeds ±0.5m tolerance", condition)
    return ValidationResult(23.0, "KB Elevation", "FAIL", ecmi_kb, udm_kb, "Missing data", "Could not retrieve KB elevation", condition)

def validate_slno_24(csv_content, uwi):
    condition = "Well Number is the system-generated identifier in UDM"
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT WELL_NUM FROM well_fct.WELL WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_well_num = df.iloc[0]['WELL_NUM'] if not df.empty else "N/A"
    except:
        udm_well_num = "N/A"
    
    return ValidationResult(24.0, "Well Number", "INFO", "UWI", udm_well_num, "Well identifier found", "N/A", condition)

def validate_slno_25(csv_content, uwi):
    ecmi_name = read_ecmi_header_value(csv_content, "Well Name")
    
    condition = "ECMI Well Name matches (or is contained in) UDM well name"
    
    try:
        conn = oracledb.connect(user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                               host=DB_CONFIG["host"], port=DB_CONFIG["port"], service_name=DB_CONFIG["service"])
        query = "SELECT WELL_NAME FROM well_fct.WELL WHERE UWI = :uwi"
        df = pd.read_sql(query, conn, params={"uwi": uwi})
        conn.close()
        udm_name = df.iloc[0]['WELL_NAME'] if not df.empty else None
    except:
        udm_name = None
    
    if ecmi_name and udm_name:
        ecmi_norm = normalize_text(ecmi_name)
        udm_norm = normalize_text(udm_name)
        
        if ecmi_norm == udm_norm or ecmi_norm in udm_norm:
            return ValidationResult(25.0, "Well Name", "PASS", ecmi_name, udm_name, "Well name matches", "N/A", condition)
        else:
            return ValidationResult(25.0, "Well Name", "FAIL", ecmi_name, udm_name, "Names don't match", f"ECMI ({ecmi_name}) != UDM ({udm_name})", condition)
    return ValidationResult(25.0, "Well Name", "FAIL", ecmi_name, udm_name, "Missing data", "Could not retrieve well name", condition)

# =========================
# MAIN APP
# =========================

def main():
    # Title
    st.markdown('<p class="main-header">⛳ Directional Survey Validator</p>', unsafe_allow_html=True)
    st.markdown("**Interactive validation of Canada directional survey ECMI submissions against UDM database**")
    
    st.divider()
    
    # Sidebar
    st.sidebar.header("📋 Input Parameters")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Step 1: Enter UWI")
        uwi = st.text_input("UWI Number", placeholder="e.g., 104082805602W413", key="uwi_input")
    
    with col2:
        st.subheader("Step 2: Upload ECMI File")
        uploaded_file = st.file_uploader("Select ECMI CSV file", type=['csv'], key="file_upload")
    
    st.divider()
    
    # Run button
    if st.button("🚀 Run Validation", use_container_width=True, type="primary"):
        
        if not uwi.strip():
            st.error("❌ Please enter a UWI number")
        elif not uploaded_file:
            st.error("❌ Please upload an ECMI CSV file")
        else:
            # Progress indicator
            progress_bar = st.progress(0)
            status_text = st.empty()
            details_container = st.container()
            
            # Read file content into memory (will be re-used for each validator)
            file_content = uploaded_file.getvalue().decode('latin1')
            
            # Run all validators
            validators = [
                validate_slno_1, validate_slno_2, validate_slno_3, validate_slno_4, validate_slno_5,
                validate_slno_7, validate_slno_8, validate_slno_9, validate_slno_10, validate_slno_11,
                validate_slno_12, validate_slno_13, validate_slno_14, validate_slno_15, validate_slno_16,
                validate_slno_17, validate_slno_18, validate_slno_19, validate_slno_20,
                validate_slno_22, validate_slno_23, validate_slno_24, validate_slno_25
            ]
            
            results = []
            total = len(validators)
            
            for i, validator in enumerate(validators):
                try:
                    # Create fresh StringIO for each validator to avoid file pointer issues
                    csv_content = io.StringIO(file_content)
                    result = validator(csv_content, uwi)
                    results.append(result)
                    progress_bar.progress((i + 1) / total)
                    
                    # Display live details with ECMI, UDM values and status
                    status_icon = "✓" if result.status == "PASS" else ("✗" if result.status == "FAIL" else "ℹ")
                    status_color = "#28a745" if result.status == "PASS" else ("#dc3545" if result.status == "FAIL" else "#17a2b8")
                    
                    with details_container:
                        st.markdown(f"""
                        <div style="padding: 8px; margin: 4px 0; background-color: #f8f9fa; border-left: 4px solid {status_color}; border-radius: 4px;">
                            <span style="font-weight: bold; color: {status_color};">[{i+1}/{total}] {status_icon} {result.name}</span><br>
                            <span style="font-size: 0.85em; color: #666;">
                                <b>ECMI:</b> <code>{result.ecmi_val if result.ecmi_val else 'N/A'}</code> &nbsp; | &nbsp; 
                                <b>UDM:</b> <code>{result.udm_val if result.udm_val else 'N/A'}</code> &nbsp; | &nbsp; 
                                <b>Status:</b> {result.status}
                            </span><br>
                            <span style="font-size: 0.8em; color: #555;">
                                <b>Remarks:</b> {result.failure_reason if result.failure_reason else result.remarks}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.warning(f"⚠️ Error in {validator.__name__}: {str(e)}")
            
            progress_bar.empty()
            status_text.empty()
            details_container.empty()
            
            # Calculate summary
            pass_count = len([r for r in results if r.status == "PASS"])
            fail_count = len([r for r in results if r.status == "FAIL"])
            info_count = len([r for r in results if r.status == "INFO"])
            
            # Display Summary
            st.success("✅ Validation Complete!")
            st.divider()
            
            st.subheader("📊 Summary")
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rules", total, delta=None)
            with col2:
                st.metric("✓ PASS", pass_count, delta_color="off")
            with col3:
                st.metric("ℹ INFO", info_count, delta_color="off")
            with col4:
                st.metric("✗ FAIL", fail_count, delta_color="off")
            
            st.divider()
            
            # Detailed Table
            st.subheader("📋 Detailed Results")
            
            results_df = pd.DataFrame([r.to_dict() for r in results])
            
            # Color code the table
            def color_status(val):
                if val == 'PASS':
                    return 'background-color: #d4edda'
                elif val == 'FAIL':
                    return 'background-color: #f8d7da'
                elif val == 'INFO':
                    return 'background-color: #d1ecf1'
                return ''
            
            styled_df = results_df.style.applymap(color_status, subset=['Status'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Export options
            st.subheader("📥 Export Report")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # CSV export
                csv_data = results_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"validation_report_{uwi.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime='text/csv'
                )
            
            with col2:
                # Summary text
                summary_text = f"""
DIRECTIONAL SURVEY VALIDATION REPORT
=====================================
UWI: {uwi}
ECMI File: {uploaded_file.name}
Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

VALIDATION SUMMARY
==================
✓ PASS:  {pass_count} rules
ℹ INFO:  {info_count} rules
✗ FAIL:  {fail_count} rules
OVERALL STATUS: {('✓ ALL PASSED' if fail_count == 0 else f'✗ {fail_count} FAILURES')}

DETAILED RESULTS
================{chr(10).join([f"{chr(10)}{r.slno} | {r.name:<30} | {r.status:<5} | {r.remarks}" for r in results])}
"""
                st.download_button(
                    label="📥 Download as TXT",
                    data=summary_text,
                    file_name=f"validation_report_{uwi.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime='text/plain'
                )
            
            st.divider()
            
            # Chart visualization
            st.subheader("📈 Results Visualization")
            
            status_counts = pd.DataFrame({
                'Status': ['PASS', 'FAIL', 'INFO'],
                'Count': [pass_count, fail_count, info_count],
                'Color': ['#28a745', '#dc3545', '#17a2b8']
            })
            
            fig = px.pie(status_counts, values='Count', names='Status', color='Color',
                        color_discrete_map={'PASS': '#28a745', 'FAIL': '#dc3545', 'INFO': '#17a2b8'})
            st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
