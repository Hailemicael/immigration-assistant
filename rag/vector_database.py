from __future__ import annotations as _annotations

import abc
from pathlib import Path

import asyncpg
from sentence_transformers import SentenceTransformer


class VectorDatabase(abc.ABC):
    """Abstract base class for vector database implementations."""

    def __init__(self, model: SentenceTransformer, data_dir: Path, insert_embedding_prefix: str = None, query_embedding_prefix: str = None) -> None:
        """
        Initialize the vector database.

        Args:
            model: SentenceTransformer model for generating embeddings
            data_dir: Directory containing data files to be processed
            insert_embedding_prefix: Optional prefix for insert embedding generation
            query_embedding_prefix: Optional prefix for query embedding generation
        """
        self.model = model
        self.data_dir = data_dir
        self.insert_embedding_prefix = insert_embedding_prefix
        self.query_embedding_prefix = query_embedding_prefix

    @abc.abstractmethod
    async def populate(self, pool: asyncpg.Pool) -> None:
        """
        Populate the database with data from files.

        Args:
            pool: Database connection pool
        """
        pass

    @abc.abstractmethod
    async def search(self, pool: asyncpg.Pool, search_query: str, limit: int = 10, verbose: bool = False):
        """
        Search the database for entries matching the query.

        Args:
            pool: Database connection pool
            search_query: Query string to search for
            limit: Maximum number of results to return
            verbose:

        Returns:
            List of matching entries
        """
        pass

    @staticmethod
    @abc.abstractmethod
    async def clear(pool: asyncpg.Pool) -> None:
        """
        Clear all data from the database tables.

        Args:
            pool: Database connection pool
        """
        pass