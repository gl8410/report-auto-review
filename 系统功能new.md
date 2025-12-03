
# ADS系统原型需求规格说明书

## 1\. 功能模块需求详解

### 1.1 规则管理模块 (Rule Management)

**功能描述：**
该模块用于维护审查的“标尺”。核心是将非结构化的法规/规范文本转化为系统可执行的原子化规则。

  * **规则组管理**：支持创建、编辑、删除规则组（如“防洪评价导则2025版”）。
  * **智能解析导入**：支持上传文本文件（.txt/.md），系统调用LLM自动识别条文，将其拆解为原子规则（包含条文号、内容、强条标识等），存入当前规则组。
  * **规则CRUD**：解析后的规则以列表展示，支持人工校对、修改、新增或删除单条规则。

**数据结构 (Relational DB & Memory):**

  * **RuleGroup (规则组)**:
      * `id`: UUID
      * `name`: 组名 (如：某某导则)
      * `description`: 描述
      * `created_at`: 创建时间
  * **Rule (原子规则)**:
      * `id`: UUID
      * `group_id`: 关联的规则组ID
      * `standard_name`: 来源标准名称
      * `clause_number`: 条文号 (如 3.1.2)
      * `content`: 规则具体内容 (自然语言)
      * `review_type`: 审查类型 (内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性)六种之一，由llm自行判断
      * `importance`: 重要性 (一般/中等/重要)，由llm自行判断

### 1.2 文档管理模块 (Document Management)

**功能描述：**
该模块不仅是文件的仓库，更是**数据结构化（ETL）的入口**。

  * **文件上传**：支持 `.doc`, `.docx`, `.pdf` 格式上传。
  * **自动结构化 (Ingestion)**：上传成功后，**自动触发后台异步任务**。该任务包含：
    1.  **解析**：提取文本。
    2.  **切片与向量化**：存入 Chroma (向量库)。
  * **文档列表与状态**：展示文档列表及处理状态（上传中 -\> 解析中 -\> 向量完成/失败）。只有状态为“结构化完成”的文档才能被用于审查。

**数据结构 (Relational DB):**

  * **Document (文档)**:
      * `id`: UUID
      * `filename`: 原始文件名
      * `storage_path`: 存储路径
      * `status`: 枚举 (UPLOADED, PARSING, INDEXED, FAILED)
      * `meta_info`: JSON (包含项目名称、项目类型等初步提取的元数据)
      * `upload_time`: 上传时间

### 1.3 文档审查模块 (Review Execution)

**功能描述：**
该模块是业务的核心触发点，连接规则与文档。

  * **任务创建**：用户选择 **一个文档** 和 **一个规则组**，发起审查任务。
  * **异步执行**：后端接收请求后立即返回 `task_id`，在后台启动双源对比审查流程（检索 -\> LLM比对）。
  * **进度监控**：前端轮询或通过WebSocket接收任务进度（如：正在审查第N条规则）。

**数据结构 (Relational DB):**

  * **ReviewTask (审查任务)**:
      * `id`: UUID
      * `document_id`: 关联文档
      * `rule_group_id`: 关联规则组
      * `status`: 枚举 (PENDING, PROCESSING, COMPLETED, FAILED)
      * `progress`: 进度百分比 (0-100)
      * `start_time`: 开始时间
      * `end_time`: 结束时间

### 1.4 审查结果管理模块 (Result Analysis)

**功能描述：**
该模块用于展示和输出最终的审查产物。

  * **结果总览**：查看任务的总体结论（通过率、风险等级）。
  * **明细列表**：展示每一条规则的审查详情，包括：审查结论（通过/不通过/不适用）、LLM给出的理由、引用的原文片段（Evidence）。不同结论用不同颜色表示
  * **报告导出**：
      * **Excel/JSON导出**：结构化数据下载。
      * **智能PDF报告**：调用LLM基于审查明细生成一份包含综述、问题汇总、修改建议的正式PDF报告。

**数据结构 (Relational DB & NoSQL):**

  * **ReviewResultItem (单条结果)**:
      * `id`: UUID
      * `task_id`: 关联任务
      * `rule_id`: 关联规则
      * `result_code`: 枚举 (PASS, REJECT, MANUAL\_CHECK)
      * `reasoning`: LLM生成的判断理由
      * `evidence`: 引用原文片段 (及其在文档中的位置/页码)
      * `suggestion`: 修改建议

-----

## 2\. 整体架构补充设计

### 2.1 系统业务流程 (Process Flow)

1.  **准备阶段 (Setup)**:
      * 用户上传《防洪评价导则.txt》。
      * 后端调用 LLM 将文本拆解为 50 条原子规则 -\> 存入  后端数据库。
2.  **入库阶段 (Ingestion)**:
      * 用户上传《某项目防洪评价报告.docx》。
      * 后端 (FastAPI) 存文件至 MinIO -\> 触发 Celery/BackgroundTasks。
      * Worker 解析文档 -\> 文本块存 Chroma  -\> 更新文档状态为 `INDEXED`。
3.  **审查阶段 (Execution)**:
      * 用户选择文档 + 规则组 -\> 点击“开始审查”。
      * Worker 遍历规则组中的规则 -\> 针对每条规则生成检索意图 -\> **向量检索 (Chroma )** 获取上下文 -\> 调用 LLM 进行比对 -\> 写入 `ReviewResultItem` 表。
4.  **产出阶段 (Output)**:
      * 用户查看列表 -\> 点击“生成报告” -\> 后端聚合所有 `ReviewResultItem` -\> LLM 生成综述 -\> 渲染 PDF 下载。

### 2.2 Pydantic 模型输出结构化

为了保证 LLM 输出稳定，用Pydantic 开展“规则解析”和“审查结果”


### 2.3 前后端技术栈 (Tech Stack)

针对快速原型开发，建议采用以下技术栈，兼顾开发效率与企业级展示效果：

  * **前端 (Frontend)**:

      * **框架**: **Vue 3** (Composition API) + **Vite**
      * **UI库**: **Element Plus** (组件丰富，适合管理后台)
      * **HTTP**: Axios
      * **主要页面**: 规则库视图、文档上传组件、审查Dashboard、报告预览页。

  * **后端 (Backend)**:

      * **框架**: **FastAPI** (Python) 
      * **ORM**: **SQLModel** (结合了 Pydantic 和 SQLAlchemy，开发极快) 或 SQLAlchemy。
      * **异步任务**: **FastAPI BackgroundTasks** (原型阶段够用) 或 **Celery + Redis** (更稳定)。
      * **LLM框架**: **LangChain** 或 **LlamaIndex** (用于编排)。

  * **数据基础设施 (Infrastructure)**:

      * **关系型库**:  **PostgreSQL** (建议，支持JSONB)。
      * **向量库**: **Chroma** (轻量级，本地文件模式)。
      * **文件存储**: 原型阶段直接存本地 `uploads/` 目录即可。

### 2.4 前后端文件结构

基于你提供的后端结构，融合前端结构如下：

```text
ADS-Project/
├── backend/                  # 后端工程 (FastAPI)
│   ├── main.py               # 入口
│   ├── .env                  # 环境变量 (Keys, DB URL)
│   ├── api/                  # 接口层
│   │   ├── routers/
│   │   │   ├── rules.py      # 规则管理接口
│   │   │   ├── docs.py       # 文档上传与结构化接口
│   │   │   └── reviews.py    # 审查执行与结果接口
│   ├── core/
│   │   ├── database.py       # SQLModel/Postgres连接
│   │   ├── config.py
│   │   └── models.py         # DB Table定义 (ReviewTask, Document等)
│   ├── schemas/              # Pydantic模型 (请求/响应体)
│   │   ├── rule_schema.py
│   │   └── review_schema.py
│   ├── services/             # 业务逻辑
│   │   ├── parser.py         # 文档解析
│   │   ├── ingestion.py      # 写入Neo4j/Chroma逻辑
│   │   └── reviewer.py       # LLM审查逻辑
│   └── workflows/            # LangChain/Agent编排
│
├── frontend/                 # 前端工程 (Vue3 + Vite)
│   ├── src/
│   │   ├── api/              # Axios请求封装
│   │   ├── components/       # 公共组件 (Upload, StatusBadge)
│   │   ├── views/
│   │   │   ├── RuleManager.vue    # 规则管理页
│   │   │   ├── DocManager.vue     # 文档管理页
│   │   │   ├── ReviewLauncher.vue # 发起审查页
│   │   │   └── ResultDetail.vue   # 结果详情与报告页
│   │   ├── router/
│   │   └── store/            # Pinia状态管理
│   ├── package.json
│   └── vite.config.ts
│
└── docker-compose.yml        # 编排 Neo4j, Postgres, Chroma
```

### 2.5 快速启动建议

为了在极短时间内完成原型：


1.  **异步简化**：直接使用 `FastAPI.BackgroundTasks` 处理文档解析和审查，暂不引入 Redis/Celery，减少部署复杂度。
2.  **UI简化**：前端直接使用 Element Plus 的 `el-table`, `el-upload`, `el-descriptions` 组件，不要纠结样式定制。