def render(title, content, active_nav=''):
    nav_items = [
        ('/',       'Dashboard',  'dashboard'),
        ('/fs',     'Filesystem', 'fs'),
        ('/hsr',    'HSR Status', 'hsr'),
        ('/backup', 'Backup',     'backup'),
    ]
    nav_links = ''
    for href, label, key in nav_items:
        active = 'background:#154360;' if active_nav == key else ''
        nav_links += (
            f'<a href="{href}" style="color:white;text-decoration:none;'
            f'padding:12px 22px;display:inline-block;{active}">{label}</a>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - SAP Landscape Manager</title>
<style>
*{{box-sizing:border-box;}}
body{{font-family:Arial,sans-serif;margin:0;background:#f0f2f5;color:#333;}}
nav{{background:#1a5276;display:flex;align-items:center;}}
.brand{{color:white;font-weight:bold;padding:12px 24px;font-size:1.05em;
        border-right:1px solid #154360;white-space:nowrap;}}
.container{{padding:24px;max-width:1280px;margin:0 auto;}}
h2{{color:#1a5276;margin-top:0;}}
table{{width:100%;border-collapse:collapse;background:white;border-radius:4px;
       overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.12);}}
th{{background:#1a5276;color:white;padding:11px 14px;text-align:left;font-size:.92em;}}
td{{padding:10px 14px;border-bottom:1px solid #eee;font-size:.92em;}}
tr:last-child td{{border-bottom:none;}}
tr:hover td{{background:#f8f9fa;}}
.btn{{padding:7px 16px;border:none;border-radius:3px;cursor:pointer;
      font-size:.9em;text-decoration:none;display:inline-block;}}
.btn-primary{{background:#1a5276;color:white;}}
.btn-warning{{background:#e67e22;color:white;}}
.btn-danger {{background:#c0392b;color:white;}}
.btn-success{{background:#1e8449;color:white;}}
.btn-sm{{padding:4px 10px;font-size:.82em;}}
.alert{{padding:12px 16px;border-radius:4px;margin:12px 0;font-size:.92em;}}
.alert-danger {{background:#fdedec;border-left:4px solid #e74c3c;}}
.alert-warning{{background:#fef9e7;border-left:4px solid #f39c12;}}
.alert-success{{background:#eafaf1;border-left:4px solid #27ae60;}}
.alert-info   {{background:#eaf4fb;border-left:4px solid #2980b9;}}
.card{{background:white;border-radius:4px;padding:20px;
       box-shadow:0 1px 4px rgba(0,0,0,.12);margin-bottom:20px;}}
.badge{{padding:3px 9px;border-radius:12px;font-size:.8em;color:white;font-weight:bold;}}
.badge-danger {{background:#c0392b;}}
.badge-warning{{background:#e67e22;}}
.badge-ok     {{background:#1e8449;}}
.badge-info   {{background:#2980b9;}}
input[type=text],input[type=number],select{{
  padding:6px 10px;border:1px solid #ccc;border-radius:3px;font-size:.9em;}}
label{{font-size:.9em;color:#555;display:block;margin-bottom:3px;}}
.form-row{{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px;}}
.form-group{{display:flex;flex-direction:column;}}
pre{{background:#2c3e50;color:#ecf0f1;padding:14px;border-radius:4px;
     font-size:.82em;overflow-x:auto;white-space:pre-wrap;margin:0;}}
code{{background:#eee;padding:1px 5px;border-radius:3px;font-size:.9em;}}
.stat-box{{background:white;border-radius:4px;padding:20px;
           box-shadow:0 1px 4px rgba(0,0,0,.12);flex:1;min-width:180px;}}
.stat-num{{font-size:2.2em;font-weight:bold;color:#1a5276;}}
.stat-lbl{{color:#888;font-size:.9em;margin-bottom:12px;}}
</style>
</head>
<body>
<nav>
  <div class="brand">SAP Landscape Manager</div>
  {nav_links}
</nav>
<div class="container">
  <h2>{title}</h2>
  {content}
</div>
</body>
</html>"""
