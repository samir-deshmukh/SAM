# Dependency Inventory and Audit Status

Declared requirements are in `requirements.txt`; these are not a resolved transitive lock or vulnerability certification.

| Package | Declared version/range | Purpose |
|---|---|---|
| pandas | 2.2.3 | Tabular normalization |
| pdfplumber | 0.11.10 | PDF text/table extraction |
| pdfminer.six | 20260107 | PDF parsing |
| SQLAlchemy | 2.0.36 | DB toolkit |
| psycopg2-binary | 2.9.10 | PostgreSQL driver |
| openpyxl | 3.1.5 | Spreadsheet support |
| pytest | 9.0.3 | Tests |
| python-dotenv | 1.2.2 | Local environment config |
| FastAPI | 0.141.1 | API/admin framework |
| uvicorn[standard] | 0.34.0 | ASGI server |
| python-multipart | 0.0.32 | Uploads |
| itsdangerous | 2.2.0 | Signing support |
| pytesseract | 0.3.13 | OCR wrapper |
| Pillow | 12.3.0 | Image handling |
| PyMuPDF | 1.25.3 | PDF page handling |
| pypdfium2 | 5.13.0 | PDF rendering |
| Streamlit | >=1.40,<2.0 | Retained app |
| Plotly | >=6.0,<7.0 | Charts |
| boto3 | >=1.35,<2.0 | Optional S3-compatible storage |

Before adding dependencies, document purpose, alternatives, maintenance/license/security posture, and resource cost. Audit the resolved release environment; a fresh vulnerability audit was not run here.
