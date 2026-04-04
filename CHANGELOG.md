# Changelog / 更新日志

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
