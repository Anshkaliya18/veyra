# ARCHITECTURE.md

# Veyra System Architecture

## Overview

Veyra follows a modular, service-oriented architecture that transforms unstructured documents into structured, searchable, and intelligent knowledge. The application is built around a Python Flask backend, a lightweight HTML/CSS/JavaScript frontend, AI-powered document processing services, Supabase cloud storage, and a relational database.

The system is divided into independent layers, allowing each component to evolve without affecting the rest of the application.

---

# High-Level Architecture

```text
                                   ┌──────────────────────┐
                                   │        User          │
                                   │ Desktop / Laptop Web │
                                   └──────────┬───────────┘
                                              │
                                              ▼
                    ┌──────────────────────────────────────────┐
                    │              Frontend Layer              │
                    │ HTML • CSS • JavaScript • Responsive UI │
                    └─────────────────┬────────────────────────┘
                                      │
                                      ▼
                    ┌──────────────────────────────────────────┐
                    │              Flask Backend               │
                    │ Authentication • Routes • Sessions • API │
                    └───────────────┬───────────────┬──────────┘
                                    │               │
                    ┌───────────────┘               └───────────────┐
                    ▼                                               ▼
        ┌──────────────────────┐                     ┌──────────────────────┐
        │   Database Layer     │                     │   File Storage Layer │
        │ User Data            │                     │      Supabase        │
        │ Documents            │                     │ Uploaded Documents   │
        │ Metadata             │                     │ Processed Files      │
        └──────────┬───────────┘                     └──────────┬───────────┘
                   │                                            │
                   └──────────────────┬─────────────────────────┘
                                      ▼
                ┌───────────────────────────────────────────────┐
                │           AI Processing Engine                │
                │                                               │
                │ • Text Extraction                             │
                │ • Content Cleaning                            │
                │ • AI Summarization                            │
                │ • Entity Detection                            │
                │ • Relationship Discovery                      │
                │ • Timeline Generation                         │
                │ • Semantic Search Indexing                    │
                └───────────────────┬───────────────────────────┘
                                    │
                                    ▼
                ┌───────────────────────────────────────────────┐
                │         Intelligence Presentation Layer       │
                │                                               │
                │ Dashboard                                     │
                │ Search                                        │
                │ Timeline                                      │
                │ Profile                                       │
                │ AI Insights                                   │
                └───────────────────────────────────────────────┘
```

---

# System Layers

## 1. Presentation Layer

The Presentation Layer provides the complete user interface of Veyra.

### Responsibilities

* User authentication
* Dashboard
* Profile page
* Upload interface
* Timeline visualization
* Search interface
* Document management

### Technologies

* HTML5
* CSS3
* JavaScript

---

## 2. Application Layer

The Application Layer is powered by Flask.

It controls every request coming from the frontend.

### Responsibilities

* Authentication
* Session management
* API endpoints
* Upload handling
* AI pipeline orchestration
* Database communication
* Response generation

---

## 3. Storage Layer

The Storage Layer stores uploaded files.

### Responsibilities

* Store uploaded documents
* Retrieve files
* Manage cloud storage
* Secure file access

### Technology

* Supabase Storage

---

## 4. Database Layer

Stores application data.

### Primary Data

* Users
* Uploaded documents
* Metadata
* AI summaries
* Timeline events
* Search information
* Relationships

---

## 5. AI Processing Layer

The AI Engine is the core of Veyra.

Every uploaded document passes through this processing pipeline.

```text
Upload
   │
   ▼
Validation
   │
   ▼
Extraction
   │
   ▼
Cleaning
   │
   ▼
AI Analysis
   │
   ▼
Summary
   │
   ▼
Entity Detection
   │
   ▼
Relationship Discovery
   │
   ▼
Timeline Builder
   │
   ▼
Semantic Search Index
   │
   ▼
Dashboard
```

### Major Components

* Document Extractor
* AI Summarizer
* Entity Detection
* Relationship Engine
* Timeline Generator
* Semantic Search Engine

---

# Request Flow

```text
User

↓

Browser

↓

Flask Route

↓

Authentication

↓

Upload Service

↓

Supabase Storage

↓

Extraction Service

↓

AI Processing

↓

Timeline Builder

↓

Search Index

↓

Database

↓

Dashboard Response

↓

Browser
```

---

# Component Interaction

```text
Frontend
     │
     ▼
Flask Backend
     │
     ├──────── Authentication
     │
     ├──────── Upload Service
     │
     ├──────── AI Pipeline
     │
     ├──────── Timeline Service
     │
     ├──────── Search Service
     │
     └──────── Profile Service
```

---

# AI Pipeline Architecture

```text
Uploaded Document
        │
        ▼
Document Extraction
        │
        ▼
Text Cleaning
        │
        ▼
Chunk Processing
        │
        ▼
AI Model
        │
        ├──────── Summary
        │
        ├──────── Entities
        │
        ├──────── Relationships
        │
        ├──────── Metadata
        │
        └──────── Timeline Events
                  │
                  ▼
        Search Index
                  │
                  ▼
Dashboard
```

---

# Technology Stack

| Layer          | Technology            |
| -------------- | --------------------- |
| Frontend       | HTML, CSS, JavaScript |
| Backend        | Python, Flask         |
| AI             | OpenRouter AI Models  |
| Database       | Relational Database   |
| Cloud Storage  | Supabase              |
| Authentication | Flask Sessions        |
| Deployment     | Railway               |

---

# Design Principles

Veyra follows several architectural principles:

* Modular service-oriented design
* Separation of concerns
* Scalable AI pipeline
* Independent processing services
* Cloud-native storage
* Maintainable codebase
* Lightweight frontend
* Fast request handling
* Extensible architecture

---

# Scalability

The architecture is designed so additional capabilities can be integrated without major structural changes.

Planned extensions include:

* OCR for scanned documents
* Multi-language AI
* Vector databases
* Real-time collaboration
* Mobile applications
* AI recommendations
* Workflow automation
* Enterprise authentication
* Analytics engine
* Plugin ecosystem

---

# Security Architecture

Security is implemented at multiple levels.

* Secure session management
* Protected authentication
* File validation before processing
* Environment-based secrets
* Cloud storage isolation
* Backend-only AI credentials
* Database protection
* Secure API communication

---

# Deployment Architecture

```text
                Railway Cloud
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
   Flask Application         Supabase Storage
         │                         │
         └────────────┬────────────┘
                      ▼
               Database Services
                      │
                      ▼
               OpenRouter AI API
                      │
                      ▼
             AI Document Processing
```

---

# Future Architecture

Future versions of Veyra will evolve toward a microservice-oriented architecture with dedicated services for AI processing, search, analytics, collaboration, and notifications while maintaining the same modular foundation established in the hackathon prototype.
