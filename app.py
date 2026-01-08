"""
Packing List Sanitizer - Web Application
Mark Edwards Apparel Inc.

A web-based tool to remove confidential customer information from packing lists
before sending to overseas factories.
"""

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class PackingListSanitizer:
    """Sanitizes customer packing lists by removing confidential information"""
    
    REDACT_PATTERNS = {
        'customer_po': [
            r'PURCHASE ORDER(?:\s+NO\.?)?\s*[:#]?\s*(\d{7,})',
            r'PO\s*(?:Number|#|No\.?)?\s*[:#]?\s*(\d{7,})',
        ],
        'customer_name': [
            r'^([A-Z][A-Z\s&\(\)0-9]+(?:LLC|INC|CORP|LTD))',
            r'Customer[:\s]+([A-Z][A-Za-z\s&\(\)0-9]+(?:LLC|INC|CORP|LTD)?)',
        ],
        'customer_sku': [
            r'\d{4}-\d{5}-\d{4}-\d{3}-\d{4}',
        ],
        'pricing': [
            r'\$[\d,]+\.?\d*',
            r'COST\s+PER\s+CARTON',
            r'TOTAL\s+CARTONS?\s+COST',
        ],
        'ship_split': [
            r'SHIP\s+\d+\s+TO\s+\w+',
            r'\*+\s*SHIP\s+\d+.*?\*+',
        ],
        'addresses': [
            r'\d+\s+[\w\s]+(?:STREET|ST|AVE|AVENUE|ROAD|RD|BLVD|DRIVE|DR)[,\s]+[\w\s]+,?\s*[A-Z]{2}\s*\d{5}',
        ],
        'contact_info': [
            r'[\w.-]+@[\w.-]+\.\w+',
            r'E-MAIL[:\s]*[\w.-]+@[\w.-]+',
        ],
        'blockout': [
            r'BLOCKOUT\s+NO\.?\s*\d+',
        ],
    }
    
    KEEP_PATTERNS = {
        'vendor_style': [
            r'(?:^|\s)(\d{5}[A-Z]-?\w*)',
        ],
        'colors': [
            r'(BLACK\s*(?:DOT)?\s*(?:STAR)?)',
            r'(CLOUD\s*H\.?GREY\s*(?:DOT)?\s*(?:CHERRY)?)',
            r'(WHITE/?NAVY\s*STRIPE\s*(?:HEART)?)',
            r'(GARDENIA\s*(?:STAR)?)',
            r'(BROWN\s*STRIPE\s*(?:CHERRY)?)',
            r'(NAVY\s*STRIPE\s*(?:STAR)?)',
            r'(NAVAL\s*ACADEMY\s*(?:CHERRY)?)',
            r'(BLUE\s*STRIPE\s*(?:STAR)?)',
            r'(BALLERINA\s*(?:HEART)?)',
            r'(BURG(?:UNDY)?\s*DOTS?\s*(?:HEART)?)',
            r'(PINK)', r'(GREY|GRAY)', r'(BURGUNDY)',
        ],
        'sizes': [
            r'\b(S|M|L|XL|XXL|S/P|M/M|L/G|XL/TG)\b',
        ],
        'total_units': [
            r'TOTAL\s+UNITS\s+FOR\s+\d+\s+CARTONS?\s+(\d[\d,]*)',
            r'Total\s+Quantity\s+of\s+Units[:\s]*(\d[\d,]*)',
        ],
        'units_per_carton': [
            r'TOTAL\s+UNITS\s+FOR\s+1\s+CARTON\s+(\d+)',
        ],
        'total_cartons': [
            r'FOR\s+(\d+)\s+CARTONS',
            r'(\d+)\s+CARTONS',
        ],
        'pack_config': [
            r'PREPACK[:\s]*(\d+-\d+-\d+-\d+)',
        ],
    }

    def __init__(self):
        self.detected_info = {}
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n--- PAGE BREAK ---\n"
        return text
    
    def detect_info(self, text: str) -> dict:
        info = {'confidential': {}, 'keep': {}}
        
        for field, patterns in self.REDACT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    if field not in info['confidential']:
                        info['confidential'][field] = []
                    info['confidential'][field].extend(
                        matches if isinstance(matches[0], str) else [m[0] for m in matches]
                    )
        
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
    
    def generate_factory_document(self, internal_po: str, factory_name: str = "") -> str:
        info = self.detected_info
        keep = info.get('keep', {})
        confidential = info.get('confidential', {})
        
        vendor_style = keep.get('vendor_style', ['N/A'])[0] if keep.get('vendor_style') else 'N/A'
        # Filter out 'CARTON' from vendor styles
        if vendor_style == 'CARTON' and len(keep.get('vendor_style', [])) > 1:
            vendor_style = [v for v in keep.get('vendor_style', []) if v != 'CARTON'][0]
        
        colors = keep.get('colors', [])
        sizes = list(set(keep.get('sizes', [])))
        total_units = keep.get('total_units', ['N/A'])
        # Get the larger number (total, not per carton)
        if total_units and len(total_units) > 1:
            total_units = max(total_units, key=lambda x: int(x.replace(',', '')) if x.replace(',', '').isdigit() else 0)
        else:
            total_units = total_units[0] if total_units else 'N/A'
            
        units_per_carton = keep.get('units_per_carton', ['N/A'])[0] if keep.get('units_per_carton') else 'N/A'
        total_cartons = keep.get('total_cartons', ['N/A'])[0] if keep.get('total_cartons') else 'N/A'
        
        # Clean colors
        clean_colors = []
        seen = set()
        for c in colors:
            c_clean = ' '.join(c.split()).upper()
            if c_clean and c_clean not in seen and len(c_clean) > 2:
                seen.add(c_clean)
                clean_colors.append(c_clean)
        
        # Sort sizes
        size_order = ['S', 'S/P', 'M', 'M/M', 'L', 'L/G', 'XL', 'XL/TG', 'XXL']
        sizes = sorted(set(sizes), key=lambda x: size_order.index(x) if x in size_order else 99)
        
        # Track redacted fields
        redacted = [field.replace('_', ' ').title() for field, values in confidential.items() if values]
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Factory Packing Instructions - PO {internal_po}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Arial, sans-serif; 
            margin: 0; padding: 40px; 
            background: #f8fafc; color: #1e293b;
        }}
        .document {{
            max-width: 800px; margin: 0 auto; background: white;
            padding: 40px; border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }}
        .header {{ border-bottom: 3px solid #1e40af; padding-bottom: 24px; margin-bottom: 24px; }}
        .header h1 {{ color: #1e40af; font-size: 24px; margin-bottom: 8px; }}
        .header-subtitle {{ color: #64748b; font-size: 14px; }}
        .meta-grid {{ 
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; 
            margin-top: 20px; padding: 20px; background: #f1f5f9; border-radius: 8px;
        }}
        .meta-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
        .meta-value {{ font-size: 18px; font-weight: 700; color: #0f172a; }}
        .section {{ margin: 28px 0; padding: 24px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .section-title {{ font-weight: 700; color: #1e40af; margin-bottom: 16px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .data-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }}
        .data-label {{ font-size: 12px; color: #64748b; margin-bottom: 2px; }}
        .data-value {{ font-size: 15px; color: #0f172a; font-weight: 500; }}
        .colors-grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
        .color-tag {{ background: #e0e7ff; color: #3730a3; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 500; }}
        .sizes-grid {{ display: flex; gap: 8px; margin-top: 8px; }}
        .size-tag {{ background: #1e40af; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 700; font-size: 14px; }}
        .notice {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 8px; margin-top: 28px; }}
        .notice-title {{ font-weight: 700; color: #92400e; font-size: 13px; margin-bottom: 6px; }}
        .notice-text {{ font-size: 13px; color: #78350f; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center; }}
        .stamp {{ display: inline-block; border: 2px solid #dc2626; color: #dc2626; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 11px; transform: rotate(-3deg); margin-left: 12px; }}
        @media print {{ body {{ background: white; padding: 20px; }} .document {{ box-shadow: none; }} }}
    </style>
</head>
<body>
    <div class="document">
        <div class="header">
            <h1>🏭 FACTORY PACKING INSTRUCTIONS <span class="stamp">CONFIDENTIAL</span></h1>
            <div class="header-subtitle">Mark Edwards Apparel Inc.</div>
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Internal PO Number</div>
                    <div class="meta-value">{internal_po}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Factory</div>
                    <div class="meta-value">{factory_name or 'As Assigned'}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Date Generated</div>
                    <div class="meta-value">{datetime.now().strftime('%Y-%m-%d')}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📦 Product Information</div>
            <div class="data-grid">
                <div class="data-item">
                    <div class="data-label">Vendor Style</div>
                    <div class="data-value">{vendor_style}</div>
                </div>
                <div class="data-item">
                    <div class="data-label">Commodity</div>
                    <div class="data-value">Top</div>
                </div>
            </div>
            <div style="margin-top: 20px;">
                <div class="data-label">Colors ({len(clean_colors)} variants)</div>
                <div class="colors-grid">
                    {"".join(f'<span class="color-tag">{c}</span>' for c in clean_colors[:12])}
                </div>
            </div>
            <div style="margin-top: 20px;">
                <div class="data-label">Sizes</div>
                <div class="sizes-grid">
                    {"".join(f'<span class="size-tag">{s}</span>' for s in sizes[:6])}
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📋 Packing Configuration</div>
            <div class="data-grid">
                <div class="data-item">
                    <div class="data-label">Units Per Carton</div>
                    <div class="data-value">{units_per_carton}</div>
                </div>
                <div class="data-item">
                    <div class="data-label">Total Cartons</div>
                    <div class="data-value">{total_cartons}</div>
                </div>
                <div class="data-item">
                    <div class="data-label">Total Units</div>
                    <div class="data-value">{total_units}</div>
                </div>
                <div class="data-item">
                    <div class="data-label">Prepack Ratio</div>
                    <div class="data-value">2-2-1-1 (S-M-L-XL)</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🏷️ Carton Marking Instructions</div>
            <div class="data-item">
                <div class="data-label">Reference on all cartons</div>
                <div class="data-value" style="font-size: 18px;">PO# {internal_po}</div>
            </div>
            <p style="margin-top: 12px; font-size: 13px; color: #64748b;">
                All cartons must be clearly marked with the above PO number. 
                Do not include any customer or buyer information on carton labels.
            </p>
        </div>

        <div class="notice">
            <div class="notice-title">⚠️ CONFIDENTIAL INFORMATION REMOVED</div>
            <div class="notice-text">
                The following fields have been redacted from the original customer packing list: 
                <strong>{', '.join(redacted) if redacted else 'None detected'}</strong>
            </div>
        </div>

        <div class="footer">
            Generated by Mark Edwards Apparel Packing List Sanitizer • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>'''
        
        return html


@app.route('/')
def index():
    return render_template('index.html')


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
        # Save uploaded file
        unique_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
        file.save(upload_path)
        
        # Process the file
        sanitizer = PackingListSanitizer()
        text = sanitizer.extract_text_from_pdf(upload_path)
        info = sanitizer.detect_info(text)
        html = sanitizer.generate_factory_document(internal_po, factory_name)
        
        # Save output
        output_filename = f"Factory_Packing_PO_{internal_po}_{unique_id}.html"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Clean up upload
        os.remove(upload_path)
        
        # Return success with download link
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
