# 在 Olares 中使用 Lares 控制 Blender

本文供文档、测试与演示同事使用，说明如何在 Olares 中配置 Blender MCP、验证连接，并通过 Lares 创建和渲染一个完整示例。

## 适用版本

- Olares 1.12.7 或更高版本
- Blender 5.2.2，OAC 0.1.26 或更高版本
- 已安装 Lares

Blender 与 Lares 必须安装在同一台 Olares 上。MCP 连接使用 Olares 内部入口，不需要开放 Blender 的 9876 端口，也不要把 MCP 地址公开到互联网。

## 工作原理

Blender 应用同时提供两个入口：

- **Blender**：浏览器中的 Blender 桌面，端口 3000。
- **Blender MCP**：供 Lares 等 MCP 客户端调用，端口 8765，内部入口，不显示在桌面启动器中。

Lares 通过 MCP 修改的就是浏览器中打开的同一个 Blender 进程和场景。执行成功后，模型、材质、相机和动画会直接出现在当前 Blender 窗口中。

Blender 与 Lares 的容器文件系统彼此隔离。需要跨应用读取的 `.blend`、图片和逐帧序列必须保存到 Blender 的 `/config/Home`，它在 Olares Files 中对应 `Home`。

## 一、安装并启动应用

1. 从 Olares Market 安装 Blender。
2. 从 Olares Market 安装 Lares。
3. 打开 Blender，等待浏览器桌面和默认场景加载完成。
4. 保持 Blender 运行。Lares 调用 MCP 时复用这个 Blender 进程。

如果安装时可以选择计算模式：

- 普通设备选择 **CPU**。
- 有 Intel 核显并希望使用硬件视频编码时选择 **Intel**。
- 有已正确绑定的 NVIDIA GPU 时选择 **NVIDIA**。

计算模式主要影响桌面串流和 Cycles 等工作负载，不影响 MCP 的配置方式。

## 二、在 Lares 中配置 Blender MCP

1. 在 Olares 中找到 Blender 的 **Blender MCP** 内部入口地址。
2. 复制该地址，并在末尾保留或补上 `/mcp`。
3. 打开 **Lares → Settings → MCP**。
4. 新增一个 MCP Server，填写：

   - **Server name**：`blender`
   - **Transport**：`Streamable HTTP`
   - **MCP URL**：复制的 Blender MCP 内部地址，以 `/mcp` 结尾
   - **Headers**：`{}`

5. 保存并启用该 Server。

地址格式类似：

```text
https://<内部入口域名>/mcp
```

请直接复制 Olares 显示的实际内部入口，不要根据应用名手工拼接域名。

## 三、连接冒烟测试

新建一个 Lares 会话，发送：

```text
使用 Blender MCP 检查当前 Blender 场景。
请报告 Blender 版本、当前场景名称、对象总数和对象名称。
不要修改场景。
```

通过标准：

- Lares 调用了 Blender MCP 工具，而不是只返回操作说明。
- 返回的版本为 Blender 5.2.x。
- 默认场景通常能看到 `Camera`、`Cube`、`Light`。
- Blender 页面保持可用，没有新启动第二个独立实例。

如果 Lares 看不到 Blender 工具：

1. 确认 Blender 仍在运行。
2. 确认 MCP Server 已启用。
3. 确认 Transport 为 `Streamable HTTP`。
4. 确认 URL 以 `/mcp` 结尾。
5. 确认使用的是内部入口，而不是 Blender 桌面入口。

## 四、可视化修改测试

连接测试通过后，发送：

```text
使用 Blender MCP 完成以下操作：
1. 清空当前场景。
2. 创建一个蓝色金属立方体和一个红色粗糙球体。
3. 添加地面、相机和两盏灯。
4. 把相机对准两个物体。
5. 保存到 /config/Home/blender-renders/mcp-smoke-test.blend。

请在一次 execute_blender_code 调用中完成，并在最后报告保存路径。
```

通过标准：

- Blender 浏览器窗口中能看到场景变化。
- Olares Files 的 `Home/blender-renders` 中出现 `mcp-smoke-test.blend`。
- Lares 报告的 Olares Drive 路径为：

```text
drive/Home/blender-renders/mcp-smoke-test.blend
```

## 五、完整测试示例：太阳系静帧

下面的提示词已经针对当前 Blender MCP 运行方式做过验证。请完整粘贴，尤其不要删除“已知事实”部分，否则模型可能花大量时间反复探测 Blender API。

```text
使用 Blender MCP 创建并渲染一个太阳系插画。

要求：
- 清空当前场景。
- 在原点创建一个发光的太阳。
- 在 XY 平面放置八颗行星，每颗行星使用独立的圆形轨道。
- 为了在画面中清晰可见，明显夸大行星尺寸；这是一张插画，不要求真实比例。
- 每条轨道使用细而微弱发光的圆环。
- 木星要有横向云带，土星要有由扁平圆环构成的行星环。
- 地球使用蓝色海洋和绿色陆地的程序化材质，并添加月球。
- 使用太阳中心的强点光源和一盏较弱的补光灯。
- 使用程序化星空背景。
- 相机从斜上方拍摄，完整容纳最外侧轨道。
- 输出一张 1600x900 PNG。
- 保存工程到 /config/Home/blender-renders/lares-solar-system.blend。
- 保存图片到 /config/Home/blender-renders/lares-solar-system.png。
- 完成后报告两个 Olares Drive 路径。

整个场景尽量在一次 execute_blender_code 调用中完成。

已知事实，请直接使用，不要重新验证：
- 当前是 Blender 5.2，Eevee 引擎 ID 是 "BLENDER_EEVEE"。
- MCP 脚本不在 Blender 主线程执行，bpy.ops.render.render() 会静默返回但不生成图片。
- 必须在 VIEW_3D 的 temp_override 中，把 region_3d.view_perspective 设为 "CAMERA"，
  把 shading.type 设为 "RENDERED"，然后调用
  bpy.ops.render.opengl(write_still=True, animation=False)。
- 采样数使用 scene.eevee.taa_samples。
- 当前没有可用的合成器，不要创建 compositor 节点或 glare。
- 安全模式已启用：不要导入 os、sys、pathlib，不要调用 dir()、bpy.data.texts 或 bpy.app.timers。
- Blender 保存和 OpenGL 渲染操作会自动创建输出目录。
- /data/workspace、/tmp 和 /dev/shm 不能用于与 Lares 交换文件。
```

预期输出：

```text
drive/Home/blender-renders/lares-solar-system.blend
drive/Home/blender-renders/lares-solar-system.png
```

在 Olares Files 中打开 **Home → blender-renders**，确认工程文件和 PNG 都存在。静帧本身通常只需要数秒；Lares 分析和生成脚本所需时间取决于使用的模型。

## 六、追加公转动画

在太阳系静帧确认无误后，在同一个 Lares 会话中继续发送：

```text
继续使用当前 Blender 场景制作公转动画：

- 设置为 72 帧、24 fps、960x540。
- 八颗行星都围绕太阳公转，同时绕各自轴线自转。
- 内侧行星比外侧行星转得快。
- 每颗行星在 72 帧内转整数圈，使动画可以无缝循环。
- 每颗行星挂在原点处的 Empty 下，通过 Empty 的 Z 轴旋转完成公转。
- 使用基于 frame 的 scripted driver，保持匀速，不要逐帧手工创建关键帧。
- 使用 bpy.ops.render.opengl(animation=True) 和同一个 VIEW_3D temp_override 渲染。
- 使用 JPEG，质量 92，保存到
  /config/Home/blender-renders/lares-solar-system-frames/f。

当前 Blender 构建不提供 FFMPEG 输出格式，不要尝试直接生成 MP4。
完成后报告逐帧目录的 Olares Drive 路径。
```

预期结果：

- `Home/blender-renders/lares-solar-system-frames` 中有 72 张图片。
- 在 Blender 时间轴中播放时能看到行星公转。
- 第一帧与循环结束后的下一帧位置连续。

需要 MP4 时，在有 ffmpeg 的环境中下载逐帧目录后执行：

```bash
ffmpeg -framerate 24 -i f%04d.jpg \
  -c:v libx264 -pix_fmt yuv420p -crf 20 \
  solar-system.mp4
```

Blender 应用内不包含 FFmpeg 编码器。`image_settings.file_format` 只有图片格式，直接设置 `FFMPEG` 会报错，这是当前构建的正常限制。

## 七、获取输出文件

图形界面方式：

1. 打开 Olares Files。
2. 进入 **Home → blender-renders**。
3. 预览或下载 `.png`、`.blend` 和逐帧图片。

命令行方式：

```bash
olares-cli files ls drive/Home/blender-renders
olares-cli files download \
  drive/Home/blender-renders/lares-solar-system.png \
  ./lares-solar-system.png
```

使用 `files ls`，不是 `files list`。

## 八、验收清单

- [ ] Blender 与 Lares 安装在同一台 Olares 上。
- [ ] Blender 已打开并保持运行。
- [ ] Lares MCP Transport 为 `Streamable HTTP`。
- [ ] MCP URL 使用内部入口并以 `/mcp` 结尾。
- [ ] 冒烟测试能读取 Blender 5.2 和当前对象。
- [ ] Lares 修改的是浏览器中正在显示的同一场景。
- [ ] `.blend` 与 PNG 出现在 `Home/blender-renders`。
- [ ] 静帧通过 `bpy.ops.render.opengl()` 生成。
- [ ] 动画目录包含 72 帧。
- [ ] 没有把输出写到 `/data/workspace`、`/tmp` 或 `/dev/shm`。

## 九、常见问题

### `.blend` 已保存，但 PNG 没有生成

脚本很可能调用了 `bpy.ops.render.render()`。该操作通过 MCP 执行时会静默失效。必须使用 `VIEW_3D` 上下文中的 `bpy.ops.render.opengl()`。

### Lares 反复探测 Blender API，迟迟不创建场景

保留示例提示词中的“已知事实”，并要求尽量在一次 `execute_blender_code` 调用中完成。

### 发光光晕或透明大气没有出现在图片中

OpenGL 渲染路径会丢弃 alpha 混合材质。请使用实体几何、自发光材质和表面渐变模拟效果，不要依赖透明加法平面或合成器。

### 行星程序化条纹变成纯色或密集摩尔纹

纹理 `Scale` 以物体单位计算。大半径球体需要更小的 Scale；比例过大会导致条纹密集到无法辨认。

### 发光太阳变成惨白色

AgX 会压缩高亮并降低饱和度。降低绿色、蓝色通道和发光强度，再用 `Layer Weight` 或噪声生成表面明暗变化。

### 无法直接输出 MP4

当前 Blender 构建没有 FFmpeg。先生成 JPEG/PNG 序列，再在外部使用 ffmpeg 编码。

### Lares 无法读取 Blender 中的 `/tmp` 文件

两个应用的容器文件系统不同。跨应用文件必须写到 `/config/Home`，并通过 Olares Files 的 `Home` 访问。

## 文档发布建议

- 对最终用户保留“一至六”与“常见问题”即可。
- MCP URL 截图中应遮盖用户域名，只保留 `/mcp` 结尾和字段位置。
- 不要在公开文档中引导用户暴露 9876 端口。
- 示例截图应同时展示 Lares 对话、Blender 场景和 Files 输出路径，便于证明三者属于同一工作流。
