# 📑 Report Review Lite

English | [中文版](README_CN.md)

**Report Review Lite** is a powerful, AI-driven document analysis and review platform. It leverages state-of-the-art LLMs (Gemini, OpenAI) to automate the process of reviewing complex reports against a set of predefined or custom rules.

---

## 🚀 Key Features

- **🧠 AI-Powered Review Engine**: Automatically analyze documents using advanced AI models to identify inconsistencies, errors, and areas for improvement.
- **📋 Rule Management**: Define and manage complex sets of rules to tailor the review process to specific industry standards or project requirements.
- **📁 Multi-Format Support**: Seamlessly upload and process various document formats (PDF, Docx).
- **📊 Detailed Report Viewer**: High-quality visualization of review results with actionable insights.
- **🕒 History & Trend Analysis**: Track changes over time and analyze historical data to identify recurring patterns.
- **🔍 Comparison Tool**: Compare different versions of reports or different documents side-by-side to highlight variations.
- **🔒 Secure & Scalable**: Built with Supabase for robust authentication and Qdrant for efficient vector search and embeddings.

---

## 📸 Screenshots
![Rule Management](https://media.guil.top/api/public/dl/lhCaevOk?inline=true)
![Document Repository](https://media.guil.top/api/public/dl/WsZLdPtj?inline=true)
![Review Results](https://media.guil.top/api/public/dl/jQ0ALZSz?inline=true)
![Comparison Analysis](https://media.guil.top/api/public/dl/eVRni-LS?inline=true)

---

## 🛠️ Tech Stack

### 🎨 Frontend
- **Framework**: [React](https://reactjs.org/) + [Vite](https://vitejs.dev/)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **State Management**: React Context & Hooks

### ⚙️ Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **DB & Auth**: [Supabase](https://supabase.com/) (PostgreSQL)
- **ORM**: [SQLModel](https://sqlmodel.tiangolo.com/)
- **AI Integrations**: [LangChain](https://www.langchain.com/), [Google Gemini](https://ai.google.dev/), [OpenAI](https://openai.com/)
- **Vector DB**: [Qdrant](https://qdrant.tech/)
- **Object Storage**: [MinIO](https://min.io/)

---

## 🔧 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Docker (optional, for local infrastructure)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/report_review_lite.git
cd report_review_lite
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
# Set up your .env file based on .env.example
uvicorn app.main:app --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
# Set GEMINI_API_KEY in .env.local
npm run dev
```

---

## 📂 Project Structure

```
├── backend/            # FastAPI Backend
│   ├── app/            # Core logic, API routers, models, services
│   ├── alembic/        # Database migrations
│   └── tests/          # Backend tests
├── frontend/           # React Frontend
│   ├── components/     # UI Components
│   ├── contexts/       # React Contexts
│   ├── hooks/          # Custom Hooks
│   └── services/       # API integration services
├── data/               # Persistent data (local)
└── docker-compose.yml  # Infrastructure as Code
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
