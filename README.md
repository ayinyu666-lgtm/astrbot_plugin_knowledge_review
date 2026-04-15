# astrbot_plugin_knowledge_review — 知识候选审核中心

> 候选知识治理与发布插件 —— 收集来自 Memorix 等记忆插件的候选知识，AI 自动分类，人工审核后自动发布到 AstrBot 知识库（RAG）。  
> 内置 WebUI 审核面板，支持标准 REST API 对接任意第三方插件。

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 📥 候选收集 | 通过 REST API 接收来自任意插件（Memorix、Self-Learning 等）的候选知识 |
| 🤖 AI 自动分类 | 可选启用 AI 分类（6 种业务知识类型），支持回退链和启发式分类 |
| 🔍 人工审核 | WebUI 面板可浏览、批准、驳回、编辑候选知识 |
| 📤 一键发布 | 审核通过的知识自动发布到 AstrBot 内置知识库（RAG） |
| 📊 审计日志 | 完整的审核/发布操作记录 |
| 🔗 Provider 回退链 | AI 分类支持多 provider 回退，主模型不可用时自动切换 |
| 🌐 标准 REST API | 便于第三方插件和外部系统集成 |

---

## 前置条件

1. **AstrBot ≥ 4.16**
2. **已安装 `astrbot_plugin_knowledge_base` 插件**（用于发布到 RAG 知识库）
3. *（可选）* 配置一个对话模型 provider（用于 AI 自动分类功能）
4. *（可选）* 如果使用 Docker 部署，需要在 `docker-compose.yml` 中映射 WebUI 端口（默认 8095）

### Docker 端口映射

如果 AstrBot 运行在 Docker 中，需要在 `docker-compose.yml` 的 `ports` 段添加 WebUI 端口：

```yaml
ports:
  - "6185:6185"
  - "8095:8095"   # 知识审核 WebUI
```

修改后执行：
```bash
docker compose up -d --force-recreate
```

---

## 安装

在 AstrBot 管理面板 → **插件** → 搜索 `knowledge_review` → 安装

或手动克隆到插件目录：

```bash
cd <AstrBot数据目录>/plugins/
git clone https://github.com/ayinyu666-lgtm/astrbot_plugin_knowledge_review.git
```

安装后重启 AstrBot 或在管理面板点击「重载插件」。

---

## 配置说明

安装后，在管理面板 → **插件** → 找到 **知识候选审核中心** → 点击 ⚙️ 齿轮图标。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `webui_port` | int | `8095` | 审核 WebUI 端口 |
| `webui_host` | string | `0.0.0.0` | WebUI 绑定地址（`0.0.0.0` 允许外部访问） |
| `astr_base_url` | string | `http://localhost:6185` | AstrBot HTTP API 地址 |
| `astr_token` | string | `""` | AstrBot API Token（如已启用鉴权） |
| `auto_classify` | bool | `true` | 候选进入后是否自动调用 AI 分类 |
| `gate_provider_id` | string | `""` | AI 分类使用的 provider ID，留空使用默认 |
| `fallback_provider_ids` | list | `[]` | 回退 provider ID 列表，按优先级排列 |

### Provider 回退链

AI 分类按以下优先级获取模型：

1. `gate_provider_id` — 用户指定的首选分类模型
2. `fallback_provider_ids` — 回退列表中逐个尝试
3. 启发式分类（无 LLM 时的规则匹配兜底）

---

## 使用方法

### 1. WebUI 审核面板

启动后访问 `http://<你的服务器IP>:8095/`

面板功能：
- 查看所有候选知识列表（按状态过滤）
- 查看候选详情（原始文本、AI 分类结果、来源信息）
- 批准 / 驳回 / 编辑后批准
- 选择目标知识库并一键发布
- 查看审核日志和发布记录

### 2. 聊天命令

| 命令 | 说明 |
|------|------|
| `/kr_status` | 显示审核中心状态（各状态候选数量 + WebUI 地址） |

### 3. REST API

外部插件可通过 HTTP POST 向审核中心提交候选知识：

```
POST http://<host>:8095/api/candidates/ingest
Content-Type: application/json

{
  "text": "候选知识内容",
  "source_plugin": "astrbot_plugin_memorix",
  "session": "session_id_xxx",
  "user": "user_123",
  "metadata": {"custom_key": "value"}
}
```

**批量提交：**

```
POST http://<host>:8095/api/candidates/ingest/batch
Content-Type: application/json

{
  "items": [
    {"text": "知识1", "source_plugin": "memorix"},
    {"text": "知识2", "source_plugin": "self_learning"}
  ]
}
```

**其他 API 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/candidates` | 列出候选知识（支持 `?status=xxx&limit=N` 参数） |
| `GET` | `/api/candidates/{id}` | 获取候选详情 |
| `POST` | `/api/candidates/{id}/approve` | 批准候选 |
| `POST` | `/api/candidates/{id}/reject` | 驳回候选 |
| `POST` | `/api/candidates/{id}/publish` | 发布到知识库 |
| `GET` | `/api/kbs` | 列出可用的 AstrBot 知识库 |
| `GET` | `/api/logs/publish` | 查看发布日志 |

---

## 业务知识类型

插件支持 6 种业务知识类型，AI 分类器会自动识别：

| 类型标识 | 中文名 | 说明 | 冲突策略 |
|---------|--------|------|----------|
| `faq_card` | 问答卡片 | 高频问答，含问题和解答 | 替换 |
| `rule_entry` | 规则条目 | 约束/禁止/规定 | 替换 |
| `procedure` | 操作流程 | 步骤型操作指南 | 替换 |
| `versioned_fact` | 版本化事实 | 带版本条件的事实 | 共存 |
| `entity_profile` | 实体档案 | 对象/人物资料卡 | 合并 |
| `config_item` | 配置项 | 系统配置参数说明 | 替换 |

---

## 与其他插件的协作

### Memorix 插件
Memorix 可通过 HTTP POST 到 `/api/candidates/ingest` 提交候选知识。设置 `source_plugin` 为 `astrbot_plugin_memorix`，审核面板中可按来源过滤。

### Self-Learning 插件
Self-Learning 学习到的新知识可通过相同的 REST API 提交审核。

### Knowledge Base 插件
审核通过的知识通过 AstrBot 的 KB API（`/api/kb/document/import`）发布到知识库。需要先在 AstrBot 管理面板中创建至少一个知识库。

### 任意第三方插件
只要能发送 HTTP POST 请求即可接入，无需任何特殊依赖。

---

## 项目结构

```
astrbot_plugin_knowledge_review/
├── main.py                      # 插件入口
├── metadata.yaml                # 插件元数据
├── _conf_schema.json            # 配置 schema
├── README.md                    # 本文件
├── services/
│   ├── candidate_ingest_service.py  # 候选摄取服务
│   ├── classifier_service.py        # AI 分类服务
│   ├── review_service.py            # 审核服务
│   └── publish_service.py           # 发布服务
├── webui/
│   └── server.py                # WebUI HTTP 服务
├── storage/
│   ├── models.py                # 数据模型
│   └── review_store.py          # SQLite 存储层
├── knowledge_types/
│   ├── schemas.py               # 业务知识类型定义
│   ├── registry.py              # 类型注册表
│   ├── validators.py            # Schema 校验器
│   ├── change_resolution.py     # 变更冲突解析
│   └── renderers.py             # 知识渲染器
└── integrations/
    ├── astr_kb_client.py        # AstrBot KB API 客户端
    └── memorix_bridge.py        # Memorix 桥接工具
```

---

## 常见问题

**Q: WebUI 打不开？**  
A: 检查端口是否被占用，Docker 部署需要映射端口。查看 AstrBot 日志中 `[knowledge_review]` 相关输出。

**Q: AI 分类不生效？**  
A: 确认 `auto_classify` 已开启，且 `gate_provider_id` 指向一个有效的 provider。如果 provider 不可用，会退回启发式分类。

**Q: 发布到知识库失败？**  
A: 确认 `astr_base_url` 配置正确，且 AstrBot 内置知识库已创建。检查发布日志中的错误信息。

**Q: 如何对接我自己的插件？**  
A: 向 `http://<host>:8095/api/candidates/ingest` 发送 POST 请求即可，格式见上方 REST API 部分。

---

## License

MIT

## ⚙️ 核心前置与环境要求 (Prerequisites)
1. **AstrBot 核心版本**：>= 4.16
2. **联动依赖**：必须预先安装官方的 `astrbot_plugin_knowledge_base` 插件。本审核中心负责通过 AstrBot 的 KB API (`/api/kb/document/import`) 拦截并发布高质量知识。
3. **网络与部署要求**：
   - 插件内置了一个独立的 WebUI (默认端口 `8095`)。
   - 如果您使用 Docker 部署 AstrBot，**必须在 `docker-compose.yml` 中映射端口 `8095:8095`**。
4. **无需修改核心代码**：纯插件架构下载即用，安装后可通过插件面板动态开启或关闭 AI 自动 QA 提取等功能。
