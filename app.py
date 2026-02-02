import os
import re
import sys
import time
import json
import pickle
import base64
import asyncio
import subprocess
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from github_storage import get_github_storage
from cta_audit_analyzer import perform_cta_audit
from universal_sky_extractor import UniversalSkyExtractor, SkyProduct



# if os.name == 'nt':  # Windows
#     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Check if browsers are installed
def install_playwright_browsers():
    if not os.path.exists('/root/.cache/ms-playwright'):  # Check the path where browsers are cached
        subprocess.run(['playwright', 'install'], check=True)

# Run the installation process when the app starts
install_playwright_browsers()



# -------------------- STYLE VARIABLES --------------------
PRIMARY_COLOR = "#1ABC9C"
SECONDARY_COLOR = "#888888"
TAB_SELECTED_COLOR = "#FF7300"
FONT_FAMILY = "'Poppins','Nunito Sans','Inter','Segoe UI','Roboto','Helvetica Neue',Arial,sans-serif"


# goal = 'Increase sign-ups for the Sky subscription service'
# API_URL = "https://api.firecrawl.dev/v2/scrape" # not used 
# API_KEY = "fc-1256db4cbfb34fd7b63316bb1f90390c" # not used
# url = "https://www.sky.com"
# token = "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" # not used
gemini_api_key = "AIzaSyDppq6vhQdeWTRQmlqb4onJ9R43DxKlhnA"
# openai_api_key = "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" # not used

# -------------------- PAGE CONFIG & STYLING --------------------
st.set_page_config(page_title="Exp Agents", layout="wide")

# Initialize session state
if 'cta_audit_in_progress' not in st.session_state:
    st.session_state.cta_audit_in_progress = False
if 'cta_audit_results' not in st.session_state:
    st.session_state.cta_audit_results = None
if 'generating' not in st.session_state:
    st.session_state.generating = False
if 'process_generation' not in st.session_state:
    st.session_state.process_generation = False

st.markdown(
    f"""
    <style>
    /* Material Icons font for use inside custom HTML blocks */
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    .mi {{ font-family: 'Material Icons'; font-weight: normal; font-style: normal; line-height: 1; letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; word-wrap: normal; direction: ltr; -webkit-font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased; vertical-align: -0.2em; margin-right: 6px; }}
    .stApp {{
        font-family: {FONT_FAMILY};
        background: #ffffff;
        min-height: 100vh;
    }}

    /* EXL Orange color scheme */
    :root {{
        --exl-orange: #FF6B35;
        --exl-orange-dark: #E55A2B;
        --exl-orange-light: #FF8A65;
        --exl-gray: #6C757D;
        --exl-dark: #343A40;
    }}
    
    /* Make all Material icons grayscale */
    .stTabs [data-baseweb="tab"] svg,
    button svg,
    .stButton svg,
    [class*="material"] {{
        filter: grayscale(100%);
        opacity: 0.7;
    }}

    /* Enhanced centered message styling - removed dotted box */
    .center-message {{
        display: flex;
        justify-content: center;
        align-items: center;
        height: 350px;
        flex-direction: column;
        text-align: center;
        background: #ffffff;
        border-radius: 15px;
        padding: 40px;
        transition: all 0.3s ease;
    }}
    .center-message:hover {{
        transform: translateY(-5px);
    }}
    .center-message h4 {{
        margin: 0;
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--exl-dark);
        margin-bottom: 10px;
    }}
    .center-message p {{
        margin: 0;
        font-size: 1rem;
        color: var(--exl-gray);
    }}

    /* Bold labels for form fields */
    .stTextInput label, .stSelectbox label,
    .stTextInput > div > label, .stSelectbox > div > label,
    div[data-testid="stTextInput"] label, div[data-testid="stSelectbox"] label {{
        font-weight: 600 !important;
        color: var(--exl-dark) !important;
        font-size: 1rem !important;
    }}
    
    /* Additional targeting for Streamlit labels */
    .stTextInput p, .stSelectbox p,
    .stTextInput > div > p, .stSelectbox > div > p {{
        font-weight: 600 !important;
        color: var(--exl-dark) !important;
        font-size: 1rem !important;
    }}
    
    /* Target all possible label elements in form widgets */
    .stTextInput, .stSelectbox {{
        font-weight: 600 !important;
    }}
    
    .stTextInput *, .stSelectbox * {{
        font-weight: 600 !important;
    }}
    
    /* Specific targeting for the label text */
    div[data-testid="stTextInput"] > div > div > p,
    div[data-testid="stSelectbox"] > div > div > p {{
        font-weight: 600 !important;
        color: var(--exl-dark) !important;
        font-size: 1rem !important;
    }}
    
    /* More aggressive targeting for Streamlit labels */
    .stTextInput label, .stSelectbox label,
    .stTextInput .stMarkdown, .stSelectbox .stMarkdown,
    .stTextInput .stMarkdown p, .stSelectbox .stMarkdown p {{
        font-weight: 700 !important;
        color: #2c3e50 !important;
        font-size: 1rem !important;
    }}
    
    /* Target the specific label containers */
    .stTextInput > div:first-child, .stSelectbox > div:first-child {{
        font-weight: 700 !important;
        color: #2c3e50 !important;
    }}
    
    /* Orange save button styling */
    .stButton > button[data-testid="baseButton-secondary"],
    .stButton > button:has-text("💾 Save") {{
        background: linear-gradient(135deg, #FF6B35 0%, #E55A2B 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(255, 107, 53, 0.3) !important;
    }}
    .stButton > button[data-testid="baseButton-secondary"]:hover,
    .stButton > button:has-text("💾 Save"):hover {{
        background: linear-gradient(135deg, #E55A2B 0%, #FF6B35 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.4) !important;
    }}
    
    /* Alternative approach for save button */
    .stButton > button {{
        background: linear-gradient(135deg, #FF6B35 0%, #E55A2B 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(255, 107, 53, 0.3) !important;
    }}
    .stButton > button:hover {{
        background: linear-gradient(135deg, #E55A2B 0%, #FF6B35 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.4) !important;
    }}

    /* Enhanced hypothesis container with EXL styling */
    .hypo-card {{
        border: 2px solid var(--exl-orange);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        background: #ffffff;
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.1);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}
    .hypo-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 107, 53, 0.1), transparent);
        transition: left 0.5s;
    }}
    .hypo-card:hover {{
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 15px 35px rgba(255, 107, 53, 0.2);
        border-color: var(--exl-orange-dark);
    }}
    .hypo-card:hover::before {{
        left: 100%;
    }}
    .hypo-title {{
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 8px;
        color: var(--exl-dark);
        transition: color 0.3s ease;
    }}
    .hypo-card:hover .hypo-title {{
        color: var(--exl-orange);
    }}

    /* Enhanced left container styling with EXL colors */
    .left-container {{
        border: 2px solid var(--exl-orange);
        border-radius: 15px;
        padding: 25px;
        background: #ffffff;
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.1);
        width: 100%;
        box-sizing: border-box;
        display: block;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }}
    .left-container::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255, 107, 53, 0.05) 0%, transparent 70%);
        animation: float 6s ease-in-out infinite;
    }}
    .left-container:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 30px rgba(255, 107, 53, 0.15);
    }}
    @keyframes float {{
        0%, 100% {{ transform: translateY(0px) rotate(0deg); }}
        50% {{ transform: translateY(-10px) rotate(180deg); }}
    }}
    .hypo-desc {{
        font-size: 0.9rem;
        color: var(--exl-gray);
        margin-bottom: 8px;
    }}

    /* Enhanced button styling with EXL orange */
    .stButton > button {{
        background: linear-gradient(135deg, var(--exl-orange) 0%, var(--exl-orange-dark) 100%);
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
        position: relative;
        overflow: hidden;
    }}
    .stButton > button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.4);
        background: linear-gradient(135deg, var(--exl-orange-dark) 0%, var(--exl-orange) 100%);
        color: white !important;
    }}
    .stButton > button:active {{
        transform: translateY(-1px);
        color: white !important;
    }}
    .stButton > button:focus {{
        color: white !important;
    }}
    .stButton > button:visited {{
        color: white !important;
    }}

    /* Enhanced input field styling */
    .stTextInput > div > div > input {{
        border-radius: 12px;
        border: 2px solid #e9ecef;
        padding: 12px 16px;
        font-size: 1rem;
        transition: all 0.3s ease;
        background: #ffffff;
        box-shadow: none;
        font-weight: 400 !important;
    }}
    .stTextInput > div > div > input:focus {{
        border-color: var(--exl-orange);
        box-shadow: none;
        background: white;
        font-weight: 400 !important;
    }}

    /* Enhanced select box styling */
    .stSelectbox > div > div {{
        border-radius: 12px;
        border: 2px solid #e9ecef;
        transition: all 0.3s ease;
        box-shadow: none;
    }}
    .stSelectbox > div > div:focus-within {{
        border-color: var(--exl-orange);
        box-shadow: none;
    }}
    .stSelectbox > div > div > div {{
        font-weight: 400 !important;
    }}

    /* Enhanced file uploader styling */
    .stFileUploader > div {{
        border-radius: 12px;
        border: 2px dashed #e9ecef;
        transition: all 0.3s ease;
        box-shadow: none;
    }}
    .stFileUploader > div:hover {{
        border-color: var(--exl-orange);
        background: rgba(255, 107, 53, 0.05);
        box-shadow: none;
    }}

    /* Enhanced tab styling with EXL colors - text style */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        border-bottom: 2px solid #e9ecef;
        padding-bottom: 5px;
        margin-bottom: 20px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 0;
        padding: 12px 20px;
        font-weight: 500;
        font-size: 0.9rem !important;
        transition: all 0.3s ease;
        background: transparent;
        border: none;
        color: var(--exl-gray);
        position: relative;
        cursor: pointer;
        transform: translateY(5px);
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: var(--exl-orange);
        transform: translateY(3px);
        font-size: 1.1rem !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: transparent !important;
        color: var(--exl-orange) !important;
        font-weight: 700 !important;
        font-size: 1.2rem !important;
        transform: translateY(3px);
    }}
    .stTabs [data-baseweb="tab"]::after {{
        content: '';
        position: absolute;
        bottom: -5px;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(135deg, var(--exl-orange) 0%, var(--exl-orange-dark) 100%);
        border-radius: 2px;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        transform: scaleX(0);
        transform-origin: left;
    }}
    
    .stTabs [data-baseweb="tab"][aria-selected="true"]::after {{
        transform: scaleX(1);
    }}
    
    /* Additional specific selectors for tab text */
    .stTabs [data-baseweb="tab"] > div {{
        font-size: inherit !important;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] > div {{
        font-size: 1.1rem !important;
        font-weight: 700 !important;
    }}
    
    /* Reset: remove colored boxes around tabs, keep original underline/text styles */
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"] {{
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 12px 20px !important; /* keep spacing consistent */
        margin: 0 !important;
    }}

    /* Enhanced expander styling */
    .streamlit-expander {{
        border: 2px solid var(--exl-orange);
        border-radius: 15px;
        margin-bottom: 15px;
        background: #ffffff;
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.1);
        transition: all 0.3s ease;
    }}
    .streamlit-expander:hover {{
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.2);
        border-color: var(--exl-orange-dark);
    }}

    /* Enhanced dashboard card styling */
    .card {{
        border: 2px solid #e9ecef;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        background: #ffffff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}
    .card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 107, 53, 0.1), transparent);
        transition: left 0.5s;
    }}
    .card:hover {{
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 15px 35px rgba(255, 107, 53, 0.15);
        border-color: var(--exl-orange);
    }}
    .card:hover::before {{
        left: 100%;
    }}

    /* Enhanced success/error message styling */
    .stSuccess {{
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        border-radius: 12px;
        padding: 15px;
        border: none;
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
    }}
    .stError {{
        background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
        color: white;
        border-radius: 12px;
        padding: 15px;
        border: none;
        box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);
    }}
    .stInfo {{
        background: linear-gradient(135deg, var(--exl-orange) 0%, var(--exl-orange-dark) 100%);
        color: white;
        border-radius: 12px;
        padding: 15px;
        border: none;
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
    }}

    /* Custom scrollbar with EXL colors */
    ::-webkit-scrollbar {{
        width: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: #f1f1f1;
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(135deg, var(--exl-orange) 0%, var(--exl-orange-dark) 100%);
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(135deg, var(--exl-orange-dark) 0%, var(--exl-orange) 100%);
    }}

    /* Enhanced loading animation styles - removed dotted box */
    .loading-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        min-height: 500px;
        background: transparent;
        position: relative;
        overflow: hidden;
    }}

    .floating-elements {{
        position: absolute;
        width: 100%;
        height: 100%;
        pointer-events: none;
    }}

    .floating-element {{
        position: absolute;
        width: 20px;
        height: 20px;
        background: linear-gradient(45deg, var(--exl-orange), var(--exl-orange-light));
        border-radius: 50%;
        animation: float 3s ease-in-out infinite;
        opacity: 0.7;
    }}

    .floating-element:nth-child(1) {{
        top: 20%;
        left: 20%;
        animation-delay: 0s;
    }}

    .floating-element:nth-child(2) {{
        top: 60%;
        right: 20%;
        animation-delay: 1s;
    }}

    .floating-element:nth-child(3) {{
        bottom: 30%;
        left: 30%;
        animation-delay: 2s;
    }}

    .floating-element:nth-child(4) {{
        top: 40%;
        right: 30%;
        animation-delay: 1.5s;
    }}

    .loading-spinner {{
        width: 60px;
        height: 60px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid var(--exl-orange);
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
        position: relative;
        z-index: 2;
    }}

    .loading-dots {{
        display: flex;
        gap: 8px;
        margin-bottom: 20px;
        position: relative;
        z-index: 2;
    }}

    .loading-dot {{
        width: 12px;
        height: 12px;
        background-color: var(--exl-orange);
        border-radius: 50%;
        animation: bounce 1.4s ease-in-out infinite both;
    }}

    .loading-dot:nth-child(1) {{ animation-delay: -0.32s; }}
    .loading-dot:nth-child(2) {{ animation-delay: -0.16s; }}
    .loading-dot:nth-child(3) {{ animation-delay: 0s; }}

    .loading-text {{
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--exl-dark);
        text-align: center;
        margin-bottom: 10px;
        position: relative;
        z-index: 2;
        animation: pulse 2s ease-in-out infinite;
    }}

    .loading-subtext {{
        font-size: 1rem;
        color: var(--exl-gray);
        text-align: center;
        max-width: 300px;
        position: relative;
        z-index: 2;
    }}

    .progress-container {{
        width: 100%;
        max-width: 300px;
        margin-top: 20px;
        position: relative;
        z-index: 2;
    }}

    .progress-bar {{
        width: 100%;
        height: 8px;
        background-color: #f0f0f0;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 8px;
    }}

    .progress-fill {{
        height: 100%;
        background: linear-gradient(90deg, var(--exl-orange), var(--exl-orange-light));
        border-radius: 4px;
        transition: width 0.5s ease-in-out;
    }}

    .progress-text {{
        font-size: 0.8rem;
        color: var(--exl-gray);
        text-align: center;
        font-weight: 500;
    }}

    /* Enhanced expander styling */
    .streamlit-expander {{
        border: 2px solid var(--exl-orange);
        border-radius: 15px;
        margin-bottom: 15px;
        background: #ffffff;
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.1);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }}

    .streamlit-expander:hover {{
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.2);
        border-color: var(--exl-orange-dark);
        transform: translateY(-2px);
    }}

    .streamlit-expander[data-state="open"] {{
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.2);
        border-color: var(--exl-orange-dark);
    }}

    /* Modern button styling */
    .stButton > button {{
        background: linear-gradient(135deg, var(--exl-orange) 0%, var(--exl-orange-dark) 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(255, 107, 53, 0.3);
        position: relative;
        overflow: hidden;
    }}

    .stButton > button:hover {{
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 8px 25px rgba(255, 107, 53, 0.4);
        background: linear-gradient(135deg, var(--exl-orange-dark) 0%, var(--exl-orange) 100%);
    }}

    .stButton > button:active {{
        transform: translateY(0) scale(0.98);
    }}

    /* Enhanced image display */
    .stImage {{
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }}

    .stImage:hover {{
        transform: scale(1.02);
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.15);
    }}

    /* Keyframe animations */
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}

    @keyframes bounce {{
        0%, 80%, 100% {{ 
            transform: scale(0);
        }} 
        40% {{ 
            transform: scale(1);
        }}
    }}

    @keyframes float {{
        0%, 100% {{ 
            transform: translateY(0px) rotate(0deg);
            opacity: 0.7;
        }}
        50% {{ 
            transform: translateY(-20px) rotate(180deg);
            opacity: 1;
        }}
    }}

    @keyframes pulse {{
        0%, 100% {{ 
            opacity: 1;
        }}
        50% {{ 
            opacity: 0.7;
        }}
    }}

    .pulse-animation {{
        animation: pulse 2s ease-in-out infinite;
    }}

    .floating-elements {{
        position: absolute;
        width: 100%;
        height: 100%;
        overflow: hidden;
    }}

    .floating-element {{
        position: absolute;
        width: 20px;
        height: 20px;
        background: var(--exl-orange);
        border-radius: 50%;
        opacity: 0.1;
        animation: float-up 3s ease-in-out infinite;
    }}

    .floating-element:nth-child(1) {{ left: 20%; animation-delay: 0s; }}
    .floating-element:nth-child(2) {{ left: 40%; animation-delay: 1s; }}
    .floating-element:nth-child(3) {{ left: 60%; animation-delay: 2s; }}
    .floating-element:nth-child(4) {{ left: 80%; animation-delay: 0.5s; }}

    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}

    @keyframes bounce {{
        0%, 80%, 100% {{
            transform: scale(0);
        }}
        40% {{
            transform: scale(1);
        }}
    }}

    @keyframes pulse {{
        0% {{
            transform: scale(1);
            opacity: 1;
        }}
        50% {{
            transform: scale(1.05);
            opacity: 0.7;
        }}
        100% {{
            transform: scale(1);
            opacity: 1;
        }}
    }}

    @keyframes float-up {{
        0% {{
            transform: translateY(100vh) scale(0);
            opacity: 0;
        }}
        10% {{
            opacity: 0.1;
        }}
        90% {{
            opacity: 0.1;
        }}
        100% {{
            transform: translateY(-100px) scale(1);
            opacity: 0;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------- HELPER FUNCTIONS --------------------
def show_loading_step(placeholder, step_text, sub_text, step_number=1, total_steps=5): # not used
    """Show dynamic loading step with progress"""
    progress = (step_number / total_steps) * 100
    placeholder.markdown(
        f"""
        <div class='loading-container'>
            <div class='floating-elements'>
                <div class='floating-element'></div>
                <div class='floating-element'></div>
                <div class='floating-element'></div>
                <div class='floating-element'></div>
                <div class='floating-element'></div>
                <div class='floating-element'></div>
            </div>
            <div class='loading-spinner'></div>
            <div class='loading-dots'>
                <div class='loading-dot'></div>
                <div class='loading-dot'></div>
                <div class='loading-dot'></div>
            </div>
            <div class='loading-text'>{step_text}</div>
            <div class='loading-subtext'>{sub_text}</div>
            <div class='progress-container'>
                <div class='progress-bar'>
                    <div class='progress-fill' style='width: {progress}%'></div>
                </div>
                <div class='progress-text'>Step {step_number} of {total_steps}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
def save_hypothesis_to_github(session_data): # not used
    """Save hypothesis data to GitHub repository"""
    github_storage = get_github_storage()
    if not github_storage:
        # Fallback to local storage if GitHub is not configured
        return save_hypothesis_locally(session_data)
    
    success = github_storage.save_hypothesis(session_data)
    if success:
        hyp_id = session_data["hypothesis"].get("id", f"H{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        return f"GitHub: {hyp_id}.json"
    return None

def save_hypothesis_locally(session_data): # not used
    """Save hypothesis data to local files (fallback)"""
    artifacts_dir = Path("artifacts")
    hypotheses_dir = artifacts_dir / "saved_hypotheses"
    hypotheses_dir.mkdir(parents=True, exist_ok=True)
    
    hyp_id = session_data["hypothesis"].get("id", f"H{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    # Save JSON data
    json_file = hypotheses_dir / f"{hyp_id}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2, ensure_ascii=False, default=str)
    
    # Save images if they exist
    if session_data.get("original_screenshot"):
        original_img_path = hypotheses_dir / f"{hyp_id}_original.png"
        img_data = session_data["original_screenshot"]
        if hasattr(img_data, 'read'):  # If it's a file-like object
            img_data = img_data.read()
        elif isinstance(img_data, (str, Path)):  # If it's a path (string or Path object)
            with open(img_data, 'rb') as f:
                img_data = f.read()
        elif not isinstance(img_data, bytes):  # If it's not bytes, try to convert
            img_data = bytes(img_data)
        with open(original_img_path, 'wb') as f:
            f.write(img_data)
    
    if session_data.get("generated_image"):
        generated_img_path = hypotheses_dir / f"{hyp_id}_generated.png"
        img_data = session_data["generated_image"]
        if hasattr(img_data, 'read'):  # If it's a file-like object
            img_data = img_data.read()
        elif isinstance(img_data, (str, Path)):  # If it's a path (string or Path object)
            with open(img_data, 'rb') as f:
                img_data = f.read()
        elif not isinstance(img_data, bytes):  # If it's not bytes, try to convert
            img_data = bytes(img_data)
        with open(generated_img_path, 'wb') as f:
            f.write(img_data)
    
    return json_file

def load_hypotheses_from_github():
    """Load all saved hypotheses from GitHub repository"""
    github_storage = get_github_storage()
    if not github_storage:
        # Fallback to local storage if GitHub is not configured
        return load_hypotheses_from_local()
    
    return github_storage.load_hypotheses()

def load_hypotheses_from_local():
    """Load all saved hypotheses from local files (fallback)"""
    hypotheses_dir = Path("artifacts") / "saved_hypotheses"
    if not hypotheses_dir.exists():
        return []
    
    loaded_sessions = []
    for json_file in hypotheses_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                loaded_sessions.append(session_data)
        except Exception as e:
            # Error loading JSON file - skipping
            pass
    
    return loaded_sessions

def delete_hypothesis_from_github(hyp_id): # not used
    """Delete hypothesis files from GitHub repository"""
    github_storage = get_github_storage()
    if not github_storage:
        # Fallback to local storage if GitHub is not configured
        return delete_hypothesis_locally(hyp_id)
    
    return github_storage.delete_hypothesis(hyp_id)

def delete_hypothesis_locally(hyp_id): # not used
    """Delete hypothesis files from local storage (fallback)"""
    hypotheses_dir = Path("artifacts") / "saved_hypotheses"
    
    # Delete JSON file
    json_file = hypotheses_dir / f"{hyp_id}.json"
    if json_file.exists():
        json_file.unlink()
    
    # Delete image files
    for img_file in hypotheses_dir.glob(f"{hyp_id}_*.png"):
        img_file.unlink()
    
    return True

def generate_hypotheses(target_url, optimization, kpi, reference_upload): # not used
    return [
        {
            "title": "1. Optimise Call to Action",
            "description": "Focus on improving CTA",
            "clicks": optimization,
            "%hike": 20,
            "rationale": "Clearer CTAs increase user engagement and reduce confusion.\nStrategically placing CTAs drives conversions."
        },
        {
            "title": "2. Improve User Interface",
            "description": "Enhance layout and interactions",
            "clicks": optimization,
            "%hike": 10,
            "rationale": "A cleaner interface boosts usability and trust.\nStreamlined UI keeps users focused on key actions."
        },
        {
            "title": "3. Reduce Form Friction",
            "description": "Simplify signup flow",
            "clicks": optimization,
            "%hike": 15,
            "rationale": "Shorter forms reduce drop-offs during onboarding.\nLess friction increases conversion rates."
        },
        {
            "title": "4. Personalize Content",
            "description": "Tailor offers for users",
            "clicks": optimization,
            "%hike": 12,
            "rationale": "Personalized messages resonate more with users.\nContextual targeting improves engagement."
        },
        {
            "title": "5. Optimise Navigation",
            "description": "Streamline user journey",
            "clicks": optimization,
            "%hike": 18,
            "rationale": "Better navigation reduces bounce rate.\nEfficient paths improve task completion."
        },
    ]

# -------------------- SESSION STATE INIT -------------------- # not used
if "dashboard_history" not in st.session_state:
    # Load from GitHub repository on startup
    st.session_state.dashboard_history = load_hypotheses_from_github()

if "generated_hypotheses" not in st.session_state:
    st.session_state.generated_hypotheses = []

# -------------------- PAGE HEADER --------------------
top_left, top_right = st.columns([2, 1], vertical_alignment="top")
with top_left:
    st.markdown(
        """
        <div style='display:flex; flex-direction:column; gap:2px; margin-bottom: 1px;'>
            <div style='font-weight:800; font-size:35px; color:#FF7300;'>⚙ Experium AI </div>
            <div style='font-size:14px; font-weight:400; color:#666;'>AI-powered audit co-pilot: generates Intelligent CTA audits</div>

        </div>
        """,
        unsafe_allow_html=True
    )
# -------------------- MAIN CONTENT: TABS --------------------
tab4, tab5 = st.tabs([":material/analytics: CTA Audit", ":material/price_check: Price Validator"])

# -------------------- CTA AUDIT TAB --------------------
with tab4:
    st.markdown("#### :material/analytics: CTA Audit Analysis")
    
    # if st.session_state.get("generating", False):
    #     st.info(":material/autorenew: Hypothesis generation in progress... You can continue using the dashboard while it processes.")

    # Always show search and filter controls
    col1, col2 = st.columns([0.7, 0.3])
    
    with col1:
        cta_url = st.text_input("Website URL", placeholder="Enter the URL to audit", key="cta_url")
        cta_analysis_type = st.selectbox(
            "Analysis Type", 
            ["Comprehensive CTA Audit", "Button Analysis", "Form Analysis", "Link Analysis"],
            key="cta_analysis_type"
        )
    
    with col2:
        st.markdown("**Analysis Options**")
        include_heatmap = st.checkbox("Generate Visual Heat Map", value=True, key="cta_heatmap")
        include_recommendations = st.checkbox("AI-Powered Recommendations", value=True, key="cta_recommendations")
        include_competitor_analysis = st.checkbox("Competitor Analysis", value=False, key="cta_competitor")
    
    # CTA Audit Button - Smaller and left-aligned
    col_btn, col_space = st.columns([0.3, 0.7])
    with col_btn:
        if st.button("Start CTA Audit", key="cta_audit_btn"):
            if cta_url:
                # Clear previous filter states when starting new audit
                if 'unified_search' in st.session_state:
                    del st.session_state.unified_search
                if 'unified_severity_filter' in st.session_state:
                    del st.session_state.unified_severity_filter
                if 'unified_issue_type_filter' in st.session_state:
                    del st.session_state.unified_issue_type_filter
                if 'unified_cta_type_filter' in st.session_state:
                    del st.session_state.unified_cta_type_filter
                if 'detailed_search' in st.session_state:
                    del st.session_state.detailed_search
                if 'detailed_type_filter' in st.session_state:
                    del st.session_state.detailed_type_filter
                if 'detailed_severity_filter' in st.session_state:
                    del st.session_state.detailed_severity_filter
                if 'detailed_element_id_filter' in st.session_state:
                    del st.session_state.detailed_element_id_filter
                
                # Clear all existing CTA audit results when starting new audit
                st.session_state.cta_audit_results = None
                
                st.session_state.cta_audit_in_progress = True
                st.session_state.cta_audit_url = cta_url
                st.session_state.cta_audit_type = cta_analysis_type
                st.session_state.cta_include_heatmap = include_heatmap
                st.session_state.cta_include_recommendations = include_recommendations
                st.session_state.cta_include_competitor = include_competitor_analysis
                st.rerun()
            else:
                st.warning("Please enter a website URL to audit.")
    
    # CTA Audit Results Section
    if st.session_state.get("cta_audit_results"):
        results = st.session_state.cta_audit_results
        
        # Add visual separator between button and tabs
        st.markdown("---")
        st.markdown("### Analysis Results")
        
        # ==================== MAIN RESULTS TABS ====================
        # Create tabs for different views
        tab_overview, tab_detailed, tab_recommendations = st.tabs([
            "Overview", 
            "Detailed Analysis", 
            "Recommendations"
        ])
        
        with tab_overview:
            # ==================== ENHANCED SUMMARY SECTION ====================
            st.markdown("### CTA Audit Summary")
            
            # Top-level summary with key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                score_color = "#28A745" if results["score"] >= 80 else "#FFC107" if results["score"] >= 60 else "#DC3545"
                st.metric(
                    label="Overall Score", 
                    value=f"{results['score']}/100",
                    delta=f"{'Excellent' if results['score'] >= 80 else 'Good' if results['score'] >= 60 else 'Needs Improvement'}"
                )
            
            with col2:
                st.metric(
                    label="Total CTAs Found", 
                    value=results["total_ctas"],
                    delta=f"{results['primary_ctas']} primary"
                )
            
            with col3:
                st.metric(
                    label="Issues Detected", 
                    value=results.get("total_issues", 0),
                    delta=f"{len([i for i in results.get('cta_issues', []) if i.get('severity') == 'High'])} high priority"
                )
            
            with col4:
                st.metric(
                    label="Recommendations", 
                    value=results.get("total_recommendations", 0),
                    delta="Actionable insights"
                )
            
            # Quick summary cards
            st.markdown("---")
            col_summary1, col_summary2 = st.columns(2)
            
            with col_summary1:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
                    border-radius: 10px;
                    padding: 15px;
                    border-left: 4px solid #FF6B35;
                    margin-bottom: 10px;
                ">
                    <h4 style="color: #FF6B35; margin-bottom: 10px;">Analysis Details</h4>
                    <p><strong>Website:</strong> {results["url"]}</p>
                    <p><strong>Analysis Type:</strong> {results["analysis_type"]}</p>
                    <p><strong>CTAs by Type:</strong></p>
                    <ul style="margin: 5px 0; padding-left: 15px; font-size: 14px;">
                        <li>Buttons: {results.get("cta_counts_by_type", {}).get("button", 0)}</li>
                        <li>Links: {results.get("cta_counts_by_type", {}).get("link", 0)}</li>
                        <li>Forms: {results.get("cta_counts_by_type", {}).get("form", 0)}</li>
                        <li>Dropdowns: {results.get("cta_counts_by_type", {}).get("dropdown", 0)}</li>
                        <li>Other: {results.get("other_ctas", 0)}</li>
                    </ul>
                    <p style="font-size: 12px; color: #666; margin-top: 5px;"><strong>Total:</strong> {results["total_ctas"]} CTAs</p>
                    <p><strong>Link Validity:</strong> {results.get("scoring_breakdown", {}).get("link_validity_score", 0)}/100</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col_summary2:
                # Strengths summary
                strengths_text = "<br>".join([f"✓ {s}" for s in results.get("cta_strengths", [])])
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #f0f8f0 0%, #ffffff 100%);
                    border-radius: 10px;
                    padding: 15px;
                    border-left: 4px solid #28A745;
                    margin-bottom: 10px;
                ">
                    <h4 style="color: #28A745; margin-bottom: 10px;"><span class="material-icons mi">check_circle</span>Key Strengths</h4>
                    <div style="font-size: 14px;">
                        {strengths_text if strengths_text else "No specific strengths identified"}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Unified Search and Filter Section (moved outside columns)
            st.markdown("#### :material/search: Search & Filter")
        
            # Create filter columns with clear button in same row
            col_search, col_severity, col_issue_type, col_cta_type, col_clear = st.columns([0.4, 0.15, 0.15, 0.15, 0.15])
            
            with col_search:
                search_query = st.text_input(
                    "Search across all data", 
                    placeholder="e.g., 'broken link', 'accessibility', 'button'",
                    key="unified_search"
                )
            
            with col_severity:
                severity_filter = st.selectbox(
                    "Severity",
                    ["All", "High", "Medium", "Low"],
                    key="unified_severity_filter"
                )
            
            with col_issue_type:
                # Get unique issue types from all issues
                all_issues = results.get("cta_issues", [])
                issue_types = ["All"] + sorted(list(set([issue.get('type', 'Unknown') for issue in all_issues])))
                issue_type_filter = st.selectbox(
                    "Issue Type",
                    issue_types,
                    key="unified_issue_type_filter"
                )
            
            with col_cta_type:
                # Get unique CTA types from detailed analysis
                cta_types = ["All"]
                if results.get("detailed_analysis"):
                    cta_types.extend(sorted(list(set([cta['element'].element_type for cta in results["detailed_analysis"]]))))
                cta_type_filter = st.selectbox(
                    "CTA Type",
                    cta_types,
                    key="unified_cta_type_filter"
                )
            
            with col_clear:
                st.write("")  # Empty space for alignment
                if st.button("Clear All Filters", key="clear_unified_filters", use_container_width=True):
                    st.rerun()
            
            # Get all issues
            all_issues = results.get("cta_issues", [])
            
            # Apply unified filters to issues
            filtered_issues = all_issues
            
            # Apply search filter
            if search_query:
                search_lower = search_query.lower()
                filtered_issues = [
                    issue for issue in filtered_issues
                    if (search_lower in issue.get('type', '').lower() or
                        search_lower in issue.get('description', '').lower() or
                        search_lower in issue.get('element', '').lower() or
                        search_lower in issue.get('recommendation', '').lower())
                ]
            
            # Apply severity filter
            if severity_filter != "All":
                filtered_issues = [i for i in filtered_issues if i.get("severity") == severity_filter]
            
            # Apply issue type filter
            if issue_type_filter != "All":
                filtered_issues = [i for i in filtered_issues if i.get("type") == issue_type_filter]
            
            # Apply CTA type filter
            if cta_type_filter != "All":
                filtered_issues = [
                    issue for issue in filtered_issues
                    if issue.get("cta_details", {}).get("type") == cta_type_filter
                ]
            
            # Show search results summary
            if search_query or severity_filter != "All" or issue_type_filter != "All" or cta_type_filter != "All":
                st.info(f"Found {len(filtered_issues)} issues matching your criteria")
            
            # Group filtered issues by severity
            high_issues = [i for i in filtered_issues if i.get("severity") == "High"]
            medium_issues = [i for i in filtered_issues if i.get("severity") == "Medium"]
            low_issues = [i for i in filtered_issues if i.get("severity") == "Low"]
            
            # Priority Issue Summaries Dashboard
            st.markdown("#### Priority Issue Summaries")
            
            # Create three columns for priority cards
            col_high, col_medium, col_low = st.columns(3, gap="medium")
            
            # High Priority Card
            with col_high:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #ffebee 0%, #ffffff 100%);
                    border-radius: 10px;
                    padding: 20px;
                    border-left: 5px solid #f44336;
                    margin-bottom: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #f44336; margin: 0 0 15px 0; display: flex; align-items: center;">
                        High Priority ({len(high_issues)})
                    </h4>
                </div>
                """, unsafe_allow_html=True)
                
                if high_issues:
                    # Group high priority issues by type
                    from collections import Counter
                    high_types = Counter([issue.get('type', 'Unknown') for issue in high_issues])
                    
                    for issue_type, count in sorted(high_types.items(), key=lambda x: x[1], reverse=True):
                        # Create progress bar
                        progress_width = min(100, (count / max(high_types.values())) * 100)
                        st.markdown(f"""
                        <div style="margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                <span style="font-weight: 500;">{issue_type}</span>
                                <span style="color: #f44336; font-weight: bold;">{count}</span>
                            </div>
                            <div style="background: #ffcdd2; border-radius: 10px; height: 8px; overflow: hidden;">
                                <div style="background: #f44336; height: 100%; width: {progress_width}%; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #666; font-style: italic;'>No high priority issues found</p>", unsafe_allow_html=True)
            
            # Medium Priority Card
            with col_medium:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #fff3e0 0%, #ffffff 100%);
                    border-radius: 10px;
                    padding: 20px;
                    border-left: 5px solid #ff9800;
                    margin-bottom: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #ff9800; margin: 0 0 15px 0; display: flex; align-items: center;">
                        Medium Priority ({len(medium_issues)})
                    </h4>
                </div>
                """, unsafe_allow_html=True)
                
                if medium_issues:
                    # Group medium priority issues by type
                    medium_types = Counter([issue.get('type', 'Unknown') for issue in medium_issues])
                    
                    for issue_type, count in sorted(medium_types.items(), key=lambda x: x[1], reverse=True):
                        # Create progress bar
                        progress_width = min(100, (count / max(medium_types.values())) * 100)
                        st.markdown(f"""
                        <div style="margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                <span style="font-weight: 500;">{issue_type}</span>
                                <span style="color: #ff9800; font-weight: bold;">{count}</span>
                            </div>
                            <div style="background: #ffe0b2; border-radius: 10px; height: 8px; overflow: hidden;">
                                <div style="background: #ff9800; height: 100%; width: {progress_width}%; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #666; font-style: italic;'>No medium priority issues found</p>", unsafe_allow_html=True)
            
            # Low Priority Card
            with col_low:
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%);
                    border-radius: 10px;
                    padding: 20px;
                    border-left: 5px solid #2196f3;
                    margin-bottom: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <h4 style="color: #2196f3; margin: 0 0 15px 0; display: flex; align-items: center;">
                        Low Priority ({len(low_issues)})
                    </h4>
                </div>
                """, unsafe_allow_html=True)
                
                if low_issues:
                    # Group low priority issues by type
                    low_types = Counter([issue.get('type', 'Unknown') for issue in low_issues])
                    
                    for issue_type, count in sorted(low_types.items(), key=lambda x: x[1], reverse=True):
                        # Create progress bar
                        progress_width = min(100, (count / max(low_types.values())) * 100)
                        st.markdown(f"""
                        <div style="margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                                <span style="font-weight: 500;">{issue_type}</span>
                                <span style="color: #2196f3; font-weight: bold;">{count}</span>
                            </div>
                            <div style="background: #bbdefb; border-radius: 10px; height: 8px; overflow: hidden;">
                                <div style="background: #2196f3; height: 100%; width: {progress_width}%; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='color: #666; font-style: italic;'>No low priority issues found</p>", unsafe_allow_html=True)
            
            # Issue Summary Table
            st.markdown("---")
            st.markdown("#### :material/table_chart: Issue Summary Table")
            
            if filtered_issues:
                    # Create a summary table
                    # import pandas as pd
                    table_data = []
                    for issue in filtered_issues:
                        # Get element ID from CTA details or generate one
                        element_id = issue.get('cta_details', {}).get('element_id', 'N/A')
                        if element_id == 'N/A':
                            # Try to get from other fields or generate a unique ID
                            element_id = issue.get('element_id', f"CTA-{hash(issue.get('element', 'unknown')) % 10000}")
                        
                        table_data.append({
                            'Priority': issue.get('severity', 'Unknown'),
                            'Issue Type': issue.get('type', 'Unknown'),
                            'CTA Type': issue.get('cta_details', {}).get('type', 'Unknown'),
                            'Element ID': element_id,
                            'Title': issue.get('description', 'No description')[:50] + ('...' if len(issue.get('description', '')) > 50 else ''),
                            'CTA Text': issue.get('element', 'Unknown')[:30] + ('...' if len(issue.get('element', '')) > 30 else ''),
                            'Location': issue.get('location', 'Unknown')
                        })
                    
                    df_issues = pd.DataFrame(table_data)
                    
                    # Add priority color coding
                    def color_priority(val):
                        if val == 'High':
                            return 'background-color: #ffebee; color: #f44336; font-weight: bold;'
                        elif val == 'Medium':
                            return 'background-color: #fff3e0; color: #ff9800; font-weight: bold;'
                        elif val == 'Low':
                            return 'background-color: #e3f2fd; color: #2196f3; font-weight: bold;'
                        return ''
                    
                    styled_df = df_issues.style.applymap(color_priority, subset=['Priority'])
                    st.dataframe(styled_df, use_container_width=True)
                    
                    st.markdown(f"**Showing {len(filtered_issues)} of {len(all_issues)} issues**")
            else:
                st.info("No issues found matching your criteria.")
            
            # Visual Heatmap Section (only in Overview tab)
            if results.get("heatmap_data") and st.session_state.get("cta_include_heatmap", True):
                st.markdown("---")
                st.markdown("### :material/map: Visual Heatmap")
                heatmap_data = results["heatmap_data"]
                
                if heatmap_data.get("cta_positions"):
                        # Create a simple visual representation
                        st.markdown("**CTA Distribution on Page:**")
                        
                        # Create a DataFrame for visualization
                        # import pandas as pd
                        positions = heatmap_data.get('cta_positions') or []
                        texts = heatmap_data.get('cta_texts') or []
                        types_ = heatmap_data.get('cta_types') or []
                        issues_ = heatmap_data.get('cta_issues') or ['None'] * len(positions)
                        severities_ = heatmap_data.get('cta_severity') or ['None'] * len(positions)
                        element_ids_ = heatmap_data.get('cta_element_ids') or [''] * len(positions)

                        df = pd.DataFrame({
                            'X Position': [pos[0] for pos in positions],
                            'Y Position': [pos[1] for pos in positions],
                            'CTA Text': texts,
                            'Type': types_,
                            'Issues': issues_,
                            'Severity': severities_,
                            'Element ID': element_ids_
                        })
                        
                        # Apply unified filters to heatmap data
                        filtered_df = df.copy()
                        
                        # Apply search filter to heatmap
                        if search_query:
                            search_lower = search_query.lower()
                            mask = (
                                filtered_df['CTA Text'].str.lower().str.contains(search_lower, na=False) |
                                filtered_df['Type'].str.lower().str.contains(search_lower, na=False) |
                                filtered_df['Issues'].str.lower().str.contains(search_lower, na=False) |
                                filtered_df['Severity'].str.lower().str.contains(search_lower, na=False)
                            )
                            filtered_df = filtered_df[mask]
                        
                        # Apply severity filter to heatmap
                        if severity_filter != "All":
                            filtered_df = filtered_df[filtered_df['Severity'] == severity_filter]
                        
                        # Apply CTA type filter to heatmap
                        if cta_type_filter != "All":
                            filtered_df = filtered_df[filtered_df['Type'] == cta_type_filter]
                        
                        # Apply issue type filter to heatmap (filter by issues column)
                        if issue_type_filter != "All":
                            filtered_df = filtered_df[filtered_df['Issues'].str.contains(issue_type_filter, na=False)]
                        
                        # Display filtered results summary
                        st.markdown(f"**Showing {len(filtered_df)} of {len(df)} CTAs on heatmap**")
                        
                        # Create a simple scatter plot
                        import matplotlib.pyplot as plt
                        fig, ax = plt.subplots(figsize=(10, 6))
                        scatter = ax.scatter(df['X Position'], df['Y Position'], 
                                           c=range(len(df)), cmap='viridis', s=100, alpha=0.7)
                        
                        # Add labels for each point
                        for i, (x, y, text) in enumerate(zip(df['X Position'], df['Y Position'], df['CTA Text'])):
                            ax.annotate(f"{i+1}", (x, y), xytext=(5, 5), textcoords='offset points', fontsize=8)
                        
                        ax.set_xlabel('X Position (pixels)')
                        ax.set_ylabel('Y Position (pixels)')
                        ax.set_title('CTA Elements Distribution')
                        ax.grid(True, alpha=0.3)
                        
                        st.pyplot(fig)
                else:
                    st.info("No position data available for heatmap visualization.")
            
        with tab_detailed:
            st.markdown("#### Complete CTA Analysis")
            
            # All CTAs with full details
            if results.get("detailed_analysis"):
                st.markdown(f"**Found {len(results['detailed_analysis'])} CTAs total**")
                
                # Enhanced Filter and Search Section
                st.markdown("---")
                st.markdown("##### :material/search: Search & Filter CTAs")
                
                # Search and filter controls with clear button in same row
                col_search, col_type, col_severity, col_element_id, col_clear = st.columns([0.4, 0.15, 0.15, 0.15, 0.15])
                
                with col_search:
                    search_query = st.text_input(
                        "Search CTAs", 
                        placeholder="Search by text, type, or ID...",
                        key="detailed_search"
                    )
                
                with col_type:
                    # Get unique CTA types
                    cta_types = ["All"] + sorted(list(set([cta['element'].element_type for cta in results["detailed_analysis"]])))
                    type_filter = st.selectbox(
                        "CTA Type",
                        cta_types,
                        key="detailed_type_filter"
                    )
                
                with col_severity:
                    # Get unique severities from issues
                    all_issues = results.get("cta_issues", [])
                    severities = ["All"] + sorted(list(set([issue.get('severity', 'Unknown') for issue in all_issues if issue.get('severity')])))
                    severity_filter = st.selectbox(
                        "Issue Severity",
                        severities,
                        key="detailed_severity_filter"
                    )
                
                with col_element_id:
                    # Get unique element IDs
                    element_ids = ["All"] + sorted([str(cta['element'].element_id) for cta in results["detailed_analysis"] if cta['element'].element_id])
                    element_id_filter = st.selectbox(
                        "Element ID",
                        element_ids,
                        key="detailed_element_id_filter"
                    )
                
                with col_clear:
                    st.write("")  # Empty space for alignment
                    if st.button("Clear All Filters", key="clear_detailed_filters", help="Clear all filters", use_container_width=True):
                        st.rerun()
                
                # Additional filter options
                col_visibility, col_js, col_dropdown = st.columns(3)
                with col_visibility:
                    show_hidden = st.checkbox("Show Hidden CTAs", value=False, key="detailed_hidden")
                with col_js:
                    show_js = st.checkbox("Show JS-Generated", value=True, key="detailed_js")
                with col_dropdown:
                    show_dropdown = st.checkbox("Show Dropdown CTAs", value=True, key="detailed_dropdown")
                
                # Apply comprehensive filtering
                filtered_ctas = results["detailed_analysis"].copy()
                
                # Apply search filter
                if search_query:
                    search_lower = search_query.lower()
                    filtered_ctas = [
                        cta for cta in filtered_ctas
                        if (search_lower in cta['element'].text.lower() or
                            search_lower in cta['element'].element_type.lower() or
                            search_lower in str(cta['element'].element_id).lower() or
                            search_lower in (cta['element'].html_id or "").lower() or
                            search_lower in (cta['element'].html_class or "").lower())
                    ]
                
                # Apply type filter
                if type_filter != "All":
                    filtered_ctas = [cta for cta in filtered_ctas if cta['element'].element_type == type_filter]
                
                # Apply severity filter (based on issues)
                if severity_filter != "All":
                    filtered_ctas = [
                        cta for cta in filtered_ctas
                        if any(issue.get('severity') == severity_filter 
                              for issue in results.get("cta_issues", [])
                              if issue.get("cta_details", {}).get("element_id") == cta['element'].element_id)
                    ]
                
                # Apply element ID filter
                if element_id_filter != "All":
                    filtered_ctas = [cta for cta in filtered_ctas if str(cta['element'].element_id) == element_id_filter]
                
                # Apply visibility filters
                if not show_hidden:
                    filtered_ctas = [cta for cta in filtered_ctas if not cta['element'].is_hidden]
                if not show_js:
                    filtered_ctas = [cta for cta in filtered_ctas if not cta['element'].is_js_generated]
                if not show_dropdown:
                    filtered_ctas = [cta for cta in filtered_ctas if not cta['element'].is_dropdown]
                
                # Show filter results
                if search_query or type_filter != "All" or severity_filter != "All" or element_id_filter != "All":
                    st.info(f"Found {len(filtered_ctas)} CTAs matching your criteria")
                else:
                    st.markdown(f"**Showing {len(filtered_ctas)} CTAs**")
                
                for i, cta_analysis in enumerate(filtered_ctas, 1):
                    cta = cta_analysis['element']
                    
                    # CTA header with metadata including Element ID
                    element_id_display = f"ID: {cta.element_id}" if cta.element_id else "ID: N/A"
                    expander_title = f"**{i}. {cta.element_type.upper()}:** \"{cta.text[:30]}{'...' if len(cta.text) > 30 else ''}\" | {element_id_display}"
                    
                    with st.expander(expander_title, expanded=False):
                        # Performance Scores
                        st.markdown("**Performance Scores**")
                        col_v, col_u, col_c, col_a, col_l = st.columns(5)
                        with col_v:
                            st.metric("Visibility", f"{cta_analysis['visibility_score']}/100")
                        with col_u:
                            st.metric("Urgency", f"{cta_analysis['urgency_score']}/100")
                        with col_c:
                            st.metric("Clarity", f"{cta_analysis['action_clarity']}/100")
                        with col_a:
                            st.metric("Accessibility", f"{cta_analysis['accessibility_score']}/100")
                        with col_l:
                            st.metric("Link Validity", f"{cta_analysis['link_validity_score']}/100")
                        
                        
                        col_info1, col_info2 = st.columns(2)
                        
                        with col_info1:
                            st.markdown("**Basic Info:**")
                            st.write(f"• **Text:** \"{cta.text}\"")
                            st.write(f"• **Type:** {cta.element_type}")
                            st.write(f"• **Position:** x:{cta.position['x']}, y:{cta.position['y']}")
                            st.write(f"• **Size:** {cta.size['width']}x{cta.size['height']}")
                            st.write(f"• **Href:** {cta.href or 'N/A'}")
                            
                        with col_info2:
                            st.markdown("**Technical Details:**")
                            st.write(f"• **ID:** {cta.html_id or 'N/A'}")
                            st.write(f"• **Class:** {cta.html_class or 'N/A'}")
                            st.write(f"• **Role:** {cta.role or 'N/A'}")
                            st.write(f"• **ARIA Label:** {cta.aria_label or 'N/A'}")
                            st.write(f"• **Tab Index:** {cta.tabindex or 'N/A'}")
                            
                            # Link checking information
                            if cta.href:
                                st.markdown("**Link Status:**")
                                if cta.link_is_valid is True:
                                    st.write(f"• **Status:** :material/check_circle: Valid ({cta.link_status})")
                                    if cta.link_response_time:
                                        st.write(f"• **Response Time:** {cta.link_response_time:.2f}s")
                                    if cta.link_redirect_url and cta.link_redirect_url != cta.href:
                                        st.write(f"• **Redirects to:** {cta.link_redirect_url}")
                                elif cta.link_is_valid is False:
                                    st.write(f"• **Status:** :material/close: Invalid ({cta.link_status or 'Error'})")
                                    if cta.link_error_message:
                                        st.write(f"• **Error:** {cta.link_error_message}")
                            else:
                                    st.write(f"• **Status:** :material/hourglass_empty: Not checked")
                            
                        
                        
                        # Issues for this CTA
                        cta_issues = cta_analysis.get('issues', [])
                        if cta_issues:
                            st.markdown("**Issues Found:**")
                            for issue in cta_issues:
                                col_issue, col_fix = st.columns(2, gap="medium")
                                
                                with col_issue:
                                    severity_icon = "🔴" if issue["severity"] == "High" else "🟡" if issue["severity"] == "Medium" else "🟢"
                                    st.markdown(f"**{severity_icon} {issue['type']}**")
                                    st.write(issue['description'])
                                
                                with col_fix:
                                    st.markdown("**:material/tips_and_updates: Fix:**")
                                    st.write(issue['recommendation'])
            else:
                st.info("No detailed analysis data available.")
        
        with tab_recommendations:
            st.markdown("#### :material/tips_and_updates: Actionable Recommendations")
            
            # AI Recommendations
            if results.get("ai_recommendations"):
                st.markdown("**:material/smart_toy: AI-Powered Recommendations:**")
                for i, rec in enumerate(results["ai_recommendations"], 1):
                    st.info(f"**{i}.** {rec}")
                st.markdown("---")
        
            # General Recommendations
            if results.get("recommendations"):
                st.markdown("**:material/checklist: General Best Practices:**")
                for i, rec in enumerate(results["recommendations"], 1):
                    st.success(f"**{i}.** {rec}")
            
            # Priority-based recommendations
            if results.get("cta_issues"):
                st.markdown("**Priority Actions:**")
                high_count = len([i for i in results["cta_issues"] if i.get("severity") == "High"])
                medium_count = len([i for i in results["cta_issues"] if i.get("severity") == "Medium"])
                
                if high_count > 0:
                    st.error(f":material/error: **Critical:** Fix {high_count} high-priority issues immediately")
                if medium_count > 0:
                    st.warning(f":material/error: **Next Steps:** Address {medium_count} medium-priority issues")
                if high_count == 0 and medium_count == 0:
                    st.success(":material/celebration: **Great Job!** No critical issues found")
    
    # CTA Audit Processing
    if st.session_state.get("cta_audit_in_progress", False):
        with st.spinner(":material/search: Analyzing CTAs on your website..."):
            try:
                # Perform real CTA audit using Playwright with AI recommendations
                cta_results = perform_cta_audit(
                    st.session_state.cta_audit_url, 
                    st.session_state.cta_audit_type,
                    gemini_api_key=gemini_api_key
                )
                
                if "error" in cta_results:
                    st.error(f":material/error: Audit failed: {cta_results['error']}")
                    st.session_state.cta_audit_in_progress = False
                else:
                    st.session_state.cta_audit_results = cta_results
                    st.session_state.cta_audit_in_progress = False
                    st.success(":material/check_circle: CTA audit completed successfully!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f":material/error: Error during CTA audit: {str(e)}")
                st.session_state.cta_audit_in_progress = False
                if not show_js:
                    filtered_ctas = [cta for cta in filtered_ctas if not cta['element'].is_js_generated]
                if not show_dropdown:
                    filtered_ctas = [cta for cta in filtered_ctas if not cta['element'].is_dropdown]
                
                st.markdown(f"**Showing {len(filtered_ctas)} filtered CTAs**")
                
                for i, cta_analysis in enumerate(filtered_ctas, 1):
                    cta = cta_analysis['element']
                    
                    # CTA header with metadata
                    with st.expander(f"**{i}. {cta.element_type.upper()}:** \"{cta.text[:40]}{'...' if len(cta.text) > 40 else ''}\"", expanded=False):
                        col_info1, col_info2 = st.columns(2)
                        
                        with col_info1:
                            st.markdown("**Basic Info:**")
                            st.write(f"• **Text:** \"{cta.text}\"")
                            st.write(f"• **Type:** {cta.element_type}")
                            st.write(f"• **Position:** x:{cta.position['x']}, y:{cta.position['y']}")
                            st.write(f"• **Size:** {cta.size['width']}x{cta.size['height']}")
                            st.write(f"• **Href:** {cta.href or 'N/A'}")
                            
                        with col_info2:
                            st.markdown("**Technical Details:**")
                            st.write(f"• **ID:** {cta.html_id or 'N/A'}")
                            st.write(f"• **Class:** {cta.html_class or 'N/A'}")
                            st.write(f"• **Role:** {cta.role or 'N/A'}")
                            st.write(f"• **ARIA Label:** {cta.aria_label or 'N/A'}")
                            st.write(f"• **Tab Index:** {cta.tabindex or 'N/A'}")
                            
                            # Link checking information
                            if cta.href:
                                st.markdown("**Link Status:**")
                                if cta.link_is_valid is True:
                                    st.write(f"• **Status:** :material/check_circle: Valid ({cta.link_status})")
                                    if cta.link_response_time:
                                        st.write(f"• **Response Time:** {cta.link_response_time:.2f}s")
                                    if cta.link_redirect_url and cta.link_redirect_url != cta.href:
                                        st.write(f"• **Redirects to:** {cta.link_redirect_url}")
                                elif cta.link_is_valid is False:
                                    st.write(f"• **Status:** :material/close: Invalid ({cta.link_status or 'Error'})")
                                    if cta.link_error_message:
                                        st.write(f"• **Error:** {cta.link_error_message}")
                                else:
                                    st.write(f"• **Status:** :material/hourglass_empty: Not checked")
                        
                        # Status indicators
                        col_status1, col_status2, col_status3 = st.columns(3)
                        with col_status1:
                            st.write(f"**Visibility:** {':material/check_circle:' if cta.is_visible else ':material/close:'} { 'Visible' if cta.is_visible else 'Hidden'}")
                        with col_status2:
                            st.write(f"**JS Generated:** {':material/check_circle:' if cta.is_js_generated else ':material/close:'} { 'Yes' if cta.is_js_generated else 'No'}")
                        with col_status3:
                            st.write(f"**Dropdown:** {':material/check_circle:' if cta.is_dropdown else ':material/close:'} { 'Yes' if cta.is_dropdown else 'No'}")
                        
                        # Performance scores
                        st.markdown("**Performance Scores:**")
                        col_score1, col_score2, col_score3, col_score4, col_score5 = st.columns(5)
                        with col_score1:
                            st.metric("Visibility", f"{cta_analysis['visibility_score']}/100")
                        with col_score2:
                            st.metric("Urgency", f"{cta_analysis['urgency_score']}/100")
                        with col_score3:
                            st.metric("Clarity", f"{cta_analysis['action_clarity']}/100")
                        with col_score4:
                            st.metric("Accessibility", f"{cta_analysis['accessibility_score']}/100")
                        with col_score5:
                            st.metric("Link Validity", f"{cta_analysis['link_validity_score']}/100")
                        
                        # Screenshot if available
                        if cta.screenshot:
                            st.markdown("**Screenshot:**")
                            st.image(base64.b64decode(cta.screenshot), caption="CTA Element", width=300)
                        
                        # Issues for this CTA
                        cta_issues = [issue for issue in results.get("cta_issues", []) 
                                    if issue.get("cta_details", {}).get("element_id") == cta.element_id]
                        if cta_issues:
                            st.markdown("**Issues Found:**")
                            for issue in cta_issues:
                                severity_icon = "🔴" if issue["severity"] == "High" else "🟡" if issue["severity"] == "Medium" else "🟢"
                                st.write(f"{severity_icon} **{issue['type']}:** {issue['description']}")
                                st.write(f"   :material/tips_and_updates: **Fix:** {issue['recommendation']}")
        
        
        # Remove old redundant sections - now handled in tabs above
        
        
        # Action Buttons
        st.markdown("---")
        col_export, col_new, col_clear = st.columns(3)
        
        with col_export:
            # Create a simple text report
            report_text = f"""
CTA AUDIT REPORT
================
Website: {results["url"]}
Analysis Type: {results["analysis_type"]}
Overall Score: {results["score"]}/100
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

SUMMARY
-------
Total CTAs Found: {results["total_ctas"]}
- Primary CTAs: {results["primary_ctas"]}
- Secondary CTAs: {results["secondary_ctas"]}
- Form CTAs: {results["form_ctas"]}
- Link CTAs: {results["link_ctas"]}

ISSUES FOUND
------------
"""
            for issue in results["cta_issues"]:
                cta_details = issue.get("cta_details", {})
                element_info = issue.get("element", "Unknown CTA")
                location_info = issue.get("location", "Position: Unknown")
                
                report_text += f"""
{issue["severity"].upper()}: {issue.get("type", "CTA Issue")}
Element: {element_info}
Location: {location_info}
Size: {cta_details.get("size", "Unknown")}
Link: {cta_details.get("href", "N/A")}
Description: {issue["description"]}
Recommendation: {issue["recommendation"]}

"""
            
            report_text += """
STRENGTHS
---------
"""
            for strength in results["cta_strengths"]:
                report_text += f"• {strength}\n"
            
            report_text += """
RECOMMENDATIONS
---------------
"""
            for rec in results["recommendations"]:
                report_text += f"• {rec}\n"
            
            st.download_button(
                ":material/description: Download Report",
                data=report_text,
                file_name=f"cta_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col_new:
            if st.button(":material/autorenew: New Audit", use_container_width=True):
                st.session_state.cta_audit_results = None
                st.session_state.cta_audit_in_progress = False
                st.rerun()
        
        with col_clear:
            if st.button(":material/delete: Clear Results", use_container_width=True, key="clear_cta_audit_results"):
                st.session_state.cta_audit_results = None
                st.session_state.cta_audit_in_progress = False
                st.rerun()
    
    else:
        # Show empty state when no audit has been performed
        # st.markdown("""
        # <div style="
        #     display: flex;
        #     flex-direction: column;
        #     align-items: center;
        #     justify-content: center;
        #     height: 400px;
        #     text-align: center;
        #     background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        #     border-radius: 15px;
        #     border: 2px dashed #dee2e6;
        #     margin: 20px 0;
        # ">
        #     <div style="font-size: 4rem; margin-bottom: 20px;"></div>
        #     <h3 style="color: #6c757d; margin-bottom: 10px; font-weight: 600;">Ready to Audit CTAs</h3>
        #     <p style="color: #6c757d; margin-bottom: 20px; max-width: 400px;">
        #         Enter a website URL above to start analyzing call-to-action elements and get optimization recommendations.
        #     </p>
        # </div>
        # """, unsafe_allow_html=True)
        pass

# -------------------- PRICE VALIDATOR TAB --------------------
with tab5:
    # URL Input Section
    st.markdown("#### :material/price_check: Price Validator")
    
    col1, col2 = st.columns([2, 1], gap="medium")
    
    with col1:
        sky_url = st.text_input(
            "Enter Sky URL to extract deals from:",
            placeholder="https://www.sky.com/deals",
            help="Enter any Sky UK website URL (deals, TV, broadband, mobile, etc.)",
            key="sky_extractor_url"
        )
    
    with col2:
        uploaded_file = st.file_uploader(
            "Upload Source of Truth CSV",
            type=['csv'],
            help="Upload CSV with columns: product_name, price",
            key="source_of_truth_csv"
        )
    
    col1, col2, col3 = st.columns([2, 1, 1], gap="small")
    
    with col1:
        st.write("")  # Empty space for alignment
    
    with col2:
        extract_compare_button = st.button(":material/compare: Extract & Compare", use_container_width=True, type="primary")
    
    with col3:
        extract_button = st.button(":material/search: Extract Only", use_container_width=True)
    
    # URL validation
    if sky_url and not sky_url.startswith(('http://', 'https://')):
        st.warning(":material/warning: Please enter a valid URL starting with http:// or https://")
        sky_url = None
    
    if sky_url and 'sky.com' not in sky_url.lower():
        st.warning(":material/warning: This extractor is optimized for Sky UK websites (sky.com). Results may vary for other sites.")
    
    # Initialize session state for extraction results
    if 'sky_extraction_results' not in st.session_state:
        st.session_state.sky_extraction_results = None
    if 'sky_extraction_in_progress' not in st.session_state:
        st.session_state.sky_extraction_in_progress = False
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = None
    
    # Load source of truth data
    def load_source_of_truth():
        """Load source of truth data from uploaded file or default."""
        if uploaded_file is not None:
            try:
                # import pandas as pd
                df = pd.read_csv(uploaded_file)
                if 'product_name' in df.columns and 'price' in df.columns:
                    return df
                else:
                    st.error("CSV must contain 'product_name' and 'price' columns")
                    return None
            except Exception as e:
                st.error(f"Error reading uploaded CSV: {str(e)}")
                return None
        else:
            # Use default source of truth
            try:
                # import pandas as pd
                df = pd.read_csv('default_source_of_truth.csv')
                return df
            except Exception as e:
                st.warning(f"Could not load default source of truth: {str(e)}")
                return None
    
    # Price comparison function
    def compare_prices(extracted_products, source_of_truth_df):
        """Compare extracted prices with source of truth."""
        if source_of_truth_df is None:
            return None
        
        comparison_results = []
        
        for product in extracted_products:
            if not product.price or not product.price.strip():
                continue
                
            # Try to find matching product in source of truth
            product_name_lower = product.name.lower()
            best_match = None
            best_score = 0
            
            for _, row in source_of_truth_df.iterrows():
                source_name_lower = str(row['product_name']).lower()
                
                # Simple matching logic - can be improved
                if product_name_lower in source_name_lower or source_name_lower in product_name_lower:
                    score = len(set(product_name_lower.split()) & set(source_name_lower.split()))
                    if score > best_score:
                        best_score = score
                        best_match = row
            
            if best_match is not None:
                # Extract numeric price from product price
                import re
                extracted_price_str = re.findall(r'[\d.]+', product.price)
                if extracted_price_str:
                    try:
                        extracted_price = float(extracted_price_str[0])
                        source_price = float(best_match['price'])
                        
                        price_difference = extracted_price - source_price
                        price_difference_percent = (price_difference / source_price) * 100 if source_price > 0 else 0
                        
                        comparison_results.append({
                            'product_name': product.name,
                            'extracted_price': extracted_price,
                            'source_price': source_price,
                            'price_difference': price_difference,
                            'price_difference_percent': price_difference_percent,
                            'status': 'match' if abs(price_difference_percent) < 5 else 'mismatch',
                            'source_product': best_match['product_name']
                        })
                    except ValueError:
                        continue
        
        return comparison_results
    
    # Extraction process
    if (extract_button or extract_compare_button) and sky_url:
        st.session_state.sky_extraction_in_progress = True
        
        with st.spinner(":material/search: Extracting deals from Sky website..."):
            try:
                # Create extractor instance
                extractor = UniversalSkyExtractor()
                
                # Extract products
                products = extractor.extract_from_url(sky_url)
                
                if products:
                    st.session_state.sky_extraction_results = {
                        'products': products,
                        'url': sky_url,
                        'extraction_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'total_products': len(products)
                    }
                    
                    # If extract & compare button was clicked, perform comparison
                    if extract_compare_button:
                        source_of_truth_df = load_source_of_truth()
                        if source_of_truth_df is not None:
                            comparison_results = compare_prices(products, source_of_truth_df)
                            st.session_state.comparison_results = comparison_results
                            # st.success(f":material/check: Successfully extracted {len(products)} products and compared prices from {sky_url}")
                        else:
                            st.warning(":material/warning: Extraction successful but price comparison failed - no valid source of truth data")
                            st.session_state.comparison_results = None
                    else:
                        # st.success(f":material/check: Successfully extracted {len(products)} products from {sky_url}")
                        st.session_state.comparison_results = None
                else:
                    st.error(":material/error: No products found. Please check the URL or try a different Sky page.")
                    st.session_state.sky_extraction_results = None
                    st.session_state.comparison_results = None
                
            except Exception as e:
                st.error(f":material/error: Extraction failed: {str(e)}")
                st.session_state.sky_extraction_results = None
                st.session_state.comparison_results = None
            finally:
                st.session_state.sky_extraction_in_progress = False
    
        # Display results
        if st.session_state.sky_extraction_results:
            results = st.session_state.sky_extraction_results
            products = results['products']
            
            st.markdown("### :material/analytics: Extraction Results")
            
            # Display comparison results if available
            if st.session_state.comparison_results:
                st.markdown("#### :material/compare: Price Comparison Results")
                
                comparison_df = pd.DataFrame(st.session_state.comparison_results)
                
                # Summary metrics
                total_comparisons = len(comparison_df)
                matches = len(comparison_df[comparison_df['status'] == 'match'])
                mismatches = len(comparison_df[comparison_df['status'] == 'mismatch'])
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Comparisons", total_comparisons)
                
                with col2:
                    st.metric("Price Matches", matches)
                
                with col3:
                    st.metric("Price Mismatches", mismatches)
                
                with col4:
                    match_percentage = (matches / total_comparisons * 100) if total_comparisons > 0 else 0
                    st.metric("Match Rate", f"{match_percentage:.1f}%")
                
                # Display comparison table
                st.dataframe(
                    comparison_df,
                    use_container_width=True,
                    height=300,
                    column_config={
                        "product_name": st.column_config.TextColumn("Product Name", width="medium"),
                        "extracted_price": st.column_config.NumberColumn("Extracted Price", format="£%.2f"),
                        "source_price": st.column_config.NumberColumn("Source Price", format="£%.2f"),
                        "price_difference": st.column_config.NumberColumn("Difference", format="£%.2f"),
                        "price_difference_percent": st.column_config.NumberColumn("Difference %", format="%.1f%%"),
                        "status": st.column_config.TextColumn("Status", width="small"),
                        "source_product": st.column_config.TextColumn("Matched With", width="medium")
                    }
                )
                
                # Download comparison results
                comparison_csv = comparison_df.to_csv(index=False)
                st.download_button(
                    ":material/download: Download Comparison Results",
                    comparison_csv,
                    file_name=f"price_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.markdown("---")
        
        # Filter to only show products with prices for all statistics
        products_with_prices = [p for p in products if p.price and p.price.strip()]
        products_without_prices = [p for p in products if not p.price or not p.price.strip()]
        
        # Summary statistics - ONLY for products with prices
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Products with Prices", len(products_with_prices))
        
        with col2:
            categories = set(p.category for p in products_with_prices if p.category)
            st.metric("Categories", len(categories))
        
        with col3:
            products_with_cta = len([p for p in products_with_prices if p.cta_text])
            st.metric("Products with CTA", products_with_cta)
        
        with col4:
            products_with_images = len([p for p in products_with_prices if p.media_url])
            st.metric("Products with Images", products_with_images)
        
        # Category breakdown - ONLY for products with prices
        if categories:
            st.markdown("#### :material/bar_chart: Category Breakdown (Products with Prices)")
            category_counts = {}
            for product in products_with_prices:
                cat = product.category or 'Other'
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(category_counts)
            
            with col2:
                for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"• **{cat}**: {count} products")
        
        # Product details
        st.markdown("#### :material/shopping_bag: Product Details")
        
        # Filter options - ONLY for products with prices
        col1, col2, col3 = st.columns(3)
        
        with col1:
            category_filter = st.selectbox(
                "Filter by Category:",
                ["All"] + sorted(categories),
                key="sky_category_filter"
            )
        
        with col2:
            search_term = st.text_input(
                "Search products:",
                placeholder="Enter product name or feature...",
                key="sky_search_filter"
            )
        
        with col3:
            st.write("")  # Empty column for spacing
        
        # Apply filters - ONLY to products with prices
        filtered_products = products_with_prices.copy()
        
        if category_filter != "All":
            filtered_products = [p for p in filtered_products if p.category == category_filter]
        
        if search_term:
            search_lower = search_term.lower()
            filtered_products = [p for p in filtered_products if 
                               search_lower in p.name.lower() or 
                               search_lower in p.description.lower() or
                               any(search_lower in feature.lower() for feature in p.features)]
        
        st.write(f"Showing {len(filtered_products)} of {len(products_with_prices)} products with prices")
        
        # Display products with table first, then individual expanders
        if filtered_products:
            st.markdown(f"#### :material/attach_money: Products with Prices ({len(filtered_products)} products)")
            
            # Create table data
            table_data = []
            for product in filtered_products:
                # Extract media URL if it's a dictionary
                media_url = ""
                if product.media_url:
                    if isinstance(product.media_url, dict):
                        media_url = product.media_url.get('url') or product.media_url.get('src') or product.media_url.get('asset') or ""
                    elif isinstance(product.media_url, str):
                        media_url = product.media_url
                
                # Format features and included items
                features_text = ", ".join(product.features[:3]) if product.features else ""
                if product.features and len(product.features) > 3:
                    features_text += f" (+{len(product.features) - 3} more)"
                
                included_text = ", ".join(product.included_items[:2]) if product.included_items else ""
                if product.included_items and len(product.included_items) > 2:
                    included_text += f" (+{len(product.included_items) - 2} more)"
                
                table_data.append({
                    "Product Name": product.name,
                    "Category": product.category,
                    "Price": product.price_display or product.price,
                    "Original Price": product.original_price or "-",
                    "Discount": product.discount_info or "-",
                    "Offer Tag": product.offer_tag or "-",
                    "Description": product.description[:100] + "..." if len(product.description) > 100 else product.description,
                    "Features": features_text,
                    "Included Items": included_text,
                    "Contract": product.contract_info or "-",
                    "Availability": product.availability or "-",
                    "CTA": product.cta_text or "-",
                    "Image": ":material/check_circle:" if media_url else ":material/close:"
                })
            
            # Display as DataFrame
            # import pandas as pd
            df = pd.DataFrame(table_data)
            
            # Configure column display
            st.dataframe(
                df,
                use_container_width=True,
                height=400,
                column_config={
                    "Product Name": st.column_config.TextColumn(
                        "Product Name",
                        width="medium",
                        help="Name of the product/offer"
                    ),
                    "Category": st.column_config.TextColumn(
                        "Category",
                        width="small",
                        help="Product category"
                    ),
                    "Price": st.column_config.TextColumn(
                        "Price",
                        width="small",
                        help="Current price"
                    ),
                    "Original Price": st.column_config.TextColumn(
                        "Original Price",
                        width="small",
                        help="Original price before discount"
                    ),
                    "Discount": st.column_config.TextColumn(
                        "Discount",
                        width="small",
                        help="Discount amount or percentage"
                    ),
                    "Offer Tag": st.column_config.TextColumn(
                        "Offer Tag",
                        width="small",
                        help="Special offer tag"
                    ),
                    "Description": st.column_config.TextColumn(
                        "Description",
                        width="large",
                        help="Product description"
                    ),
                    "Features": st.column_config.TextColumn(
                        "Features",
                        width="medium",
                        help="Key features"
                    ),
                    "Included Items": st.column_config.TextColumn(
                        "Included",
                        width="medium",
                        help="Included items/services"
                    ),
                    "Contract": st.column_config.TextColumn(
                        "Contract",
                        width="small",
                        help="Contract terms"
                    ),
                    "Availability": st.column_config.TextColumn(
                        "Availability",
                        width="small",
                        help="Customer availability"
                    ),
                    "CTA": st.column_config.TextColumn(
                        "CTA",
                        width="small",
                        help="Call-to-action text"
                    ),
                    "Image": st.column_config.TextColumn(
                        "Image",
                        width="small",
                        help="Has product image"
                    )
                }
            )
            
            # Download table as CSV
            csv_data = df.to_csv(index=False)
            col1, col2 = st.columns([1, 1])
            with col1:
                st.download_button(
                    ":material/download: Download Table as CSV",
                    csv_data,
                    file_name=f"sky_products_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            st.markdown("#### :material/visibility: Detailed Product View")
            
            # Individual expanders for each product with prices
            for i, product in enumerate(filtered_products):
                # Extract media URL if it's a dictionary
                media_url = ""
                if product.media_url:
                    if isinstance(product.media_url, dict):
                        media_url = product.media_url.get('url') or product.media_url.get('src') or product.media_url.get('asset') or ""
                    elif isinstance(product.media_url, str):
                        media_url = product.media_url
                
                with st.expander(f":material/shopping_bag: {product.name} - {product.price_display or product.price}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Category:** {product.category}")
                        st.write(f"**Sub-category:** {product.sub_category}")
                        st.write(f"**Page Type:** {product.page_type}")
                        
                        st.write(f"**Price:** {product.price_display or product.price}")
                        if product.original_price:
                            st.write(f"**Original Price:** {product.original_price}")
                        if product.discount_info:
                            st.write(f"**Discount:** {product.discount_info}")
                        
                        if product.offer_tag:
                            st.write(f"**Offer Tag:** {product.offer_tag}")
                        
                        if product.primary_label:
                            st.write(f"**Label:** {product.primary_label}")
                        
                        if product.description:
                            st.write(f"**Description:** {product.description}")
                        
                        if product.contract_info:
                            st.write(f"**Contract:** {product.contract_info}")
                        
                        if product.availability:
                            st.write(f"**Availability:** {product.availability}")
                        
                        # Features and included items
                        if product.features:
                            st.write("**Features:**")
                            for feature in product.features:
                                st.write(f"• {feature}")
                        
                        if product.included_items:
                            st.write("**Included Items:**")
                            for item in product.included_items:
                                st.write(f"• {item}")
                    
                    with col2:
                        if media_url:
                            st.image(media_url, width=200, caption="Product Image")
                        
                        if product.cta_text and product.cta_link:
                            st.link_button(
                                f":material/link: {product.cta_text}",
                                product.cta_link,
                                use_container_width=True
                            )
            
            # Removed "Show Other Deals" section per request
        else:
            st.info("No products match the current filters.")
        
        # Export functionality
        st.markdown("#### :material/download: Export Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export as JSON
            json_data = json.dumps([p.to_dict() for p in products], indent=2, ensure_ascii=False)
            st.download_button(
                ":material/file_download: Download JSON",
                json_data,
                file_name=f"sky_deals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col2:
            # Export as CSV
            # import pandas as pd
            df = pd.DataFrame([p.to_dict() for p in products])
            csv_data = df.to_csv(index=False)
            st.download_button(
                ":material/table_chart: Download CSV",
                csv_data,
                file_name=f"sky_deals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col3:
            # Clear results
            if st.button(":material/clear: Clear Results", use_container_width=True, key="clear_sky_extraction_results"):
                st.session_state.sky_extraction_results = None
                st.rerun()
    
    elif st.session_state.sky_extraction_in_progress:
        st.info(":material/hourglass_empty: Extraction in progress... Please wait.")
    
    else:
        # # Show example URLs when no extraction has been performed
        # st.markdown("#### :material/lightbulb: Example URLs to Try")
        
        # example_urls = [
        #     "https://www.sky.com/deals",
        #     "https://www.sky.com/tv",
        #     "https://www.sky.com/broadband",
        #     "https://www.sky.com/mobile",
        #     "https://www.sky.com/tv/sky-glass",
        #     "https://www.sky.com/sports"
        # ]
        
        # st.markdown("**Click to copy URLs:**")
        # for url in example_urls:
        #     st.markdown(f"• `{url}`")
        
        st.markdown("""
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 400px;
            text-align: center;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border-radius: 15px;
            border: 2px dashed #dee2e6;
            margin-top: 20px;
        ">
            <h4 style="color: #6c757d; margin-bottom: 10px; font-weight: 600;">Ready to Validate Prices</h4>
            <p style="color: #6c757d; margin-bottom: 0; max-width: 400px;">
                Enter a Sky UK URL above or click one of the example URLs to start extracting product deals and offers.
            </p>
        </div>
        """, unsafe_allow_html=True)





