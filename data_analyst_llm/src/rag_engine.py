import os, re, hashlib
from pathlib import Path
from typing import List, Dict
import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "knowledge_base"
DB_DIR = ROOT / "chroma_db"
COLLECTION = "fokara_knowledge"
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks

def build_index():
    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space":"cosine"})
    ids, docs, metas = [], [], []
    for path in sorted(KB_DIR.glob("*.md")):
        role = path.stem.replace("_", " ").title()
        for i, chunk in enumerate(chunk_text(path.read_text(encoding="utf-8"))):
            uid = hashlib.sha1(f"{path.name}:{i}:{chunk}".encode()).hexdigest()
            ids.append(uid); docs.append(chunk)
            metas.append({"source":path.name, "role":role})
    if docs:
        embeddings = model.encode(docs, normalize_embeddings=True).tolist()
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
    print(f"Indexed {len(docs)} chunks into {COLLECTION}")

def retrieve(query: str, role: str = None, top_k: int = 4) -> List[Dict]:
    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(DB_DIR))
    collection = client.get_collection(COLLECTION)
    qemb = model.encode([query], normalize_embeddings=True).tolist()
    where = None
    if role:
        role_map = {"Data Analyst":"Data Analyst", "Data Scientist":"Data Scientist", "Data Engineer":"Data Engineer"}
        where = {"role": role_map.get(role, role)}
    result = collection.query(query_embeddings=qemb, n_results=top_k, where=where)
    output = []
    for i, doc in enumerate((result.get("documents") or [[]])[0]):
        output.append({
            "text":doc,
            "source":(result.get("metadatas") or [[]])[0][i].get("source"),
            "distance":(result.get("distances") or [[]])[0][i]
        })
    return output

if __name__ == "__main__":
    build_index()
    print(retrieve("Bagaimana menangani missing values?", "Data Analyst"))
