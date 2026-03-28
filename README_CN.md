# 📑 Report Review Lite

[English](README.md) | 中文版

**Report Review Lite** 是一个强大的、由 AI 驱动的文档分析和评审平台。它利用最先进的 LLM（Gemini、OpenAI）来自动执行针对预定义或自定义规则集的复杂报告评审过程。

---

## 🚀 核心特性

- **🧠 AI 驱动的评审引擎**: 使用先进的 AI 模型自动分析文档，识别不一致、错误和改进区域。
- **📋 规则管理**: 定义和管理复杂的规则集，使评审过程适应特定的行业标准或项目要求。
- **📁 多格式支持**: 无缝上传和处理各种文档格式（PDF、Docx）。
- **📊 详细报告查看器**: 评审结果的高质量可视化，提供可操作的见解。
- **🕒 历史与趋势分析**: 跟踪随时间的变化，分析历史数据以识别重复出现的模式。
- **🔍 比较工具**: 并排比较不同版本的报告或不同文档，以突出差异。
- **🔒 安全且可扩展**: 使用 Supabase 进行强大的身份验证，使用 Qdrant 进行高效的向量搜索和嵌入。

---

##  图片
![规则管理](https://media.guil.top/api/public/dl/lhCaevOk?inline=true)
![文档仓库](https://media.guil.top/api/public/dl/WsZLdPtj?inline=true)
![审查结果](https://media.guil.top/api/public/dl/jQ0ALZSz?inline=true)
![差异对比](https://media.guil.top/api/public/dl/eVRni-LS?inline=true)



## 🛠️ 技术栈

### 前端
- **框架**: [React](https://reactjs.org/) + [Vite](https://vitejs.dev/)
- **语言**: [TypeScript](https://www.typescriptlang.org/)
- **样式**: [Tailwind CSS](https://tailwindcss.com/)
- **状态管理**: React Context & Hooks

### 后端
- **框架**: [FastAPI](https://fastapi.tiangolo.com/)
- **数据库与认证**: [Supabase](https://supabase.com/) (PostgreSQL)
- **ORM**: [SQLModel](https://sqlmodel.tiangolo.com/)
- **AI 集成**: [LangChain](https://www.langchain.com/), [Google Gemini](https://ai.google.dev/), [OpenAI](https://openai.com/)
- **向量数据库**: [Qdrant](https://qdrant.tech/)
- **对象存储**: [MinIO](https://min.io/)

---

## 🔧 快速入门

### 前提条件
- Node.js (v18+)
- Python (3.10+)
- Docker (可选，用于本地基础架构)

### 1. 克隆仓库
```bash
git clone https://github.com/your-username/report_review_lite.git
cd report_review_lite
```

### 2. 后端设置
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows 系统: venv\Scripts\activate
pip install -r requirements.txt
# 根据 .env.example 设置您的 .env 文件
uvicorn app.main:app --reload
```

### 3. 前端设置
```bash
cd frontend
npm install
# 在 .env.local 中设置 GEMINI_API_KEY
npm run dev
```

---

## 📂 项目结构

```
├── backend/            # FastAPI 后端
│   ├── app/            # 核心逻辑、API 路由、模型、服务
│   ├── alembic/        # 数据库迁移
│   └── tests/          # 后端测试
├── frontend/           # React 前端
│   ├── components/     # UI 组件
│   ├── contexts/       # React 上下文
│   ├── hooks/          # 自定义 Hooks
│   └── services/       # API 集成服务
├── data/               # 持久化数据 (本地)
└── docker-compose.yml  # 基础设施即代码
```

---

## 🤝 贡献

欢迎贡献！请随意提交 Pull Request。

## 📄 许可证

本项目在 MIT 许可证下获得许可 - 详见 [LICENSE](LICENSE) 文件。
