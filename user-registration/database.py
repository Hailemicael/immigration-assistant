from pathlib import Path
from typing import Tuple, Optional


class Config:
    def __init__(self, schema_dir: str = "", dsn: str = "postgresql://@localhost:5432", database: str = "maia", pool_size: Tuple[int, int] = (1, 10)) -> None:
        self.schema_dir = Path(schema_dir)
        self.dsn = dsn
        self.database = database
        self.min_pool_size = pool_size[0]
        self.max_pool_size = pool_size[1]

    def copy(
            self,
            schema_dir: Optional[str] = None,
            dsn: Optional[str] = None,
            database: Optional[str] = None,
            pool_size: Optional[Tuple[int, int]] = None
    ) -> 'Config':
        return Config(
            schema_dir=str(schema_dir) if schema_dir is not None else str(self.schema_dir),
            dsn=dsn if dsn is not None else self.dsn,
            database=database if database is not None else self.database,
            pool_size=pool_size if pool_size is not None else (self.min_pool_size, self.max_pool_size),
        )