# Packing List Sanitizer

A web application for Mark Edwards Apparel to remove confidential customer information from packing lists before sending to overseas factories.

## What It Does

- **Removes**: Customer names, PO numbers, addresses, SKU codes, pricing, shipping splits, contact info
- **Keeps**: Vendor styles, colors, sizes, quantities, packing configurations
- **Outputs**: Clean HTML document ready to send to factory

---

## Deployment Options

### Option 1: Railway (Easiest - Recommended)

Railway is a modern hosting platform. $5/month for light usage.

1. **Create Account**: Go to [railway.app](https://railway.app) and sign up with GitHub

2. **Create New Project**: 
   - Click "New Project" → "Deploy from GitHub repo"
   - Or click "Empty Project" → "Add Service" → "Empty Service"

3. **Upload Files**:
   - Connect your GitHub repo containing these files, OR
   - Use Railway CLI: `railway up`

4. **Configure**:
   - Go to Settings → Networking → Generate Domain
   - Your app will be live at `your-app.up.railway.app`

5. **Share with Team**:
   - Give staff the URL (e.g., `https://packing-sanitizer.up.railway.app`)

---

### Option 2: Render (Also Easy)

Render offers free tier with some limitations.

1. **Create Account**: Go to [render.com](https://render.com) and sign up

2. **New Web Service**:
   - Click "New" → "Web Service"
   - Connect GitHub repo or upload directly

3. **Configure**:
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```

4. **Deploy**: Click "Create Web Service"

Your app will be at `your-app.onrender.com`

---

### Option 3: Your Own Server (IT Team)

If you have an internal server or IT department:

#### Using Docker:

```bash
# Build the container
docker build -t packing-sanitizer .

# Run it
docker run -d -p 5000:5000 --name packing-sanitizer packing-sanitizer

# Access at http://your-server-ip:5000
```

#### Without Docker:

```bash
# Install Python 3.11+
# Then:
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:5000 app:app

# Or for development:
python app.py
```

---

### Option 4: Heroku

```bash
# Install Heroku CLI, then:
heroku login
heroku create packing-sanitizer
git push heroku main
```

---

## Quick Start (Local Testing)

Test on your computer before deploying:

```bash
# 1. Install Python 3.11+ from python.org

# 2. Open terminal/command prompt in this folder

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# 5. Open browser to http://localhost:5000
```

---

## Files Included

```
packing-sanitizer-app/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── Dockerfile          # For container deployment
├── templates/
│   └── index.html      # Web interface
├── uploads/            # Temporary upload folder
└── outputs/            # Generated documents
```

---

## Security Notes

- Uploaded files are processed and immediately deleted
- Generated documents are stored temporarily for download
- Consider adding authentication for production use
- All processing happens server-side; nothing is sent to external services

---

## Adding Password Protection (Optional)

To add a simple password, modify `app.py`:

```python
# Add at top of app.py
from functools import wraps
from flask import request, Response

def check_auth(username, password):
    return username == 'mea' and password == 'your-password-here'

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response('Login Required', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

# Then add @requires_auth before each route:
@app.route('/')
@requires_auth
def index():
    ...
```

---

## Support

For issues or modifications, contact your IT team or the developer who set this up.

---

## Cost Estimates

| Platform | Monthly Cost | Notes |
|----------|--------------|-------|
| Railway | $5-10 | Pay for usage |
| Render | $0-7 | Free tier available |
| Heroku | $7+ | No free tier |
| Your Server | $0 | If you have one |

---

*Mark Edwards Apparel Inc. - Internal Tool*
