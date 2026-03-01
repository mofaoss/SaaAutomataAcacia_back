# SAA 后端服务使用说明

本说明用于对接 `SAA_backend.py`。

目标：

- 将 SAA 核心任务以后端方式运行
- 前端通过 HTTP 控制任务启动/停止
- 通过 SSE（HTTP Stream）实时接收日志
- 仅使用标准库
- 为未来替换不同前端预留稳定后端协议

---

## 0. 架构分层（多前端预留）

当前后端采用两层：

- 核心应用层：`app/backend/application.py`
  - 聚合 `DailyTaskRunner`、`FeatureTaskRunner`、`CommandRegistry`、`LogHub`
  - 提供统一能力：健康检查、命令发现、命令执行、状态查询、日志查询、生命周期关闭
- 传输适配层：`app/backend/http_server.py`
  - 仅负责 HTTP 路由、状态码映射、SSE 输出
  - 不承载任务编排逻辑

这意味着未来若增加其他前端通道（如 stdio、WebSocket、gRPC），只需新增新的“传输适配层”，复用同一核心应用层。

---

## 1. 启动后端服务

在项目根目录执行：

```bash
python SAA_backend.py
```

默认监听：

- Host: `127.0.0.1`
- Port: `17800`

可选参数：

```bash
python SAA_backend.py --host 127.0.0.1 --port 17800 --config AppData/config.json
```

参数说明：

- `--host`: 绑定地址
- `--port`: 服务端口
- `--config`: 配置文件路径（默认 `AppData/config.json`）

---

## 2. HTTP API

### 2.1 健康检查

- Method: `GET`
- Path: `/api/health`

返回示例：

```json
{
  "ok": true,
  "service": "saa-backend"
}
```

### 2.2 命令发现

- Method: `GET`
- Path: `/api/commands`

说明：

- 返回当前后端支持的命令清单（命令名、描述、payload 结构）
- 前端可据此做动态路由或类型映射

### 2.3 当前状态（兼容）

- Method: `GET`
- Path: `/api/status`

返回字段：

- `state`: `idle | running | finished | stopped | error`
- `current_task`: 当前日常任务编码（如 `entry`）
- `started_at`: 开始时间
- `finished_at`: 结束时间
- `message`: 状态说明
- `running`: 是否仍在执行

> 说明：该接口保留用于兼容旧调用，命令模式下更建议使用 `daily.status`/`feature.status`。

### 2.4 最近日志

- Method: `GET`
- Path: `/api/logs?limit=200`

参数：

- `limit`: 返回条数，范围 `1~1000`

### 2.5 实时日志流（SSE）

- Method: `GET`
- Path: `/api/logs/stream`
- Content-Type: `text/event-stream`

事件数据格式：

```text
data: {"log":"23:31:00 - INFO - 当前任务：Use Stamina"}

```

> 包含心跳注释帧（`": heartbeat"`），用于保持连接活跃。

### 2.6 通用命令调用（推荐）

- Method: `POST`
- Path: `/api/commands/{name}`

常用命令：

- `game.open`：启动游戏（带防重复启动）
- `daily.start`：启动日常任务（可传 `tasks`）
- `daily.stop`：停止日常任务
- `daily.status`：查询日常任务状态
- `feature.start`：启动单功能任务（传 `feature`）
- `feature.stop`：停止单功能任务
- `feature.status`：查询单功能状态 + 支持列表

`daily.start` 示例：

```json
{
  "tasks": ["entry", "stamina", "reward"]
}
```

`feature.start` 示例：

```json
{
  "feature": "fishing"
}
```

### 2.7 兼容接口（旧）

为兼容旧前端，以下接口仍可用：

- `POST /api/open-game`
- `POST /api/start`
- `POST /api/stop`

### 2.8 启动任务（兼容）

- Method: `POST`
- Path: `/api/start`
- Body: 可选

可选任务列表：

- `entry`
- `collect`
- `shop`
- `stamina`
- `person`
- `chasm`
- `reward`

请求示例（指定任务）：

```json
{
  "tasks": ["entry", "stamina", "reward"]
}
```

不传 `tasks` 时：按配置文件中的勾选项执行。

### 2.9 停止任务（兼容，可随时调用）

- Method: `POST`
- Path: `/api/stop`
- Body: 可选

请求示例：

```json
{
  "reason": "user clicked stop"
}
```

说明：

- 该接口用于“任意时刻中止脚本”
- 若当前无任务运行，会返回 `409`

---

## 3. 前端对接建议（最小方案）

推荐保留单向控制 + 日志上行：

1. 启动应用时拉起 Python 后端进程
2. 前端通过 `GET /api/commands` 获取命令清单（可选）
3. 前端通过 `POST /api/commands/{name}` 发起执行
4. 前端通过 `EventSource('/api/logs/stream')` 展示实时日志
5. 用户点击停止时调用 `POST /api/commands/daily.stop` 或 `feature.stop`
6. 轮询 `POST /api/commands/daily.status` 或 `feature.status` 更新状态

通常不需要复杂双向协议。

前端替换建议：

- 把 `/api/commands/{name}` 视作稳定控制面，尽量不要耦合旧兼容路由
- 所有前端共享同一命令语义（例如 `daily.start`、`feature.start`）
- 在前端内做命令结果归一化（`ok/code/error/status`），避免 UI 与具体协议细节耦合

---

## 4. 快速联调示例（PowerShell）

健康检查：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/health -Method Get
```

查看命令清单：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/commands -Method Get
```

启动游戏：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/commands/game.open -Method Post
```

启动日常任务（仅刷体力）：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/commands/daily.start -Method Post -Body '{"tasks":["stamina"]}' -ContentType 'application/json'
```

查询日常状态：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/commands/daily.status -Method Post -Body '{}' -ContentType 'application/json'
```

停止日常任务：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/commands/daily.stop -Method Post -Body '{"reason":"manual stop"}' -ContentType 'application/json'
```

兼容旧接口（仍可用）示例：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/start -Method Post -Body '{"tasks":["entry","stamina"]}' -ContentType 'application/json'
```

查看实时日志（浏览器/EventSource）：

```text
GET http://127.0.0.1:17800/api/logs/stream
```

查看最近日志：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:17800/api/logs?limit=200 -Method Get
```

---

## 5. 注意事项

- 后端服务设计为与现有 Qt UI 并行存在，暂时不影响原有 `SAA.py` 启动方式
- 任务执行仍依赖现有自动化模块与系统环境（窗口句柄、分辨率、OCR 等）
- 建议新前端优先使用 `api/commands` 命令模式，旧接口仅保留兼容
- 建议统一处理 `409`（重复启动、空任务停止）等可预期状态码
