#!/bin/bash
#===============================================================================
# 腾讯文档 MySQL 同步系统 - 部署前检查脚本
#===============================================================================

set -e

echo "========================================================================"
echo "腾讯文档 MySQL 同步系统 - 部署前检查"
echo "========================================================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_ok() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
}

#-------------------------------------------------------------------------------
# 1. 系统要求检查
#-------------------------------------------------------------------------------
echo "📋 检查系统要求..."
echo ""

echo "1.1 检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    check_ok "Python 版本: $PYTHON_VERSION (要求 >= 3.8)"
else
    check_fail "Python 版本: $PYTHON_VERSION (要求 >= 3.8)"
    exit 1
fi

echo ""
echo "1.2 检查 pip..."
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version | awk '{print $2}')
    check_ok "pip 版本: $PIP_VERSION"
else
    check_fail "pip 未安装"
    exit 1
fi

#-------------------------------------------------------------------------------
# 2. 依赖检查
#-------------------------------------------------------------------------------
echo ""
echo "📦 检查项目依赖..."
echo ""

cd "$(dirname "$0")/.." || exit 1

echo "2.1 检查 requirements.txt..."
if [ -f "requirements.txt" ]; then
    check_ok "requirements.txt 存在"
else
    check_fail "requirements.txt 不存在"
    exit 1
fi

echo ""
echo "2.2 检查虚拟环境..."
if [ -d ".venv" ]; then
    check_ok "虚拟环境存在"
    
    echo ""
    echo "2.3 激活虚拟环境并检查依赖..."
    source .venv/bin/activate
    
    MISSING_DEPS=()
    while IFS= read -r package; do
        PACKAGE_NAME=$(echo "$package" | cut -d'=' -f1 | cut -d'>' -f1 | cut -d'<' -f1 | tr -d ' ')
        
        if ! pip show "$PACKAGE_NAME" &> /dev/null; then
            MISSING_DEPS+=("$PACKAGE_NAME")
        fi
    done < requirements.txt
    
    if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
        check_ok "所有依赖已安装"
    else
        check_fail "缺少依赖: ${MISSING_DEPS[*]}"
        echo "请运行: pip install -r requirements.txt"
        exit 1
    fi
else
    check_warn "虚拟环境不存在，建议创建"
    echo "创建虚拟环境: python3 -m venv .venv"
fi

#-------------------------------------------------------------------------------
# 3. 配置文件检查
#-------------------------------------------------------------------------------
echo ""
echo "⚙️  检查配置文件..."
echo ""

echo "3.1 检查 config.yaml..."
if [ -f "config.yaml" ]; then
    check_ok "config.yaml 存在"
    
    # 检查必需配置项
    echo "    检查配置项..."
    
    if grep -q "database:" config.yaml && grep -q "host:" config.yaml; then
        check_ok "数据库配置存在"
    else
        check_fail "数据库配置缺失"
        exit 1
    fi
    
    if grep -q "tencent:" config.yaml && grep -q "app_id:" config.yaml; then
        check_ok "腾讯API配置存在"
    else
        check_warn "腾讯API配置缺失"
    fi
else
    check_fail "config.yaml 不存在"
    echo "请复制 config.yaml.example 并配置"
    exit 1
fi

#-------------------------------------------------------------------------------
# 4. 数据库检查
#-------------------------------------------------------------------------------
echo ""
echo "🗄️  检查数据库..."
echo ""

# 从配置读取数据库信息
DB_HOST=$(grep -A 2 "^database:" config.yaml | grep "host:" | awk '{print $2}' | tr -d '"' || echo "localhost")
DB_PORT=$(grep -A 2 "^database:" config.yaml | grep "port:" | awk '{print $2}' | tr -d '"' || echo "3306")
DB_USER=$(grep -A 2 "^database:" config.yaml | grep "user:" | awk '{print $2}' | tr -d '"' || echo "root")
DB_NAME=$(grep -A 2 "^database:" config.yaml | grep "name:" | awk '{print $2}' | tr -d '"' || echo "tencent_sheets_sync")

echo "4.1 检查 MySQL 连接..."
if command -v mysql &> /dev/null; then
    if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -e "SELECT 1" &> /dev/null; then
        check_ok "MySQL 连接成功"
        
        echo ""
        echo "4.2 检查数据库..."
        if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -e "USE $DB_NAME" &> /dev/null; then
            check_ok "数据库 $DB_NAME 存在"
        else
            check_warn "数据库 $DB_NAME 不存在，将自动创建"
        fi
        
        echo ""
        echo "4.3 检查系统表..."
        TABLES=("sync_configs" "sync_logs" "change_tracking")
        ALL_TABLES_EXIST=true
        
        for table in "${TABLES[@]}"; do
            if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" -e "SELECT 1 FROM $table LIMIT 1" &> /dev/null; then
                echo "    ✅ $table"
            else
                echo "    ⚠️  $table (将在首次启动时创建)"
                ALL_TABLES_EXIST=false
            fi
        done
        
        if [ "$ALL_TABLES_EXIST" = false ]; then
            check_warn "部分系统表不存在，将在首次启动时自动创建"
        fi
    else
        check_warn "MySQL 连接失败，请检查配置"
        echo "    提示: 服务启动后将自动重试"
    fi
else
    check_warn "mysql 客户端未安装，无法预检查"
fi

#-------------------------------------------------------------------------------
# 5. 权限检查
#-------------------------------------------------------------------------------
echo ""
echo "🔐 检查权限..."
echo ""

echo "5.1 检查配置文件权限..."
if [ -f "config.yaml" ]; then
    CONFIG_PERMS=$(stat -f %Sp config.yaml 2>/dev/null || stat -c %a config.yaml 2>/dev/null)
    if [ "$CONFIG_PERMS" = "600" ] || [ "$CONFIG_PERMS" = "rw-------" ]; then
        check_ok "config.yaml 权限正确 (600)"
    else
        check_warn "config.yaml 权限为 $CONFIG_PERMS，建议设为 600"
        echo "    chmod 600 config.yaml"
    fi
fi

echo ""
echo "5.2 检查日志目录..."
if [ -d "logs" ]; then
    check_ok "logs 目录存在"
else
    echo "    📁 创建 logs 目录..."
    mkdir -p logs
    check_ok "logs 目录已创建"
fi

#-------------------------------------------------------------------------------
# 6. 端口检查
#-------------------------------------------------------------------------------
echo ""
echo "🔌 检查端口..."
echo ""

APP_PORT=$(grep -A 2 "^app:" config.yaml | grep "port:" | awk '{print $2}' | tr -d '"' || echo "8080")

echo "6.1 检查端口 $APP_PORT 是否可用..."
if lsof -Pi :$APP_PORT -sTCP:LISTEN -t &> /dev/null; then
    check_fail "端口 $APP_PORT 已被占用"
    echo "    请修改 config.yaml 中的端口或停止占用进程"
else
    check_ok "端口 $APP_PORT 可用"
fi

#-------------------------------------------------------------------------------
# 7. 网络检查
#-------------------------------------------------------------------------------
echo ""
echo "🌐 检查网络连接..."
echo ""

echo "7.1 检查腾讯文档 API 连接..."
if curl -s --max-time 5 "https://docs.qq.com" &> /dev/null; then
    check_ok "腾讯文档 API 可访问"
else
    check_warn "无法访问腾讯文档 API，请检查网络"
fi

echo ""
echo "7.2 检查 MySQL 端口可访问性..."
if nc -zv "$DB_HOST" "$DB_PORT" &> /dev/null; then
    check_ok "MySQL 端口 $DB_PORT 可访问"
else
    check_warn "MySQL 端口 $DB_PORT 不可访问"
fi

#-------------------------------------------------------------------------------
# 8. 代码检查
#-------------------------------------------------------------------------------
echo ""
echo "📝 检查代码完整性..."
echo ""

echo "8.1 检查关键文件..."
KEY_FILES=(
    "app/main.py"
    "app/config.py"
    "app/services/sync_engine.py"
    "app/services/tencent_api.py"
    "app/services/mysql_service.py"
    "app/routers/config_router.py"
    "app/routers/sync_router.py"
)

ALL_FILES_OK=true
for file in "${KEY_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "    ✅ $file"
    else
        echo "    ❌ $file (缺失)"
        ALL_FILES_OK=false
    fi
done

if [ "$ALL_FILES_OK" = true ]; then
    check_ok "所有关键文件存在"
else
    check_fail "部分关键文件缺失"
    exit 1
fi

echo ""
echo "8.2 检查新增功能文件..."
NEW_FILES=(
    "app/services/audit_logger.py"
    "app/services/metrics_collector.py"
    "app/services/retry_handler.py"
    "app/services/sync_engine_enhanced.py"
    "app/services/config_validator.py"
    "app/services/batch_optimizer.py"
    "app/routers/enhanced_router.py"
    "app/routers/monitoring_router.py"
)

NEW_FILES_EXIST=0
for file in "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "    ✅ $file"
        ((NEW_FILES_EXIST++))
    else
        echo "    ⚠️  $file (可选)"
    fi
done

echo ""
if [ $NEW_FILES_EXIST -ge 5 ]; then
    check_ok "增强功能已安装 ($NEW_FILES_EXIST/$(( ${#NEW_FILES[@]} )) )"
else
    check_warn "增强功能不完整 ($NEW_FILES_EXIST/$(( ${#NEW_FILES[@]} )) )"
fi

#-------------------------------------------------------------------------------
# 9. 测试运行
#-------------------------------------------------------------------------------
echo ""
echo "🧪 运行基础测试..."
echo ""

if [ -d ".venv" ]; then
    source .venv/bin/activate
    
    echo "9.1 运行集成测试..."
    if PYTHONPATH=. python3 tests/integration_test.py &> /tmp/integration_test.log; then
        if grep -q "所有测试通过" /tmp/integration_test.log; then
            check_ok "集成测试通过"
        else
            check_warn "集成测试部分通过"
        fi
    else
        check_warn "集成测试运行失败"
        cat /tmp/integration_test.log | tail -20
    fi
else
    check_warn "跳过测试 (虚拟环境不存在)"
fi

#-------------------------------------------------------------------------------
# 10. 总结
#-------------------------------------------------------------------------------
echo ""
echo "========================================================================"
echo "📊 部署前检查总结"
echo "========================================================================"
echo ""
echo "✅ 检查完成!"
echo ""
echo "下一步:"
echo "  1. 确保 config.yaml 配置正确"
echo "  2. 确保 MySQL 数据库可访问"
echo "  3. 配置腾讯文档 API 凭证"
echo "  4. 启动服务: uvicorn app.main:app --host 0.0.0.0 --port $APP_PORT"
echo ""
echo "访问地址:"
echo "  - API 文档: http://localhost:$APP_PORT/docs"
echo "  - 健康检查: http://localhost:$APP_PORT/health"
echo "  - 监控 Dashboard: http://localhost:$APP_PORT/api/dashboard/overview"
echo ""
echo "========================================================================"

exit 0
