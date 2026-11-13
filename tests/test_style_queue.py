from hashlib import sha256
from io import BytesIO
import base64
import json
import re
import zipfile
from PIL import Image, ImageDraw
import pytest
from backend.image.style_queue import StyleQueue


def source_png():
    image=Image.new('RGB',(160,80),'white');ImageDraw.Draw(image).text((10,10),'Label A',fill='black')
    output=BytesIO();image.save(output,format='PNG');return output.getvalue()


def test_frozen_worker_protocol_uses_only_owned_files(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import backend.image.style_queue as module
    identifier='a'*32;source=source_png()
    (tmp_path/(identifier+'.source')).write_bytes(source)
    payload={'id':identifier,'sha256':sha256(source).hexdigest(),'label':'Original label A.png',
             'style':'soft','parameters':module.STYLES['soft']}
    monkeypatch.setattr(module,'image_work_dir',lambda name:tmp_path)
    monkeypatch.setattr(module.sys,'stdin',SimpleNamespace(buffer=BytesIO(json.dumps(payload).encode())))
    module.frozen_worker()
    assert json.loads((tmp_path/(identifier+'.report')).read_text())['ok']
    with zipfile.ZipFile(tmp_path/(identifier+'.zip')) as result:
        assert result.read('source/original.png')==source


@pytest.mark.parametrize('change',[{'id':'../outside'},{'parameters':{'ink':'url(file:///private)'}},{'sha256':'invalid'}])
def test_frozen_worker_rejects_path_and_style_injection(tmp_path,monkeypatch,change):
    from types import SimpleNamespace
    import backend.image.style_queue as module
    payload={'id':'a'*32,'sha256':'a'*64,'label':'Synthetic.png','style':'clean','parameters':module.STYLES['clean'],**change}
    monkeypatch.setattr(module,'image_work_dir',lambda name:tmp_path)
    monkeypatch.setattr(module.sys,'stdin',SimpleNamespace(buffer=BytesIO(json.dumps(payload).encode())))
    with pytest.raises(ValueError):module.frozen_worker()
    assert not list(tmp_path.iterdir())


def test_original_bytes_labels_and_style_survive_output(tmp_path):
    source=source_png();queue=StyleQueue(tmp_path,start=False)
    job=queue.submit(BytesIO(source),'Original label A.png','soft')
    assert queue.run_one()
    result=queue.get(job['id']);assert result['state']=='done'
    with zipfile.ZipFile(queue.path(job['id'],'.zip')) as archive:
        assert archive.read('source/original.png')==source
        svg=archive.read('presentation.svg').decode()
        embedded=base64.b64decode(re.search(r'base64,([^"]+)',svg)[1])
        assert embedded==source
        assert 'Original label A.png' in svg
        manifest=json.loads(archive.read('manifest.json'))
        assert not manifest['source_data_changed'] and not manifest['embedded_labels_changed']
        assert manifest['source_sha256']==sha256(source).hexdigest()
        assert result['style_parameters']==manifest['style_parameters']
    assert queue.path(job['id'],'.source').read_bytes()==source
    with pytest.raises(ValueError):queue.path('../escape','.source')


def test_single_plane_tiff_is_lossless_and_16bit_is_rejected(tmp_path):
    queue=StyleQueue(tmp_path,start=False)
    tiff=BytesIO();Image.new('L',(20,20),120).save(tiff,format='TIFF')
    good=queue.submit(BytesIO(tiff.getvalue()),'plane.tif','clean')
    high=BytesIO();Image.new('I;16',(20,20),120).save(high,format='TIFF')
    bad=queue.submit(BytesIO(high.getvalue()),'depth.tif','clean')
    while queue.run_one():pass
    assert queue.get(good['id'])['state']=='done'
    assert queue.get(bad['id'])['state']=='failed'
    assert queue.path(bad['id'],'.source').read_bytes()==high.getvalue()


def test_restart_recovers_unfinished_and_does_not_redo_done(tmp_path):
    source=source_png();first=StyleQueue(tmp_path,start=False)
    done=first.submit(BytesIO(source),'done.png','clean');first.run_one()
    pending=first.submit(BytesIO(source),'pending.png','soft')
    with first.connect() as db:
        db.execute("UPDATE jobs SET state='running',attempts=1 WHERE id=?",(pending['id'],))
    resumed=StyleQueue(tmp_path,start=False)
    assert resumed.get(pending['id'])['state']=='queued'
    resumed.run_one()
    assert resumed.get(done['id'])['attempts']==1
    assert resumed.get(pending['id'])['attempts']==2 and resumed.get(pending['id'])['state']=='done'


def test_100_jobs_isolate_three_failures_and_retry_only_failures(tmp_path):
    source=source_png();queue=StyleQueue(tmp_path,start=False)
    identifiers=[]
    for index in range(100):
        payload=b'not an image' if index in (7,31,86) else source
        identifiers.append(queue.submit(BytesIO(payload),f'original-{index}.png','clean')['id'])
    with pytest.raises(ValueError):queue.submit(BytesIO(source),'overflow.png','clean')
    while queue.run_one():pass
    jobs=queue.list();failed=[job for job in jobs if job['state']=='failed']
    assert len(failed)==3 and len([job for job in jobs if job['state']=='done'])==97
    for job in failed:queue.retry(job['id'])
    while queue.run_one():pass
    assert all(queue.get(job['id'])['attempts']==1 for job in jobs if job['state']=='done')
    assert all(queue.get(job['id'])['attempts']==2 for job in failed)
    assert all(queue.get(identifier)['source_sha256']==sha256(queue.path(identifier,'.source').read_bytes()).hexdigest() for identifier in identifiers)


def test_cancel_and_remove_are_explicit(tmp_path):
    queue=StyleQueue(tmp_path,start=False);job=queue.submit(BytesIO(source_png()),'cancel.png','clean')
    with pytest.raises(ValueError):queue.remove(job['id'])
    queue.cancel(job['id']);assert queue.get(job['id'])['state']=='cancelled'
    assert not queue.run_one()
    queue.remove(job['id']);assert not queue.list()


def test_one_coordinator_per_local_queue(tmp_path):
    first=StyleQueue(tmp_path);second=StyleQueue(tmp_path)
    try:
        assert first.thread is not None and second.thread is None
        first.close();second.ensure_started();assert second.thread is not None
    finally:first.close();second.close()
