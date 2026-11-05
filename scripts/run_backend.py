"""Run the supported single-worker local backend using typed environment config."""
import uvicorn

from app.settings import Settings


def main():
    settings=Settings()
    uvicorn.run('app.main:create_app',factory=True,host=settings.host,port=settings.port,
                workers=settings.workers,proxy_headers=False,log_level='info')


if __name__=='__main__':main()
