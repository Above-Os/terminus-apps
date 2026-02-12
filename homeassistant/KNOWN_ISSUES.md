# 已知问题 (Known Issues)

## 浏览器卡死问题 (Browser Freeze Issue)

### 问题描述
在连接米家（Xiaomi）集成后，浏览器在米家页面停留一段时间后会完全卡死，100% 复现。

**重要说明**：这是**前端 JavaScript 错误**导致的浏览器崩溃，与容器资源无关（容器内存使用正常，仅几百MB）。

### 错误日志分析

#### 1. Leaflet 地图组件错误（主要原因）
```
TypeError: Cannot read properties of undefined (reading '_leaflet_pos')
_leaflet_pos (node_modules/leaflet/src/dom/DomUtil.js:247:11)
getPosition (node_modules/leaflet/src/map/Map.js:1488:9)
```
这是导致浏览器卡死的**主要原因**。Leaflet 地图库在 `xiaomi_home` 组件中尝试访问已被移除或未初始化的 DOM 元素位置信息，导致 JavaScript 错误循环，最终使浏览器崩溃。

**问题根源**：
- `xiaomi_home` 自定义组件在渲染地图时，地图容器 DOM 元素可能被过早移除
- 组件卸载时没有正确清理 Leaflet 地图实例
- 可能存在多个地图实例同时操作同一个 DOM 元素

#### 2. xiaomi_home 自定义组件问题
```
ERROR (MainThread) [custom_components.xiaomi_home.config_flow] task_oauth exception, Flow aborted: already_in_progress
```
OAuth 流程冲突，可能存在多个认证流程同时运行。

#### 3. 未关闭的客户端会话
```
ERROR (MainThread) [homeassistant] Error doing job: Unclosed client session
```
后端资源泄漏问题，但不会直接导致浏览器崩溃。

### 解决方案

#### 浏览器端临时解决方案（推荐）

1. **使用浏览器开发者工具禁用 JavaScript 错误**
   - 打开浏览器开发者工具（F12）
   - 在 Console 标签页中，点击设置图标
   - 勾选 "Disable JavaScript" 或添加错误过滤器
   - 注意：这可能会影响其他功能

2. **清除浏览器缓存和存储**
   ```javascript
   // 在浏览器控制台执行
   localStorage.clear();
   sessionStorage.clear();
   // 然后清除浏览器缓存
   ```

3. **使用无痕/隐私模式**
   - 在无痕模式下访问，避免缓存和扩展插件干扰

4. **避免停留在米家页面**
   - 配置完成后立即离开米家页面
   - 不要长时间停留在包含地图的页面

#### 组件端解决方案

1. **禁用 xiaomi_home 自定义组件中的地图功能**
   - 在 Home Assistant 配置中查找 `xiaomi_home` 组件配置
   - 如果支持，禁用地图相关功能

2. **更新或替换自定义组件**
   - 检查 `xiaomi_home` 组件是否有更新版本修复此问题
   - 考虑使用 Home Assistant 官方的 Xiaomi 集成替代
   - 向组件开发者报告此问题：https://github.com/（组件仓库地址）

3. **临时禁用 xiaomi_home 组件**
   - 在 `configuration.yaml` 中注释掉或移除 `xiaomi_home` 配置
   - 使用其他方式管理小米设备

#### 前端代码修复建议（需要修改组件代码）

如果能够访问 `xiaomi_home` 组件的源代码，建议修复：

1. **确保地图容器存在**
   ```javascript
   // 在初始化地图前检查容器
   if (!this.mapContainer || !this.mapContainer.parentElement) {
     return; // 容器不存在，不初始化地图
   }
   ```

2. **正确清理地图实例**
   ```javascript
   // 组件卸载时
   disconnectedCallback() {
     if (this.map) {
       this.map.remove(); // 正确清理 Leaflet 实例
       this.map = null;
     }
   }
   ```

3. **添加错误处理**
   ```javascript
   try {
     // 地图操作
   } catch (error) {
     console.warn('Map operation failed:', error);
     // 不抛出错误，避免浏览器崩溃
   }
   ```

### 已实施的缓解措施

1. **优化 nginx 配置**：增加缓冲区大小以改善前端资源加载
2. **添加安全头**：改善前端稳定性
3. **增强日志记录**：为 xiaomi_home 组件启用调试日志，便于排查问题

### 相关链接
- [Home Assistant 故障排除文档](https://www.home-assistant.io/docs/configuration/troubleshooting/)
- [前端问题 FAQ](https://www.home-assistant.io/faq/browser/)
- [Leaflet 文档](https://leafletjs.com/reference.html)

