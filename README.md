# AI Code Review Kit

一个可在 macOS、Linux 和 Windows 上安装的 Git AI 提交门禁。安装后使用统一的 `ai-review` 命令，在 `git commit` 前审查暂存区，在 `git push` 前审查实际推送范围；发现 BUG、安全漏洞、可靠性或性能风险时逐条确认，完成最终确认后 Git 才会继续。

## 为什么需要它

团队直接把 `git diff` 粘贴给 AI 时，容易漏掉暂存或未跟踪文件，也可能意外发送密钥、构建产物和超大二进制文件。本模块把变更采集、安全过滤、提示词和 AI CLI 调用固化为可审计、可测试的跨平台脚本。

## 核心职责

- 统一采集工作区、暂存区、指定提交或相对基线的 Git 变更；
- 默认排除敏感文件、二进制文件和常见生成目录，并对常见凭据形态二次脱敏；
- 使用团队可编辑的审查提示模板，限制提示注入影响；
- 自动调用 Codex CLI，或以不经过 shell 的参数数组接入其他 AI CLI；
- 安装 `pre-commit` 与 `pre-push` hooks，要求大模型返回结构化风险清单；
- 对每条风险选择“接受”“误报”或“停止修复”，并要求输入 `CONFIRM` 二次确认；
- 在 macOS、Linux 和 Windows 上安装用户级命令，不要求管理员权限。

本工具不替代人工审批、测试、静态分析或安全扫描，也不会自动修改代码或自行执行 commit/push；它只通过 Git hook 的退出码决定当前 Git 操作是否继续。

## 平台与依赖

| 平台 | 安装脚本 | 运行入口 |
|---|---|---|
| macOS 12+ | `install.sh` | `ai-review` |
| 主流 Linux | `install.sh` | `ai-review` |
| Windows 10/11 | `install.cmd` / `install.ps1` | `ai-review.cmd` / `ai-review.ps1` |

必需依赖：

- Python 3.9 或更高版本；
- Git 2.x；
- 可选的 Codex CLI，或一个能从标准输入读取提示的 AI CLI。

未检测到 AI CLI 时，`auto` 模式会安全回退为输出完整提示。Codex 适配器使用官方文档中的非交互 `codex exec` 标准输入方式，并固定为只读沙箱和临时会话；参见 [Codex CLI 命令参考](https://developers.openai.com/codex/cli/reference)。

## GitHub 在线一键安装

在线安装器会通过 HTTPS 从当前仓库下载最小安装载荷，再调用本地安装器。公开仓库可匿名安装；私有仓库设置 `GITHUB_TOKEN` 或 `GH_TOKEN` 后，安装器会改用 GitHub Contents API 下载。令牌只需对该仓库拥有 Contents: read 权限，不要把令牌写入仓库或脚本。

### macOS / Linux

```sh
curl -fsSL https://raw.githubusercontent.com/oomheap/ai-code-review-kit/main/install-online.sh | sh
export PATH="$HOME/.local/bin:$PATH"
ai-review --doctor
```

当前仓库为私有仓库时，首次下载安装器本身也需要认证。先由终端的安全凭据管理方式设置环境变量，再执行：

```sh
{
  printf 'header = "Authorization: Bearer %s"\n' "$GITHUB_TOKEN"
  printf '%s\n' 'header = "Accept: application/vnd.github.raw+json"'
} | curl --config - -fsSL \
  "https://api.github.com/repos/oomheap/ai-code-review-kit/contents/install-online.sh?ref=main" | sh
```

令牌经 curl 标准输入传递，不会出现在 curl 进程参数中；管道中的安装器会继承 `GITHUB_TOKEN`，继续认证下载其他载荷。安装完成后可执行 `unset GITHUB_TOKEN`；不要直接把真实令牌粘贴进会被保存的命令历史。

安装命令后，还需在每个需要保护的 Git 仓库中单独启用门禁：

```sh
cd /path/to/your-repository
ai-review --install-hooks
```

自定义安装位置：

```sh
curl -fsSL https://raw.githubusercontent.com/oomheap/ai-code-review-kit/main/install-online.sh \
  | sh -s -- --install-dir "$HOME/tools/ai-code-review" --bin-dir "$HOME/bin"
```

生产环境建议把安装器和载荷固定到发布标签。把 `<tag>` 替换为实际标签：

```sh
curl -fsSL "https://raw.githubusercontent.com/oomheap/ai-code-review-kit/<tag>/install-online.sh" \
  | AI_REVIEW_REF="<tag>" sh
```

如果希望先检查脚本再执行：

```sh
curl -fsSL https://raw.githubusercontent.com/oomheap/ai-code-review-kit/main/install-online.sh \
  -o /tmp/install-ai-review.sh
less /tmp/install-ai-review.sh
sh /tmp/install-ai-review.sh
```

### Windows PowerShell

```powershell
$Installer = Join-Path $env:TEMP "install-ai-review.ps1"
Invoke-WebRequest `
  "https://raw.githubusercontent.com/oomheap/ai-code-review-kit/main/install-online.ps1" `
  -OutFile $Installer
& $Installer -AddToPath
Remove-Item $Installer
ai-review --doctor
```

私有仓库的 PowerShell 安装方式：

```powershell
$Headers = @{
  Authorization = "Bearer $env:GITHUB_TOKEN"
  Accept = "application/vnd.github.raw+json"
  "X-GitHub-Api-Version" = "2022-11-28"
}
$Installer = Join-Path $env:TEMP "install-ai-review.ps1"
Invoke-WebRequest `
  "https://api.github.com/repos/oomheap/ai-code-review-kit/contents/install-online.ps1?ref=main" `
  -Headers $Headers -OutFile $Installer
& $Installer -AddToPath
Remove-Item $Installer
```

在线安装器也接受 `-Token`，默认读取 `$env:GITHUB_TOKEN`，其次读取 `$env:GH_TOKEN`。

然后进入目标仓库启用门禁：

```powershell
Set-Location C:\path\to\your-repository
ai-review --install-hooks
```

固定版本时可传入 `-Ref <tag>`：

```powershell
$Installer = Join-Path $env:TEMP "install-ai-review.ps1"
Invoke-WebRequest `
  "https://raw.githubusercontent.com/oomheap/ai-code-review-kit/<tag>/install-online.ps1" `
  -OutFile $Installer
& $Installer -Ref "<tag>" -AddToPath
Remove-Item $Installer
```

Windows 在线安装器先保存到临时文件再执行，不使用 `Invoke-Expression`。

## 从源码安装

### macOS / Linux

```sh
git clone https://github.com/oomheap/ai-code-review-kit.git
cd ai-code-review-kit
./install.sh
export PATH="$HOME/.local/bin:$PATH"
ai-review --doctor
```

自定义安装位置：

```sh
./install.sh --install-dir "$HOME/tools/ai-code-review" --bin-dir "$HOME/bin"
```

### Windows PowerShell

```powershell
git clone https://github.com/oomheap/ai-code-review-kit.git
cd ai-code-review-kit
.\install.cmd -AddToPath
ai-review --doctor
```

也可以直接运行 PowerShell 安装器：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -AddToPath
```

`-AddToPath` 只更新当前用户的 `PATH`；若当前终端未识别新命令，请重新打开终端。自定义安装位置：

```powershell
.\install.ps1 -InstallDir "$HOME\tools\ai-code-review" -BinDir "$HOME\bin" -AddToPath
```

安装器可重复执行，已有的本工具文件会原位升级，不会删除目标目录中的其他文件。

## 配置 AI

### 方案一：Codex CLI（推荐）

`ai-review` 内置 Codex 适配器，不需要在本工具的 JSON 配置中保存 API Key。先确认 Codex 可用：

```sh
codex --version
codex login
codex login status
```

`codex login` 会打开浏览器，允许使用 ChatGPT 账号登录。也可以通过标准输入登录 OpenAI API Key：

```sh
printenv OPENAI_API_KEY | codex login --with-api-key
codex login status
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY | codex login --with-api-key
codex login status
```

不要把 API Key 写进 `.ai-review.json`、命令数组或 Git 仓库。Codex 会使用自己的凭据存储和模型配置；本工具默认调用：

```text
codex exec --ephemeral --sandbox read-only -C <repository> -
```

完成登录后，在任意 Git 仓库执行 `ai-review` 即可。官方登录方式参见 [Codex Authentication](https://developers.openai.com/codex/auth)，非交互参数参见 [Codex CLI Reference](https://developers.openai.com/codex/cli/reference)。

确认手动审查可用后，为当前仓库安装门禁：

```sh
ai-review --provider codex --scope staged
ai-review --provider codex --install-hooks
```

第二条命令会把本次明确指定的 `--provider codex` 固化到生成的 hooks 中。若省略 `--provider`，hooks 每次按用户配置的 `provider` 选择执行器。

如需为代码审查固定某个账号已支持的模型，可把 Codex 当作自定义命令配置：

```json
{
  "provider": "command",
  "command": [
    "codex", "exec", "--ephemeral", "--sandbox", "read-only",
    "--model", "<model-name>", "-C", "{repo}", "-"
  ]
}
```

### 方案二：其他 AI CLI

其他 AI CLI 必须能从标准输入接收完整提示，并把最终回答写到标准输出。把它配置为参数数组，工具不会通过 shell 拼接命令：

```json
{
  "provider": "command",
  "command": ["your-ai-cli", "--read-prompt-from-stdin", "--repository", "{repo}"]
}
```

AI 服务的 API Key、Base URL 和模型应由对应 CLI 自己管理，不应写进本工具配置。`{repo}` 会在执行时替换为仓库绝对路径。

门禁模式会在提示末尾附加严格 JSON 协议；AI CLI 必须原样输出模型的最终 JSON。如果输出为空、命令失败或 JSON 不符合风险字段约定，Git 会默认阻断。配置完成后执行：

```sh
ai-review --config /path/to/review-config.json --install-hooks
```

显式配置文件的绝对路径会写入 hooks，后续 commit/push 无需重复传参。

### 方案三：任意网页 AI

如果没有本地 AI CLI，可以只生成经过过滤的审查提示，再上传到 ChatGPT、Claude 或其他服务：

```sh
ai-review --prompt-only --output review-prompt.md
```

## 使用方法

### 推荐：启用 commit/push 门禁

先配置并登录 AI，然后在目标 Git 仓库执行一次：

```sh
# 同时安装 pre-commit 和 pre-push
ai-review --install-hooks

# 或只安装其中一个
ai-review --install-hooks --hooks pre-commit
ai-review --install-hooks --hooks pre-push
```

之后正常使用 Git，无需改变原命令：

```sh
git add src tests
git commit -m "feat: add feature"
git push
```

实际流程如下：

```text
git commit                  git push
    │                           │
    ▼                           ▼
审查暂存区 staged diff      审查本次将推送的 ref 范围
    └──────────────┬────────────┘
                   ▼
       AI 输出 BUG / 安全 / 性能风险 JSON
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
     无风险                有风险或覆盖不完整
        │                     │
     Git 继续          逐条选择 a / m / f
                              │
                   全部确认后输入 CONFIRM
                              │
                    Git 继续，否则阻断
```

每条风险的选择含义：

- `a`：已理解触发条件并接受本次风险；
- `m`：人工判断为误报；
- `f`：停止当前 Git 操作，修改代码后重试。

所有风险处理完还必须准确输入 `CONFIRM`。默认策略是失败关闭：AI 未配置、调用失败、结果不是合法 JSON，或有风险但当前 IDE/客户端无法提供交互终端时，commit/push 都会失败。无风险时无需人工输入。

差异被截断或有文件因敏感、二进制、排除规则而跳过时，会生成独立的覆盖风险，也必须人工确认。

安装 hooks 时若已有同名 hook，工具会将其保存为 `pre-commit.ai-review-original` 或 `pre-push.ai-review-original`，先运行原 hook，再运行 AI 门禁。重复安装是幂等的。卸载并恢复原 hook：

```sh
ai-review --uninstall-hooks
# 也可指定：--hooks pre-commit 或 --hooks pre-push
```

若仓库配置了 `core.hooksPath`，自动安装会拒绝修改该共享目录，请由维护者手动集成。Git 自带的紧急绕过方式 `git commit --no-verify` / `git push --no-verify` 仍然有效，应只用于已经记录并经团队批准的例外情况。

### 手动审查

在任意 Git 仓库中执行：

```sh
# 审查所有未提交变更：暂存、未暂存、未跟踪
ai-review

# 只审查暂存区
ai-review --scope staged

# 审查指定提交
ai-review --scope commit --ref HEAD

# 审查当前 HEAD 相对 main 分支的变更
ai-review --scope base --ref main

# 不调用 AI，仅检查或保存最终提示
ai-review --provider prompt
ai-review --prompt-only --output review-prompt.md

# 从仓库外指定目标目录
ai-review /path/to/repository
```

默认 `provider=auto` 的选择顺序为：配置的自定义命令、Codex CLI、输出提示。若要强制使用 Codex：

```sh
ai-review --provider codex
```

“输出提示”只适用于手动审查；Git 门禁不能等待用户把提示复制到网页，因此 `auto` 找不到可执行 AI 时会阻断 Git 操作。

## 配置文件

建议把 AI 执行器放在用户级配置中，把团队共享的排除规则和提示模板放在项目配置中。

用户级配置路径：

- macOS/Linux：`~/.config/ai-code-review/config.json`；
- Windows：`%APPDATA%\AiCodeReview\config.json`。

项目级配置路径为仓库根目录的 `.ai-review.json`，出于安全考虑默认不自动加载。

配置从低到高按以下顺序覆盖：

1. 内置默认值；
2. 用户配置：macOS/Linux 的 `~/.config/ai-code-review/config.json`，Windows 的 `%APPDATA%\AiCodeReview\config.json`；
3. 传入 `--trust-project-config` 后，仓库根目录的 `.ai-review.json`；
4. `--config /path/to/config.json` 显式指定的文件；
5. 命令行参数。

仓库内容属于审查对象，默认不信任其中的配置，避免恶意 `.ai-review.json` 指定本地命令。只应对已确认来源的仓库使用 `--trust-project-config`；团队也可以始终用 `--config` 显式选择受控配置。

配置字段：

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `provider` | 字符串 | `auto` | `auto`、`codex`、`command` 或 `prompt` |
| `command` | 字符串数组 | `[]` | 自定义 AI CLI 及参数；提示从标准输入传入 |
| `max_diff_chars` | 整数 | `120000` | 最多进入提示的 diff 字符数，范围 1000–2000000 |
| `language` | 字符串 | `zh-CN` | 要求 AI 使用的输出语言 |
| `exclude` | 字符串数组 | `[]` | 追加的仓库相对 glob 排除规则 |
| `prompt_file` | 字符串 | 空 | 自定义 Markdown 提示模板，相对路径基于被审查仓库 |

示例：

```json
{
  "provider": "auto",
  "command": [],
  "max_diff_chars": 120000,
  "language": "zh-CN",
  "exclude": ["generated/**", "fixtures/large/**"],
  "prompt_file": "prompts/team-review.md"
}
```

默认配置见 [config/default.json](config/default.json)，自定义执行器完整示例见 [examples/custom-command.json](examples/custom-command.json)。

加载可信项目配置：

```sh
ai-review --trust-project-config
ai-review --trust-project-config --install-hooks
```

第二条命令会把信任选项写入 hooks。启用后，仓库中的配置可以指定本地 AI 命令，因此只应对受控仓库使用。

显式指定其他配置文件：

```sh
ai-review --config /path/to/review-config.json
```

自定义提示模板可以使用 `{{REPOSITORY}}`、`{{SCOPE}}`、`{{METADATA}}`、`{{LANGUAGE}}` 和 `{{DIFF}}` 占位符。若模板没有 `{{DIFF}}`，工具会自动把 diff 追加到不可信数据区块。

## 安全行为

- `.env*`、私钥、证书、凭据配置等文件默认不进入提示；
- 常见二进制扩展名、依赖目录和构建目录默认排除；
- 未跟踪文件必须是仓库内普通、非符号链接、UTF-8 小文件；
- diff 中形如 `password=...`、`api_key=...` 的值及常见令牌形态会替换为 `<REDACTED>`；
- 默认最多发送 120,000 个 diff 字符，超过部分带标记截断；
- Codex 在 `read-only` 沙箱中运行，自定义命令使用 `shell=False` 等价行为；
- 仓库内 `.ai-review.json` 默认不加载，防止不可信代码指定本地执行命令；
- 提示模板明确把 diff 标记为不可信数据，降低代码注释中的提示注入风险。
- 门禁只接受单个结构化 JSON 对象，格式错误和 AI 调用错误默认阻断；
- AI 风险文本在显示前移除终端控制字符，推送 ref 仍通过 Git 参数数组解析；
- 已有 hooks 在改名前备份，卸载只删除带本工具标记的 hook，并恢复原文件。
- 私有 GitHub 下载令牌不写入安装目录；POSIX 只在权限受限的临时 curl 配置中传递，并随临时目录删除。

过滤是降低误发概率的防线，不是完备的密钥检测器。运行前仍应确认目标仓库和配置；`--allow-sensitive` 只关闭按文件名的敏感过滤，内容脱敏仍然生效。

## 升级

重复运行相同的本地或在线安装命令即可原位升级。在线安装默认跟随 `main`，生产环境应通过发布标签固定 `AI_REVIEW_REF`/`-Ref`，避免安装结果随分支变化。

## 开发与验证

```sh
python3 -m unittest discover -s tests -v
sh -n install.sh
sh -n install-online.sh
sh tests/test_install.sh
sh tests/test_online_install.sh
python3 src/ai_review.py --doctor
```

当前环境没有 PowerShell 时，Windows 安装器由单元测试执行结构和危险调用检查；发布前建议再在 Windows PowerShell 5.1 与 PowerShell 7 各运行一次安装冒烟测试。

## 目录结构

```text
ai-code-review-kit/
├── bin/                    # Windows 命令入口
├── config/default.json     # 默认配置样例
├── examples/               # 自定义 AI CLI 配置样例
├── prompts/review.md       # 默认代码审查提示
├── src/ai_review.py        # 跨平台核心 CLI
├── tests/                  # 单元测试与 POSIX 安装测试
├── install-online.sh       # GitHub 在线安装器（macOS/Linux）
├── install-online.ps1      # GitHub 在线安装器（Windows）
├── install.sh              # macOS / Linux 安装器
├── install.cmd             # Windows 一键安装入口
├── install.ps1             # Windows PowerShell 安装器
├── DESIGN.md               # 架构与安全决策
└── README.md
```

## 相关文档

- [设计文档](DESIGN.md)
- [默认配置](config/default.json)
- [默认审查提示](prompts/review.md)
