"""Create missing Phase3 tables; never drop or silently migrate existing tables."""
import json

from app.db import create_db_engine, initialize_schema
from app.settings import Settings


def main():
    engine = create_db_engine(Settings())
    try:
        print(json.dumps(initialize_schema(engine),indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':main()
