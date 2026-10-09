from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from cricai.config import Settings
from cricai.db import Base, make_engine


@pytest.fixture
def database() -> Iterator[Engine]:
    url = Settings().database_url
    if not url:
        pytest.skip("PostgreSQL integration requires CRICAI_DATABASE_URL")
    admin = make_engine(url)
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5},
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
