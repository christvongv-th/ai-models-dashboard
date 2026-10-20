import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import time
import io
import random
import urllib.request
import urllib.error
import urllib.parse

# ตั้งค่าหน้าเพจ
st.set_page_config(page_title="AI Models Dashboard", layout="wide")

st.title("📊 แดชบอร์ดสรุปโมเดล AI ยอดนิยมของแต่ละบริษัท (2026)")
st.write("เครื่องมือจำลองการเลือกและดูข้อมูลโมเดล AI ยอดนิยม พร้อมย้อนกลับเวอร์ชันได้ 2 เวอร์ชัน")

NOTE = "⚠️ ราคา คะแนน และ Benchmark เป็นค่าคร่าว ๆ (ประมาณการ ต.ค. 2026) กรุณาตรวจสอบล่าสุดจากเว็บไซต์ทางการของแต่ละเจ้า"

# อัตราแลกเปลี่ยน USD -> THB (แก้ไขได้ที่ sidebar)
USD_THB_DEFAULT = 35.0


def get_rate():
    try:
        return float(st.session_state.get("usd_thb", USD_THB_DEFAULT))
    except (TypeError, ValueError):
        return USD_THB_DEFAULT


def thb(usd):
    return usd * get_rate()


def fmt_usd(u):
    return f"${u:,.2f}"


def fmt_thb(u):
    return f"฿{u * get_rate():,.2f}"


def fmt_both(u):
    return f"${u:,.2f} ≈ ฿{u * get_rate():,.2f}"


def rate_caption():
    return f"💱 อัตราแลกเปลี่ยนที่ใช้: 1 USD = {get_rate()} บาท (เปลี่ยนได้ที่ Sidebar)"


# ชุด Prompt สำเร็จรูปสำหรับแท็บทดสอบแชต
PROMPT_TEMPLATES = {
    "💬 ทั่วไป (ค่าเริ่มต้น)": "เปรียบเทียบข้อดีข้อเสียของโมเดล AI แบบสั้น ๆ 3 ข้อ",
    "✍️ เขียนโค้ด": "เขียนฟังก์ชัน Python อ่านไฟล์ CSV แล้วหาค่าเฉลี่ยของคอลัมน์ตัวเลข พร้อมจัดการ error ให้ครบ ตอบเป็นโค้ดอย่างเดียว",
    "🇹🇭 แปลไทย-อังกฤษ": "แปลข้อความนี้เป็นภาษาอังกฤษอย่างเป็นธรรมชาติ: 'พรุ่งนี้เราต้องนำเสนองานลูกค้า ขอไฟล์สรุปตัวเลขยอดขายประจำไตรมาสให้หน่อย'",
    "📄 สรุปเอกสาร": "สรุปประเด็นสำคัญ 5 ข้อจากข้อความนี้แบบสั้นกระชับ: บริษัทหลายแห่งเริ่มนำ AI เข้ามาช่วยงานฝ่ายสนับสนุนลูกค้า โดยพบว่าเวลาตอบสนองลดลง 40% แต่พนักงานต้องได้รับการอบรมเพิ่มเติมเพื่อตรวจสอบคำตอบของ AI ก่อนส่งถึงลูกค้า",
    "🔢 คณิตศาสตร์/ตรรกะ": "มีลูกเต๋า 2 ลูก ทอยแล้วผลรวมมากกว่า 7 แต่น้อยกว่า 10 มีโอกาสเกิดขึ้นกี่เปอร์เซ็นต์? แสดงวิธีทำ",
    "🔍 รีวิวโค้ด": "รีวิวโค้ดนี้ ชี้จุดที่ควรแก้ (performance, security, readability):\n\ndef get_user(id):\n    import sqlite3\n    conn = sqlite3.connect('db.sqlite')\n    cur = conn.execute(f\"SELECT * FROM users WHERE id = {id}\")\n    return cur.fetchone()",
}

# ตารางสี Use-Case Matrix (คะแนนคร่าว ๆ 1-10 ต่อภารกิจ)
USECASE_TASKS = [
    "เขียนโค้ด", "ภาษาไทย/แปล", "สรุปเอกสารยาว", "มัลติมีเดีย (ภาพ/วิดีโอ)",
    "ค้นข้อมูลสด", "งบจำกัด", "ปรับแต่ง/Open Source", "ความเป็นส่วนตัว (On-premise)",
]
USECASE = {
    "OpenAI":       [9, 9, 9, 9, 6, 6, 4, 4],
    "Google":       [8, 9, 9, 10, 7, 7, 4, 5],
    "Anthropic":    [9, 9, 9, 7, 5, 5, 4, 5],
    "Microsoft":    [8, 7, 7, 6, 6, 8, 7, 7],
    "DeepSeek":     [9, 7, 7, 5, 5, 10, 9, 8],
    "Qwen":         [8, 7, 8, 6, 5, 9, 9, 7],
    "Perplexity":   [6, 8, 7, 5, 10, 7, 3, 6],
    "Meta AI":      [8, 7, 7, 5, 5, 9, 10, 10],
    "Nova (Amazon)": [7, 8, 7, 9, 5, 7, 4, 6],
    "xAI (Grok)":   [7, 6, 7, 7, 9, 6, 4, 5],
    "Mistral":      [8, 7, 7, 5, 5, 9, 9, 7],
    "Moonshot AI":  [7, 5, 9, 5, 5, 8, 8, 6],
    "Z.ai (Zhipu)": [8, 6, 7, 5, 5, 9, 9, 7],
    "NVIDIA":       [8, 5, 6, 6, 5, 8, 9, 8],
    "MiniMax":      [7, 5, 8, 7, 5, 9, 8, 7],
    "ByteDance Seed": [7, 6, 7, 8, 5, 10, 6, 6],
    "OpenRouter":   [8, 8, 8, 6, 7, 8, 5, 6],
}


def score_emoji(v):
    if v >= 9:
        return f"{v} 🟢"
    if v >= 7:
        return f"{v} 🟡"
    if v >= 5:
        return f"{v} 🟠"
    return f"{v} 🔴"


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def to_md_bytes(df):
    cols = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines).encode("utf-8")

# สร้างข้อมูลหลัก (Data)
data = {
    "OpenAI": {
        "series": "GPT-4 / GPT-4o",
        "thai_support": "ดีเยี่ยม (Excellent)",
        "web_ui": "ChatGPT",
        "api_paid": "GPT-4o, GPT-4o-mini",
        "api_free": "ไม่มี (มีโควต้าฟรีจำกัดสำหรับบัญชีใหม่)",
        "features": "เข้าใจบริบทซับซ้อน, วิเคราะห์ภาพ/เสียง/โค้ด (Multimodal), ให้เหตุผลขั้นสูง (Reasoning)",
        "use_case": "งานวิเคราะห์ข้อมูลเชิงลึก, พัฒนาแอปพลิเคชันอัจฉริยะ, แชตบอตองค์กร",
        "versions": ["GPT-4o (Current)", "GPT-4 Turbo (v-1)", "GPT-4 (v-2)"],
        "price_in": 2.50, "price_out": 10.00,
        "context": 128000,
        "open_source": False, "free_api": False, "thai_score": 3,
        "scores": {"ภาษาไทย": 9, "โค้ด": 9, "ราคา": 6, "เหตุผล": 9},
        "benchmarks": {"MMLU": 88.7, "GPQA": 53.6, "HumanEval": 90.2},
        "updated": "ต.ค. 2026",
        "signup": "https://platform.openai.com/signup",
    },
    "Google": {
        "series": "Gemini",
        "thai_support": "ดีเยี่ยม (Excellent)",
        "web_ui": "Gemini (ชื่อเดิม Bard)",
        "api_paid": "Gemini 1.5 Pro, Gemini 1.5 Flash",
        "api_free": "Gemini 1.5 Flash (มีโควต้าฟรีผ่าน Google AI Studio)",
        "features": "รองรับบริบทขนาดใหญ่มาก (Context Window สูงสุด 2M tokens), วิเคราะห์วิดีโอและไฟล์ขนาดใหญ่",
        "use_case": "งานที่ต้องประมวลผลเอกสารจำนวนมาก, สรุปวิดีโอยาว, งานประมวลผลมัลติมีเดีย",
        "versions": ["Gemini 1.5 (Current)", "Gemini 1.0 Pro (v-1)", "PaLM 2 (v-2)"],
        "price_in": 1.25, "price_out": 10.00,
        "context": 2000000,
        "open_source": False, "free_api": True, "thai_score": 3,
        "scores": {"ภาษาไทย": 9, "โค้ด": 8, "ราคา": 7, "เหตุผล": 8},
        "benchmarks": {"MMLU": 88.0, "GPQA": 59.1, "HumanEval": 84.1},
        "updated": "ต.ค. 2026",
        "signup": "https://aistudio.google.com/",
    },
    "Anthropic": {
        "series": "Claude 3 / 3.5",
        "thai_support": "ดีเยี่ยม (Excellent - เด่นด้านภาษาเขียนสละสลวย)",
        "web_ui": "Claude.ai",
        "api_paid": "Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus",
        "api_free": "ไม่มี (ต้องใช้ผ่าน Web UI แบบจำกัด หรือพาร์ทเนอร์)",
        "features": "เขียนบทความสละสลวย, เขียนและแก้ไขโค้ดแม่นยำสูง (Artifacts), มีความปลอดภัยและจริยธรรมสูง",
        "use_case": "งานเขียนคอนเทนต์, งานเขียนโปรแกรม/ตรวจสอบโค้ด, งานวิจัยที่ต้องการความถูกต้องเชิงตรรกะ",
        "versions": ["Claude 3.5 (Current)", "Claude 3.0 (v-1)", "Claude 2.1 (v-2)"],
        "price_in": 3.00, "price_out": 15.00,
        "context": 200000,
        "open_source": False, "free_api": False, "thai_score": 3,
        "scores": {"ภาษาไทย": 9, "โค้ด": 9, "ราคา": 6, "เหตุผล": 8},
        "benchmarks": {"MMLU": 88.7, "GPQA": 65.0, "HumanEval": 93.7},
        "updated": "ต.ค. 2026",
        "signup": "https://console.anthropic.com/",
    },
    "Microsoft": {
        "series": "Phi / Copilot",
        "thai_support": "ดี (ผ่านระบบ Copilot)",
        "web_ui": "Microsoft Copilot (ชื่อเดิม Bing Chat)",
        "api_paid": "Azure OpenAI Services",
        "api_free": "Phi-3 (โมเดลขนาดเล็ก รันฟรีแบบ Open Source)",
        "features": "เน้นการทำงานร่วมกับระบบปฏิบัติการและโปรแกรม Office, โมเดลขนาดเล็ก (SLM) ที่มีประสิทธิภาพสูง",
        "use_case": "งานออฟฟิศอัตโนมัติ, รันโมเดลบนอุปกรณ์ขนาดเล็ก (Edge Devices)",
        "versions": ["Phi-3 / Copilot (Current)", "Phi-2 (v-1)", "Phi-1.5 (v-2)"],
        "price_in": 2.50, "price_out": 10.00,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 7, "โค้ด": 8, "ราคา": 8, "เหตุผล": 7},
        "benchmarks": {"MMLU": 79.0, "GPQA": 37.0, "HumanEval": 63.0},
        "updated": "ต.ค. 2026",
        "signup": "https://portal.azure.com/",
        "price_note": "รัน Phi เองฟรี / ใช้ผ่าน Azure ในราคาเดียวกับ OpenAI",
    },
    "DeepSeek": {
        "series": "DeepSeek-V3 / DeepSeek-R1",
        "thai_support": "ดี (รองรับภาษาไทยปานกลางถึงดี)",
        "web_ui": "DeepSeek Chat",
        "api_paid": "DeepSeek API (ราคาถูกมาก)",
        "api_free": "DeepSeek-R1, DeepSeek-V3 (Open Source ดาวน์โหลดฟรี)",
        "features": "เชี่ยวชาญการให้เหตุผลเชิงตรรกะ (Reasoning) และคณิตศาสตร์, โค้ดเก่ง, ต้นทุน API ต่ำ",
        "use_case": "งานวิจัยคณิตศาสตร์และตรรกะ, พัฒนาแอปด้วยงบจำกัด, ฝึก/ปรับแต่งโมเดลเอง",
        "versions": ["DeepSeek-R1 / V3 (Current)", "DeepSeek-V2 (v-1)", "DeepSeek-Coder (v-2)"],
        "price_in": 0.27, "price_out": 1.10,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 7, "โค้ด": 9, "ราคา": 10, "เหตุผล": 9},
        "benchmarks": {"MMLU": 90.0, "GPQA": 71.5, "HumanEval": 85.0},
        "updated": "ต.ค. 2026",
        "signup": "https://platform.deepseek.com/",
    },
    "Qwen": {
        "series": "Qwen 2.5 / QwQ",
        "thai_support": "ดี (รองรับหลายภาษาจำนวนมาก)",
        "web_ui": "Qwen Chat (Tongyi Lingma)",
        "api_paid": "DashScope (Alibaba Cloud)",
        "api_free": "Qwen 2.5 (Open Source หลายขนาด ดาวน์โหลดฟรี)",
        "features": "รองรับภาษาหลายภาษา, โมเดลเปิดที่เก่งด้านโค้ดและคณิตศาสตร์, มีเวอร์ชัน Reasoning (QwQ)",
        "use_case": "งานที่ต้องรองรับหลายภาษา, พัฒนาแอปในจีน/เอเชีย, ปรับแต่งโมเดลเอง",
        "versions": ["Qwen 2.5 / QwQ (Current)", "Qwen 2 (v-1)", "Qwen 1.5 (v-2)"],
        "price_in": 0.40, "price_out": 1.20,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 7, "โค้ด": 8, "ราคา": 9, "เหตุผล": 7},
        "benchmarks": {"MMLU": 86.0, "GPQA": 49.0, "HumanEval": 86.0},
        "updated": "ต.ค. 2026",
        "signup": "https://dashscope.console.aliyun.com/",
    },
    "Perplexity": {
        "series": "Sonar (อิง GPT/Claude)",
        "thai_support": "ดี (รองรับภาษาไทยผ่านการค้นหา)",
        "web_ui": "Perplexity AI",
        "api_paid": "Sonar API (ต่อจำนวนคำขอ)",
        "api_free": "ใช้ Perplexity ฟรี (มีโควต้า Pro จำกัด)",
        "features": "ค้นหาเว็บแบบเรียลไทม์พร้อมอ้างอิงแหล่งที่มา (Citations), ตอบคำถามตามข้อมูลปัจจุบัน",
        "use_case": "ค้นคว้าข้อมูลและอ้างอิงแหล่งที่มา, ติดตามข่าวสารล่าสุด, งานวิจัยเบื้องต้น",
        "versions": ["Sonar (Current)", "PPLX Models (v-1)", "Perplexity Classic (v-2)"],
        "price_in": 1.00, "price_out": 1.00,
        "context": 131072,
        "open_source": False, "free_api": True, "thai_score": 3,
        "scores": {"ภาษาไทย": 8, "โค้ด": 6, "ราคา": 7, "เหตุผล": 7},
        "benchmarks": {"MMLU": 85.0, "GPQA": 48.0, "HumanEval": 80.0},
        "updated": "ต.ค. 2026",
        "signup": "https://www.perplexity.ai/",
    },
    "Meta AI": {
        "series": "Llama 3.1 / 3.2 / 4",
        "thai_support": "ปานกลางถึงดี (รองรับภาษาไทยในเวอร์ชันหลังๆ)",
        "web_ui": "Meta AI (Facebook, Instagram, WhatsApp)",
        "api_paid": "ผ่านพาร์ทเนอร์คลาวด์ (Groq, AWS, Together AI)",
        "api_free": "Llama (Open Source ดาวน์โหลดไปรันเองได้)",
        "features": "โมเดลเปิด (Open Source) ปรับแต่งง่าย (Fine-tuning), ประสิทธิภาพสูงเมื่อเทียบกับขนาดโมเดล, มีโมเดลขนาดเล็กสำหรับอุปกรณ์พกพา",
        "use_case": "ปรับแต่งโมเดลใช้เองในองค์กร (On-premise), งานที่ต้องการความเป็นส่วนตัวของข้อมูล",
        "versions": ["Llama 4 / 3.1 (Current)", "Llama 3.0 (v-1)", "Llama 2 (v-2)"],
        "price_in": 0.59, "price_out": 0.79,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 7, "โค้ด": 8, "ราคา": 9, "เหตุผล": 7},
        "benchmarks": {"MMLU": 88.6, "GPQA": 51.0, "HumanEval": 89.0},
        "updated": "ต.ค. 2026",
        "signup": "https://www.llama.com/",
        "price_note": "ราคาตัวอย่างผ่าน Groq (Llama 3.3 70B) - รันเองฟรี",
    },
    "Nova (Amazon)": {
        "series": "Amazon Nova",
        "thai_support": "ดี (รองรับหลายภาษาผ่าน Amazon Bedrock)",
        "web_ui": "Amazon Bedrock / Nova Canvas",
        "api_paid": "Amazon Bedrock (AWS)",
        "api_free": "มีโควต้าทดลองฟรีบน AWS Free Tier",
        "features": "ครอบคลุมทั้งแชต (Micro/Pro), สร้างภาพ (Canvas), สร้างวิดีโอ (Reel), เชื่อมกับระบบนิเวศ AWS",
        "use_case": "งานในองค์กรที่ใช้ AWS, สร้างภาพ/วิดีโอเชิงพาณิชย์, แอปที่ต้องการสเกลบนคลาวด์",
        "versions": ["Amazon Nova (Current)", "Titan /第三方 Models (v-1)", "Amazon Lex/Compose (v-2)"],
        "price_in": 0.80, "price_out": 3.20,
        "context": 300000,
        "open_source": False, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 8, "โค้ด": 7, "ราคา": 7, "เหตุผล": 7},
        "benchmarks": {"MMLU": 79.0, "GPQA": 40.0, "HumanEval": 75.0},
        "updated": "ต.ค. 2026",
        "signup": "https://console.aws.amazon.com/bedrock/",
        "price_note": "ราคา Nova Pro ต่อ 1M tokens บน Bedrock",
    },
    "xAI (Grok)": {
        "series": "Grok 3 / 4",
        "thai_support": "ปานกลาง (รองรับภาษาไทยพอใช้)",
        "web_ui": "Grok (X / Twitter)",
        "api_paid": "xAI API",
        "api_free": "จำกัดบน X (ผู้ใช้ Premium ได้สิทธิ์มากกว่า)",
        "features": "เข้าถึงข้อมูลโซเชียลเรียลไทม์บน X, น้ำเสียงทะลึ่ง/อารมณ์ขัน, เชี่ยวชาญ Reasoning และคณิตศาสตร์",
        "use_case": "ติดตามเทรนด์โซเชียลเรียลไทม์, งานวิเคราะห์เชิงเหตุผล, ทดลองโมเดลรุ่นใหม่",
        "versions": ["Grok 4 / 3 (Current)", "Grok 2 (v-1)", "Grok 1 (v-2)"],
        "price_in": 3.00, "price_out": 15.00,
        "context": 262144,
        "open_source": "บางส่วน", "free_api": False, "thai_score": 2,
        "scores": {"ภาษาไทย": 6, "โค้ด": 7, "ราคา": 6, "เหตุผล": 8},
        "benchmarks": {"MMLU": 90.0, "GPQA": 75.0, "HumanEval": 85.0},
        "updated": "ต.ค. 2026",
        "signup": "https://console.x.ai/",
        "price_note": "Grok 1 เป็น Open Source (บางส่วน)",
    },
    "Mistral": {
        "series": "Mistral Large / Mixtral",
        "thai_support": "ปานกลาง (รองรับหลายภาษา)",
        "web_ui": "Le Chat (Mistral Chat)",
        "api_paid": "Mistral API / La Plateforme",
        "api_free": "Mixtral 8x7B (Open Source ดาวน์โหลดฟรี)",
        "features": "โมเดลเปิดประสิทธิภาพสูงจากยุโรป, โมเดลแบบ Mixture-of-Experts ประหยัดค่าใช้จ่าย, รองรับ Function Calling",
        "use_case": "งานในยุโรปที่ต้องปฏิบัติตาม GDPR, พัฒนาแอปด้วยโมเดลเปิด, ต้นทุน API ต่ำ",
        "versions": ["Mistral Large / Mixtral (Current)", "Mistral Medium (v-1)", "Mistral 7B (v-2)"],
        "price_in": 2.00, "price_out": 6.00,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 7, "โค้ด": 8, "ราคา": 9, "เหตุผล": 7},
        "benchmarks": {"MMLU": 84.0, "GPQA": 46.0, "HumanEval": 82.0},
        "updated": "ต.ค. 2026",
        "signup": "https://console.mistral.ai/",
    },
    "Moonshot AI": {
        "series": "Kimi (k1.5 / K2)",
        "thai_support": "ปานกลาง (เด่นด้านภาษาจีน)",
        "web_ui": "Kimi Chat",
        "api_paid": "Moonshot API",
        "api_free": "Kimi (ใช้ฟรีบนเว็บพร้อมโควต้า)",
        "features": "รองรับบริบทยาวมาก (Long Context สูงสุด ~2M tokens), เก่งด้านภาษาจีน, มีโมเดล Reasoning (k1.5)",
        "use_case": "ประมวลผลเอกสาร/โค้ดขนาดยาว, งานที่เกี่ยวกับภาษาจีน, วิเคราะห์ข้อมูลจำนวนมาก",
        "versions": ["Kimi K2 / k1.5 (Current)", "Moonshot v1 (v-1)", "Moonshot 120K (v-2)"],
        "price_in": 0.60, "price_out": 2.50,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 1,
        "scores": {"ภาษาไทย": 5, "โค้ด": 7, "ราคา": 8, "เหตุผล": 7},
        "benchmarks": {"MMLU": 92.0, "GPQA": 60.0, "HumanEval": 90.0},
        "updated": "ต.ค. 2026",
        "signup": "https://platform.moonshot.ai/",
        "price_note": "Kimi K2 เป็น Open Source",
    },
    "Z.ai (Zhipu)": {
        "series": "GLM-4 / GLM-4.5 / GLM-4.6",
        "thai_support": "ปานกลางถึงดี (รองรับหลายภาษา)",
        "web_ui": "ChatGLM / Z.ai",
        "api_paid": "GLM-4.5, GLM-4.6, GLM-4-Plus",
        "api_free": "GLM-4-Flash (ฟรี) + โมเดล Open Source (GLM-4-9B, GLM-4.5-Air)",
        "features": "โมเดลจีนประสิทธิภาพสูงระดับใกล้เคียง GPT-4 แต่ราคาถูกกว่า, เก่งด้านโค้ดและ Agent, มีโมเดลเปิดให้ดาวน์โหลด",
        "use_case": "งานที่ต้องการคุณภาพสูงด้วยงบต่ำ, พัฒนา Agent/เขียนโค้ด, ตลาดจีนและเอเชีย",
        "versions": ["GLM-4.5 / 4.6 (Current)", "GLM-4-Plus (v-1)", "GLM-3 (v-2)"],
        "price_in": 0.60, "price_out": 2.20,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 6, "โค้ด": 8, "ราคา": 9, "เหตุผล": 8},
        "benchmarks": {"MMLU": 87.0, "GPQA": 60.0, "HumanEval": 88.0},
        "updated": "ต.ค. 2026",
        "signup": "https://z.ai/",
        "price_note": "GLM-4-Flash ใช้ฟรี / โมเดลเปิดดาวน์โหลดเองฟรี",
    },
    "NVIDIA": {
        "series": "Nemotron / NIM",
        "thai_support": "ปานกลาง (ขึ้นกับโมเดลเปิดที่เลือก)",
        "web_ui": "NVIDIA NIM (chat.nvidia.com)",
        "api_paid": "NVIDIA API Catalog (NIM) — มีทั้งแบบฟรีและจ่ายรายเดือน",
        "api_free": "NIM Microservices + โมเดลเปิด (Nemotron, Llama รุ่นปรับแต่ง) ดาวน์โหลดฟรี",
        "features": "รวมโมเดลเปิดประสิทธิภาพสูง, ปรับ optimize สำหรับ GPU NVIDIA (TensorRT), มี API ฟรีให้ทดลอง, น้ำหนักโมเดลเปิดทั้งหมด",
        "use_case": "รัน inference บน GPU ให้เร็ว/คุ้มที่สุด, สร้างโมเดลเฉพาะอุตสาหกรรม, งานที่ต้องการ open weights",
        "versions": ["Nemotron Ultra / Super (Current)", "Nemotron 4 (v-1)", "NIM / Megatron (v-2)"],
        "price_in": 0.80, "price_out": 0.80,
        "context": 131072,
        "open_source": True, "free_api": True, "thai_score": 1,
        "scores": {"ภาษาไทย": 5, "โค้ด": 8, "ราคา": 8, "เหตุผล": 8},
        "benchmarks": {"MMLU": 85.0, "GPQA": 55.0, "HumanEval": 80.0},
        "updated": "ต.ค. 2026",
        "signup": "https://build.nvidia.com/",
        "price_note": "หลาย endpoint ฟรีบน NIM / รันเองฟรี (โมเดลเปิด)",
    },
    "MiniMax": {
        "series": "MiniMax M1 / M2 / Text-01",
        "thai_support": "ปานกลาง (รองรับหลายภาษา)",
        "web_ui": "MiniMax Chat / Hailuo AI",
        "api_paid": "MiniMax API (ราคาถูก, context ยาว)",
        "api_free": "มีโควต้าทดลอง + Hailuo ใช้ฟรีบางส่วน",
        "features": "โมเดลเปิดขนาดใหญ่แบบ MoE (M1) ที่รองรับบริบทยาวถึง 1 ล้าน tokens, ราคาถูก, เก่งภาษาจีน และสร้างวิดีโอ (Hailuo)",
        "use_case": "งานที่ต้องประมวลผลบริบทยาวมาก, ตลาดจีน/เอเชีย, สร้างวิดีโอ, ต้นทุนต่ำ",
        "versions": ["MiniMax M2 / M1 (Current)", "MiniMax Text-01 (v-1)", "abab (v-2)"],
        "price_in": 0.30, "price_out": 1.20,
        "context": 1000000,
        "open_source": True, "free_api": True, "thai_score": 1,
        "scores": {"ภาษาไทย": 5, "โค้ด": 7, "ราคา": 9, "เหตุผล": 7},
        "benchmarks": {"MMLU": 85.0, "GPQA": 50.0, "HumanEval": 78.0},
        "updated": "ต.ค. 2026",
        "signup": "https://www.minimax.io/",
        "price_note": "M1 เป็น Open Source (น้ำหนักเปิด) / ราคาคร่าว ๆ",
    },
    "ByteDance Seed": {
        "series": "Seed 1.6 / Doubao (豆包)",
        "thai_support": "ปานกลางถึงดี (รองรับหลายภาษาผ่าน Doubao)",
        "web_ui": "Doubao (豆包)",
        "api_paid": "Volcengine Ark (Doubao / Seed)",
        "api_free": "มีโควต้าทดลองฟรีบน Volcengine",
        "features": "โมเดลจาก ByteDance (เจ้าของ TikTok/Doubao), Seed 1.6 ประสิทธิภาพระดับ frontier ในราคาถูกมาก, รองรับข้อความ/ภาพ",
        "use_case": "งานทั่วไปราคาถูกมาก, ระบบองค์กรบน Volcengine, ตลาดจีน/เอเชีย",
        "versions": ["Seed 1.6 (Current)", "Doubao 1.5 (v-1)", "Seed 1.0 (v-2)"],
        "price_in": 0.15, "price_out": 0.60,
        "context": 262144,
        "open_source": False, "free_api": True, "thai_score": 2,
        "scores": {"ภาษาไทย": 6, "โค้ด": 7, "ราคา": 10, "เหตุผล": 7},
        "benchmarks": {"MMLU": 87.0, "GPQA": 58.0, "HumanEval": 82.0},
        "updated": "ต.ค. 2026",
        "signup": "https://console.volcengine.com/ark",
        "price_note": "ราคาบน Volcengine Ark (ราคาถูกมากในจีน)",
    },
    "OpenRouter": {
        "series": "Auto Router (รวมทุกโมเดล)",
        "thai_support": "ดีเยี่ยม (เท่ากับโมเดลต้นทางที่เลือกใช้)",
        "web_ui": "OpenRouter Chat",
        "api_paid": "ราคาตามผู้ให้บริการต้นทาง + ค่าธรรมเนียม routing ~5%",
        "api_free": "มีโมเดลฟรี (`:free`) หลายตัว เช่น Llama, GPT-OSS",
        "features": "คีย์เดียวเรียกได้ทุกโมเดลทุกเจ้า, สลับผู้ให้บริการอัตโนมัติ, เปรียบเทียบราคา/ความเร็วได้, ไม่ต้องสมัครหลายที่",
        "use_case": "ทดสอบหลายโมเดลในที่เดียว, เปรียบเทียบราคา/คุณภาพ, ลดภาระรวม API หลายเจ้า, ทดลองโมเดลใหม่ก่อนใคร",
        "versions": ["Auto Router (Current)", "Provider Routing (v-1)", "Classic API (v-2)"],
        "price_in": 2.50, "price_out": 10.00,
        "context": 200000,
        "open_source": False, "free_api": True, "thai_score": 3,
        "scores": {"ภาษาไทย": 8, "โค้ด": 8, "ราคา": 7, "เหตุผล": 8},
        "benchmarks": {"MMLU": 88.0, "GPQA": 60.0, "HumanEval": 88.0},
        "updated": "ต.ค. 2026",
        "signup": "https://openrouter.ai/",
        "price_note": "ราคาเปลี่ยนตามโมเดลต้นทาง (แสดงตัวอย่างเท่า GPT-4o) + ค่าธรรมเนียม ~5%",
    },
}

providers = list(data.keys())

# ประเทศต้นกำเนิดของแต่ละ Provider
COUNTRIES = {
    "OpenAI": "สหรัฐอเมริกา 🇺🇸",
    "Google": "สหรัฐอเมริกา 🇺🇸",
    "Anthropic": "สหรัฐอเมริกา 🇺🇸",
    "Microsoft": "สหรัฐอเมริกา 🇺🇸",
    "DeepSeek": "จีน 🇨🇳",
    "Qwen": "จีน 🇨🇳 (Alibaba)",
    "Perplexity": "สหรัฐอเมริกา 🇺🇸",
    "Meta AI": "สหรัฐอเมริกา 🇺🇸",
    "Nova (Amazon)": "สหรัฐอเมริกา 🇺🇸",
    "xAI (Grok)": "สหรัฐอเมริกา 🇺🇸",
    "Mistral": "ฝรั่งเศส 🇫🇷 (ยุโรป)",
    "Moonshot AI": "จีน 🇨🇳",
    "Z.ai (Zhipu)": "จีน 🇨🇳",
    "NVIDIA": "สหรัฐอเมริกา 🇺🇸",
    "MiniMax": "จีน 🇨🇳",
    "ByteDance Seed": "จีน 🇨🇳 (ByteDance)",
    "OpenRouter": "สหรัฐอเมริกา 🇺🇸",
}

# endpoint แบบ OpenAI-compatible สำหรับแท็บทดสอบแชต (None = ไม่มี API ตรง ต้องใช้ OpenRouter)
CHAT_ENDPOINTS = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o"),
    "Google": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "Anthropic": ("https://api.anthropic.com/v1", "claude-sonnet-4-5"),
    "Microsoft": None,
    "DeepSeek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "Qwen": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "Perplexity": ("https://api.perplexity.ai", "sonar"),
    "Meta AI": None,
    "Nova (Amazon)": None,
    "xAI (Grok)": ("https://api.x.ai/v1", "grok-3"),
    "Mistral": ("https://api.mistral.ai/v1", "mistral-large-latest"),
    "Moonshot AI": ("https://api.moonshot.ai/v1", "kimi-k2-0711-preview"),
    "Z.ai (Zhipu)": ("https://api.z.ai/api/paas/v4", "glm-4.5"),
    "NVIDIA": ("https://integrate.api.nvidia.com/v1", "nvidia/llama-3.1-nemotron-70b-instruct"),
    "MiniMax": ("https://api.minimax.io/v1", "MiniMax-M1"),
    "ByteDance Seed": ("https://ark.cn-beijing.volces.com/api/v3", "doubao-1-5-pro-32k"),
    "OpenRouter": ("https://openrouter.ai/api/v1", "openrouter/auto"),
}

# โมเดลตั้งต้นบน OpenRouter (แก้ไขได้ในหน้าจอ)
OPENROUTER_MODELS = {
    "OpenAI": "openai/gpt-4o",
    "Google": "google/gemini-2.5-flash",
    "Anthropic": "anthropic/claude-sonnet-4.5",
    "Microsoft": "microsoft/phi-4",
    "DeepSeek": "deepseek/deepseek-chat-v3-0324",
    "Qwen": "qwen/qwen3-235b-a22b",
    "Perplexity": "perplexity/sonar",
    "Meta AI": "meta-llama/llama-3.3-70b-instruct",
    "Nova (Amazon)": "amazon/nova-pro-v1",
    "xAI (Grok)": "x-ai/grok-3-mini",
    "Mistral": "mistralai/mistral-large-2411",
    "Moonshot AI": "moonshotai/kimi-k2",
    "Z.ai (Zhipu)": "z-ai/glm-4.5-air",
    "NVIDIA": "nvidia/nemotron-ultra-253b",
    "MiniMax": "minimax/minimax-m1",
    "ByteDance Seed": "bytedance-seed/seed-1.6",
    "OpenRouter": "openrouter/auto",
}

OPENROUTER_PREFIX = {
    "openai": "OpenAI",
    "google": "Google",
    "anthropic": "Anthropic",
    "microsoft": "Microsoft",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "perplexity": "Perplexity",
    "meta-llama": "Meta AI",
    "amazon": "Nova (Amazon)",
    "x-ai": "xAI (Grok)",
    "mistralai": "Mistral",
    "moonshotai": "Moonshot AI",
    "z-ai": "Z.ai (Zhipu)",
    "nvidia": "NVIDIA",
    "minimax": "MiniMax",
    "bytedance-seed": "ByteDance Seed",
    "openrouter": "OpenRouter",
}

# ลิงก์เว็บแชตฟรี (ไม่ต้องใช้ API Key) ของแต่ละ Provider
WEB_CHAT = {
    "OpenAI": "https://chatgpt.com/",
    "Google": "https://gemini.google.com/app",
    "Anthropic": "https://claude.ai/new",
    "Microsoft": "https://copilot.microsoft.com/",
    "DeepSeek": "https://chat.deepseek.com/",
    "Qwen": "https://chat.qwen.ai/",
    "Perplexity": "https://www.perplexity.ai/",
    "Meta AI": "https://www.meta.ai/",
    "Nova (Amazon)": "https://console.aws.amazon.com/bedrock/",
    "xAI (Grok)": "https://grok.com/",
    "Mistral": "https://chat.mistral.ai/chat",
    "Moonshot AI": "https://www.kimi.com/",
    "Z.ai (Zhipu)": "https://chat.z.ai/",
    "NVIDIA": "https://chat.nvidia.com/",
    "MiniMax": "https://www.minimax.io/",
    "ByteDance Seed": "https://www.doubao.com/",
    "OpenRouter": "https://openrouter.ai/chat",
}


def fmt_tokens(n):
    if n >= 1000000:
        return f"{n / 1000000:g}M tokens"
    return f"{int(n / 1000):d}K tokens"


def avg_score(info):
    s = info["scores"]
    return round(sum(s.values()) / len(s), 1)


def call_chat(base_url, api_key, model, prompt, system="", temperature=0.7, timeout=90):
    messages = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {detail[:300]}")
    elapsed = time.time() - t0
    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {}) or {}
    return content, elapsed, usage


def fetch_openrouter_models():
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"User-Agent": "ai-models-dashboard/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["data"]


def fetch_ollama_tags():
    req = urllib.request.Request(
        "http://localhost:11434/api/tags",
        headers={"User-Agent": "ai-models-dashboard/1.0"},
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode("utf-8")).get("models", [])


def fetch_hn_news(query="LLM", hits=15):
    url = (
        "https://hn.algolia.com/api/v1/search?"
        + urllib.parse.urlencode({"query": query, "tags": "story", "hitsPerPage": hits})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ai-models-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8")).get("hits", [])


def build_live_overlay(models):
    groups = {}
    for m in models or []:
        mid = m.get("id") or ""
        prefix = mid.split("/")[0] if "/" in mid else ""
        prov = OPENROUTER_PREFIX.get(prefix)
        if not prov:
            continue
        try:
            pin = float(m.get("pricing", {}).get("prompt", 0) or 0) * 1_000_000
            pout = float(m.get("pricing", {}).get("completion", 0) or 0) * 1_000_000
        except (TypeError, ValueError):
            pin = pout = 0.0
        groups.setdefault(prov, []).append({
            "id": mid,
            "name": m.get("name") or mid,
            "pin": pin,
            "pout": pout,
            "ctx": int(m.get("context_length") or 0),
            "created": float(m.get("created") or 0),
        })

    overlay = {}
    for prov, ms in groups.items():
        priced = [x for x in ms if x["pin"] > 0]
        if not priced:
            continue
        # รุ่นเรือธง = 3 ราคาสูงสุด แล้วเลือกใหม่ที่สุดในกลุ่มนั้น
        top3 = sorted(priced, key=lambda x: -x["pin"])[:3]
        flagship = max(top3, key=lambda x: x["created"])
        overlay[prov] = {
            "series": flagship["name"],
            "current": flagship["name"],
            "current_id": flagship["id"],
            "price_in": round(flagship["pin"], 2),
            "price_out": round(flagship["pout"], 2),
            "context": flagship["ctx"],
        }
    return overlay


def apply_live_update(data_dict, models, date_str):
    overlay = build_live_overlay(models)
    count = 0
    for prov, upd in overlay.items():
        d = data_dict.get(prov)
        if not d:
            continue
        d["series"] = upd["series"]
        d["price_in"] = upd["price_in"]
        d["price_out"] = upd["price_out"]
        if upd["context"]:
            d["context"] = upd["context"]
        prev = [x.replace("(Current)", "(ก่อนหน้า)") for x in d["versions"][:2]]
        d["versions"] = [f"{upd['current']} (Current · สด)"] + prev
        d["updated"] = date_str
        d["source"] = "🌐 OpenRouter สด"
        d["live_id"] = upd["current_id"]
        count += 1
    return count, len(overlay)


# ดึงข้อมูลภายนอกอัตโนมัติครั้งแรกที่เปิดแอป
if not st.session_state.get("auto_or"):
    st.session_state["auto_or"] = True
    try:
        st.session_state["or_models"] = fetch_openrouter_models()
        st.session_state["or_fetched_at"] = time.strftime("%d/%m/%Y %H:%M")
    except Exception:
        st.session_state["or_models"] = None

if not st.session_state.get("auto_ollama"):
    st.session_state["auto_ollama"] = True
    try:
        st.session_state["ollama_tags"] = fetch_ollama_tags()
    except Exception:
        st.session_state["ollama_tags"] = None

if not st.session_state.get("auto_news"):
    st.session_state["auto_news"] = True
    try:
        st.session_state["hn_news"] = fetch_hn_news("LLM")
        st.session_state["news_query"] = "LLM"
    except Exception:
        st.session_state["hn_news"] = None

# ใช้ข้อมูลสดก่อนสร้าง widget ใด ๆ เพื่อให้ทุกแท็บเห็นค่าล่าสุดทันที
if st.session_state.get("live_auto", True) and st.session_state.get("or_models"):
    apply_live_update(
        data, st.session_state["or_models"], st.session_state.get("or_fetched_at", "-")
    )


# ส่วนกรองข้อมูล (Sidebar Filters)
st.sidebar.header("🛠️ ตัวเลือกตัวกรองแผงควบคุม")

selected_provider = st.sidebar.selectbox("เลือกผู้ให้บริการ (Provider)", providers)

available_versions = data[selected_provider]["versions"]
selected_version = st.sidebar.selectbox(
    f"เลือกเวอร์ชันของ {selected_provider} (ย้อนหลังได้ 2 เวอร์ชัน)", available_versions
)

st.sidebar.markdown("---")
st.sidebar.info("💡 คุณสามารถเลือกเปลี่ยน Provider และ เวอร์ชันย้อนหลังได้ที่เมนูด้านบนนี้")

# ตั้งค่าอัตราแลกเปลี่ยน + Provider โปรด
st.sidebar.markdown("---")
st.sidebar.header("💱 อัตราแลกเปลี่ยน & 📌 ผู้โปรด")
st.sidebar.number_input(
    "อัตราแลกเปลี่ยน USD -> THB (บาท/ดอลลาร์)",
    min_value=20.0, max_value=60.0, value=USD_THB_DEFAULT, step=0.25,
    key="usd_thb", format="%.2f",
)
st.sidebar.caption(f"ปัจจุบัน 1 USD = {get_rate()} บาท — ค่าทุกค่าในระบบจะแสดงทั้ง USD และบาทไทย")

favorites = st.sidebar.multiselect("📌 Provider โปรด (ใช้เป็นค่าเริ่มต้นในแท็บเปรียบเทียบ)", providers, key="fav")
if favorites:
    st.sidebar.markdown("**📌 สรุป Provider โปรด**")
    for fp in favorites:
        fd = data[fp]
        st.sidebar.markdown(
            f"- **{fp}** — ⭐ {avg_score(fd)}/10 | {fmt_both(fd['price_in'])}/1M"
        )
else:
    st.sidebar.caption("ยังไม่มี Provider โปรด — เลือกด้านบนเพื่อปักหมุด")

# ศูนย์อัปเดตข้อมูลจริงทุก Provider
st.sidebar.markdown("---")
st.sidebar.header("🔄 ศูนย์อัปเดตข้อมูลจริง (ทุก Provider)")
st.sidebar.caption(
    "ดึงรุ่นใหม่/ราคา/Context ล่าสุดจาก OpenRouter มาใช้ในทุกแท็บ "
    "(⭐ คะแนน, Benchmark, Use-Case ยังเป็นค่าประมาณการคงที่)"
)

if st.sidebar.button("↩️ คืนค่าเป็นข้อมูลคงที่ (Static)", key="live_reset"):
    st.session_state["live_auto"] = False
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

if "live_auto" not in st.session_state:
    st.session_state["live_auto"] = True
st.sidebar.checkbox("🌐 อัปเดตอัตโนมัติตั้งแต่เปิดแอป", key="live_auto")

if st.sidebar.button("🔄 อัปเดตทุก Provider จาก OpenRouter ตอนนี้", key="live_update_now"):
    try:
        fresh = fetch_openrouter_models()
        if fresh:
            st.session_state["or_models"] = fresh
            st.session_state["or_fetched_at"] = time.strftime("%d/%m/%Y %H:%M")
            n_applied, n_group = apply_live_update(
                data, fresh, st.session_state["or_fetched_at"]
            )
            st.sidebar.success(
                f"✅ อัปเดตแล้ว {n_applied}/{n_group} Provider จากโมเดลจริงบน OpenRouter"
            )
        else:
            st.sidebar.warning("ดึงรายการโมเดลได้ 0 รายการ")
    except Exception as e:
        st.sidebar.error(f"❌ ดึงข้อมูลล้มเหลว: {e}")

if st.session_state.get("or_models"):
    st.sidebar.caption(
        f"🕐 ข้อมูลสดดึงล่าสุด: {st.session_state.get('or_fetched_at', '-')} "
        f"(ดึงอัตโนมัติตอนเปิดแอป)"
    )
else:
    st.sidebar.caption("⚠️ ยังไม่มีข้อมูลสดจาก OpenRouter — กดปุ่มอัปเดตด้านบน")

(
    tab_detail, tab_cmp, tab_search, tab_price, tab_bench,
    tab_cost, tab_rank, tab_matrix,
    tab_chat, tab_ollama, tab_free, tab_live, tab_news,
) = st.tabs(
    [
        "🔍 รายละเอียด & ตารางสรุป",
        "⚖️ เปรียบเทียบ 2 Provider",
        "🔎 ค้นหา/กรอง & แนะนำ",
        "💰 ราคา & Context",
        "📊 Benchmark",
        "🧮 คำนวณต้นทุน (บาท)",
        "🏆 จัดอันดับ (ถ่วงน้ำหนัก)",
        "🗺️ Use-Case Matrix",
        "💬 ทดสอบแชตจริง",
        "🦙 Ollama (โมเดลในเครื่อง)",
        "🌐 ทดลอง Chat ฟรี (ไม่ต้องใช้คีย์)",
        "🔄 ข้อมูลสด (OpenRouter)",
        "📰 ข่าว AI ล่าสุด",
    ]
)

# ---------------------------------------------------------------- แท็บ 1: รายละเอียด
with tab_detail:
    st.subheader(f"🔍 รายละเอียดโมเดลที่เลือก: {selected_provider} ({selected_version})")

    info = data[selected_provider]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**🤖 โมเดลซีรีส์หลัก:** {info['series']}")
        st.markdown(f"**🇹🇭 การซัปพอร์ตภาษาไทย:** {info['thai_support']}")
        st.markdown(f"**🌐 Web UI ของบริษัท:** {info['web_ui']}")
    with col2:
        st.markdown(f"**💳 API แบบเสียเงิน:** {info['api_paid']}")
        st.markdown(f"**🎁 API ฟรี / Open Source:** {info['api_free']}")
    st.markdown(f"**🌍 ประเทศต้นกำเนิด:** {COUNTRIES.get(selected_provider, '-')}")


    st.info(f"**✨ คุณสมบัติเด่น:** {info['features']}")
    st.success(f"**🎯 ประเภทงานที่เหมาะสม (Use Case):** {info['use_case']}")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("💸 ราคา Input (ต่อ 1M)", fmt_usd(info['price_in']), help=f"≈ {fmt_thb(info['price_in'])}")
    m2.metric("💸 ราคา Output (ต่อ 1M)", fmt_usd(info['price_out']), help=f"≈ {fmt_thb(info['price_out'])}")
    m3.metric("📏 Context Window", fmt_tokens(info["context"]))
    m4.metric("⭐ คะแนนรวม", f"{avg_score(info)}/10")
    m5.metric("🆓 API ฟรี", "มี" if info["free_api"] else "ไม่มี")
    st.caption(
        f"{rate_caption()} | Input: {fmt_both(info['price_in'])}/1M | "
        f"Output: {fmt_both(info['price_out'])}/1M"
    )
    if info.get("price_note"):
        st.caption(f"หมายเหตุราคา: {info['price_note']}")
    st.caption(
        f"🔄 อัปเดตล่าสุด: {info['updated']} | แหล่งข้อมูล: "
        f"{info.get('source', '⚙️ คงที่ (Static)')} | {NOTE}"
    )
    if info.get("live_id"):
        st.caption(f"🌐 ราคา/รุ่นอ้างอิงจากโมเดลจริงบน OpenRouter: `{info['live_id']}`")
    st.markdown(f"[🔗 สมัครใช้งาน {selected_provider}]({info['signup']})")

    st.markdown("---")

    st.subheader("📋 ตารางสรุปเปรียบเทียบทุก Provider (Overview Table)")

    table_rows = []
    for provider, d in data.items():
        table_rows.append({
            "Provider": provider,
            "ประเทศ": COUNTRIES.get(provider, "-"),
            "โมเดลซีรีส์": d["series"],
            "ซัปพอร์ตภาษาไทย": d["thai_support"],
            "ชื่อเว็บ UI": d["web_ui"],
            "API เสียเงิน": d["api_paid"],
            "API ฟรี": d["api_free"],
            "คุณสมบัติของโมเดล": d["features"],
            "ประเภทงานที่ควรใช้": d["use_case"],
            "ราคา Input ($/1M)": d["price_in"],
            "ราคา Output ($/1M)": d["price_out"],
            "ราคา Input (฿/1M)": round(thb(d["price_in"]), 2),
            "ราคา Output (฿/1M)": round(thb(d["price_out"]), 2),
            "Context": fmt_tokens(d["context"]),
            "Open Source": d["open_source"],
            "API ฟรี?": "มี" if d["free_api"] else "ไม่มี",
            "คะแนนภาษาไทย (/10)": d["scores"]["ภาษาไทย"],
            "คะแนนโค้ด (/10)": d["scores"]["โค้ด"],
            "คะแนนราคา (/10)": d["scores"]["ราคา"],
            "คะแนนเหตุผล (/10)": d["scores"]["เหตุผล"],
            "คะแนนรวม (/10)": avg_score(d),
            "อัปเดต": d["updated"],
            "แหล่งข้อมูล": d.get("source", "⚙️ คงที่ (Static)"),
            "เวอร์ชันที่เลือกได้ (ปัจจุบัน -> ย้อนหลัง 2 เวอร์ชัน)": ", ".join(d["versions"]),
        })

    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True)

    st.markdown("#### 📥 Export ตารางสรุป")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇️ ดาวน์โหลด CSV", to_csv_bytes(df), "ai_models_overview.csv", "text/csv", key="exp_ov_csv")
    d2.download_button("⬇️ ดาวน์โหลด Markdown", to_md_bytes(df), "ai_models_overview.md", "text/markdown", key="exp_ov_md")
    try:
        xbuf = io.BytesIO()
        df.to_excel(xbuf, index=False)
        d3.download_button(
            "⬇️ ดาวน์โหลด Excel", xbuf.getvalue(), "ai_models_overview.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="exp_ov_xls",
        )
    except Exception:
        d3.caption("⬇️ Excel ต้องติดตั้ง `pip install openpyxl`")

# ---------------------------------------------------------------- แท็บ 2: เปรียบเทียบ 2 Provider
with tab_cmp:
    st.subheader("⚖️ เปรียบเทียบ 2 Provider แบบ Side-by-Side")
    st.caption("🔄 หมายถึงค่าที่ต่างกันระหว่างสองคอลัมน์")

    cA, cB = st.columns(2)
    fav_now = st.session_state.get("fav") or []
    if st.session_state.get("fav_last") != tuple(fav_now):
        st.session_state["fav_last"] = tuple(fav_now)
        st.session_state.pop("cmp_a", None)
        st.session_state.pop("cmp_b", None)
    idx_a = providers.index(fav_now[0]) if len(fav_now) > 0 else 0
    idx_b = providers.index(fav_now[1]) if len(fav_now) > 1 else min(1, len(providers) - 1)
    a = cA.selectbox("ผู้ให้บริการ A", providers, index=idx_a, key="cmp_a")
    b = cB.selectbox("ผู้ให้บริการ B", providers, index=idx_b, key="cmp_b")

    da, db = data[a], data[b]

    fields = [
        ("country", "🌍 ประเทศต้นกำเนิด"),
        ("series", "🤖 โมเดลซีรีส์หลัก"),
        ("thai_support", "🇹🇭 การซัปพอร์ตภาษาไทย"),
        ("web_ui", "🌐 Web UI"),
        ("api_paid", "💳 API แบบเสียเงิน"),
        ("api_free", "🎁 API ฟรี / Open Source"),
        ("features", "✨ คุณสมบัติเด่น"),
        ("use_case", "🎯 Use Case"),
        ("versions", "⏮️ เวอร์ชัน (ย้อนหลัง 2)"),
        ("context", "📏 Context Window"),
        ("price_in", "💸 ราคา Input ต่อ 1M ($)"),
        ("price_out", "💸 ราคา Output ต่อ 1M ($)"),
        ("open_source", "🔓 Open Source"),
        ("free_api", "🆓 มี API ฟรี"),
        ("benchmarks", "📊 Benchmark (MMLU/GPQA/HumanEval)"),
        ("scores", "⭐ คะแนน (ภาษาไทย/โค้ด/ราคา/เหตุผล)"),
        ("updated", "🔄 อัปเดตล่าสุด"),
        ("source", "🔄 แหล่งข้อมูล"),
        ("signup", "🔗 ลิงก์สมัคร"),
    ]

    for key, label in fields:
        if key == "country":
            va, vb = COUNTRIES.get(a, "-"), COUNTRIES.get(b, "-")
        elif key == "source":
            va = da.get("source", "⚙️ คงที่ (Static)")
            vb = db.get("source", "⚙️ คงที่ (Static)")
        else:
            va, vb = da[key], db[key]
        if isinstance(va, list):
            va, vb = ", ".join(va), ", ".join(vb)
        elif isinstance(va, dict):
            va = ", ".join(f"{k}: {v}" for k, v in va.items())
            vb = ", ".join(f"{k}: {v}" for k, v in vb.items())
        elif isinstance(va, bool):
            va, vb = str(va), str(vb)
        elif key in ("price_in", "price_out"):
            va, vb = fmt_both(da[key]) + "/1M", fmt_both(db[key]) + "/1M"
        elif key == "context":
            va, vb = fmt_tokens(va), fmt_tokens(vb)
        diff = str(va) != str(vb)
        st.markdown(f"**{label}**")
        ca, cb = st.columns(2)
        ca.markdown(f"{'🔁 ' if diff else ''}**{a}:** {va}")
        cb.markdown(f"{'🔁 ' if diff else ''}**{b}:** {vb}")

    st.markdown("---")
    st.subheader("🏆 สรุปว่าใครเหนือกว่า (ตามคะแนน)")
    rank = sorted([(a, avg_score(da)), (b, avg_score(db))], key=lambda x: -x[1])
    if rank[0][1] == rank[1][1]:
        st.info(f"⚖️ เสมอกันที่ {rank[0][1]}/10 คะแนน")
    else:
        st.success(f"🏆 {rank[0][0]} นำ {rank[1][0]} ({rank[0][1]} vs {rank[1][1]} คะแนน)")
    for name, sc in [(a, da), (b, db)]:
        st.markdown(
            f"**{name}** — ภาษาไทย {sc['scores']['ภาษาไทย']} | "
            f"โค้ด {sc['scores']['โค้ด']} | ราคา {sc['scores']['ราคา']} | "
            f"เหตุผล {sc['scores']['เหตุผล']} = **{avg_score(sc)}/10**"
        )

# ---------------------------------------------------------------- แท็บ 3: ค้นหา/กรอง & แนะนำ
with tab_search:
    st.subheader("🔎 ค้นหา/กรองตามคุณสมบัติ & แนะนำ Provider")

    f1, f2, f3 = st.columns(3)
    min_thai_label = f1.selectbox(
        "ระดับภาษาไทยขั้นต่ำ",
        ["ปานกลางขึ้นไป", "ดีขึ้นไป", "ดีเยี่ยมเท่านั้น"],
        index=0,
        key="flt_thai",
    )
    need_free = f2.checkbox("ต้องมี API ฟรี", value=False, key="flt_free")
    need_oss = f3.checkbox("ต้องเป็น Open Source", value=False, key="flt_oss")

    kw = st.text_input(
        "พิมพ์งานที่ต้องทำ (ค้นจากคุณสมบัติ/Use Case เช่น: สรุปเอกสาร, เขียนโค้ด, ค้นข้อมูลสด, งบจำกัด)",
        "",
        key="flt_kw",
    )
    thai_min = {"ปานกลางขึ้นไป": 1, "ดีขึ้นไป": 2, "ดีเยี่ยมเท่านั้น": 3}[min_thai_label]
    keywords = [k.strip().lower() for k in kw.replace(",", " ").split() if k.strip()]

    results = []
    for p, d in data.items():
        if d["thai_score"] < thai_min:
            continue
        if need_free and not d["free_api"]:
            continue
        if need_oss and d["open_source"] is not True:
            continue
        text = f"{d['series']} {d['features']} {d['use_case']} {d['api_free']} {d['web_ui']}".lower()
        hits = sum(1 for k in keywords if k in text)
        score = avg_score(d) + hits * 2
        results.append({
            "Provider": p,
            "โมเดลซีรีส์": d["series"],
            "ใช้งานได้ตรงเงื่อนไข": "✔️",
            "คีย์เวิร์ดที่เจอ": hits,
            "คะแนนแนะนำ": score,
            "ภาษาไทย (/10)": d["scores"]["ภาษาไทย"],
            "โค้ด (/10)": d["scores"]["โค้ด"],
            "ราคา (/10)": d["scores"]["ราคา"],
            "เหตุผล (/10)": d["scores"]["เหตุผล"],
            "ราคา Input ($/1M)": d["price_in"],
            "ราคา Input (฿/1M)": round(thb(d["price_in"]), 2),
            "Context": fmt_tokens(d["context"]),
            "Open Source": d["open_source"],
            "API ฟรี": "มี" if d["free_api"] else "ไม่มี",
        })

    res_df = (
        pd.DataFrame(results).sort_values(
            by=["คะแนนแนะนำ", "ราคา Input ($/1M)"], ascending=[False, True]
        )
        if results
        else pd.DataFrame()
    )

    if res_df.empty:
        st.warning("ไม่มี Provider ที่ตรงกับเงื่อนไขทั้งหมด — ลองลดเงื่อนไขดู")
    else:
        if keywords:
            st.subheader("🏆 แนะนำอันดับต้น ๆ ตามคำค้นหา")
            for _, row in res_df.head(3).iterrows():
                st.markdown(
                    f"**{row['Provider']}** ({row['โมเดลซีรีส์']}) — "
                    f"คะแนนแนะนำ **{row['คะแนนแนะนำ']}/10+** | "
                    f"เจอคีย์เวิร์ด {row['คีย์เวิร์ดที่เจอ']} คำ"
                )
            st.markdown("---")
        st.subheader(f"📋 ผลการกรอง ({len(res_df)} รายการ)")
        st.dataframe(res_df, use_container_width=True)

# ---------------------------------------------------------------- แท็บ 4: ราคา & Context
with tab_price:
    st.subheader("💰 ราคา API ต่อ 1 ล้าน Tokens & ขนาด Context Window")
    st.caption(NOTE)

    price_rows = []
    for p, d in data.items():
        price_rows.append({
            "Provider": p,
            "ราคา Input ($/1M)": d["price_in"],
            "ราคา Output ($/1M)": d["price_out"],
            "ราคา Input (฿/1M)": round(thb(d["price_in"]), 2),
            "ราคา Output (฿/1M)": round(thb(d["price_out"]), 2),
            "Context (tokens)": d["context"],
            "Context": fmt_tokens(d["context"]),
            "API ฟรี": "มี" if d["free_api"] else "ไม่มี",
            "Open Source": d["open_source"],
            "อัปเดต": d["updated"],
        })
    price_df = pd.DataFrame(price_rows).sort_values("ราคา Input ($/1M)")
    st.dataframe(price_df, use_container_width=True)
    st.caption(rate_caption())
    st.download_button("⬇️ ดาวน์โหลดตารางราคา CSV", to_csv_bytes(price_df), "ai_pricing.csv", "text/csv", key="exp_price_csv")

    cur = st.radio("แสดงกราฟเป็นสกุล", ["💵 USD", "฿ บาทไทย"], horizontal=True, key="price_cur")
    suffix = "฿/1M" if cur.startswith("฿") else "$/1M"

    st.markdown(f"#### 📊 กราฟเปรียบเทียบราคา (เรียงถูก -> แพง, {suffix})")
    if cur.startswith("฿"):
        chart_df = price_df.set_index("Provider")[["ราคา Input (฿/1M)", "ราคา Output (฿/1M)"]]
    else:
        chart_df = price_df.set_index("Provider")[["ราคา Input ($/1M)", "ราคา Output ($/1M)"]]
    st.bar_chart(chart_df)

    st.markdown("#### 📏 กราฟขนาด Context Window (tokens)")
    ctx_df = price_df.set_index("Provider")["Context (tokens)"]
    st.bar_chart(ctx_df)

    cheap = price_df.iloc[0]
    big = price_df.sort_values("Context (tokens)", ascending=False).iloc[0]
    b1, b2 = st.columns(2)
    b1.success(
        f"💸 ถูกที่สุด: **{cheap['Provider']}** (Input {fmt_both(cheap['ราคา Input ($/1M)'])}/1M)"
    )
    b2.info(f"📏 Context ใหญ่ที่สุด: **{big['Provider']}** ({big['Context']})")

# ---------------------------------------------------------------- แท็บ 5: Benchmark
with tab_bench:
    st.subheader("📊 Benchmark เปรียบเทียบโมเดลหลักของแต่ละ Provider")
    st.caption(NOTE)

    bench_rows = []
    for p, d in data.items():
        b = d["benchmarks"]
        bench_rows.append({
            "Provider": p,
            "MMLU (ความรู้ทั่วไป)": b["MMLU"],
            "GPQA (เหตุผลวิทยาศาสตร์)": b["GPQA"],
            "HumanEval (เขียนโค้ด)": b["HumanEval"],
            "เฉลี่ย": round((b["MMLU"] + b["GPQA"] + b["HumanEval"]) / 3, 1),
        })
    bench_df = pd.DataFrame(bench_rows).sort_values("เฉลี่ย", ascending=False)
    st.dataframe(bench_df, use_container_width=True)

    st.markdown("#### 📈 กราฟแท่งเปรียบเทียบ (คะแนน % สูง = ดีกว่า)")
    st.bar_chart(bench_df.set_index("Provider").drop(columns=["เฉลี่ย"]))

    for metric in ["MMLU (ความรู้ทั่วไป)", "GPQA (เหตุผลวิทยาศาสตร์)", "HumanEval (เขียนโค้ด)"]:
        best = bench_df.sort_values(metric, ascending=False).iloc[0]
        st.caption(f"👑 อันดับ 1 ของ {metric}: **{best['Provider']}** ({best[metric]}%)")

# ---------------------------------------------------------------- แท็บ 6: คำนวณต้นทุน
with tab_cost:
    st.subheader("🧮 เครื่องคำนวณต้นทุน API (USD & ฿ บาทไทย)")
    st.caption(f"{NOTE} | {rate_caption()}")

    mc1, mc2, mc3 = st.columns(3)
    cost_mode = mc1.radio("คำนวณจาก", ["🔢 ใส่ตัวเลขเอง", "📝 วางข้อความจริง"], key="cost_mode")
    cost_days = mc2.number_input("จำนวนวัน/เดือน", min_value=1, max_value=366, value=30, key="cost_days")
    mc3.markdown("")
    mc3.markdown("*(เปลี่ยนอัตราแลกเปลี่ยนได้ที่ Sidebar)*")

    if cost_mode.startswith("🔢"):
        n1, n2 = st.columns(2)
        tok_in = n1.number_input("Input tokens ต่อวัน", min_value=0, value=100000, step=10000, key="cost_tin")
        tok_out = n2.number_input("Output tokens ต่อวัน", min_value=0, value=50000, step=5000, key="cost_tout")
    else:
        t1, t2 = st.columns(2)
        sample_in = t1.text_area("วางข้อความ INPUT ตัวอย่าง", "สวัสดีครับ นี่คือตัวอย่างข้อความสำหรับประมาณการ tokens", key="cost_txt_in")
        sample_out = t2.text_area("วางข้อความ OUTPUT ตัวอย่าง", "นี่คือคำตอบจำลองที่โมเดลอาจสร้างขึ้นมาเพื่อใช้ประมาณการค่าใช้จ่าย", key="cost_txt_out")
        tok_in = max(1, len(sample_in) // 2)
        tok_out = max(1, len(sample_out) // 2)
        st.caption(f"📏 ประมาณการ: input ≈ {tok_in:,} tokens | output ≈ {tok_out:,} tokens (ไทย ~2 ตัวอักษร/token — ค่าคร่าว ๆ เท่านั้น)")

    picked = st.multiselect(
        "เทียบ Provider (แนะนำ 2-3 ตัว)", providers,
        default=["OpenAI", "DeepSeek", "Google"], key="cost_sel",
    )

    if picked:
        cost_rows = []
        for p in picked:
            d = data[p]
            daily = tok_in * d["price_in"] / 1_000_000 + tok_out * d["price_out"] / 1_000_000
            monthly = daily * cost_days
            cost_rows.append({
                "Provider": p,
                "ต้นทุน/วัน ($)": round(daily, 4),
                "ต้นทุน/วัน (฿)": round(thb(daily), 2),
                f"ต้นทุน/{cost_days} วัน ($)": round(monthly, 2),
                f"ต้นทุน/{cost_days} วัน (฿)": round(thb(monthly), 2),
                f"ต้นทุน/ปี (฿)": round(thb(daily) * 365, 2),
            })
        cost_df = pd.DataFrame(cost_rows).sort_values("ต้นทุน/วัน ($)")
        st.dataframe(cost_df, use_container_width=True)

        best_cost = cost_df.iloc[0]
        worst_cost = cost_df.iloc[-1]
        kc1, kc2 = st.columns(2)
        kc1.success(
            f"💰 ถูกที่สุด: **{best_cost['Provider']}** — "
            f"{fmt_both(best_cost['ต้นทุน/วัน ($)'])}/วัน | "
            f"เดือนละ {fmt_thb(best_cost['ต้นทุน/วัน ($)'] * cost_days)}"
        )
        if len(cost_df) > 1:
            ratio = worst_cost["ต้นทุน/วัน ($)"] / best_cost["ต้นทุน/วัน ($)"] if best_cost["ต้นทุน/วัน ($)"] > 0 else 0
            kc2.warning(
                f"💸 แพงที่สุด: **{worst_cost['Provider']}** ({ratio:.1f} เท่าของตัวถูกสุด)"
            )
        st.markdown("#### 📊 กราฟต้นทุนรายเดือน (฿)")
        st.bar_chart(cost_df.set_index("Provider")[[f"ต้นทุน/{cost_days} วัน (฿)"]])
        st.download_button("⬇️ ดาวน์โหลดตารางต้นทุน CSV", to_csv_bytes(cost_df), "cost_calc.csv", "text/csv", key="exp_cost_csv")
    else:
        st.info("เลือกอย่างน้อย 1 Provider เพื่อคำนวณ")

# ---------------------------------------------------------------- แท็บ 7: จัดอันดับถ่วงน้ำหนัก
with tab_rank:
    st.subheader("🏆 จัดอันดับ Provider ตามน้ำหนักที่คุณกำหนด")
    st.caption("เลื่อน slider ให้ตรงกับสิ่งที่คุณให้ความสำคัญ ระบบจะจัดอันดับใหม่แบบ realtime")

    w1, w2, w3, w4 = st.columns(4)
    w_thai = w1.slider("⚖️ น้ำหนัก ภาษาไทย", 0, 10, 5, key="w_thai")
    w_code = w2.slider("⚖️ น้ำหนัก โค้ด", 0, 10, 5, key="w_code")
    w_price = w3.slider("⚖️ น้ำหนัก ราคา", 0, 10, 5, key="w_price")
    w_reason = w4.slider("⚖️ น้ำหนัก เหตุผล", 0, 10, 5, key="w_reason")

    total_w = w_thai + w_code + w_price + w_reason
    if total_w == 0:
        st.warning("ให้น้ำหนักอย่างน้อย 1 ข้อ (มูลค่า > 0)")
    else:
        rank_rows = []
        for p, d in data.items():
            s = d["scores"]
            weighted = (
                s["ภาษาไทย"] * w_thai + s["โค้ด"] * w_code +
                s["ราคา"] * w_price + s["เหตุผล"] * w_reason
            ) / total_w
            rank_rows.append({
                "อันดับ": 0,
                "Provider": p,
                "คะแนนถ่วงน้ำหนัก": round(weighted, 2),
                "ภาษาไทย": s["ภาษาไทย"],
                "โค้ด": s["โค้ด"],
                "ราคา": s["ราคา"],
                "เหตุผล": s["เหตุผล"],
                "ราคา Input (฿/1M)": round(thb(d["price_in"]), 2),
                "API ฟรี": "มี" if d["free_api"] else "ไม่มี",
            })
        rank_df = pd.DataFrame(rank_rows).sort_values("คะแนนถ่วงน้ำหนัก", ascending=False).reset_index(drop=True)
        rank_df["อันดับ"] = range(1, len(rank_df) + 1)
        st.dataframe(rank_df, use_container_width=True)

        champ = rank_df.iloc[0]
        runner = rank_df.iloc[1] if len(rank_df) > 1 else None
        if runner is not None and champ["คะแนนถ่วงน้ำหนัก"] == runner["คะแนนถ่วงน้ำหนัก"]:
            st.info(f"⚖️ อันดับ 1 ร่วม: **{champ['Provider']}** และ **{runner['Provider']}** "
                    f"({champ['คะแนนถ่วงน้ำหนัก']} คะแนน)")
        else:
            st.success(
                f"🥇 อันดับ 1 ตามน้ำหนักของคุณ: **{champ['Provider']}** "
                f"({champ['คะแนนถ่วงน้ำหนัก']}/10)"
                + (f" | 🥈 {runner['Provider']} ({runner['คะแนนถ่วงน้ำหนัก']})" if runner is not None else "")
            )
        st.markdown("#### 📊 กราฟคะแนนถ่วงน้ำหนัก")
        st.bar_chart(rank_df.set_index("Provider")["คะแนนถ่วงน้ำหนัก"])
        st.download_button("⬇️ ดาวน์โหลดอันดับ CSV", to_csv_bytes(rank_df), "weighted_ranking.csv", "text/csv", key="exp_rank_csv")

# ---------------------------------------------------------------- แท็บ 8: Use-Case Matrix
with tab_matrix:
    st.subheader("🗺️ Use-Case Matrix — เหมาะกับงานไหน มองทีเดียวจบ")
    st.caption("คะแนนคร่าว ๆ 1-10 | 🟢 9-10 เด่นมาก | 🟡 7-8 ดี | 🟠 5-6 พอใช้ | 🔴 <5 ไม่เหมาะ")

    matrix_rows = []
    for p in providers:
        matrix_rows.append({"Provider": p, **{
            task: score_emoji(v) for task, v in zip(USECASE_TASKS, USECASE[p])
        }})
    matrix_df = pd.DataFrame(matrix_rows)
    st.dataframe(matrix_df, use_container_width=True)

    st.markdown("#### 👑 เจ้าที่เด่นที่สุดในแต่ละภารกิจ")
    best_cols = st.columns(4)
    for idx, task in enumerate(USECASE_TASKS):
        best_p = max(providers, key=lambda p: USECASE[p][idx])
        best_v = USECASE[best_p][idx]
        with best_cols[idx % 4]:
            st.metric(f"{task}", best_p, delta=f"{best_v}/10")

    st.markdown("#### 📊 ตัวเลขดิบ (สำหรับเทียบละเอียด)")
    raw_rows = [
        {"Provider": p, **{task: v for task, v in zip(USECASE_TASKS, USECASE[p])}}
        for p in providers
    ]
    raw_df = pd.DataFrame(raw_rows)
    st.dataframe(raw_df, use_container_width=True)
    st.download_button("⬇️ ดาวน์โหลด Use-Case Matrix CSV", to_csv_bytes(raw_df), "usecase_matrix.csv", "text/csv", key="exp_matrix_csv")

# ---------------------------------------------------------------- แท็บ 9: ทดสอบแชตจริง
with tab_chat:
    st.subheader("💬 ทดสอบแชตจริง เปรียบเทียบหลายโมเดลพร้อมกัน")
    st.caption(
        "คีย์ของคุณส่งตรงไปยังผู้ให้บริการที่เลือกเท่านั้น (ไม่ผ่านเซิร์ฟเวอร์กลาง) "
        "รองรับคีย์รายเจ้า (รูปแบบ OpenAI-compatible) หรือคีย์ OpenRouter อันเดียว"
    )

    tpl = st.selectbox(
        "📚 Prompt สำเร็จรูป (เลือกแล้วเติมลงช่อง Prompt ให้อัตโนมัติ)",
        list(PROMPT_TEMPLATES), key="chat_tpl",
    )
    if st.session_state.get("chat_tpl_last") != tpl:
        st.session_state["chat_tpl_last"] = tpl
        st.session_state["chat_prompt"] = PROMPT_TEMPLATES[tpl]

    mode = st.radio(
        "วิธีเรียกใช้",
        ["🔑 คีย์เฉพาะแต่ละเจ้า", "🌍 OpenRouter (คีย์เดียว ใช้ได้ทุกเจ้า)"],
        horizontal=True,
        key="chat_mode",
    )
    is_or = mode.startswith("🌍")

    selected_chat = st.multiselect(
        "เลือก Provider ที่ต้องการทดสอบ", providers,
        default=["OpenAI", "DeepSeek"], key="chat_sel",
    )

    sys_c, tmp_c = st.columns([2, 1])
    system_prompt = sys_c.text_area(
        "🧠 System Prompt (ไม่บังคับ)", "", key="chat_sys",
        help="กำหนดบุคลิก/กติกาของโมเดล เช่น 'ตอบเป็นภาษาไทยสั้น ๆ เท่านั้น'",
    )
    temperature = tmp_c.slider(
        "🎯 Temperature", 0.0, 2.0, 0.7, 0.1, key="chat_temp",
        help="0 = คงที่/จริงจัง, 2 = สร้างสรรค์/เสี่ยงผิดพลาด",
    )

    prompt = st.text_area("Prompt ทดสอบ", key="chat_prompt")

    keys, models = {}, {}
    or_key = ""
    if is_or:
        or_key = st.text_input("OpenRouter API Key", type="password", key="or_key")
        for p in selected_chat:
            models[p] = st.text_input(
                f"โมเดลบน OpenRouter สำหรับ {p}", OPENROUTER_MODELS[p], key=f"om_{p}"
            )
    else:
        for p in selected_chat:
            ep = CHAT_ENDPOINTS.get(p)
            if ep is None:
                st.warning(f"⚠️ {p} ไม่มี API ตรงแบบ OpenAI-compatible — สลับเป็นโหมด OpenRouter เพื่อทดสอบเจ้านี้")
                continue
            kc, mc = st.columns([1, 1])
            keys[p] = kc.text_input(f"API Key ของ {p}", type="password", key=f"k_{p}")
            models[p] = mc.text_input(f"โมเดลของ {p}", ep[1], key=f"m_{p}")

    def resolve_target(p):
        if is_or:
            if not or_key:
                return None
            return "https://openrouter.ai/api/v1", or_key, models.get(p, "")
        ep = CHAT_ENDPOINTS.get(p)
        if ep is None or not keys.get(p):
            return None
        return ep[0], keys[p], models.get(p, ep[1])

    if st.button("🚀 เริ่มทดสอบ", type="primary", key="chat_go"):
        if not prompt.strip():
            st.warning("กรุณาใส่ Prompt ก่อน")
        elif not selected_chat:
            st.warning("กรุณาเลือกอย่างน้อย 1 Provider")
        else:
            results = {}
            with st.status("⏳ กำลังเรียกทุกโมเดล...", expanded=True) as status:
                for p in selected_chat:
                    tgt = resolve_target(p)
                    if tgt is None or not tgt[2]:
                        results[p] = {"text": "⚠️ ไม่มี API Key / ไม่ได้ระบุโมเดล", "time": 0, "usage": {}}
                        st.write(f"- {p}: ⚠️ ข้าม (ยังไม่พร้อม)")
                        continue
                    base, key, model = tgt
                    try:
                        text, elapsed, usage = call_chat(
                            base, key, model, prompt,
                            system=system_prompt, temperature=temperature,
                        )
                        results[p] = {"text": text, "time": elapsed, "usage": usage}
                        st.write(f"- {p}: ✅ {elapsed:.2f}s")
                    except Exception as e:
                        results[p] = {"text": f"❌ {e}", "time": 0, "usage": {}}
                        st.write(f"- {p}: ❌ {e}")
                status.update(label="✅ เรียกครบทุกโมเดล", state="complete")
            st.session_state["chat_results"] = results

    # ⏱️ Latency Benchmark
    st.markdown("---")
    st.subheader("⏱️ Latency Benchmark (วัดเวลาตอบเฉลี่ย)")
    st.caption("ยิง prompt สั้น ๆ ซ้ำหลายครั้งต่อโมเดลเพื่อวัดความเร็ว — เสียค่า API ตามจริง")
    lc1, lc2 = st.columns([3, 1])
    lat_n = lc1.slider("จำนวนครั้งต่อโมเดล", 1, 10, 3, key="lat_n")
    if lc2.button("⏱️ เริ่มวัด", key="lat_go"):
        targets = [(p, resolve_target(p)) for p in selected_chat]
        targets = [(p, t) for p, t in targets if t is not None and t[2]]
        if not targets:
            st.warning("ยังไม่พร้อมวัด — ต้องใส่คีย์และระบุโมเดลก่อน")
        else:
            lat_rows = []
            with st.status(f"⏳ วัด {lat_n} ครั้ง/โมเดล...", expanded=True) as lstatus:
                for p, (base, key, model) in targets:
                    times, err = [], ""
                    for _ in range(lat_n):
                        try:
                            _, el, _ = call_chat(
                                base, key, model, "ตอบคำว่า OK เท่านั้น",
                                system=system_prompt, temperature=0.0, timeout=60,
                            )
                            times.append(el)
                        except Exception as e:
                            err = str(e)[:100]
                            break
                    if times:
                        lat_rows.append({
                            "Provider": p,
                            "โมเดล": model,
                            "สำเร็จ (ครั้ง)": f"{len(times)}/{lat_n}",
                            "เฉลี่ย (วิ)": round(sum(times) / len(times), 2),
                            "เร็วสุด (วิ)": round(min(times), 2),
                            "ช้าสุด (วิ)": round(max(times), 2),
                        })
                        st.write(f"- {p}: เฉลี่ย {sum(times) / len(times):.2f}s")
                    else:
                        st.write(f"- {p}: ❌ {err or 'วัดไม่สำเร็จ'}")
                lstatus.update(label="✅ วัดเสร็จ", state="complete")
            if lat_rows:
                lat_df = pd.DataFrame(lat_rows)
                st.session_state["latency"] = lat_df
                st.dataframe(lat_df, use_container_width=True)
                st.bar_chart(lat_df.set_index("Provider")[["เฉลี่ย (วิ)", "ช้าสุด (วิ)"]])
                st.download_button("⬇️ ดาวน์โหลดผล Latency CSV", to_csv_bytes(lat_df), "latency.csv", "text/csv", key="exp_lat_csv")

    # 📨 ผลลัพธ์
    if "chat_results" in st.session_state:
        st.markdown("---")
        st.subheader("📨 ผลลัพธ์")
        res = st.session_state["chat_results"]
        per_row = 3
        items = list(res.items())
        for i in range(0, len(items), per_row):
            cols = st.columns(min(per_row, len(items) - i))
            for col, (p, r) in zip(cols, items[i:i + per_row]):
                with col:
                    st.markdown(f"**{p}**")
                    if r["usage"]:
                        u = r["usage"]
                        st.caption(
                            f"⏱ {r['time']:.2f} วิ | tokens: {u.get('prompt_tokens', '?')}+"
                            f"{u.get('completion_tokens', '?')} = {u.get('total_tokens', '?')}"
                        )
                    else:
                        st.caption(f"⏱ {r['time']:.2f} วิ")
                    st.text_area("คำตอบ", r["text"], height=300, disabled=True)

        # 🏆 โหวต A/B แบบซ่อนชื่อโมเดล
        st.markdown("---")
        st.subheader("🏆 โหวตคำตอบแบบ A/B (ซ่อนชื่อโมเดล)")
        good = [(p, r) for p, r in res.items()
                if not r["text"].startswith(("❌", "⚠️")) and r["text"].strip()]
        if len(good) < 2:
            st.info("ต้องมีคำตอบสำเร็จอย่างน้อย 2 คำตอบจึงจะโหวตได้")
        else:
            if st.session_state.get("vote_key") != tuple(sorted(res.keys())):
                for k in list(st.session_state.keys()):
                    if str(k).startswith("vote_") and k not in ("vote_key", "vote_log"):
                        st.session_state.pop(k)
                shuffled = good[:]
                random.shuffle(shuffled)
                st.session_state["vote_key"] = tuple(sorted(res.keys()))
                st.session_state["vote_items"] = shuffled
            items_v = st.session_state["vote_items"]
            pairs = [items_v[i:i + 2] for i in range(0, len(items_v) - 1, 2)]

            for i, pair in enumerate(pairs):
                st.markdown(f"**คู่ที่ {i + 1}**")
                ca, cb = st.columns(2)
                with ca:
                    st.markdown("🔵 **คำตอบ A**")
                    st.text_area("A", pair[0][1]["text"], height=260, key=f"va_{i}", disabled=True)
                with cb:
                    st.markdown("🟢 **คำตอบ B**")
                    st.text_area("B", pair[1][1]["text"], height=260, key=f"vb_{i}", disabled=True)
                st.radio(
                    "คำตอบไหนดีกว่า?", ["A", "B", "เท่ากัน"],
                    key=f"vote_{i}", horizontal=True, label_visibility="collapsed",
                )

            v1, v2 = st.columns([2, 1])
            if v1.button("💾 บันทึกโหวต", type="primary", key="vote_save"):
                log = st.session_state.get("vote_log", [])
                n = len(log) + 1
                for i, pair in enumerate(pairs):
                    ch = st.session_state.get(f"vote_{i}", "เท่ากัน")
                    winner = pair[0][0] if ch == "A" else pair[1][0] if ch == "B" else "เสมอ"
                    log.append({
                        "ครั้งที่": n,
                        "ผู้เข้าร่วม A": pair[0][0],
                        "ผู้เข้าร่วม B": pair[1][0],
                        "ผู้ชนะ": winner,
                        "เวลา": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                st.session_state["vote_log"] = log
                st.success(f"✅ บันทึกโหวตแล้ว (สะสม {len(log)} รายการ)")
            if v2.button("🗑️ ล้างประวัติ", key="vote_clear"):
                st.session_state.pop("vote_log", None)

            vote_log = st.session_state.get("vote_log", [])
            if vote_log:
                st.markdown("#### 📊 ตารางคะแนนโหวตสะสม")
                games, wins, draws = {}, {}, {}
                for v in vote_log:
                    a, b = v["ผู้เข้าร่วม A"], v["ผู้เข้าร่วม B"]
                    games[a] = games.get(a, 0) + 1
                    games[b] = games.get(b, 0) + 1
                    if v["ผู้ชนะ"] == "เสมอ":
                        draws[a] = draws.get(a, 0) + 1
                        draws[b] = draws.get(b, 0) + 1
                    else:
                        w = v["ผู้ชนะ"]
                        wins[w] = wins.get(w, 0) + 1
                score_rows = []
                for p in sorted(set(list(games))):
                    g = games[p]
                    w = wins.get(p, 0)
                    dr = draws.get(p, 0)
                    score_rows.append({
                        "Provider": p,
                        "ชนะ": w,
                        "เสมอ": dr,
                        "แพ้": g - w - dr,
                        "จำนวนครั้งที่ถูกโหวต": g,
                        "% ชนะ": round(w / g * 100, 1),
                    })
                score_df = pd.DataFrame(score_rows).sort_values(
                    ["ชนะ", "% ชนะ"], ascending=False
                )
                st.dataframe(score_df, use_container_width=True)
                st.bar_chart(score_df.set_index("Provider")[["ชนะ", "เสมอ", "แพ้"]])
                top = score_df.iloc[0]
                st.success(f"🏆 ตอนนี้ **{top['Provider']}** นำไป ({top['ชนะ']} ชนะ จาก {top['จำนวนครั้งที่ถูกโหวต']} ครั้ง)")

                with st.expander("📜 ดู/Export ประวัติโหวตทั้งหมด"):
                    hist_df = pd.DataFrame(vote_log)
                    st.dataframe(hist_df, use_container_width=True)
                    st.download_button(
                        "⬇️ ดาวน์โหลดประวัติโหวต CSV",
                        to_csv_bytes(hist_df), "vote_log.csv", "text/csv", key="exp_vote_csv",
                    )

# ---------------------------------------------------------------- แท็บ 10: Ollama (โมเดลในเครื่อง)
with tab_ollama:
    st.subheader("🦙 โมเดล Local ผ่าน Ollama — ทดลองแชตฟรี 100% ไม่ต้องใช้ API Key")
    st.caption(
        "ดึงรายการโมเดลจาก Ollama ที่รันบนเครื่องคุณ (localhost:11434) "
        "ถ้ายังไม่ได้ติดตั้ง ดูวิธีติดตั้งได้ที่ https://ollama.com"
    )

    oc1, oc2 = st.columns([3, 1])
    if oc2.button("🔄 ตรวจ Ollama ใหม่", key="ollama_recheck"):
        try:
            st.session_state["ollama_tags"] = fetch_ollama_tags()
        except Exception:
            st.session_state["ollama_tags"] = None
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    ollama_models = st.session_state.get("ollama_tags") or []
    if not ollama_models:
        st.warning(
            "❌ ไม่พบ Ollama ที่ localhost:11434 — ยังไม่ได้ติดตั้งหรือยังไม่ได้รัน "
            "(ติดตั้ง: https://ollama.com แล้วรัน `ollama serve` หรือ `ollama run llama3.2`)"
        )
        st.markdown("[🔗 ไปที่ ollama.com เพื่อติดตั้ง](https://ollama.com)")
    else:
        st.success(f"✅ พบโมเดลในเครื่อง {len(ollama_models)} ตัว — ทดสอบได้ฟรีไม่จำกัด")
        o_rows = [{
            "โมเดล": m.get("name", m.get("model", "?")),
            "ขนาด (GB)": round((m.get("size", 0) or 0) / 1e9, 2),
            "อัปเดต": str(m.get("modified_at", ""))[:19],
            "ครอบครัว": m.get("details", {}).get("family", "-"),
        } for m in ollama_models]
        o_df = pd.DataFrame(o_rows)
        st.dataframe(o_df, use_container_width=True)

        st.markdown("#### 💬 ทดลองแชตกับโมเดลในเครื่อง")
        op1, op2 = st.columns([2, 1])
        o_model = op1.selectbox("โมเดล", o_df["โมเดล"].tolist(), key="ollama_model")
        o_temp = op2.slider("Temperature", 0.0, 2.0, 0.7, 0.1, key="ollama_temp")
        o_prompt = st.text_area(
            "Prompt",
            PROMPT_TEMPLATES["💬 ทั่วไป (ค่าเริ่มต้น)"],
            key="ollama_prompt",
        )
        if st.button("🚀 คุยกับโมเดลในเครื่อง", type="primary", key="ollama_go"):
            if not o_prompt.strip():
                st.warning("กรุณาใส่ Prompt")
            else:
                with st.status("⏳ กำลังเรียกโมเดลในเครื่อง...", expanded=True) as ostat:
                    try:
                        text, elapsed, usage = call_chat(
                            "http://localhost:11434/v1", "ollama", o_model, o_prompt,
                            temperature=o_temp, timeout=600,
                        )
                        st.session_state["ollama_result"] = {
                            "text": text, "time": elapsed, "usage": usage, "model": o_model,
                        }
                        ostat.update(label=f"✅ เสร็จ ({elapsed:.2f}s)", state="complete")
                    except Exception as e:
                        ostat.update(label="❌ ล้มเหลว", state="error")
                        st.error(f"เรียกไม่สำเร็จ: {e}")
        if "ollama_result" in st.session_state:
            orr = st.session_state["ollama_result"]
            st.markdown(f"**🦙 {orr['model']}** — ⏱ {orr['time']:.2f} วิ")
            st.text_area("คำตอบ", orr["text"], height=350, disabled=True)

# ---------------------------------------------------------------- แท็บ 11: ทดลอง Chat ฟรี (เบราว์เซอร์)
with tab_free:
    st.subheader("🌐 ทดลอง Chat ฟรีทุก Provider โดยไม่ต้องใช้ API Key")
    st.caption(
        "เบราว์เซอร์ด้านล่างจะโหลดเว็บแชตทางการของแต่ละเจ้าโดยตรง "
        "บางเว็บป้องกันการฝังใน iframe (X-Frame-Options) ถ้าหน้าจอว่างหรือไม่ยอมโหลด ให้กดปุ่ม ↗ เปิดในแท็บใหม่"
    )

    free_sel = st.selectbox("เลือก Provider เพื่อเปิดในเบราว์เซอร์", providers, key="free_sel")
    if st.session_state.get("free_sel_last") != free_sel:
        st.session_state["free_sel_last"] = free_sel
        st.session_state["free_url"] = WEB_CHAT[free_sel]
    st.markdown(f"**{free_sel} — {data[free_sel]['web_ui']}** (รองรับภาษาไทย: {data[free_sel]['thai_support']})")

    bc1, bc2 = st.columns([5, 1])
    free_url = bc1.text_input("🌐 ที่อยู่เว็บ (URL — แก้ไขได้)", key="free_url")
    bc2.markdown("")
    bc2.markdown(f"[↗ เปิดในแท็บใหม่]({free_url})")

    components.html(
        f'<iframe src="{free_url}" style="width:100%;height:680px;border:1px solid #ddd;border-radius:8px;" '
        f'referrerpolicy="no-referrer-when-downgrade"></iframe>',
        height=700,
        scrolling=True,
    )

    if free_sel == "Nova (Amazon)":
        st.info("ℹ️ Nova ไม่มีเว็บแชตฟรีสาธารณะ ต้องใช้ผ่าน Amazon Bedrock Console (ต้องมีบัญชี AWS)")

    st.markdown("---")
    st.markdown("#### 🔗 ลิงก์ทดลอง Chat ฟรีทั้งหมด (เปิดในแท็บใหม่)")
    items = list(WEB_CHAT.items())
    for i in range(0, len(items), 3):
        cols = st.columns(3)
        for col, (p, link) in zip(cols, items[i:i + 3]):
            with col:
                st.markdown(f"**{p}**")
                st.caption(f"🌐 {data[p]['web_ui']}")
                st.markdown(f"[🔗 เปิด {link.replace('https://', '').rstrip('/')}]({link})")

# ---------------------------------------------------------------- แท็บ 12: ข้อมูลสด OpenRouter
with tab_live:
    st.subheader("🔄 ข้อมูลสดจาก OpenRouter (รายการโมเดลและราคาล่าสุด)")
    st.caption("ดึงรายการโมเดลจาก https://openrouter.ai/api/v1/models แบบเรียลไทม์ เพื่อเทียบกับข้อมูลคงที่ในตาราง")

    if st.button("🔄 ดึงข้อมูลล่าสุดจาก OpenRouter", key="live_go"):
        try:
            with st.status("⏳ กำลังดึงข้อมูล...", expanded=True) as status:
                models_live = fetch_openrouter_models()
                status.update(label=f"✅ ได้ {len(models_live)} โมเดล", state="complete")
            st.session_state["or_models"] = models_live
        except Exception as e:
            st.error(f"ดึงข้อมูลไม่สำเร็จ: {e}")

    models_live = st.session_state.get("or_models") or []
    if models_live:
        groups = {}
        for m in models_live:
            mid = m.get("id", "")
            prefix = mid.split("/")[0] if "/" in mid else "อื่น ๆ"
            try:
                pin = float(m.get("pricing", {}).get("prompt", 0)) * 1_000_000
                pout = float(m.get("pricing", {}).get("completion", 0)) * 1_000_000
            except (TypeError, ValueError):
                pin = pout = 0.0
            g = groups.setdefault(prefix, {"models": [], "pin": [], "pout": []})
            g["models"].append(m)
            g["pin"].append(pin)
            g["pout"].append(pout)

        row_live = []
        for prefix, g in groups.items():
            cheapest = sorted(
                [m for m, p in zip(g["models"], g["pin"]) if p > 0],
                key=lambda m: float(m["pricing"]["prompt"]),
            )
            row_live.append({
                "Prefix": prefix,
                "Provider ในแดชบอร์ด": OPENROUTER_PREFIX.get(prefix, "-"),
                "จำนวนโมเดล": len(g["models"]),
                "ราคา Input ถูกสุด ($/1M)": round(min(g["pin"]), 4) if any(g["pin"]) else 0,
                "ราคา Input ถูกสุด (฿/1M)": round(thb(min(g["pin"])), 2) if any(g["pin"]) else 0,
                "ราคา Output ถูกสุด ($/1M)": round(min(g["pout"]), 4) if any(g["pout"]) else 0,
                "ราคา Output ถูกสุด (฿/1M)": round(thb(min(g["pout"])), 2) if any(g["pout"]) else 0,
                "ตัวอย่างโมเดล": ", ".join(m.get("name", m.get("id", "?")) for m in cheapest[:3]),
            })
        live_df = pd.DataFrame(row_live).sort_values("จำนวนโมเดล", ascending=False)
        st.markdown("#### 📋 สรุปตาม Provider บน OpenRouter")
        st.dataframe(live_df, use_container_width=True)
        st.caption(rate_caption())

        known = [p for p in OPENROUTER_PREFIX]
        st.markdown("#### 🔍 ดูรายการโมเดลของแต่ละ Provider")
        pick = st.selectbox("เลือก Prefix", known, key="live_pick")
        rows = []
        for m in sorted(
            groups.get(pick, {}).get("models", []),
            key=lambda m: float(m.get("pricing", {}).get("prompt", 0) or 0),
        ):
            try:
                pin = float(m["pricing"]["prompt"]) * 1_000_000
                pout = float(m["pricing"]["completion"]) * 1_000_000
            except (TypeError, ValueError, KeyError):
                pin = pout = 0.0
            rows.append({
                "Model ID": m.get("id"),
                "ชื่อ": m.get("name"),
                "Context": fmt_tokens(m.get("context_length", 0) or 0),
                "Input ($/1M)": round(pin, 4),
                "Input (฿/1M)": round(thb(pin), 2),
                "Output ($/1M)": round(pout, 4),
                "Output (฿/1M)": round(thb(pout), 2),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info(f"ไม่พบโมเดลของ {pick} บน OpenRouter")

        st.markdown("#### 🆚 เทียบข้อมูลคงที่ในตารางกับราคาจริงบน OpenRouter")
        cmp_rows = []
        for p, d in data.items():
            prefix = next((k for k, v in OPENROUTER_PREFIX.items() if v == p), None)
            if prefix and prefix in groups:
                or_min = min(x for x in groups[prefix]["pin"] if x > 0) if any(
                    x > 0 for x in groups[prefix]["pin"]
                ) else 0
                diff = d["price_in"] - or_min
                cmp_rows.append({
                    "Provider": p,
                    "ราคาในตาราง ($/1M)": d["price_in"],
                    "ราคาในตาราง (฿/1M)": round(thb(d["price_in"]), 2),
                    "ราคาถูกสุดบน OpenRouter ($/1M)": round(or_min, 4),
                    "ราคาถูกสุดบน OpenRouter (฿/1M)": round(thb(or_min), 2),
                    "ผลต่าง ($)": round(diff, 4),
                    "ผลต่าง (฿)": round(thb(diff), 2),
                    "ถูกกว่าในตาราง ✔️": "ใช่ (รุ่นในตารางถูกกว่า)" if diff < 0 else "OpenRouter ถูกกว่า",
                })
        if cmp_rows:
            st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True)
            st.caption("ราคาในตารางคือรุ่นหลักของแต่ละเจ้า ส่วน OpenRouter แสดงรุ่นที่ถูกที่สุดในกลุ่ม จึงไม่ใช่โมเดลเดียวกันเสมอไป")
    else:
        st.info("ไม่สามารถดึงข้อมูลจาก OpenRouter ได้ — กดปุ่มด้านบนเพื่อลองใหม่")

# ---------------------------------------------------------------- แท็บ 13: ข่าว AI ล่าสุด
with tab_news:
    st.subheader("📰 ข่าว AI / โมเดลใหม่ล่าสุด (จาก Hacker News)")
    st.caption("ดึงข้อมูลอัตโนมัติครั้งแรกที่เปิดแอป — ค้นหาใหม่ได้ด้วยปุ่มด้านขวา")

    NEWS_QUERIES = [
        "LLM", "GPT", "Claude", "Gemini", "DeepSeek", "Llama",
        "AI model", "OpenRouter", "Mistral", "Qwen", "Anthropic",
    ]
    nc1, nc2 = st.columns([3, 1])
    news_q = nc1.selectbox("คำค้นหา", NEWS_QUERIES, key="news_q")
    if nc2.button("🔄 ค้นหาข่าว", key="news_go"):
        try:
            st.session_state["hn_news"] = fetch_hn_news(news_q)
            st.session_state["hn_query_shown"] = news_q
        except Exception as e:
            st.error(f"ดึงข่าวไม่สำเร็จ: {e}")

    hits = st.session_state.get("hn_news") or []
    shown_q = st.session_state.get("hn_query_shown", "LLM")
    if hits:
        st.markdown(f"#### ผลลัพธ์สำหรับ '{shown_q}' ({len(hits)} ข่าว)")
        news_rows = [{
            "#": i + 1,
            "หัวข้อ": h.get("title") or "-",
            "จุด (points)": h.get("points") or 0,
            "ความคิดเห็น": h.get("num_comments") or 0,
            "ลิงก์": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
        } for i, h in enumerate(hits)]
        st.dataframe(pd.DataFrame(news_rows), use_container_width=True)
        st.markdown("#### 🔗 เปิดอ่าน")
        for i, h in enumerate(hits[:10]):
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
            st.markdown(
                f"{i + 1}. [{h.get('title') or '-'}]({link}) "
                f"— ▲ {h.get('points') or 0} | 💬 {h.get('num_comments') or 0}"
            )
    else:
        st.info("ยังไม่มีข่าว — กดปุ่มค้นหา หรือรอการดึงข้อมูลอัตโนมัติครั้งแรก")

