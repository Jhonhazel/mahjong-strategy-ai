"""Generate original local vector artwork and JS catalog from one verified map."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from app.web.tile_catalog import TILE_CATALOG,WIND_NAMES

ROOT=Path(__file__).resolve().parents[1]
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
INK='#163f36';RED='#a9343e';GREEN='#20624e';GOLD='#a77a37'
NUMERALS=('一','二','三','四','五','六','七','八','九')


def element(parent,tag,**attributes):
    return ET.SubElement(parent,'{'+NS+'}'+tag,{key.replace('_','-'):str(value) for key,value in attributes.items()})


def text(parent,value,x,y,size,fill=INK):
    node=element(parent,'text',x=x,y=y,font_size=size,fill=fill,text_anchor='middle',font_family='serif')
    node.text=value


def positions(rank):
    return {
        1:[(30,43)],2:[(30,27),(30,59)],3:[(18,25),(30,43),(42,61)],
        4:[(19,27),(41,27),(19,59),(41,59)],
        5:[(17,24),(43,24),(30,43),(17,62),(43,62)],
        6:[(x,y) for y in (24,43,62) for x in (19,41)],
        7:[(30,17)]+[(x,y) for y in (34,49,64) for x in (19,41)],
        8:[(x,y) for y in (20,35,50,65) for x in (19,41)],
        9:[(x,y) for y in (23,43,63) for x in (17,30,43)],
    }[rank]


def draw_face(parent,face):
    if face.kind=='back':
        element(parent,'rect',x=1,y=1,width=58,height=82,rx=6,fill=INK,stroke='#c5b27b')
        element(parent,'rect',x=6,y=6,width=48,height=72,rx=3,fill='none',stroke='#819e81',stroke_width='.7')
        for x in (15,30,45):
            for y in (18,34,50,66):
                element(parent,'path',d=f'M{x} {y-6}l5 6-5 6-5-6z',fill='none',stroke='#8ca88e',stroke_width='.8')
        return
    element(parent,'rect',x=1,y=1,width=58,height=82,rx=6,fill='#fffdf4',stroke='#d7cfb9')
    if face.kind=='unknown':
        text(parent,'?',30,54,34,'#6b786d');return
    text(parent,face.code,49,11,6,'#5d7065')
    if face.kind=='characters':
        text(parent,NUMERALS[face.rank-1],30,36,27)
        text(parent,'萬',30,66,29,RED)
    elif face.kind=='circles':
        for i,(x,y) in enumerate(positions(face.rank)):
            radius=12 if face.rank==1 else 4.5 if face.rank==9 else 5.2
            color=RED if i%3==1 else GREEN if i%3==0 else INK
            element(parent,'circle',cx=x,cy=y,r=radius,fill='none',stroke=color,stroke_width=2)
            element(parent,'circle',cx=x,cy=y,r=radius*.42,fill=color)
    elif face.kind=='bamboo':
        if face.rank==1:
            element(parent,'path',d='M15 55Q19 35 29 31Q39 29 43 40Q42 55 27 57L20 68L22 54Z',fill=GREEN)
            element(parent,'path',d='M26 40Q34 36 37 44Q33 53 26 50Z',fill='#87a06b')
            element(parent,'circle',cx=34,cy=27,r=8,fill=INK)
            element(parent,'circle',cx=36,cy=25,r=1.4,fill='#fffdf4')
            element(parent,'path',d='M41 27l9 3-9 3Z',fill=GOLD)
            element(parent,'path',d='M13 67L44 62',stroke=GOLD,stroke_width=2)
        else:
            points=[(23,43),(37,43)] if face.rank==2 else [(17,43),(30,43),(43,43)] if face.rank==3 else positions(face.rank)
            height=27 if face.rank<=3 else 12
            for i,(x,y) in enumerate(points):
                color=RED if face.rank in (5,7,9) and i==len(points)//2 else GREEN
                element(parent,'path',d=f'M{x} {y-height/2}v{height}',stroke=color,stroke_width=4,stroke_linecap='round')
                for offset in (-height*.27,height*.27):
                    element(parent,'path',d=f'M{x-3.5} {y+offset}h7',stroke=color,stroke_width=1.8,stroke_linecap='round')
    elif face.kind=='wind':
        text(parent,('東','南','西','北')[face.rank-1],30,58,36)
    elif face.kind=='dragon':
        if face.rank==3:
            element(parent,'rect',x=15,y=23,width=30,height=39,rx=2,fill='none',stroke='#346d83',stroke_width=3)
            element(parent,'rect',x=19,y=27,width=22,height=31,fill='none',stroke='#346d83',stroke_width='.8')
        else:text(parent,('中','發')[face.rank-1],30,58,37,RED if face.rank==1 else GREEN)
    elif face.kind=='flower':
        color=RED if face.rank<=4 else GREEN
        for i in range(8):
            angle=math.pi*i/4
            element(parent,'ellipse',cx=30+11*math.sin(angle),cy=39+11*math.cos(angle),rx=5,ry=9,
                    fill=color,opacity='.8',transform=f'rotate({-i*45} {30+11*math.sin(angle)} {39+11*math.cos(angle)})')
        element(parent,'circle',cx=30,cy=39,r=6,fill=GOLD)
        text(parent,str(face.rank),30,70,14)


def build_assets(output=ROOT/'app/static'):
    output=Path(output);(output/'phase4').mkdir(parents=True,exist_ok=True)
    svg=ET.Element('{'+NS+'}svg')
    for face in TILE_CATALOG.values():
        symbol=element(svg,'symbol',id=face.symbol,viewBox='0 0 60 84')
        element(symbol,'title').text=face.label;draw_face(symbol,face)
    content=ET.tostring(svg,encoding='unicode')+'\n'
    (output/'tiles.svg').write_text(content)
    catalog={code:asdict(face) for code,face in TILE_CATALOG.items()}
    module='// Generated by scripts.build_tile_assets from the canonical presentation map.\n'
    module+='export const TILE_CATALOG = Object.freeze(Object.fromEntries(Object.entries('+json.dumps(catalog,ensure_ascii=False,indent=2)+').map(([code, value]) => [code, Object.freeze(value)])));\n'
    module+='export const WIND_NAMES = Object.freeze('+json.dumps(WIND_NAMES,ensure_ascii=False)+');\n'
    (output/'phase4/catalog.mjs').write_text(module)
    return len(content.encode())


if __name__=='__main__':print('Generated local tile sprite bytes:',build_assets())
