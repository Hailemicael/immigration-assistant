from pathlib import Path


class RAGConfig:
    def __init__(self, forms_path: str, legislation_path: str, chunk_size: int = 512, input_embedding_prefix: str = "None", query_embedding_prefix: str = "None"):
        self.forms_path = Path(forms_path)
        self.legislation_path = Path(legislation_path)
        self.chunk_size = chunk_size
        self.input_embedding_prefix = input_embedding_prefix
        self.query_embedding_prefix = query_embedding_prefix