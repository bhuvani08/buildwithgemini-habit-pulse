import os
import vertexai
from vertexai.preview import rag
from vertexai.preview.rag.utils import resources as rr

PROJECT_ID = "qwiklabs-gcp-01-4891f3ba97eb"
LOCATION = "us-central1"
GCS_PATH = "gs://habit-pulse-assets-qwiklabs-gcp-01-4891f3ba97eb/rag/pg49513.txt"

vertexai.init(project=PROJECT_ID, location=LOCATION)

# 1. Switch region RAG DB to serverless mode
cfg = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig"
rag.update_rag_engine_config(
    rag_engine_config=rag.RagEngineConfig(
        name=cfg,
        rag_managed_db_config=rag.RagManagedDbConfig(mode=rr.Serverless()),
    )
)

# 2. Create serverless corpus
corpus = rag.create_corpus(
    display_name="complete-herbal-corpus",
    embedding_model_config=rag.EmbeddingModelConfig(
        publisher_model="publishers/google/models/text-embedding-005"
    ),
)
print("CREATED_CORPUS_NAME:", corpus.name)

# 3. Import files
resp = rag.import_files(
    corpus_name=corpus.name,
    paths=[GCS_PATH],
    transformation_config=rag.TransformationConfig(
        chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=100)
    ),
)
print("IMPORTED_FILES_COUNT:", resp.imported_rag_files_count)
