from __future__ import annotations as _annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import helpers
from sentence_transformers import SentenceTransformer
from typing_extensions import AsyncGenerator
import forms
import legislation


@asynccontextmanager
async def database_connect(
        create_db: bool = False,
) -> AsyncGenerator[asyncpg.Pool, None]:
    server_dsn, database = (
        'postgresql://@localhost:5432',
        'maia',
    )
    if create_db:
        print(f"Connecting to server to check if database {database} exists...")
        conn = await asyncpg.connect(server_dsn, database=database)
        try:
            db_exists = await conn.fetchval(
                'SELECT 1 FROM pg_database WHERE datname = $1', database
            )
            if not db_exists:
                print(f"Creating database {database}...")
                await conn.execute(f'CREATE DATABASE {database}')
                print(f"Database {database} created successfully.")
            else:
                print(f"Database {database} already exists.")
        finally:
            await conn.close()

    print(f"Connecting to database {database}...")
    pool = await asyncpg.create_pool(f'{server_dsn}/{database}')
    try:
        yield pool
    finally:
        await pool.close()

async def populate_db(transformer: SentenceTransformer, forms_path: Path, legislation_path: Path):
    async with database_connect(True) as pool:
        print("Setting up database schema...")
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(helpers.read_file_to_string("sql/forms-db-init.sql"))
        # Get all JSON files in the forms_data directory

        await forms.populate_db(forms_path, pool, transformer)
        await legislation.populate_db(legislation_path, pool, transformer)


if __name__ == "__main__":
    print("Loading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2', truncate_dim=1536)
    forms_dir = Path("./uscis-crawler/documents/forms")
    forms_dir.mkdir(exist_ok=True)
    legislation_dir = Path("./uscis-crawler/documents/legislation")
    legislation_dir.mkdir(exist_ok=True)
    asyncio.run(populate_db(model, forms_dir, legislation_dir))
