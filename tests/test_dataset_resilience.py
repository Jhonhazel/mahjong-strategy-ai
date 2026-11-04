import hashlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tarfile
import threading

import pytest


def tar_bytes(name="ok/data.txt", content=b"verified", link=None):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        member = tarfile.TarInfo(name)
        if link is not None:
            member.type, member.linkname = tarfile.SYMTYPE, link
            tar.addfile(member)
        else:
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
    return output.getvalue()


@pytest.mark.integration
def test_real_http_retries_503_and_truncated_response(tmp_path):
    from training.dataset_loader import download_with_retry
    payload = tar_bytes()
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if len(hits) <= 2:
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload[:10] if len(hits) == 3 else payload)
            self.close_connection = True
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        path = download_with_retry(f"http://127.0.0.1:{server.server_port}/data", tmp_path / "data.tar.gz", len(payload), hashlib.sha256(payload).hexdigest(), base_backoff_sec=0.001)
        assert path.read_bytes() == payload and len(hits) == 4
        download_with_retry("http://127.0.0.1:1/not-needed", path, len(payload), hashlib.sha256(payload).hexdigest())
        assert not path.with_suffix(".gz.part").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


@pytest.mark.integration
def test_exhausted_download_and_bad_hash_never_publish_partial_file(tmp_path):
    from training.dataset_loader import download_with_retry
    from app.domain.exceptions import DatasetDownloadError, CorruptedDatasetError
    dest = tmp_path / "bad.tar.gz"
    with pytest.raises(DatasetDownloadError):
        download_with_retry("http://127.0.0.1:1/data", dest, max_retries=2, base_backoff_sec=0)
    assert not dest.exists() and not dest.with_suffix(".gz.part").exists()


@pytest.mark.parametrize("name,link", [("../escape.txt", None), ("/absolute.txt", None), ("C:\\escape.txt", None), ("safe/link", "../../escape"), ("safe\\..\\escape", None)])
def test_unsafe_archives_are_rejected_before_writes(tmp_path, name, link):
    from training.dataset_loader import safe_extract_tar_gz
    from app.domain.exceptions import CorruptedDatasetError
    source = tmp_path / "source.tar.gz"
    source.write_bytes(tar_bytes(name, link=link))
    dest = tmp_path / "output"
    with pytest.raises(CorruptedDatasetError):
        safe_extract_tar_gz(source, dest)
    assert not dest.exists() or not list(dest.rglob("*"))


def test_valid_archive_and_truncated_gzip(tmp_path):
    from training.dataset_loader import safe_extract_tar_gz
    from app.domain.exceptions import CorruptedDatasetError
    source = tmp_path / "source.tar.gz"
    payload = tar_bytes()
    source.write_bytes(payload)
    files = safe_extract_tar_gz(source, tmp_path / "valid")
    assert len(files) == 1 and files[0].read_bytes() == b"verified"
    source.write_bytes(payload[:-8])
    with pytest.raises(CorruptedDatasetError):
        safe_extract_tar_gz(source, tmp_path / "truncated")
