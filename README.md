<div align="center">

# 🧪 TestAI — AI驱动的测试用例生成平台

[![Streamlit App](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://ailobao.streamlit.app/)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-V4%20Flash-blue?style=for-the-badge)]()
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain)]()
[![License](https://img.shields.io/github/license/ailobao/testcase_agent?style=for-the-badge)]()

**四智能体架构 · 混合策略生成 · 双模型评估闭环**

👉 [在线体验](https://ailobao.streamlit.app/) · [问题反馈](https://github.com/ailobao/testcase_agent/issues)

</div>

---

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [功能特性](#功能特性)
- [效果数据](#效果数据)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)

---

## 概述

TestAI 是一个基于大模型的测试用例自动生成平台，覆盖从 **测试点分析 → 用例生成 → 质量评估** 的全流程。

核心思路：**不是让 AI 替代测试工程师，而是让 AI 处理重复性高、模板化的测试设计工作，工程师专注于需要业务判断的深度场景。**

### 解决的核心问题

| 问题 | 方案 |
|------|------|
| 手工设计用例慢（1-2天/模块） | AI 生成 3-5 分钟/模块 |
| 边界场景容易遗漏 | 混合策略：AI 做深度 + 固定策略兜底模板场景 |
| 用例质量不稳定、无法量化 | DeepEval + LLM Judge 双评估体系闭环 |

---

## 架构设计

```
用户操作 (Streamlit UI)
    │
    ▼
四大 Agent ─── 继承 BaseAgent（公共能力：LLM调用、缓存、JSON解析、去重）
    │
    ├── TestPointAgent    → Markdown 树形测试点（XMind 兼容）
    ├── APITestAgent      → 接口用例 Excel + JSON + Pytest 脚本
    ├── ManualTestAgent   → 手工用例 Excel（动态字段适配）
    └── AITestAgent       → AI 系统用例（5维度并发生成）
    │
Core 层
    ├── llm_client.py     → 统一 LLM 调用（单例 + 缓存 + 超时保护）
    ├── prompt_loader.py  → 提示词管理（YAML 集中存储）
    └── logger.py         → 日志 + 追踪 ID
    │
评估体系
    ├── DeepEval GEval    → 结构化评分（格式/断言/边界/场景/参数）
    └── Qwen 3.7 Max Judge → 维度评分（5-6 维度，22 模块）
```

### 接口用例生成流程（核心亮点）

```
APITestAgent.generate()
    │
    ├── Step 1: AI 业务用例生成
    │      → 从 prompts.yaml 读模板 + 业务规则
    │      → 调用 DeepSeek V4 Flash
    │      → 解析 JSON（11 种降级策略）
    │
    ├── Step 2: FixedPatternStrategy 补充
    │      ├── Token 异常 × 4（过期/错误/空/缺失）
    │      ├── 参数缺失 × N（每个必填字段去掉）
    │      └── 参数为空 × N（每个必填字段置空）
    │      └── BUSINESS_DEFAULTS（50+ 字段语义化默认值）
    │
    └── Step 3: 去重 + 重编号 + 确保正向用例存在
```

**为什么用混合策略：** 纯 AI 生成会遗漏 Token 异常这类模板场景；纯固定策略覆盖不了需要业务理解的深度场景。两者互补。

---

## 功能特性

### 四模式

| 模式 | 输入 → 输出 | 适用场景 |
|------|------------|---------|
| **测试点分析** | 项目/模块 → Markdown 测试点树 | 需求评审阶段，快速搭建测试框架 |
| **手工用例** | 项目/模块/规则 → Excel | 功能测试，动态字段适配各模块 |
| **接口用例** | 接口规则 → Excel + JSON + Pytest | 接口自动化，含 Token 管理 |
| **AI 系统测试** | 项目描述 → 分析报告 + 用例 Excel | 大模型/AI 应用专项测试 |

### 关键技术设计

- **混合策略生成**：AI 业务生成 + FixedPattern 固定模式兜底
- **11 层 JSON 降级解析**：模型输出不规范时的逐级兜底
- **四级字段解析**：DB 配置 > 业务规则正则 > 模块名映射 > 默认值
- **双缓存 LLM 调用**：内存 + 磁盘两级缓存，24 小时 TTL
- **生成-评估模型解耦**：生成用 DeepSeek V4 Flash，评估用 Qwen 3.7 Max
- **业务字段保底值**：50+ 常见字段的语义化默认值

---

## 效果数据

### 评估结果（2025.06）

| 评估类型 | 模块数 | 平均评分 | 评分维度 |
|---------|--------|---------|---------|
| **手工用例** | 10 模块 | **77.1%** | 格式规范/规则遵循/场景覆盖/可执行性/数据合理 |
| **AI 系统测试** | 8 模块 | **69.6%** | 功能/准确性/鲁棒性/用户体验/安全/分析报告 |

### 效率对比

| 方式 | 耗时 | 覆盖率 | 成本 |
|------|------|--------|------|
| 人工设计 | 1-2 天/模块 | 60-70% | 高 |
| TestAI | 3-5 分钟/模块 | 显著提升 | 降低 80%+ |

### 评分维度说明

**手工用例 5 维度**
| 维度 | 说明 |
|------|------|
| 格式规范性 | 用例结构是否完整、字段是否齐全 |
| 规则遵循度 | 是否遵循业务规则约束 |
| 场景覆盖度 | 正向/反向/异常场景覆盖是否全面 |
| 可执行性 | 测试步骤是否清晰可执行 |
| 数据合理性 | 测试数据是否合理、有意义 |

**AI 系统测试 6 维度**
| 维度 | 说明 |
|------|------|
| 功能测试质量 | AI 功能完整性测试 |
| 准确性测试质量 | 输出准确性验证 |
| 鲁棒性测试质量 | 异常输入处理能力 |
| 用户体验测试质量 | 交互体验、响应质量 |
| 安全性测试质量 | 注入、越狱、隐私保护 |
| 分析报告质量 | 四维分析深度 |

---

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **生成模型** | DeepSeek V4 Flash | 通过 DeepSeek 官方 API 调用 |
| **评估模型** | Qwen 3.7 Max | 通过阿里百炼 DashScope 调用 |
| **LLM 框架** | LangChain (ChatOpenAI) | 统一调用接口，同步/异步 |
| **评估框架** | DeepEval GEval | 结构化评分 |
| **前端** | Streamlit | 四页面 Web 应用 |
| **数据存储** | SQLite | 模块规则持久化 |
| **数据处理** | Pandas, OpenPyXL | Excel 导出与美化 |
| **部署** | Streamlit Community Cloud | 公网可访问 |

---

## 快速开始

### 在线体验

无需安装，直接访问：[https://ailobao.streamlit.app/](https://ailobao.streamlit.app/)

### 本地运行

```bash
# 1. 克隆
git clone https://github.com/ailobao/testcase_agent.git
cd testcase_agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动
streamlit run src/ui/app.py
```

### 环境变量配置

```ini
# 生成模型（DeepSeek 官方 API）
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=sk-your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/v1

# 评估模型（阿里百炼）
DASHSCOPE_API_KEY=sk-your-dashscope-key
JUDGE_MODEL=qwen3.7-max
```

---

## 项目结构

```
src/
├── agents/
│   ├── base_agent.py           # 基类（LLM调用/缓存/JSON解析/去重）
│   ├── api_agent.py            # 接口用例生成 ⭐
│   ├── manual_agent.py         # 手工用例生成
│   ├── ai_agent.py             # AI 系统测试生成
│   └── testpoint_agent.py      # 测试点分析
├── core/
│   ├── llm_client.py           # 统一 LLM 调用 ⭐
│   ├── prompt_loader.py        # 提示词加载
│   └── logger.py               # 日志
├── strategies/
│   └── fixed_pattern_strategy.py  # 固定模式生成 ⭐
├── utils/
│   ├── json_parser.py          # 11种JSON解析策略
│   ├── llm_cache.py            # LLM 缓存
│   ├── excel_exporter.py       # Excel 导出
│   └── common_tools.py         # 公共工具
├── config/
│   └── settings.py             # 全局配置
└── ui/
    ├── app.py                  # Streamlit 主入口
    └── pages/                  # 四个页面

evaluation/
├── common.py                   # 评估基类
├── evaluate_ai_agent.py        # AI 用例评估（8模块）
├── evaluate_manual_agent.py    # 手工用例评估（10模块）
└── evaluate_json_with_feedback.py  # JSON DeepEval 评估

prompts.yaml                    # 全部 LLM 提示词
```

---

## 质量评估闭环

```
生成用例 → LLM Judge 评分 → 分析薄弱维度 → 优化 Prompt → 重新生成 → 重新评分
                                                                        │
                                                                   ↑ 循环直到满意 ↓
```

评估体系由两套组成：

1. **DeepEval GEval**：对接口用例 JSON 做结构化评分（格式正确性、断言规范性、边界值覆盖、场景覆盖、参数有效性）
2. **LLM Judge（Qwen 3.7 Max）**：对手工用例和 AI 用例做维度评分，支持 5-6 个评估维度

---

## License

[MIT](LICENSE)

<div align="center">

**如果这个项目对你有帮助，欢迎 Star ⭐**

</div>
