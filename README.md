# LeafScan - Full Run Guide (Web + ML + DB)

LeafScan has two servers:
- `leafscan/` (Node/Express UI) on `http://localhost:3000`
- `ml_server/` (Flask + TensorFlow API) on `http://localhost:5000`

The UI calls the Flask API for:
- login/register (`/login`, `/register`)
- prediction (`/analyze`)

## Project Structure

```text
leafscan-project - Copy/
|-- leafscan/        # Node web app
`-- ml_server/       # Flask + TensorFlow + MySQL backend
```

## Prerequisites

- Node.js + npm
- Python 3.10+ (3.13 also works)
- MySQL/MariaDB (XAMPP MariaDB works)

## Run Steps

### 1) Start MySQL (if not already running)

If using XAMPP:

```powershell
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --standalone --console
```

Keep this terminal open while using the app.

### 2) Create DB schema

In a new terminal:

```powershell
cd "c:\Users\Snehal hashilkar\Downloads\leafscan-project - Copy\ml_server"
Get-Content -Path setup_db.sql | C:\xampp\mysql\bin\mysql.exe -u root
```

### 3) Start ML server

In `ml_server` terminal:

```powershell
python app.py
```

Wait until you see:
- `Running on http://127.0.0.1:5000`

Note: first startup can take 20-40 seconds while TensorFlow loads the model.

### 4) Start web server

In another terminal:

```powershell
cd "c:\Users\Snehal hashilkar\Downloads\leafscan-project - Copy\leafscan"
npm.cmd install
node server.js
```

Note: in PowerShell, `npm` may be blocked by execution policy. Use `npm.cmd`.

### 5) Open the app

Go to:
- `http://localhost:3000/login`

## Quick health checks

- Web: open `http://localhost:3000/login`
- ML API: open `http://localhost:5000/health`
