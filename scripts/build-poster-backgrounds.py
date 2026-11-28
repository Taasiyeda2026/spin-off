"""WebP is authoritative. Preserve immutable versions from Git before publishing.

No database credentials are needed: keep every historical version, even if a source
is removed. Legacy posters use the baseline manifest; newer posters pin bgVersion.
"""
import argparse, hashlib, io, json, re, subprocess
from pathlib import Path
from PIL import Image, ImageOps

def natural(value):
    return [(1,int(part)) if part.isdigit() else (0,part.lower()) for part in re.split(r'(\d+)',value)]

def build(root, output):
    source=root/'poster-backgrounds';target=output/'poster-backgrounds'
    legacy=json.loads((source/'legacy-versions.json').read_text()) if (source/'legacy-versions.json').exists() else {}
    versions={};latest={};active={}
    def record(id, data):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',id):raise ValueError('Invalid background ID: '+id)
        digest=hashlib.sha256(data).hexdigest()
        with Image.open(io.BytesIO(data)) as original:
            if original.format!='WEBP':raise ValueError('Source must be WebP: '+id)
            image=ImageOps.exif_transpose(original).convert('RGB')
            if image.width>=image.height:raise ValueError('Background must be portrait: '+id)
            image.verify() if hasattr(image,'verify') else None
        full=target/'versions'/f'{digest}.webp';thumb=target/'thumbs'/f'{digest}.webp'
        full.parent.mkdir(parents=True,exist_ok=True);thumb.parent.mkdir(parents=True,exist_ok=True)
        if not full.exists():full.write_bytes(data)
        if not thumb.exists():
            image.thumbnail((240,340),Image.Resampling.LANCZOS);image.save(thumb,'WEBP',quality=80,method=6)
        versions.setdefault(id,{})[digest]={'version':digest,'image':str(full.relative_to(output)),'thumb':str(thumb.relative_to(output))}
        latest.setdefault(id,digest)
        return digest
    # Current working-tree files win. History provides immutable snapshots for old drafts.
    for path in sorted((source/'webp').glob('*.webp'),key=lambda p:natural(p.stem)):
        active[path.stem]=record(path.stem,path.read_bytes())
    commits=subprocess.check_output(['git','log','--format=%H','--','poster-backgrounds/webp/'],cwd=root,text=True).splitlines()
    seen=set()
    for commit in commits:
        tree=subprocess.check_output(['git','ls-tree','-r',commit,'--','poster-backgrounds/webp/'],cwd=root,text=True)
        for line in tree.splitlines():
            info,path=line.split('\t',1);blob=info.split()[2]
            if (path,blob) in seen or not path.endswith('.webp'):continue
            seen.add((path,blob));record(Path(path).stem,subprocess.check_output(['git','cat-file','blob',blob],cwd=root))
    for id,digest in legacy.items():
        if digest not in versions.get(id,{}):raise ValueError('Missing immutable legacy background: '+id)
    catalog=[]
    for id in sorted(versions,key=natural):
        digest=active.get(id,latest[id]);entry={'id':id,**versions[id][digest], 'legacyVersion':legacy.get(id,digest), 'retired':id not in active,'versions':list(versions[id].values())}
        catalog.append(entry)
    if not catalog:raise ValueError('No backgrounds found')
    text='window.posterBackgroundCatalog = '+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n'
    (target/'catalog.js').write_text(text)
    # An HTML release query changes whenever catalog contents change.
    html=output/'poster.html'
    if html.exists():
        release=hashlib.sha256(text.encode()).hexdigest()[:16]
        html.write_text(re.sub(r'poster-backgrounds/catalog\.js(?:\?v=[^"\s]+)?','poster-backgrounds/catalog.js?v='+release,html.read_text()))
    print(f'{len(active)} active backgrounds, {sum(map(len,versions.values()))} immutable versions, {len(catalog)-len(active)} retained removed IDs')
    return catalog

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--output',type=Path)
    args=parser.parse_args();build(args.root.resolve(),(args.output or args.root).resolve())
