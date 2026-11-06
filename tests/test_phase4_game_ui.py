from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('suite',['tiles','model','http','controller','view','deletion'])
def test_phase4_node_frontend_contracts(suite):
    node=shutil.which('node')
    assert node, 'Phase4 Node tests NOT RUN: install the documented Node runtime'
    result=subprocess.run([node,'--test',str(ROOT/'tests/frontend'/f'{suite}.test.mjs')],
                          capture_output=True,text=True,timeout=30,cwd=ROOT)
    assert result.returncode==0,result.stdout+result.stderr
