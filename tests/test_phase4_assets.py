import xml.etree.ElementTree as ET

import pytest

from app.domain.tiles import TILE_LIST,FLOWER_TILES
from tests.phase4_support import phase4_client,postgres_engine,postgres_url,web_settings

pytestmark=pytest.mark.integration


def test_local_svg_contains_every_canonical_face_back_and_safe_unknown(phase4_client):
    response=phase4_client.get('/static/tiles.svg')
    assert response.status_code==200
    assert 'image/svg+xml' in response.headers['content-type']
    svg=ET.fromstring(response.content)
    symbols={element.get('id'):element for element in svg.findall('{http://www.w3.org/2000/svg}symbol')}
    assert set(symbols)=={'tile-'+code for code in (*TILE_LIST,*FLOWER_TILES,'back','unknown')}
    for code in (*TILE_LIST,*FLOWER_TILES):
        symbol=symbols['tile-'+code]
        assert symbol.get('viewBox')=='0 0 60 84'
        assert symbol.find('{http://www.w3.org/2000/svg}title').text
    for element in svg.iter():
        assert element.tag.rsplit('}',1)[-1] not in ('script','foreignObject','image')
        assert all(not name.lower().startswith('on') for name in element.attrib)
        assert all('http' not in value for key,value in element.attrib.items() if key.endswith('href'))


def test_visual_catalog_distinguishes_bamboo_dots_winds_and_flowers(phase4_client):
    response=phase4_client.get('/static/tiles.svg');assert response.status_code==200
    svg=ET.fromstring(response.content);ns={'svg':'http://www.w3.org/2000/svg'}
    labels={s.get('id'):s.find('svg:title',ns).text for s in svg.findall('svg:symbol',ns)}
    assert labels['tile-W1']=='Karakter 1'
    assert labels['tile-T1']=='Bambu 1'
    assert labels['tile-B1']=='Lingkaran 1'
    assert labels['tile-F1']=='Angin Timur' and labels['tile-F4']=='Angin Utara'
    assert labels['tile-J1']=='Naga Merah' and labels['tile-J3']=='Naga Putih'
    assert labels['tile-H1']=='Bunga 1' and labels['tile-H8']=='Bunga 8'
    assert len(response.content)<100_000


def test_local_tile_module_and_catalog_are_served_under_existing_csp(phase4_client):
    for path in ('phase4/catalog.mjs','phase4/tiles.mjs'):
        response=phase4_client.get('/static/'+path)
        assert response.status_code==200
        assert "'self'" in response.headers['content-security-policy']
        assert "'unsafe-inline'" not in response.headers['content-security-policy']
