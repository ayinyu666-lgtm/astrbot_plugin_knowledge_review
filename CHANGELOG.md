# Changelog / 更新日志

## v0.4.0

### New Features / 新功能
- **Algorithmic QA pair auto-extraction**: Automatically detects knowledge-worthy QA pairs from group chat and creates candidate records for review. Two detection pathways:
  算法自动提取知识 QA 对，双路径检测：
  - **User-User QA**: Buffers group messages; when one user asks a question and another user provides a substantive answer, creates a candidate.
    用户-用户问答：缓存消息历史，当一个用户的问题被另一个用户实质性回答时生成候选。
  - **User-Bot QA**: When the bot answers a user's question with sufficient information density, creates a candidate.
    用户-Bot问答：当Bot的回复信息密度足够时直接生成候选。
- **New `/kr_status` field**: Shows auto-extraction enabled/disabled status.
  `/kr_status` 新增自动提取状态显示。

### New Config / 新配置项
- `auto_extract_enabled` (bool, default: true): Toggle auto-extraction on/off.
- `extractor_history_size` (int, default: 30): Message buffer size per group.
- `extractor_qa_max_gap_sec` (int, default: 300): Max time gap between Q and A.
- `extractor_min_answer_len` (int, default: 10): Minimum answer length threshold.
- `extractor_cooldown_sec` (int, default: 300): Dedup cooldown for same QA pair.

### Technical / 技术细节
- Algorithmic detection ported from OlivOS Assassin's gatekeeper/runtime_patch: question markers, low-signal filter, uncertainty filter, information density check, keyword extraction.
  算法检测移植自 OlivOS 刺客的守门者/运行时补丁。
- Uses `on_decorating_result` hook — fires when bot sends a response, captures both user question and bot answer without affecting message pipeline wake state.
  使用 `on_decorating_result` 钩子——在 Bot 发送回复时触发，不影响消息管线的唤醒状态。
- SHA-256 dedup with configurable cooldown prevents duplicate candidates.

## v0.3.0

### New Features / 新功能
- **`/kr_providers` command**: List all available AI providers with IDs and models for easy configuration.
  `/kr_providers` 命令：列出所有可用 Provider 及其 ID，方便配置。
- **Startup provider validation**: Logs available providers and warns if configured `gate_provider_id` doesn't exist.
  启动时验证已配置的 Provider 是否存在。
- **Bilingual (CN/EN)**: All config descriptions, hints, commands, and log messages include both Chinese and English.
  中英双语支持：所有配置、命令输出和日志均包含中英文。

### Improvements / 改进
- **Classifier refactored to use AstrBot Context API**: Now uses `context.get_provider_by_id()` + `provider.text_chat()` instead of reading `cmd_config.json` directly and making raw HTTP calls. More robust and maintainable.
  分类服务重构：使用 AstrBot Context API 调用 Provider，不再直接读取配置文件或发起原始 HTTP 请求。
- Removed `aiohttp` dependency for LLM classification (now uses AstrBot's built-in provider layer).
  移除分类服务对 `aiohttp` 的依赖。

## v0.2.0

- Initial release with WebUI review panel, AI classification, heuristic fallback, and AstrBot KB publishing.
