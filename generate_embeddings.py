"""
अर्थAI — Embedding Generation Pipeline
Generates ChromaDB vector embeddings from PDF files and uploads to Google Drive.

MODEL        : jinaai/jina-embeddings-v2-base-en  (8192-token context window)
CHUNK SIZE   : 20,000 chars  (~5,000-6,000 tokens — safely under the limit)
CHUNK OVERLAP: 1,000 chars
EMBEDDING DIM: 768  (normalized)

─── GOOGLE DRIVE SETUP (one-time) ────────────────────────────────────────────
1. Go to  https://console.cloud.google.com/
2. Create a project (or select an existing one)
3. Search "Google Drive API" → Enable it
4. Go to Credentials → Create Credentials → OAuth 2.0 Client ID
5. Application type: Desktop app  → give it any name → Create
6. Download the JSON → rename it to  client_secrets.json
7. Place client_secrets.json in the same folder as this script:
       /Users/saumgupt/Desktop/Capstone/client_secrets.json
8. On first run, a browser window will open — log in and allow access.
   A token.json is saved so you won't need to do this again.
──────────────────────────────────────────────────────────────────────────────
"""

import os
import gc
import torch
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
PDF_DIRECTORY       = BASE_DIR                              # PDFs are here
LOCAL_CHROMA_PATH   = os.path.join(BASE_DIR, "VectorDB")   # local save path
GDRIVE_FOLDER_NAME  = "ArthAI_VectorDB"                    # name on Google Drive
# PDFs in the folder that should NOT be embedded (proposals, reports, etc.)
EXCLUDED_PDFS       = {"Capstone project proposal2.pdf"}
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, "client_secrets.json")
TOKEN_FILE          = os.path.join(BASE_DIR, "token.json")
SCOPES              = ["https://www.googleapis.com/auth/drive.file"]


# ── EMBEDDING MODEL ───────────────────────────────────────────────────────────
def get_jina_embeddings() -> HuggingFaceEmbeddings:
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():   # Apple Silicon
        device = "mps"
    else:
        device = "cpu"
    print(f"Loading Jina Embeddings on: {device}")

    return HuggingFaceEmbeddings(
        model_name="jinaai/jina-embeddings-v2-base-en",
        model_kwargs={"device": device, "trust_remote_code": True},
        encode_kwargs={"normalize_embeddings": True},
    )


# ── EMBEDDING PIPELINE ────────────────────────────────────────────────────────
def process_and_store_pdfs(pdf_directory: str, vector_db_path: str):
    embeddings = get_jina_embeddings()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=20000,
        chunk_overlap=1000,
        separators=["\n\n\n", "\n\n", "\n", ".", " ", ""],
        length_function=len,
    )

    vector_db = Chroma(
        embedding_function=embeddings,
        persist_directory=vector_db_path,
    )

    pdf_files = [f for f in os.listdir(pdf_directory) if f.endswith(".pdf")
                 and f not in EXCLUDED_PDFS]
    if not pdf_files:
        print(f"No PDF files found in {pdf_directory}")
        return None

    print(f"Found {len(pdf_files)} PDF(s): {pdf_files}\n")
    batch_size = 3

    for batch_start in range(0, len(pdf_files), batch_size):
        batch = pdf_files[batch_start : batch_start + batch_size]
        all_splits = []

        for file in batch:
            print(f"  Parsing: {file}")
            loader = PyPDFLoader(os.path.join(pdf_directory, file))
            docs = loader.load()

            for idx, doc in enumerate(docs):
                doc.metadata["source"] = file
                doc.metadata["page"] = idx + 1

            splits = text_splitter.split_documents(docs)
            all_splits.extend(splits)
            print(f"    → {len(splits)} chunks")

        print(f"\nEmbedding {len(all_splits)} chunks into ChromaDB...")
        vector_db.add_documents(all_splits)

        del all_splits
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("Memory cleared.\n")

    print(f"✅ Embeddings saved locally to: {vector_db_path}\n")
    return vector_db


# ── GOOGLE DRIVE AUTH ─────────────────────────────────────────────────────────
def authenticate_gdrive():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print("⚠️  client_secrets.json not found.")
                print("   Follow the setup instructions at the top of this file.")
                print("   Skipping Google Drive upload — VectorDB saved locally.\n")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ── GOOGLE DRIVE UPLOAD ───────────────────────────────────────────────────────
def upload_folder_to_gdrive(service, local_folder: str, folder_name: str) -> str:
    def _create_folder(name: str, parent_id=None) -> str:
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            meta["parents"] = [parent_id]
        return service.files().create(body=meta, fields="id").execute()["id"]

    def _upload_recursive(local_path: str, drive_parent_id: str):
        for item in sorted(os.listdir(local_path)):
            item_path = os.path.join(local_path, item)
            if os.path.isdir(item_path):
                sub_id = _create_folder(item, drive_parent_id)
                _upload_recursive(item_path, sub_id)
            else:
                media = MediaFileUpload(item_path, resumable=True)
                service.files().create(
                    body={"name": item, "parents": [drive_parent_id]},
                    media_body=media,
                    fields="id",
                ).execute()
                print(f"  Uploaded: {os.path.relpath(item_path, local_folder)}")

    root_id = _create_folder(folder_name)
    print(f"Created Google Drive folder '{folder_name}' (id: {root_id})")
    _upload_recursive(local_folder, root_id)
    print(f"\n✅ VectorDB uploaded to Google Drive as '{folder_name}'")
    print(f"   Folder ID (save this): {root_id}")
    return root_id


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  अर्थAI — Embedding Generation")
    print("=" * 60 + "\n")

    db = process_and_store_pdfs(PDF_DIRECTORY, LOCAL_CHROMA_PATH)
    if db is None:
        raise SystemExit("Aborted: no PDFs found.")

    print("Authenticating with Google Drive...")
    service = authenticate_gdrive()

    if service:
        upload_folder_to_gdrive(service, LOCAL_CHROMA_PATH, GDRIVE_FOLDER_NAME)
    else:
        print("Run again after placing client_secrets.json to upload to Drive.")
