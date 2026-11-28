"""Add, replace, remove, natural order and legacy preservation in disposable Git."""
import hashlib, importlib.util, io, json, subprocess, tempfile
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location('background_build',Path(__file__).parents[1]/'scripts/build-poster-backgrounds.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def webp(color,size=(210,297)):
    data=io.BytesIO();Image.new('RGB',size,color).save(data,'WEBP');return data.getvalue()
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);source=root/'poster-backgrounds';(source/'webp').mkdir(parents=True)
    def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
    git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
    old=webp('red');digest=hashlib.sha256(old).hexdigest()
    (source/'webp/bg2.webp').write_bytes(old);(source/'webp/bg10.webp').write_bytes(webp('blue'))
    (source/'legacy-versions.json').write_text(json.dumps({'bg2':digest}))
    git('add','.');git('commit','-m','baseline')
    (root/'first').mkdir();(root/'first/poster.html').write_text('<script src="poster-backgrounds/catalog.js?v=old"></script>')
    first=module.build(root,root/'first')
    assert [e['id'] for e in first]==['bg2','bg10']
    (source/'webp/bg2.webp').write_bytes(webp('green'));(source/'webp/bg100.webp').write_bytes(webp('white',(400,200)))
    git('add','poster-backgrounds');git('commit','-m','replace and add')
    (root/'second').mkdir();(root/'second/poster.html').write_text('<script src="poster-backgrounds/catalog.js?v=old"></script>')
    second=module.build(root,root/'second');two=next(e for e in second if e['id']=='bg2')
    assert (root/'first/poster.html').read_text()!=(root/'second/poster.html').read_text()
    assert len(two['versions'])==2 and two['version']!=digest and two['legacyVersion']==digest
    assert (root/'second'/f'poster-backgrounds/versions/{digest}.webp').read_bytes()==old
    (source/'webp/bg2.webp').unlink();git('add','-u');git('commit','-m','remove source')
    third=module.build(root,root/'third');two=next(e for e in third if e['id']=='bg2')
    assert two['retired'] and len(two['versions'])==2
    assert [e['id'] for e in third if not e['retired']]==['bg10','bg100']
    assert (root/'third'/f'poster-backgrounds/versions/{digest}.webp').read_bytes()==old
    a4=210/297
    for e in third:
        for version in e['versions']:
            full_path=root/'third'/version['image'];thumb_path=root/'third'/version['thumb']
            with Image.open(full_path) as full, Image.open(thumb_path) as image:
                assert image.width<=420 and image.height<=594
                # Thumbnails keep source aspect (integer rounding only); never stretch to the box.
                assert abs((image.width/image.height)-(full.width/full.height))<0.01
                if abs((full.width/full.height)-a4)<1e-6:
                    assert abs((image.width/image.height)-a4)<0.01
            # Full version bytes stay identical to the recorded digest payload.
            assert hashlib.sha256(full_path.read_bytes()).hexdigest()==version['version']
    (root/'third'/f'poster-backgrounds/versions/{digest}.webp').write_bytes(b'corrupt')
    try:module.build(root,root/'third')
    except ValueError:pass
    else:raise AssertionError('Immutable version corruption must block deployment')
    (source/'webp/bg999.webp').write_bytes(b'not an image')
    try:module.build(root,root/'invalid')
    except Exception:pass
    else:raise AssertionError('Invalid WebP must block deployment')
print('Automatic add/replace/remove, immutable content, legacy IDs, numerical ordering and thumbnail checks passed.')
