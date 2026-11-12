from io import BytesIO
import zipfile
from fastapi.testclient import TestClient
from backend.api.app import app
import backend.api.style_queue as api
from backend.image.style_queue import StyleQueue
from tests.test_style_queue import source_png


def test_submit_control_download_archive_and_cleanup(tmp_path,monkeypatch):
    queue=StyleQueue(tmp_path,start=False);monkeypatch.setattr(api,'style_queue',lambda:queue)
    with TestClient(app) as client:
        response=client.post('/api/image/style-queue/jobs',files={'file':('Original label.png',source_png(),'image/png')},data={'style':'soft'})
        assert response.status_code==202
        identifier=response.json()['id']
        assert client.get('/api/image/style-queue/jobs').json()['limits']['workers']==1
        assert queue.run_one()
        single=client.get(f'/api/image/style-queue/jobs/{identifier}/download')
        assert single.status_code==200 and zipfile.is_zipfile(BytesIO(single.content))
        bundle=client.post('/api/image/style-queue/archive',json={'ids':[identifier]})
        assert bundle.status_code==200
        with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
            assert any(name.endswith('/presentation.svg') for name in archive.namelist())
            assert any(name.endswith('/source/original.png') for name in archive.namelist())
        assert not list(tmp_path.glob('bundle-*.zip'))
        assert client.delete(f'/api/image/style-queue/jobs/{identifier}').status_code==200
        assert not queue.list()
