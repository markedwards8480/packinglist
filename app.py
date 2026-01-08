"""
Packing List Sanitizer - Web Application
Mark Edwards Apparel Inc.
Two-file version: Upload Internal PO + Customer Packing List
"""

import os
import re
import uuid
from datetime import datetime
from flask import Flask, request, send_file, jsonify, redirect, url_for, Response
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# HTML template embedded directly
INDEX_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Packing List Sanitizer | Mark Edwards Apparel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }
        .container { max-width: 700px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .logo { font-size: 48px; margin-bottom: 16px; }
        .header h1 { color: white; font-size: 28px; font-weight: 700; margin-bottom: 8px; }
        .header p { color: #94a3b8; font-size: 16px; }
        .card {
            background: white;
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25);
        }
        .upload-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .upload-box {
            border: 2px dashed #cbd5e1;
            border-radius: 12px;
            padding: 24px 16px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: #f8fafc;
        }
        .upload-box:hover { border-color: #3b82f6; background: #eff6ff; }
        .upload-box.drag-over { border-color: #3b82f6; background: #dbeafe; }
        .upload-box.has-file { border-color: #22c55e; background: #f0fdf4; }
        .upload-box.has-file .upload-icon { display: none; }
        .upload-icon { font-size: 36px; margin-bottom: 12px; }
        .upload-label { 
            font-size: 14px; 
            font-weight: 600; 
            color: #1e40af; 
            margin-bottom: 8px;
            display: block;
        }
        .upload-text { color: #475569; font-size: 13px; margin-bottom: 4px; }
        .upload-hint { color: #94a3b8; font-size: 12px; }
        .file-name { 
            color: #22c55e; 
            font-weight: 600; 
            font-size: 14px; 
            word-break: break-all;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .file-name .check { font-size: 20px; }
        .btn {
            width: 100%;
            padding: 16px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 24px;
        }
        .btn-primary { background: #1e40af; color: white; }
        .btn-primary:hover { background: #1e3a8a; }
        .btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
        .btn-success { background: #22c55e; color: white; }
        .btn-success:hover { background: #16a34a; }
        .status { margin-top: 24px; padding: 16px; border-radius: 8px; display: none; }
        .status.show { display: block; }
        .status.processing { background: #fef3c7; color: #92400e; }
        .status.success { background: #dcfce7; color: #166534; }
        .status.error { background: #fee2e2; color: #991b1b; }
        .spinner {
            display: inline-block;
            width: 16px; height: 16px;
            border: 2px solid currentColor;
            border-right-color: transparent;
            border-radius: 50%;
            animation: spin 0.75s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 32px; }
        .feature { text-align: center; padding: 16px; background: #f8fafc; border-radius: 8px; }
        .feature-icon { font-size: 24px; margin-bottom: 8px; }
        .feature-text { font-size: 13px; color: #64748b; }
        .footer { text-align: center; margin-top: 32px; color: #64748b; font-size: 13px; }
        .file-input { display: none; }
        .extracted-info {
            margin-top: 20px;
            padding: 16px;
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            border-radius: 8px;
            display: none;
        }
        .extracted-info.show { display: block; }
        .extracted-info h4 { 
            font-size: 13px; 
            color: #0369a1; 
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .extracted-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .extracted-item {
            font-size: 14px;
        }
        .extracted-label {
            color: #64748b;
            font-size: 11px;
            text-transform: uppercase;
        }
        .extracted-value {
            color: #0f172a;
            font-weight: 600;
        }
        .divider {
            display: flex;
            align-items: center;
            margin: 24px 0;
            color: #94a3b8;
            font-size: 13px;
        }
        .divider::before, .divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: #e2e8f0;
        }
        .divider span {
            padding: 0 16px;
        }
        @media (max-width: 640px) {
            .upload-row { grid-template-columns: 1fr; }
            .features { grid-template-columns: 1fr; }
            .extracted-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">[M E]</div>
            <h1>Packing List Generator</h1>
            <p>Upload both files to automatically generate factory packing instructions</p>
        </div>
        <div class="card">
            <form id="upload-form">
                <div class="upload-row">
                    <div class="upload-box" id="drop-zone-internal">
                        <input type="file" id="file-internal" class="file-input" accept=".pdf" />
                        <div class="upload-icon">[1]</div>
                        <span class="upload-label">Internal PO</span>
                        <div class="upload-text" id="text-internal">Your Mark Edwards PO</div>
                        <div class="upload-hint">Contains PO# and Factory</div>
                    </div>
                    <div class="upload-box" id="drop-zone-customer">
                        <input type="file" id="file-customer" class="file-input" accept=".pdf" />
                        <div class="upload-icon">[2]</div>
                        <span class="upload-label">Customer Packing List</span>
                        <div class="upload-text" id="text-customer">Customer's packing list</div>
                        <div class="upload-hint">Source packing details</div>
                    </div>
                </div>
                
                <div class="extracted-info" id="extracted-info">
                    <h4>Extracted from Internal PO</h4>
                    <div class="extracted-grid">
                        <div class="extracted-item">
                            <div class="extracted-label">Internal PO #</div>
                            <div class="extracted-value" id="extracted-po">-</div>
                        </div>
                        <div class="extracted-item">
                            <div class="extracted-label">Factory</div>
                            <div class="extracted-value" id="extracted-factory">-</div>
                        </div>
                    </div>
                </div>
                
                <button type="submit" class="btn btn-primary" id="submit-btn" disabled>
                    Generate Factory Packing List
                </button>
            </form>
            <div class="status" id="status"></div>
            <a href="#" class="btn btn-success" id="download-btn" style="display: none; text-decoration: none; text-align: center;">Download Factory Packing List</a>
            
            <div class="divider"><span>Included in output</span></div>
            
            <div class="features">
                <div class="feature"><div class="feature-icon">STY</div><div class="feature-text">Style Numbers</div></div>
                <div class="feature"><div class="feature-icon">QTY</div><div class="feature-text">Quantities</div></div>
                <div class="feature"><div class="feature-icon">PKG</div><div class="feature-text">Pack Config</div></div>
            </div>
        </div>
        <div class="footer">Mark Edwards Apparel Inc. - Internal Tool</div>
    </div>
    <script>
        const dropZoneInternal = document.getElementById('drop-zone-internal');
        const dropZoneCustomer = document.getElementById('drop-zone-customer');
        const fileInternal = document.getElementById('file-internal');
        const fileCustomer = document.getElementById('file-customer');
        const textInternal = document.getElementById('text-internal');
        const textCustomer = document.getElementById('text-customer');
        const submitBtn = document.getElementById('submit-btn');
        const form = document.getElementById('upload-form');
        const status = document.getElementById('status');
        const downloadBtn = document.getElementById('download-btn');
        const extractedInfo = document.getElementById('extracted-info');
        const extractedPO = document.getElementById('extracted-po');
        const extractedFactory = document.getElementById('extracted-factory');
        
        let selectedInternal = null;
        let selectedCustomer = null;
        
        // Setup for internal PO upload
        setupDropZone(dropZoneInternal, fileInternal, textInternal, 'internal');
        setupDropZone(dropZoneCustomer, fileCustomer, textCustomer, 'customer');
        
        function setupDropZone(zone, input, text, type) {
            zone.addEventListener('click', () => input.click());
            zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
            zone.addEventListener('dragleave', () => { zone.classList.remove('drag-over'); });
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                const files = e.dataTransfer.files;
                if (files.length > 0 && files[0].type === 'application/pdf') {
                    handleFile(files[0], type, zone, text);
                }
            });
            input.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFile(e.target.files[0], type, zone, text);
                }
            });
        }
        
        function handleFile(file, type, zone, text) {
            zone.classList.add('has-file');
            text.innerHTML = '<span class="file-name"><span class="check">OK</span> ' + file.name + '</span>';
            
            if (type === 'internal') {
                selectedInternal = file;
                // Extract info from internal PO
                extractInternalPO(file);
            } else {
                selectedCustomer = file;
            }
            checkFormValid();
        }
        
        async function extractInternalPO(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/extract-internal', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.success) {
                    extractedPO.textContent = data.po_number || '-';
                    extractedFactory.textContent = data.factory_name || '-';
                    extractedInfo.classList.add('show');
                }
            } catch (err) {
                console.error('Error extracting internal PO:', err);
            }
        }
        
        function checkFormValid() {
            submitBtn.disabled = !(selectedInternal && selectedCustomer);
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedInternal || !selectedCustomer) return;
            
            const formData = new FormData();
            formData.append('internal_po_file', selectedInternal);
            formData.append('customer_file', selectedCustomer);
            
            status.className = 'status show processing';
            status.innerHTML = '<span class="spinner"></span> Processing packing lists...';
            submitBtn.disabled = true;
            downloadBtn.style.display = 'none';
            
            try {
                const response = await fetch('/process', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.success) {
                    status.className = 'status show success';
                    status.innerHTML = 'Success! PO# ' + data.po_number + ' ready for download.';
                    downloadBtn.href = data.download_url;
                    downloadBtn.style.display = 'block';
                } else {
                    status.className = 'status show error';
                    status.innerHTML = 'Error: ' + data.error;
                }
            } catch (err) {
                status.className = 'status show error';
                status.innerHTML = 'Error: ' + err.message;
            }
            submitBtn.disabled = false;
        });
    </script>
</body>
</html>'''


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_internal_po_info(text):
    """Extract PO number and factory name from internal PO document"""
    info = {
        'po_number': None,
        'factory_name': None,
    }
    
    # Extract PO number - look for "Purchase Order Number XXXXXX" pattern
    po_patterns = [
        r'Purchase\s+Order\s+Number\s+(\d{6})',
        r'PO\s*#?\s*:?\s*(\d{6})',
        r'Order\s+Number[:\s]+(\d{6})',
    ]
    for pattern in po_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info['po_number'] = match.group(1)
            break
    
    # Also try to get PO from filename pattern if in text
    if not info['po_number']:
        match = re.search(r'(\d{6})\.pdf', text, re.IGNORECASE)
        if match:
            info['po_number'] = match.group(1)
    
    # Extract factory name - look for common patterns in the "To" section
    factory_patterns = [
        r'To\s+([A-Z][A-Z\s]+(?:IMP|EXP|IMPORT|EXPORT|TRADING|FACTORY|MANUFACTURING|MFG|CO\.?\s*,?\s*LTD))',
        r'NINGBO\s+[\w\s]+',
        r'SHANGHAI\s+[\w\s]+(?:CO|LTD|TRADING)',
        r'GUANGZHOU\s+[\w\s]+(?:CO|LTD|TRADING)',
        r'SHENZHEN\s+[\w\s]+(?:CO|LTD|TRADING)',
    ]
    
    for pattern in factory_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            factory = match.group(0).strip()
            # Clean up the factory name
            factory = ' '.join(factory.split())  # Normalize whitespace
            # Truncate if too long
            if len(factory) > 40:
                factory = factory[:40].rsplit(' ', 1)[0]
            info['factory_name'] = factory.upper()
            break
    
    return info


class PackingListSanitizer:
    REDACT_PATTERNS = {
        'customer_po': [r'PURCHASE ORDER(?:\s+NO\.?)?\s*[:#]?\s*(\d{7,})', r'PO\s*(?:Number|#|No\.?)?\s*[:#]?\s*(\d{7,})'],
        'customer_name': [r'^([A-Z][A-Z\s&\(\)0-9]+(?:LLC|INC|CORP|LTD))', r'Customer[:\s]+([A-Z][A-Za-z\s&\(\)0-9]+(?:LLC|INC|CORP|LTD)?)'],
        'customer_sku': [r'\d{4}-\d{5}-\d{4}-\d{3}-\d{4}'],
        'pricing': [r'\$[\d,]+\.?\d*', r'COST\s+PER\s+CARTON', r'TOTAL\s+CARTONS?\s+COST'],
        'ship_split': [r'SHIP\s+\d+\s+TO\s+\w+', r'\*+\s*SHIP\s+\d+.*?\*+'],
        'addresses': [r'\d+\s+[\w\s]+(?:STREET|ST|AVE|AVENUE|ROAD|RD|BLVD|DRIVE|DR)[,\s]+[\w\s]+,?\s*[A-Z]{2}\s*\d{5}'],
        'contact_info': [r'[\w.-]+@[\w.-]+\.\w+', r'E-MAIL[:\s]*[\w.-]+@[\w.-]+'],
        'blockout': [r'BLOCKOUT\s+NO\.?\s*\d+'],
    }
    
    KEEP_PATTERNS = {
        'vendor_style': [r'(?:^|\s)(\d{5}[A-Z]-?\w*)'],
        'colors': [r'(BLACK\s*(?:DOT)?\s*(?:STAR)?)', r'(CLOUD\s*H\.?GREY\s*(?:DOT)?\s*(?:CHERRY)?)', r'(WHITE/?NAVY\s*STRIPE\s*(?:HEART)?)', r'(GARDENIA\s*(?:STAR)?)', r'(BROWN\s*STRIPE\s*(?:CHERRY)?)', r'(NAVY\s*STRIPE\s*(?:STAR)?)', r'(NAVAL\s*ACADEMY\s*(?:CHERRY)?)', r'(BLUE\s*STRIPE\s*(?:STAR)?)', r'(BALLERINA\s*(?:HEART)?)', r'(BURG(?:UNDY)?\s*DOTS?\s*(?:HEART)?)'],
        'sizes': [r'\b(S|M|L|XL|XXL|S/P|M/M|L/G|XL/TG)\b'],
        'total_units': [r'TOTAL\s+UNITS\s+FOR\s+\d+\s+CARTONS?\s+(\d[\d,]*)', r'Total\s+Quantity\s+of\s+Units[:\s]*(\d[\d,]*)'],
        'units_per_carton': [r'TOTAL\s+UNITS\s+FOR\s+1\s+CARTON\s+(\d+)'],
        'total_cartons': [r'FOR\s+(\d+)\s+CARTONS', r'(\d+)\s+CARTONS'],
    }

    def __init__(self):
        self.detected_info = {}
    
    def detect_info(self, text):
        info = {'confidential': {}, 'keep': {}}
        for field, patterns in self.REDACT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    if field not in info['confidential']:
                        info['confidential'][field] = []
                    info['confidential'][field].extend(matches if isinstance(matches[0], str) else [m[0] for m in matches])
        for field, patterns in self.KEEP_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    if field not in info['keep']:
                        info['keep'][field] = []
                    for m in matches:
                        if isinstance(m, tuple):
                            info['keep'][field].extend([x for x in m if x])
                        else:
                            info['keep'][field].append(m)
        for category in info:
            for field in info[category]:
                info[category][field] = list(set(info[category][field]))
        self.detected_info = info
        return info
    
    def generate_factory_document(self, internal_po, factory_name=""):
        info = self.detected_info
        keep = info.get('keep', {})
        confidential = info.get('confidential', {})
        
        vendor_style = 'N/A'
        if keep.get('vendor_style'):
            styles = [v for v in keep.get('vendor_style', []) if v != 'CARTON']
            vendor_style = styles[0] if styles else keep.get('vendor_style', ['N/A'])[0]
        
        colors = keep.get('colors', [])
        sizes = list(set(keep.get('sizes', [])))
        total_units = keep.get('total_units', ['N/A'])
        if total_units and len(total_units) > 1:
            total_units = max(total_units, key=lambda x: int(x.replace(',', '')) if x.replace(',', '').isdigit() else 0)
        else:
            total_units = total_units[0] if total_units else 'N/A'
        units_per_carton = keep.get('units_per_carton', ['N/A'])[0] if keep.get('units_per_carton') else 'N/A'
        total_cartons = keep.get('total_cartons', ['N/A'])[0] if keep.get('total_cartons') else 'N/A'
        
        clean_colors = []
        seen = set()
        for c in colors:
            c_clean = ' '.join(c.split()).upper()
            if c_clean and c_clean not in seen and len(c_clean) > 2:
                seen.add(c_clean)
                clean_colors.append(c_clean)
        
        size_order = ['S', 'S/P', 'M', 'M/M', 'L', 'L/G', 'XL', 'XL/TG', 'XXL']
        sizes = sorted(set(sizes), key=lambda x: size_order.index(x) if x in size_order else 99)
        
        html = f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Factory Packing Instructions - PO {internal_po}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:40px;background:#f8fafc;color:#1e293b}}
.document{{max-width:800px;margin:0 auto;background:white;padding:40px;border-radius:12px;box-shadow:0 4px 6px -1px rgb(0 0 0/0.1)}}
.header{{border-bottom:3px solid #1e40af;padding-bottom:24px;margin-bottom:24px}}
.header h1{{color:#1e40af;font-size:24px;margin-bottom:8px}}
.header-subtitle{{color:#64748b;font-size:14px}}
.meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:20px;padding:20px;background:#f1f5f9;border-radius:8px}}
.meta-label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}}
.meta-value{{font-size:18px;font-weight:700;color:#0f172a}}
.section{{margin:28px 0;padding:24px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0}}
.section-title{{font-weight:700;color:#1e40af;margin-bottom:16px;font-size:14px;text-transform:uppercase;letter-spacing:0.5px}}
.data-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
.data-label{{font-size:12px;color:#64748b;margin-bottom:2px}}
.data-value{{font-size:15px;color:#0f172a;font-weight:500}}
.colors-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.color-tag{{background:#e0e7ff;color:#3730a3;padding:6px 14px;border-radius:6px;font-size:13px;font-weight:500}}
.sizes-grid{{display:flex;gap:8px;margin-top:8px}}
.size-tag{{background:#1e40af;color:white;padding:8px 16px;border-radius:6px;font-weight:700;font-size:14px}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;text-align:center}}
@media print{{body{{background:white;padding:20px}}.document{{box-shadow:none}}}}
</style>
</head>
<body>
<div class="document">
<div class="header">
<h1>FACTORY PACKING INSTRUCTIONS</h1>
<div class="header-subtitle">Mark Edwards Apparel Inc.</div>
<div class="meta-grid">
<div class="meta-item"><div class="meta-label">PO Number</div><div class="meta-value">{internal_po}</div></div>
<div class="meta-item"><div class="meta-label">Factory</div><div class="meta-value">{factory_name or 'As Assigned'}</div></div>
<div class="meta-item"><div class="meta-label">Date</div><div class="meta-value">{datetime.now().strftime('%Y-%m-%d')}</div></div>
</div>
</div>

<div class="section">
<div class="section-title">Product Information</div>
<div class="data-grid">
<div class="data-item"><div class="data-label">Vendor Style</div><div class="data-value">{vendor_style}</div></div>
<div class="data-item"><div class="data-label">Commodity</div><div class="data-value">Top</div></div>
</div>
<div style="margin-top:20px"><div class="data-label">Colors ({len(clean_colors)} variants)</div>
<div class="colors-grid">{"".join(f'<span class="color-tag">{c}</span>' for c in clean_colors[:12])}</div></div>
<div style="margin-top:20px"><div class="data-label">Sizes</div>
<div class="sizes-grid">{"".join(f'<span class="size-tag">{s}</span>' for s in sizes[:6])}</div></div>
</div>

<div class="section">
<div class="section-title">Packing Configuration</div>
<div class="data-grid">
<div class="data-item"><div class="data-label">Units Per Carton</div><div class="data-value">{units_per_carton}</div></div>
<div class="data-item"><div class="data-label">Total Cartons</div><div class="data-value">{total_cartons}</div></div>
<div class="data-item"><div class="data-label">Total Units</div><div class="data-value">{total_units}</div></div>
<div class="data-item"><div class="data-label">Prepack Ratio</div><div class="data-value">2-2-1-1 (S-M-L-XL)</div></div>
</div>
</div>

<div class="section">
<div class="section-title">Carton Marking Instructions</div>
<div class="data-item"><div class="data-label">Reference on all cartons</div>
<div class="data-value" style="font-size:18px">PO# {internal_po}</div></div>
<p style="margin-top:12px;font-size:13px;color:#64748b">All cartons must be clearly marked with the above PO number.</p>
</div>

<div class="footer">Mark Edwards Apparel Inc. - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</div>
</body>
</html>'''
        return html


@app.route('/')
def index():
    return Response(INDEX_HTML, mimetype='text/html')


@app.route('/extract-internal', methods=['POST'])
def extract_internal():
    """Extract PO number and factory from internal PO file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file'}), 400
    
    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        unique_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
        file.save(upload_path)
        
        text = extract_text_from_pdf(upload_path)
        info = extract_internal_po_info(text)
        
        # Also try to get PO from filename
        if not info['po_number']:
            po_match = re.search(r'(\d{6})', filename)
            if po_match:
                info['po_number'] = po_match.group(1)
        
        os.remove(upload_path)
        
        return jsonify({
            'success': True,
            'po_number': info['po_number'],
            'factory_name': info['factory_name'],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/process', methods=['POST'])
def process_files():
    """Process both files and generate sanitized output"""
    if 'internal_po_file' not in request.files or 'customer_file' not in request.files:
        return jsonify({'error': 'Both files are required'}), 400
    
    internal_file = request.files['internal_po_file']
    customer_file = request.files['customer_file']
    
    if not allowed_file(internal_file.filename) or not allowed_file(customer_file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    try:
        unique_id = str(uuid.uuid4())[:8]
        
        # Save internal PO file
        internal_filename = secure_filename(internal_file.filename)
        internal_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_internal_{internal_filename}")
        internal_file.save(internal_path)
        
        # Save customer file
        customer_filename = secure_filename(customer_file.filename)
        customer_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_customer_{customer_filename}")
        customer_file.save(customer_path)
        
        # Extract info from internal PO
        internal_text = extract_text_from_pdf(internal_path)
        internal_info = extract_internal_po_info(internal_text)
        
        # Also try to get PO from filename
        if not internal_info['po_number']:
            po_match = re.search(r'(\d{6})', internal_filename)
            if po_match:
                internal_info['po_number'] = po_match.group(1)
        
        po_number = internal_info['po_number'] or 'UNKNOWN'
        factory_name = internal_info['factory_name'] or ''
        
        # Process customer packing list
        customer_text = extract_text_from_pdf(customer_path)
        sanitizer = PackingListSanitizer()
        info = sanitizer.detect_info(customer_text)
        html = sanitizer.generate_factory_document(po_number, factory_name)
        
        # Save output
        output_filename = f"Factory_Packing_PO_{po_number}_{unique_id}.html"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Cleanup
        os.remove(internal_path)
        os.remove(customer_path)
        
        return jsonify({
            'success': True,
            'download_url': url_for('download_file', filename=output_filename),
            'po_number': po_number,
            'factory_name': factory_name,
            'detected': {
                'redacted': list(info['confidential'].keys()),
                'kept': list(info['keep'].keys()),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download_file(filename):
    return send_file(
        os.path.join(app.config['OUTPUT_FOLDER'], filename),
        as_attachment=True,
        download_name=filename
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
