# AI Digital Identity System - Folder Structure

```text
digital-identity-system/
│
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── docs/                               # Project Documentation
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── AI_WORKFLOW.md
│   ├── UI_UX.md
│   ├── DEPLOYMENT.md
│   ├── TESTING.md
│   └── PRESENTATION.md
│
├── frontend/                           # React Frontend
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   ├── logo.png
│   │   └── index.html
│   │
│   ├── src/
│   │   │
│   │   ├── assets/
│   │   │   ├── images/
│   │   │   ├── icons/
│   │   │   ├── animations/
│   │   │   └── fonts/
│   │   │
│   │   ├── components/
│   │   │   ├── Navbar/
│   │   │   ├── Sidebar/
│   │   │   ├── Upload/
│   │   │   ├── Dashboard/
│   │   │   ├── Timeline/
│   │   │   ├── Search/
│   │   │   ├── Chat/
│   │   │   ├── KnowledgeGraph/
│   │   │   ├── Cards/
│   │   │   └── Common/
│   │   │
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── Register.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Upload.jsx
│   │   │   ├── Search.jsx
│   │   │   ├── Timeline.jsx
│   │   │   ├── Profile.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── NotFound.jsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.js
│   │   │   ├── auth.js
│   │   │   ├── upload.js
│   │   │   ├── search.js
│   │   │   └── graph.js
│   │   │
│   │   ├── hooks/
│   │   ├── context/
│   │   ├── routes/
│   │   ├── utils/
│   │   ├── styles/
│   │   ├── App.jsx
│   │   └── main.jsx
│   │
│   └── package.json
│
├── backend/                            # FastAPI Backend
│   │
│   ├── app/
│   │   │
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── upload.py
│   │   │   ├── documents.py
│   │   │   ├── search.py
│   │   │   ├── timeline.py
│   │   │   ├── graph.py
│   │   │   └── profile.py
│   │   │
│   │   ├── ai/
│   │   │   ├── llm.py
│   │   │   ├── prompt.py
│   │   │   ├── classifier.py
│   │   │   ├── extractor.py
│   │   │   ├── embeddings.py
│   │   │   ├── rag.py
│   │   │   ├── summarizer.py
│   │   │   └── recommendation.py
│   │   │
│   │   ├── vector_db/
│   │   │   ├── chroma.py
│   │   │   ├── retrieval.py
│   │   │   └── indexing.py
│   │   │
│   │   ├── graph/
│   │   │   ├── knowledge_graph.py
│   │   │   ├── relationships.py
│   │   │   └── timeline_builder.py
│   │   │
│   │   ├── ocr/
│   │   │   ├── pdf_parser.py
│   │   │   ├── image_parser.py
│   │   │   ├── docx_parser.py
│   │   │   └── ocr_engine.py
│   │   │
│   │   ├── database/
│   │   │   ├── connection.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   └── migrations/
│   │   │
│   │   ├── middleware/
│   │   ├── services/
│   │   ├── utils/
│   │   ├── config.py
│   │   └── main.py
│   │
│   ├── uploads/
│   │   ├── certificates/
│   │   ├── resumes/
│   │   ├── internships/
│   │   ├── projects/
│   │   ├── achievements/
│   │   └── others/
│   │
│   ├── vector_store/
│   │   └── chroma_db/
│   │
│   └── requirements.txt
│
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   └── migrations/
│
├── sample_data/
│   ├── certificates/
│   ├── resumes/
│   ├── internships/
│   ├── projects/
│   └── achievements/
│
├── scripts/
│   ├── setup.py
│   ├── ingest_documents.py
│   ├── build_embeddings.py
│   ├── reset_database.py
│   └── generate_demo_data.py
│
├── tests/
│   ├── backend/
│   ├── frontend/
│   ├── ai/
│   └── integration/
│
├── deployment/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── docker-compose.yml
│   └── cloud/
│
└── diagrams/
    ├── architecture.png
    ├── workflow.png
    ├── database.png
    ├── knowledge_graph.png
    └── timeline.png
```

---

# Folder Description

| Folder | Purpose |
|---------|----------|
| **docs/** | All project documentation (PRD, Architecture, API, AI Workflow, Deployment) |
| **frontend/** | React web application |
| **backend/** | FastAPI backend services |
| **backend/ai/** | AI modules (LLM, Embeddings, RAG, Classification) |
| **backend/vector_db/** | ChromaDB integration and semantic search |
| **backend/graph/** | Knowledge graph and relationship engine |
| **backend/ocr/** | PDF, DOCX, Image text extraction |
| **backend/database/** | Database models and schemas |
| **uploads/** | Original uploaded documents |
| **vector_store/** | ChromaDB persistent storage |
| **database/** | SQL schema and migrations |
| **sample_data/** | Demo files for testing |
| **scripts/** | Utility scripts |
| **tests/** | Unit and integration tests |
| **deployment/** | Docker and deployment configuration |
| **diagrams/** | Architecture and workflow diagrams |

---

# Recommended Tech Stack

- **Frontend:** React + Tailwind CSS + Framer Motion
- **Backend:** FastAPI
- **Database:** PostgreSQL (SQLite for MVP)
- **Vector Database:** ChromaDB
- **LLM:** Gemini 2.5 / OpenAI GPT
- **Embeddings:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **OCR:** Tesseract OCR
- **Knowledge Graph:** NetworkX
- **Authentication:** JWT
- **Deployment:** Docker + Nginx