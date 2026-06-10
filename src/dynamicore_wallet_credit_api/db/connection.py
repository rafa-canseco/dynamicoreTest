from collections.abc import Generator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from dynamicore_wallet_credit_api.core.config import get_settings


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    settings = get_settings()

    with Connection.connect(settings.database_url, row_factory=dict_row) as connection:
        yield connection
