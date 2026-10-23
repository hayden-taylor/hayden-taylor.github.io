#!/usr/bin/env python3
"""Banner and research-page editor for the group website (Jekyll).

Run from the repository folder:   python tools/banner_editor.py
(or double-click tools/banner_editor.bat on Windows). It opens http://127.0.0.1:8765 in your browser.

  * Banner tab: pick a page, move images from the image library into its banner and back with the
    < and > buttons, reorder them, and click Save. Images are 240, 480 or 720 pixels wide (set from
    each image's shape); the banner should add up to 720. Saving rewrites the "banner:" block in the
    page's front matter.
  * Research page tab: change the order of topics, the theme each belongs to, and whether it is shown,
    then click Save. Saving rewrites _data/projects.csv.

Uses only the Python standard library. Nothing is sent anywhere: the server listens on this computer only.
"""
import csv, io, json, os, re, struct, sys, webbrowser, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PORT = 8765
IMG_EXT = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
VID_EXT = ('.mp4', '.webm')


def image_size(path):
    """Return (width, height) for PNG, JPEG, GIF or WebP using only the standard library."""
    with open(path, 'rb') as f:
        head = f.read(32)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', head[16:24])
        if head[:6] in (b'GIF87a', b'GIF89a'):
            return struct.unpack('<HH', head[6:10])
        if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
            f.seek(12); chunk = f.read(4); f.seek(20); data = f.read(10)
            if chunk == b'VP8X':
                return (1 + int.from_bytes(data[4:7], 'little'), 1 + int.from_bytes(data[7:10], 'little'))
            if chunk == b'VP8 ':
                return struct.unpack('<HH', data[6:10])
            return (240, 240)
        if head[:2] == b'\xff\xd8':
            f.seek(2)
            while True:
                b = f.read(1)
                while b and b != b'\xff':
                    b = f.read(1)
                while b == b'\xff':
                    b = f.read(1)
                if not b:
                    break
                marker = b[0]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(3)
                    h, w = struct.unpack('>HH', f.read(4))
                    return (w, h)
                seg = struct.unpack('>H', f.read(2))[0]
                f.seek(seg - 2, 1)
    return (240, 240)


def slot_width(w, h):
    ratio = w / float(h or 1)
    return 240 * max(1, min(3, int(round(ratio))))


def split_front_matter(text):
    m = re.match(r'---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def parse_banner(fm):
    items = []
    lines = fm.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == 'banner:':
            for l2 in lines[i + 1:]:
                if not l2.startswith('  - '):
                    break
                d = {}
                for k, v in re.findall(r'(\w+):\s*("[^"]*"|[^,}]+)', l2):
                    d[k] = v.strip().strip('"')
                items.append({'type': d.get('type', 'img'), 'src': d.get('src', ''), 'width': int(d.get('width', 240))})
    return items


def get_field(fm, key):
    m = re.search(r'^' + key + r':\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1) if m else ''


def write_banner(path, items):
    text = open(path, encoding='utf-8').read()
    fm, body = split_front_matter(text)
    lines = fm.splitlines()
    out, i = [], 0
    while i < len(lines):
        if lines[i].strip() == 'banner:':
            i += 1
            while i < len(lines) and lines[i].startswith('  - '):
                i += 1
            continue
        out.append(lines[i]); i += 1
    if items:
        block = ['banner:'] + ['  - {type: %s, src: "%s", width: %d, height: 240}' % (
            'video' if it['src'].lower().endswith(VID_EXT) else 'img', it['src'], int(it['width'])) for it in items]
        # keep the banner just after panel_title when possible
        idx = next((k + 1 for k, l in enumerate(out) if l.startswith('panel_title:')), len(out))
        out = out[:idx] + block + out[idx:]
    new = '---\n' + '\n'.join(out) + '\n---\n' + body
    open(path, 'w', encoding='utf-8', newline='\n').write(new)


def pages():
    res = []
    for name in sorted(os.listdir(ROOT), key=str.lower):
        if not name.endswith('.html') or name == '404.html':
            continue
        text = open(os.path.join(ROOT, name), encoding='utf-8').read()
        fm, _ = split_front_matter(text)
        if fm is None:
            continue
        panel = re.sub(r'<br\s*/?>', ' ', get_field(fm, 'panel_title'))
        res.append({'file': name, 'panel': panel, 'banner': parse_banner(fm)})
    return res


def library():
    res = []
    d = os.path.join(ROOT, 'images')
    for n in sorted(os.listdir(d), key=str.lower):
        if n.lower().endswith(IMG_EXT):
            try:
                w, h = image_size(os.path.join(d, n))
            except Exception:
                w, h = 240, 240
            res.append({'src': 'images/' + n, 'w': w, 'h': h, 'slot': slot_width(w, h)})
    vd = os.path.join(ROOT, 'videos')
    if os.path.isdir(vd):
        for n in sorted(os.listdir(vd), key=str.lower):
            if n.lower().endswith(VID_EXT):
                res.append({'src': 'videos/' + n, 'w': 240, 'h': 240, 'slot': 240, 'video': True})
    return res


def read_projects():
    path = os.path.join(ROOT, '_data', 'projects.csv')
    raw = open(path, encoding='utf-8-sig').read()
    rows = list(csv.reader(io.StringIO(raw)))
    return rows[0], rows[1:]


def themes():
    path = os.path.join(ROOT, '_data', 'themes.yml')
    return re.findall(r'^- name:\s*(.+?)\s*$', open(path, encoding='utf-8').read(), re.M)


def write_projects(order):
    header, rows = read_projects()
    ci = {h: i for i, h in enumerate(header)}
    byfile = {}
    for r in rows:
        if len(r) > ci['Source file'] and r[ci['Source file']]:
            byfile.setdefault(r[ci['Source file']], r)
    new_rows, used = [], set()
    for o in order:
        r = list(byfile[o['file']]); used.add(o['file'])
        r[ci['Theme']] = o['theme']
        r[ci['Include?']] = '1' if o['include'] else '0'
        new_rows.append(r)
    for r in rows:
        f = r[ci['Source file']] if len(r) > ci['Source file'] else ''
        if f not in used:
            new_rows.append(r)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(header); w.writerows(new_rows)
    open(os.path.join(ROOT, '_data', 'projects.csv'), 'w', encoding='utf-8', newline='').write(buf.getvalue())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/':
            return self.send(200, PAGE, 'text/html; charset=utf-8')
        if path == '/api/state':
            header, rows = read_projects()
            ci = {h: i for i, h in enumerate(header)}
            projects = [{'title': r[ci['Project title']], 'theme': r[ci['Theme']], 'file': r[ci['Source file']],
                         'include': r[ci['Include?']] == '1'} for r in rows if len(r) > ci['Source file'] and r[ci['Source file']]]
            return self.send(200, json.dumps({'pages': pages(), 'library': library(), 'themes': themes(), 'projects': projects}))
        if path.startswith('/site/'):
            rel = os.path.normpath(path[len('/site/'):]).replace('\\', '/')
            full = os.path.join(ROOT, rel)
            if rel.startswith('..') or not os.path.isfile(full):
                return self.send(404, 'not found', 'text/plain')
            ext = os.path.splitext(full)[1].lower()
            ctype = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
                     '.webp': 'image/webp', '.mp4': 'video/mp4', '.webm': 'video/webm'}.get(ext, 'application/octet-stream')
            return self.send(200, open(full, 'rb').read(), ctype)
        self.send(404, 'not found', 'text/plain')

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(n) or b'{}')
        path = urlparse(self.path).path
        try:
            if path == '/api/banner':
                f = os.path.basename(data['file'])
                write_banner(os.path.join(ROOT, f), data['banner'])
                return self.send(200, json.dumps({'ok': True}))
            if path == '/api/projects':
                write_projects(data['order'])
                return self.send(200, json.dumps({'ok': True}))
        except Exception as e:
            return self.send(500, json.dumps({'ok': False, 'error': str(e)}))
        self.send(404, '{}')


PAGE = r'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Banner editor</title>
<style>
 body{font-family:Arial,Helvetica,sans-serif;margin:16px;color:#1a1a1a;background:#fafafa}
 h1{font-size:20px;margin:0 0 10px} h2{font-size:16px;margin:16px 0 6px;color:#0E2E87}
 .tabs button{font:inherit;padding:6px 14px;border:1px solid #999;background:#fff;cursor:pointer}
 .tabs button.on{background:#0E2E87;color:#fff;border-color:#0E2E87}
 .row{display:flex;gap:16px;align-items:flex-start}
 select,input,button{font:inherit}
 #banner{width:720px;height:240px;display:flex;background:#ddd;outline:1px solid #999;overflow:hidden}
 #banner .it{height:240px;flex:none;position:relative;cursor:pointer}
 #banner .it img,#banner .it video{width:100%;height:100%;object-fit:cover;display:block}
 #banner .it.sel{outline:4px solid #FDB515;outline-offset:-4px}
 .panel{width:240px;height:240px;background:#0E2E87;color:#fff;font-weight:bold;font-size:20px;padding:10px;box-sizing:border-box;flex:none}
 .ctrls{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
 .ctrls button{padding:4px 10px}
 #lib{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;max-height:520px;overflow:auto;background:#fff;border:1px solid #ccc;padding:8px;flex:1}
 #lib .im{cursor:pointer;border:2px solid transparent;font-size:11px;text-align:center;word-break:break-all}
 #lib .im.sel{border-color:#FDB515}
 #lib .im img,#lib .im video{width:100%;height:80px;object-fit:contain;background:#eee;display:block}
 .badge{display:inline-block;background:#0E2E87;color:#fff;border-radius:3px;padding:0 4px;margin-top:2px}
 .warn{color:#b00020;font-weight:bold} .ok{color:#1b7f3a;font-weight:bold}
 table{border-collapse:collapse;background:#fff} td,th{border:1px solid #ccc;padding:4px 6px;font-size:13px}
 #status{margin-left:8px}
</style></head><body>
<h1>Website banner and research-page editor</h1>
<div class="tabs"><button id="t1" class="on">Banners</button><button id="t2">Research page order and themes</button></div>
<div id="v1">
 <div class="ctrls">Page: <select id="page"></select> <span id="total"></span></div>
 <div class="row"><div class="panel" id="ptitle"></div><div id="banner"></div></div>
 <div class="ctrls">
  <button id="left" title="Move selected banner image left">&#9664; Move left</button>
  <button id="right" title="Move selected banner image right">Move right &#9654;</button>
  <button id="out" title="Remove selected image from banner">Remove from banner &gt;</button>
  <button id="in" title="Add selected library image to banner">&lt; Add to banner</button>
  <label>Width of selected banner item: <select id="w"><option>240</option><option>480</option><option>720</option></select></label>
  <button id="save"><b>Save banner</b></button><span id="status"></span>
 </div>
 <h2>Image library</h2>
 <div class="ctrls">Filter: <input id="filter" placeholder="part of a file name"> <label><input type="checkbox" id="unused"> only images not used in any banner</label></div>
 <div id="lib"></div>
</div>
<div id="v2" hidden>
 <p>Topics appear on the Research page in this order, under the theme chosen. Unticked topics are hidden.</p>
 <table id="ptab"><thead><tr><th>Order</th><th>Shown</th><th>Topic</th><th>Theme</th><th>Page</th></tr></thead><tbody></tbody></table>
 <div class="ctrls"><button id="psave"><b>Save research page</b></button><span id="pstatus"></span></div>
</div>
<script>
let S=null, cur=null, banner=[], selB=-1, selL=null;
const $=id=>document.getElementById(id);
function media(src,video){return video||/\.(mp4|webm)$/i.test(src)?`<video src="/site/${src}" muted loop autoplay playsinline></video>`:`<img src="/site/${src}" alt="">`}
async function load(){S=await (await fetch('/api/state')).json();
 const p=$('page'); p.innerHTML=S.pages.map((x,i)=>`<option value="${i}">${x.file} — ${x.panel}</option>`).join('');
 p.onchange=()=>pick(+p.value); pick(cur===null?0:cur); renderLib(); renderProjects();}
function pick(i){cur=i; banner=S.pages[i].banner.map(b=>({...b})); selB=-1; $('ptitle').innerHTML=S.pages[i].panel; render();}
function render(){const t=banner.reduce((a,b)=>a+(+b.width),0); if(selB>=0&&banner[selB]) $('w').value=banner[selB].width;
 $('banner').innerHTML=banner.map((b,i)=>`<div class="it ${i==selB?'sel':''}" style="width:${b.width}px" data-i="${i}">${media(b.src)}</div>`).join('');
 [...document.querySelectorAll('#banner .it')].forEach(e=>e.onclick=()=>{selB=+e.dataset.i; $('w').value=banner[selB].width; render();});
 $('total').innerHTML=`Banner width: ${t} px `+(t==720?'<span class="ok">(complete)</span>':`<span class="warn">(should be 720)</span>`);}
function used(){const u=new Set(); S.pages.forEach(p=>p.banner.forEach(b=>u.add(b.src))); return u;}
function renderLib(){const f=$('filter').value.toLowerCase(), u=used(), only=$('unused').checked;
 $('lib').innerHTML=S.library.filter(x=>x.src.toLowerCase().includes(f)&&(!only||!u.has(x.src))).map(x=>`<div class="im ${selL&&selL.src==x.src?'sel':''}" data-src="${x.src}">${media(x.src,x.video)}<div>${x.src.replace('images/','').replace('hkt_research_image_','')}</div><span class="badge">${x.slot}</span> <small>${x.w}×${x.h}</small></div>`).join('');
 [...document.querySelectorAll('#lib .im')].forEach(e=>{e.onclick=()=>{selL=S.library.find(x=>x.src==e.dataset.src); renderLib();}; e.ondblclick=()=>{selL=S.library.find(x=>x.src==e.dataset.src); addSel();};});}
function addSel(){if(!selL)return; const at=selB>=0?selB+1:banner.length; banner.splice(at,0,{type:selL.video?'video':'img',src:selL.src,width:selL.slot}); selB=at; render();}
$('in').onclick=addSel;
$('out').onclick=()=>{if(selB<0)return; banner.splice(selB,1); selB=Math.min(selB,banner.length-1); render();};
$('left').onclick=()=>{if(selB>0){[banner[selB-1],banner[selB]]=[banner[selB],banner[selB-1]]; selB--; render();}};
$('right').onclick=()=>{if(selB>=0&&selB<banner.length-1){[banner[selB+1],banner[selB]]=[banner[selB],banner[selB+1]]; selB++; render();}};
$('w').onchange=()=>{if(selB>=0){banner[selB].width=+$('w').value; render();}};
$('filter').oninput=renderLib; $('unused').onchange=renderLib;
$('save').onclick=async()=>{const r=await fetch('/api/banner',{method:'POST',body:JSON.stringify({file:S.pages[cur].file,banner})});
 const j=await r.json(); $('status').innerHTML=j.ok?'<span class="ok">Saved.</span>':'<span class="warn">'+j.error+'</span>'; if(j.ok){S.pages[cur].banner=banner.map(b=>({...b})); renderLib();}};
function renderProjects(){const tb=document.querySelector('#ptab tbody'); const P=S.projects;
 tb.innerHTML=P.map((p,i)=>`<tr><td><button data-u="${i}">&#9650;</button><button data-d="${i}">&#9660;</button></td><td><input type="checkbox" data-c="${i}" ${p.include?'checked':''}></td><td>${p.title}</td><td><select data-t="${i}">${[...new Set([...S.themes,p.theme])].map(t=>`<option ${t==p.theme?'selected':''}>${t}</option>`).join('')}</select></td><td>${p.file}</td></tr>`).join('');
 tb.querySelectorAll('[data-u]').forEach(b=>b.onclick=()=>{const i=+b.dataset.u; if(i>0){[P[i-1],P[i]]=[P[i],P[i-1]]; renderProjects();}});
 tb.querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>{const i=+b.dataset.d; if(i<P.length-1){[P[i+1],P[i]]=[P[i],P[i+1]]; renderProjects();}});
 tb.querySelectorAll('[data-c]').forEach(c=>c.onchange=()=>{P[+c.dataset.c].include=c.checked;});
 tb.querySelectorAll('[data-t]').forEach(s=>s.onchange=()=>{P[+s.dataset.t].theme=s.value;});}
$('psave').onclick=async()=>{const r=await fetch('/api/projects',{method:'POST',body:JSON.stringify({order:S.projects})}); const j=await r.json(); $('pstatus').innerHTML=j.ok?'<span class="ok">Saved.</span>':'<span class="warn">'+j.error+'</span>';};
$('t1').onclick=()=>{$('v1').hidden=false;$('v2').hidden=true;$('t1').className='on';$('t2').className='';};
$('t2').onclick=()=>{$('v1').hidden=true;$('v2').hidden=false;$('t2').className='on';$('t1').className='';};
load();
</script></body></html>'''

if __name__ == '__main__':
    os.chdir(ROOT)
    srv = HTTPServer(('127.0.0.1', PORT), Handler)
    url = 'http://127.0.0.1:%d/' % PORT
    print('Banner editor running at', url, '(press Ctrl+C to stop)')
    if '--no-browser' not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
