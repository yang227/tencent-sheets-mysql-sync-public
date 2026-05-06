# 贡献指南 (Contributing Guide)

感谢您考虑为腾讯文档 MySQL 同步系统做出贡献！本指南将帮助您了解如何参与项目开发。

## 目录

- [行为准则](#行为准则)
- [开始贡献](#开始贡献)
- [开发环境搭建](#开发环境搭建)
- [编码规范](#编码规范)
- [测试要求](#测试要求)
- [提交规范](#提交规范)
- [Pull Request 流程](#pull-request-流程)
- [代码审查](#代码审查)
- [发布流程](#发布流程)

## 行为准则

### 我们的承诺

为了营造一个开放、友好的社区环境，我们承诺：

- 使用友好和包容的语言
- 尊重不同的观点和经验
- 优雅地接受建设性的批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

### 禁止行为

- 使用性暗示语言或图像
- 挑衅、侮辱或贬低性评论
- 公开或私下骚扰
- 未经明确许可发布他人的私人信息
- 其他不专业或不道德的行为

## 开始贡献

### 贡献方式

您可以通过以下方式为本项目做出贡献：

1. **提交 Issue**：报告 Bug、提出新功能建议
2. **提交 Pull Request**：修复 Bug、实现新功能、改进文档
3. **改进文档**：修正错误、补充缺失内容、翻译文档
4. **测试**：编写测试用例、进行性能测试
5. **代码审查**：审查他人的 Pull Request

### 报告 Bug

提交 Bug 报告前，请：

1. 检查 [现有 Issue](https://github.com/your-repo/issues) 确认问题未被报告
2. 使用最新版本测试确认问题仍然存在
3. 收集相关信息（错误日志、截图等）

**Bug 报告模板**：

```markdown
## Bug 描述
简明扼要地描述 Bug。

## 复现步骤
1. 进入 '...'
2. 点击 '...'
3. 滚动到 '...'
4. 看到错误

## 预期行为
描述您期望发生的事情。

## 实际行为
描述实际发生的事情。

## 环境信息
- 操作系统：[例如：Ubuntu 22.04]
- Python 版本：[例如：3.10.6]
- 应用版本：[例如：1.0.0]
- 浏览器（如果相关）：[例如：Chrome 120]

## 相关日志
```
粘贴相关错误日志
```

## 截图
如果适用，添加截图帮助解释问题。

## 其他信息
添加任何其他有助于解决问题的信息。
```

### 提出功能建议

**功能建议模板**：

```markdown
## 功能描述
简明扼要地描述您希望添加的功能。

## 问题背景
描述这个功能将解决什么问题或改进什么。

## 建议解决方案
描述您希望如何实现这个功能。

## 替代方案
描述您考虑过的其他解决方案。

## 附加信息
添加任何其他选项或关于功能请求的信息。
```

## 开发环境搭建

### 前置条件

- Python 3.10+
- MySQL 8.0+
- Git
- pip / uv（推荐）

### 步骤

#### 1. Fork 和克隆仓库

```bash
# Fork 仓库（在 GitHub 上操作）

# 克隆您的 Fork
git clone https://github.com/your-username/tencent-sheets-mysql-sync.git
cd tencent-sheets-mysql-sync

# 添加上游仓库
git remote add upstream https://github.com/original-owner/tencent-sheets-mysql-sync.git
```

#### 2. 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
# Linux/Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

#### 3. 安装依赖

```bash
# 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 如果有

# 或使用 uv（更快）
uv pip install -r requirements.txt
```

#### 4. 配置环境

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
vim .env

# 配置 config.yaml
vim config.yaml
```

#### 5. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE tencent_sheets_sync;"

# 运行初始化 SQL
mysql -u root -p tencent_sheets_sync < migrations/init.sql
```

#### 6. 运行应用

```bash
# 启动应用（开发模式，支持热重载）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8083 --reload

# 访问应用
# 管理界面：http://localhost:8083/
# API 文档：http://localhost:8083/docs
```

#### 7. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_sync_engine.py

# 运行特定测试函数
pytest tests/test_sync_engine.py::test_sync_to_mysql

# 带覆盖率报告
pytest --cov=app --cov-report=html
```

## 编码规范

### Python 代码规范

本项目遵循 [PEP 8](https://pep8.org/) 和以下规范：

#### 1. 代码格式

使用以下工具自动格式化代码：

```bash
# 安装格式化工具
pip install black isort flake8

# 格式化代码
black app/ tests/

# 排序导入
isort app/ tests/

# 检查代码风格
flake8 app/ tests/
```

#### 2. 命名规范

```python
# 模块和包：小写，可包含下划线
# 例如：sync_engine.py, mysql_service.py

# 类名：驼峰命名法（CapWords）
class SyncEngine:
    pass

# 函数和方法：小写，单词间用下划线连接
def sync_to_mysql():
    pass

# 常量：全大写，单词间用下划线连接
MAX_RETRY_TIMES = 3

# 私有属性/方法：前缀下划线
class SyncEngine:
    def _private_method(self):
        pass
```

#### 3. 类型注解

所有函数和方法都应包含类型注解：

```python
from typing import List, Optional

def process_data(items: List[str], threshold: Optional[int] = None) -> bool:
    """处理数据并返回是否成功"""
    pass
```

#### 4. 文档字符串

使用 Google 风格的文档字符串：

```python
def sync_to_mysql(config_id: int, batch_size: int = 100) -> SyncResult:
    """同步腾讯文档数据到 MySQL

    Args:
        config_id: 同步配置 ID
        batch_size: 批量处理大小，默认 100

    Returns:
        SyncResult: 同步结果对象，包含成功状态、影响行数等

    Raises:
        SyncEngineError: 同步引擎错误
        DatabaseError: 数据库操作错误
    """
    pass
```

#### 5. 错误处理

```python
# 使用具体的异常类型
try:
    result = api.call()
except TencentAPIError as e:
    logger.error(f"API 调用失败: {e}")
    raise SyncEngineError(f"同步失败: {e}") from e

# 使用自定义异常
class SyncEngineError(Exception):
    """同步引擎基础异常类"""
    pass
```

#### 6. 日志规范

```python
import logging
logger = logging.getLogger(__name__)

# 使用适当的日志级别
logger.debug("调试信息：%s", variable)
logger.info("操作成功：%s", operation)
logger.warning("警告信息：%s", warning)
logger.error("错误信息：%s", error)
logger.critical("严重错误：%s", critical_error)
```

### 测试规范

#### 1. 单元测试

```python
import pytest
from app.services.sync_engine import SyncEngine

def test_sync_to_mysql_success(mocker):
    """测试同步到 MySQL 成功场景"""
    # Arrange
    engine = SyncEngine(config_id=1)
    mocker.patch.object(engine, 'fetch_source_data', return_value=[...])

    # Act
    result = engine.sync_to_mysql()

    # Assert
    assert result.success is True
    assert result.rows_affected > 0
```

#### 2. 集成测试

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_config_api():
    """测试创建配置 API"""
    response = client.post(
        "/api/configs",
        json={
            "spreadsheet_id": "test123",
            "sheet_id": "Sheet1",
            ...
        }
    )
    assert response.status_code == 200
    assert response.json()["id"] is not None
```

#### 3. 测试覆盖率

- 目标覆盖率：≥ 80%
- 核心模块覆盖率：≥ 90%
- 新代码必须包含测试

```bash
# 检查测试覆盖率
pytest --cov=app --cov-report=term-missing

# 生成 HTML 覆盖率报告
pytest --cov=app --cov-report=html
```

## 测试要求

### 测试清单

提交代码前，请确保：

- [ ] 所有测试通过：`pytest`
- [ ] 新功能有对应的测试用例
- [ ] 测试覆盖率没有下降
- [ ] 代码通过静态检查：`flake8`
- [ ] 代码已格式化：`black`、`isort`

### 编写测试

#### 单元测试示例

```python
# tests/test_sync_engine.py
import pytest
from unittest.mock import Mock, MagicMock
from app.services.sync_engine import SyncEngine

class TestSyncEngine:
    """同步引擎测试类"""

    @pytest.fixture
    def engine(self):
        """创建同步引擎实例"""
        return SyncEngine(config_id=1)

    def test_sync_to_mysql_success(self, engine, mocker):
        """测试同步到 MySQL 成功"""
        # Mock 依赖
        mocker.patch.object(engine, 'fetch_source_data', return_value=[
            {"id": 1, "name": "Test"}
        ])
        mocker.patch.object(engine.mysql, 'bulk_insert', return_value=1)

        # 执行测试
        result = engine.sync_to_mysql()

        # 验证结果
        assert result.success is True
        assert result.rows_affected == 1

    def test_sync_to_mysql_api_error(self, engine, mocker):
        """测试 API 调用失败场景"""
        # Mock API 抛出异常
        mocker.patch.object(
            engine, 'fetch_source_data',
            side_effect=TencentAPIError("API 错误")
        )

        # 验证异常抛出
        with pytest.raises(SyncEngineError):
            engine.sync_to_mysql()
```

#### 集成测试示例

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestConfigAPI:
    """配置管理 API 测试"""

    def test_create_config(self):
        """测试创建配置"""
        response = client.post(
            "/api/configs",
            json={
                "spreadsheet_id": "test123",
                "sheet_id": "Sheet1",
                "table_name": "users",
                "database": "test_db",
                "mapping_json": {
                    "columns": [...]
                },
                "sync_direction": "bidirectional",
                "poll_interval": 30
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["spreadsheet_id"] == "test123"

    def test_create_config_invalid_data(self):
        """测试创建配置 - 无效数据"""
        response = client.post(
            "/api/configs",
            json={
                # 缺少必填字段
            }
        )

        assert response.status_code == 422  # Unprocessable Entity
```

## 提交规范

### Git 提交信息规范

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

#### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type 类型

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 Bug |
| docs | 文档更新 |
| style | 代码格式调整（不影响功能） |
| refactor | 重构（既不修复 Bug 也不添加功能） |
| perf | 性能优化 |
| test | 测试相关 |
| chore | 构建过程或辅助工具变动 |
| ci | CI 配置文件和脚本变动 |

#### 示例

```bash
# 新功能
git commit -m "feat(sync): 添加增量同步功能"

# 修复 Bug
git commit -m "fix(api): 修复创建配置时字段验证错误

修复了当 mapping_json 为空时导致的 API 500 错误

Closes #123"

# 文档更新
git commit -m "docs(README): 更新安装步骤

补充了 Windows 环境下的安装说明"

# 性能优化
git commit -m "perf(sync): 优化批量同步性能

将批量处理大小从 100 提升到 500，同步速度提升 3x"
```

### 提交前检查

```bash
# 运行测试
pytest

# 检查代码风格
flake8 app/ tests/

# 格式化代码
black app/ tests/
isort app/ tests/

# 检查类型（如果使用 mypy）
mypy app/
```

## Pull Request 流程

### 创建 Pull Request

#### 1. 创建功能分支

```bash
# 从 main 分支创建新分支
git checkout main
git pull upstream main

# 创建功能分支
git checkout -b feat/add-retry-mechanism
```

#### 2. 开发和提交

```bash
# 进行代码修改
# ...

# 添加修改的文件
git add app/services/retry_handler.py
git add tests/test_retry_handler.py

# 提交修改
git commit -m "feat(retry): 添加指数退避重试机制"

# 推送到您的 Fork
git push origin feat/add-retry-mechanism
```

#### 3. 创建 Pull Request

1. 访问您的 Fork 页面：https://github.com/your-username/tencent-sheets-mysql-sync
2. 点击 "Compare & pull request" 按钮
3. 填写 PR 描述模板
4. 选择审查者
5. 提交 PR

#### 4. PR 描述模板

```markdown
## PR 描述
简明扼要地描述此 PR 的修改内容。

## 修改类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 性能优化
- [ ] 重构
- [ ] 文档更新
- [ ] 测试更新

## 相关 Issue
Closes #123
Relates to #456

## 修改内容
- 修改了 `app/services/retry_handler.py`：添加指数退避重试逻辑
- 添加了 `tests/test_retry_handler.py`：新增重试处理器测试用例
- 更新了 `README.md`：补充重试机制说明

## 测试方法
1. 运行单元测试：`pytest tests/test_retry_handler.py`
2. 手动测试：创建同步配置，模拟网络错误观察重试行为

## 测试截图
（如果适用）添加测试运行截图或日志输出

## Checklist
- [ ] 代码遵循项目编码规范
- [ ] 添加了相应的测试用例
- [ ] 所有测试通过
- [ ] 文档已更新（如果需要）
- [ ] 提交了 sign-off（如果需要）
```

### PR 审查流程

#### 审查者责任

1. **代码审查**
   - 代码逻辑是否正确
   - 是否遵循编码规范
   - 是否有足够的测试覆盖
   - 是否有性能问题

2. **测试验证**

   ```bash
   # 拉取 PR 分支
   git fetch origin pull/123/head:pr-123
   git checkout pr-123

   # 运行测试
   pytest

   # 手动验证
   python -m uvicorn app.main:app --reload
   ```

3. **提供反馈**
   - 明确、建设性地提供反馈
   - 解释为什么建议修改
   - 提供改进建议

#### PR 作者责任

1. **回应反馈**
   - 及时回应审查意见
   - 讨论不同方案的优缺点
   - 根据反馈修改代码

2. **修改代码**

   ```bash
   # 在功能分支上修改代码
   git add <modified_files>
   git commit -m "fix: 根据审查意见修改"
   git push origin feat/add-retry-mechanism
   ```

3. **保持 PR 更新**

   ```bash
   # 同步上游 main 分支
   git fetch upstream
   git rebase upstream/main

   # 解决冲突（如果有）
   # ...

   # 强制推送（如果 rebase 了）
   git push origin feat/add-retry-mechanism --force-with-lease
   ```

## 代码审查

### 审查清单

审查代码时，请关注以下方面：

#### 1. 功能正确性

- [ ] 代码逻辑是否正确
- [ ] 是否处理了边界情况
- [ ] 错误处理是否完善
- [ ] 是否有潜在的 Bug

#### 2. 代码质量

- [ ] 代码是否易于理解
- [ ] 是否遵循编码规范
- [ ] 是否有重复代码可以抽象
- [ ] 函数和类的职责是否单一

#### 3. 性能

- [ ] 是否有性能瓶颈
- [ ] 是否有不必要的数据库查询
- [ ] 是否有内存泄漏风险
- [ ] 是否可以并行处理

#### 4. 安全性

- [ ] 是否有 SQL 注入风险
- [ ] 是否有 XSS 风险
- [ ] 敏感信息是否加密
- [ ] 输入验证是否充分

#### 5. 测试

- [ ] 是否有足够的测试覆盖
- [ ] 测试是否覆盖了主要场景
- [ ] 是否包含边界情况测试
- [ ] 测试是否易于理解

### 审查最佳实践

1. **及时审查**
   - 在 48 小时内完成审查
   - 如果无法及时审查，告知 PR 作者

2. **提供建设性反馈**
   - 解释为什么建议修改
   - 提供具体的改进建议
   - 认可好的实践

3. **讨论而非命令**
   - 使用建议的语气："可以考虑..." 而非 "必须..."
   - 解释设计原则而非个人偏好

4. **表扬好的代码**
   - 如果代码写得好，给予肯定
   - 营造积极的工作氛围

## 发布流程

### 版本号规范

本项目遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)：

- **主版本号**：做了不兼容的 API 修改
- **次版本号**：做了向下兼容的功能性新增
- **修订号**：做了向下兼容的问题修正

示例：`v1.2.3` 表示主版本 1，次版本 2，修订号 3

### 发布步骤

#### 1. 更新版本号

```bash
# 更新版本号（在 app/main.py 或 pyproject.toml 中）
# 例如：__version__ = "1.2.3"

# 提交版本号修改
git add app/main.py
git commit -m "chore(release): bump version to v1.2.3"
```

#### 2. 更新 CHANGELOG

```bash
# 更新 CHANGELOG.md
# 添加新版本的变更记录

git add CHANGELOG.md
git commit -m "docs(changelog): update CHANGELOG for v1.2.3"
```

#### 3. 创建标签

```bash
# 创建版本标签
git tag -a v1.2.3 -m "Release v1.2.3"

# 推送标签
git push upstream v1.2.3
```

#### 4. 发布到 GitHub

1. 访问 Releases 页面：https://github.com/your-repo/releases
2. 点击 "Create a new release"
3. 选择标签：`v1.2.3`
4. 填写发布说明（从 CHANGELOG.md 复制）
5. 上传构建产物（如果有）
6. 发布

#### 5. 构建和发布到 PyPI（如果适用）

```bash
# 构建分发包
python -m build

# 发布到 PyPI
python -m twine upload dist/*
```

## 社区

### 联系方式

- **GitHub Issues**：[https://github.com/your-repo/issues](https://github.com/your-repo/issues)
- **邮件列表**：community@example.com
- **Slack/Discord**：[邀请链接]

### 贡献者认可

感谢所有为项目做出贡献的开发者！

（此处可以添加贡献者列表或链接到外部贡献者页面）

---

**文档版本**：v1.0.0  
**最后更新**：2026-04-30  
**维护者**：开发团队
