"""Optional RAG tool: turns the SMAM scheme PDFs into a retriever the agent can call as a tool."""
import os

import requests
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config

INDEX_DIR = os.path.join(config.ROOT, "faiss_scheme_index")


def download_scheme_pdfs(data_dir: str = config.DATA_DIR) -> list[str]:
    os.makedirs(data_dir, exist_ok=True)
    paths = []
    for name, url in config.SCHEME_PDF_URLS:
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (KisanMitra academic project)"}, timeout=60)
                r.raise_for_status()
                if not r.content.startswith(b"%PDF"):
                    raise ValueError("not a PDF")
                open(path, "wb").write(r.content)
                print(f"saved {name}")
            except Exception as exc:
                print(f"FAILED {name}: {exc}")
                continue
        paths.append(path)
    return paths


def build_scheme_retriever(pdf_paths: list[str], k: int = 3):
    """Index the scheme PDFs and return a VectorStoreRetriever (None if no PDFs are available)."""
    if not pdf_paths:
        return None
    from langchain_huggingface import HuggingFaceEmbeddings
    docs = []
    for path in pdf_paths:
        for page in PyPDFLoader(path).load():
            page.metadata["source_file"] = os.path.basename(path)
            page.metadata["page_no"] = page.metadata.get("page", 0) + 1
            if len(page.page_content.strip()) > 40:
                docs.append(page)
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5",
                                       encode_kwargs={"normalize_embeddings": True})
    vs = FAISS.from_documents(chunks, embeddings)
    vs.save_local(INDEX_DIR)
    print(f"Scheme index: {len(chunks)} chunks from {len(pdf_paths)} PDFs")
    return vs.as_retriever(search_type="mmr", search_kwargs={"k": k, "fetch_k": 15})


def make_scheme_tool(retriever):
    """Wrap a retriever as a tool so the agent can decide when scheme rules are needed."""

    @tool("lookup_scheme_rules")
    def lookup_scheme_rules(question: str) -> str:
        """Look up government farm-mechanisation scheme rules (SMAM subsidy percentages, eligibility,
        Custom Hiring Centres) in the official guideline PDFs. Use for any subsidy or eligibility question.
        Returns passages with file and page so they can be cited."""
        docs = retriever.invoke(question)
        if not docs:
            return "TOOL_ERROR: nothing found in the scheme guidelines for that question."
        return "\n\n".join(f"[{d.metadata.get('source_file')} p.{d.metadata.get('page_no')}] {d.page_content[:700]}"
                           for d in docs)

    return lookup_scheme_rules
