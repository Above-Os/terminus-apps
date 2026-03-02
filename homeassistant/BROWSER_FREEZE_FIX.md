# 浏览器卡死问题快速修复指南

## 问题确认
- ✅ 容器资源正常（内存仅几百MB）
- ❌ 浏览器完全卡死，无法响应
- 🔍 错误：`TypeError: Cannot read properties of undefined (reading '_leaflet_pos')`

## 立即解决方案

### 方案 1：浏览器端错误捕获（最快）

在浏览器控制台（F12）执行以下代码，可以捕获错误并防止浏览器崩溃：

```javascript
// 添加到浏览器控制台，防止 Leaflet 错误导致浏览器崩溃
window.addEventListener('error', function(e) {
  if (e.message && e.message.includes('_leaflet_pos')) {
    e.preventDefault();
    console.warn('Leaflet map error caught and prevented:', e.message);
    return true;
  }
}, true);

// 捕获未处理的 Promise 拒绝
window.addEventListener('unhandledrejection', function(e) {
  if (e.reason && e.reason.message && e.reason.message.includes('_leaflet_pos')) {
    e.preventDefault();
    console.warn('Leaflet map promise rejection caught:', e.reason);
  }
});
```

### 方案 2：使用浏览器扩展

安装浏览器扩展来阻止特定 JavaScript 错误：
- Chrome: "JavaScript Error Notifier" 或类似扩展
- 配置扩展忽略 Leaflet 相关错误

### 方案 3：修改 Home Assistant 前端（需要访问）

如果可以访问 Home Assistant 的 `custom_components/xiaomi_home` 目录，可以添加错误处理：

在组件的前端代码中添加 try-catch 包装所有 Leaflet 操作。

### 方案 4：禁用地图功能

如果 `xiaomi_home` 组件支持配置，在 `configuration.yaml` 中禁用地图：

```yaml
xiaomi_home:
  # 如果支持，禁用地图功能
  enable_map: false
```

### 方案 5：使用其他浏览器

- 尝试使用不同的浏览器（Chrome、Firefox、Edge）
- 某些浏览器对 JavaScript 错误的处理更宽容

## 长期解决方案

1. **联系组件开发者**
   - 在 `xiaomi_home` 组件的 GitHub 仓库提交 issue
   - 提供完整的错误日志和复现步骤

2. **使用官方集成**
   - 考虑迁移到 Home Assistant 官方的 Xiaomi 集成
   - 官方集成通常更稳定

3. **等待组件更新**
   - 关注组件更新，问题可能在后续版本中修复

## 预防措施

- 配置完成后立即离开米家页面
- 避免长时间停留在包含地图的页面
- 定期清除浏览器缓存
- 使用无痕模式进行配置操作




