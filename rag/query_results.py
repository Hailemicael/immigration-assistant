from dataclasses import dataclass
from typing import List


@dataclass
class QueryResult:
    query: str
    forms: List
    legislation: List