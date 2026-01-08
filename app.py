"""
Packing List Sanitizer - Web Application
Mark Edwards Apparel Inc.
Single-file version for easy deployment
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
        .container { max-width: 600px; margin: 0 auto; }
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
        .upload-zone {
            border: 2px dashed #cbd5e1;
            border-radius: 12px;
            padding: 48px 24px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: #f8fafc;
        }
        .upload-zone:hover { border-color: #3b82f6; background: #eff6ff; }
        .upload-zone.drag-over { border-color: #3b82f6; background: #dbeafe; }
        .upload-zone.has-file { border-color: #22c55e; background: #f0fdf4; }
        .upload-icon { font-size: 48px; margin-bottom: 16px; }
        .upload-text { color: #475569; font-size: 16px; margin-bottom: 8px; }
        .upload-hint { color: #94a3b8; font-size: 14px; }
        .file-name { color: #22c55e; font-weight: 600; font-size: 16px; }
        .form-group { margin-top: 24px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        label { display: block; font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; }
        .required { color: #ef4444; }
        input[type="text"] {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-size: 16px;
            transition: all 0.2s;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
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
        #file-input { display: none; }
        @media (max-width: 640px) {
            .form-row { grid-template-columns: 1fr; }
            .features { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🔒</div>
            <h1>Packing List Sanitizer</h1>
            <p>Remove confidential customer info before sending to factories</p>
        </div>
        <div class="card">
            <form id="upload-form">
                <div class="upload-zone" id="drop-zone">
                    <input type="file" id="file-input" accept=".pdf" />
                    <div class="upload-icon">📄</div>
                    <div class="upload-text" id="upload-text">Drop customer packing list here or click to browse</div>
                    <div class="upload-hint">PDF files only</div>
                </div>
                <div class="form-group">
                    <div class="form-row">
                        <div>
                            <label for="internal_po">Internal PO # <span class="required">*</span></label>
                            <input type="text" id="internal_po" name="internal_po" placeholder="e.g., 219043" required />
                        </div>
                        <div>
                            <label for="factory_name">Factory Name</label>
                            <input type="text" id="factory_name" name="factory_name" placeholder="e.g., NINGBO PHOENIX" />
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" id="submit-btn" disabled>Generate Sanitized Packing List</button>
            </form>
            <div class="status" id="status"></div>
            <a href="#" class="btn btn-success" id="download-btn" style="display: none; text-decoration: none; text-align: center;">⬇️ Download Sanitized Document</a>
            <div class="features">
                <div class="feature"><div class="feature-icon">🏢</div><div class="feature-text">Removes Customer Names</div></div>
                <div class="feature"><div class="feature-icon">💰</div><div class="feature-text">Hides Pricing Info</div></div>
                <div class="feature"><div class="feature-icon">📍</div><div class="feature-text">Redacts Addresses</div></div>
            </div>
        </div>
        <div class="footer">Mark Edwards Apparel Inc. • Internal Tool</div>
    </div>
    <script>
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const uploadText = document.getElementById('upload-text');
        const submitBtn = document.getElementById('submit-btn');
        const form = document.getElementById('upload-form');
        const status = document.getElementById('status');
        const downloadBtn = document.getElementById('download-btn');
        const internalPO = document.getElementById('internal_po');
        let selectedFile = null;
        
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
        dropZone.addEventListener('dragleave', () => { dropZone.classList.remove('drag-over'); });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type === 'application/pdf') handleFile(files[0]);
        });
        fileInput.addEventListener('change', (e) => { if (e.target.files.length > 0) handleFile(e.target.files[0]); });
        
        function handleFile(file) {
            selectedFile = file;
            dropZone.classList.add('has-file');
            uploadText.innerHTML = '<span class="file-name">✅ ' + file.name + '</span>';
            checkFormValid();
        }
        function checkFormValid() { submitBtn.disabled = !(selectedFile && internalPO.value.trim()); }
        internalPO.addEventListener('input', checkFormValid);
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!selectedFile || !internalPO.value.trim()) return;
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('internal_po', internalPO.value.trim());
            formData.append('factory_name', document.getElementById('factory_name').value.trim());
            status.className = 'status show processing';
            status.innerHTML = '<span class="spinner"></span> Processing packing list...';
            submitBtn.disabled = true;
            downloadBtn.style.display = 'none';
            try {
                const response = await fetch('/upload', { method: 'POST', body: formData });
                const data = await response.json();
                if (data.success) {
                    status.className = 'status show success';
                    status.innerHTML = '✅ Successfully sanitized! Redacted: ' + data.detected.redacted.join(', ');
                    downloadBtn.href = data.download_url;
                    downloadBtn.style.display = 'block';
                } else {
                    status.className = 'status show error';
                    status.innerHTML = '❌ Error: ' + data.error;
                }
            } catch (err) {
                status.className = 'status show error';
                status.innerHTML = '❌ Error: ' + err.message;
            }
            submitBtn.disabled = false;
        });
    </script>
</body>
</html>'''


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
        
    def extract_text_from_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    
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
        redacted = [field.replace('_', ' ').title() for field, values in confidential.items() if values]
        
        html = f'''<!DOCTYPE html>
<html><head><title>Factory Packing Instructions - PO {internal_po}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:40px;background:#f8fafc;color:#1e293b}}.document{{max-width:800px;margin:0 auto;background:white;padding:40px;border-radius:12px;box-shadow:0 4px 6px -1px rgb(0 0 0/0.1)}}.header{{border-bottom:3px solid #1e40af;padding-bottom:24px;margin-bottom:24px}}.header h1{{color:#1e40af;font-size:24px;margin-bottom:8px}}.header-subtitle{{color:#64748b;font-size:14px}}.meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:20px;padding:20px;background:#f1f5f9;border-radius:8px}}.meta-label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}}.meta-value{{font-size:18px;font-weight:700;color:#0f172a}}.section{{margin:28px 0;padding:24px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0}}.section-title{{font-weight:700;color:#1e40af;margin-bottom:16px;font-size:14px;text-transform:uppercase;letter-spacing:0.5px}}.data-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}.data-label{{font-size:12px;color:#64748b;margin-bottom:2px}}.data-value{{font-size:15px;color:#0f172a;font-weight:500}}.colors-grid{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}.color-tag{{background:#e0e7ff;color:#3730a3;padding:6px 14px;border-radius:6px;font-size:13px;font-weight:500}}.sizes-grid{{display:flex;gap:8px;margin-top:8px}}.size-tag{{background:#1e40af;color:white;padding:8px 16px;border-radius:6px;font-weight:700;font-size:14px}}.notice{{background:#fef3c7;border:1px solid #f59e0b;padding:16px;border-radius:8px;margin-top:28px}}.notice-title{{font-weight:700;color:#92400e;font-size:13px;margin-bottom:6px}}.notice-text{{font-size:13px;color:#78350f}}.footer{{margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;text-align:center}}.stamp{{display:inline-block;border:2px solid #dc2626;color:#dc2626;padding:4px 12px;border-radius:4px;font-weight:700;font-size:11px;transform:rotate(-3deg);margin-left:12px}}@media print{{body{{background:white;padding:20px}}.document{{box-shadow:none}}}}
</style></head><body><div class="document">
<div class="header"><h1>🏭 FACTORY PACKING INSTRUCTIONS <span class="stamp">CONFIDENTIAL</span></h1><div class="header-subtitle">Mark Edwards Apparel Inc.</div>
<div class="meta-grid"><div class="meta-item"><div class="meta-label">Internal PO Number</div><div class="meta-value">{internal_po}</div></div><div class="meta-item"><div class="meta-label">Factory</div><div class="meta-value">{factory_name or 'As Assigned'}</div></div><div class="meta-item"><div class="meta-label">Date Generated</div><div class="meta-value">{datetime.now().strftime('%Y-%m-%d')}</div></div></div></div>
<div class="section"><div class="section-title">📦 Product Information</div><div class="data-grid"><div class="data-item"><div class="data-label">Vendor Style</div><div class="data-value">{vendor_style}</div></div><div class="data-item"><div class="data-label">Commodity</div><div class="data-value">Top</div></div></div>
<div style="margin-top:20px"><div class="data-label">Colors ({len(clean_colors)} variants)</div><div class="colors-grid">{"".join(f'<span class="color-tag">{c}</span>' for c in clean_colors[:12])}</div></div>
<div style="margin-top:20px"><div class="data-label">Sizes</div><div class="sizes-grid">{"".join(f'<span class="size-tag">{s}</span>' for s in sizes[:6])}</div></div></div>
<div class="section"><div class="section-title">📋 Packing Configuration</div><div class="data-grid"><div class="data-item"><div class="data-label">Units Per Carton</div><div class="data-value">{units_per_carton}</div></div><div class="data-item"><div class="data-label">Total Cartons</div><div class="data-value">{total_cartons}</div></div><div class="data-item"><div class="data-label">Total Units</div><div class="data-value">{total_units}</div></div><div class="data-item"><div class="data-label">Prepack Ratio</div><div class="data-value">2-2-1-1 (S-M-L-XL)</div></div></div></div>
<div class="section"><div class="section-title">🏷️ Carton Marking Instructions</div><div class="data-item"><div class="data-label">Reference on all cartons</div><div class="data-value" style="font-size:18px">PO# {internal_po}</div></div><p style="margin-top:12px;font-size:13px;color:#64748b">All cartons must be clearly marked with the above PO number. Do not include any customer or buyer information on carton labels.</p></div>
<div class="notice"><div class="notice-title">⚠️ CONFIDENTIAL INFORMATION REMOVED</div><div class="notice-text">The following fields have been redacted from the original customer packing list: <strong>{', '.join(redacted) if redacted else 'None detected'}</strong></div></div>
<div class="footer">Generated by Mark Edwards Apparel Packing List Sanitizer • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div></div></body></html>'''
        return html


@app.route('/')
def index():
    return Response(INDEX_HTML, mimetype='text/html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    internal_po = request.form.get('internal_po', '').strip()
    factory_name = request.form.get('factory_name', '').strip()
    
    if not internal_po:
        return jsonify({'error': 'Internal PO number is required'}), 400
    
    try:
        unique_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
        file.save(upload_path)
        
        sanitizer = PackingListSanitizer()
        text = sanitizer.extract_text_from_pdf(upload_path)
        info = sanitizer.detect_info(text)
        html = sanitizer.generate_factory_document(internal_po, factory_name)
        
        output_filename = f"Factory_Packing_PO_{internal_po}_{unique_id}.html"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        os.remove(upload_path)
        
        return jsonify({
            'success': True,
            'download_url': url_for('download_file', filename=output_filename),
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
