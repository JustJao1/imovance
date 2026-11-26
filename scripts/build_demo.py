"""Create a static, offline-capable portfolio demo from the application assets."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'static'
html = (source / 'demo.html').read_text(encoding='utf-8')
css = (source / 'style.css').read_text(encoding='utf-8')
js = (source / 'app.js').read_text(encoding='utf-8')
html = html.replace('<html lang="pt-BR">', '<html data-mode="demo" lang="pt-BR">', 1)
html, css_count = re.subn(r'<link\b[^>]*href=["\']/style\.css["\'][^>]*>', lambda _: '<style>' + css + '</style>', html, count=1)
html, js_count = re.subn(r'<script\b[^>]*src=["\']/app\.js["\'][^>]*></script>', lambda _: '<script>' + js.replace('</script', '<\\/script') + '</script>', html, count=1)
if css_count != 1 or js_count != 1 or 'data-mode="demo"' not in html:
    raise SystemExit('Unexpected demo template structure')
out = ROOT / 'dist'
out.mkdir(exist_ok=True)
(out / 'index.html').write_text(html, encoding='utf-8')
print('Built dist/index.html')
