"""Standard FastAPI CLI entry point; resources initialize only in app lifespan."""
from app.main import create_app

app = create_app()
