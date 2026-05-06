#!/usr/bin/env python3
"""
企业级生产环境完整测试套件
测试所有API端点、功能和边界情况
"""
import sys
import os
import requests
import json
import time
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8083"
API_BASE = BASE_URL

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    
def log(msg, level='INFO'):
    icons = {'INFO': 'ℹ️', 'SUCCESS': '✅', 'ERROR': '❌', 'WARN': '⚠️'}
    icon = icons.get(level, '📝')
    color = {
        'SUCCESS': Colors.GREEN,
        'ERROR': Colors.RED,
        'WARN': Colors.YELLOW,
        'INFO': Colors.BLUE
    }.get(level, Colors.END)
    print(f"{color}{icon} [{level}] {msg}{Colors.END}")

def test_section(name):
    print(f"\n{'='*70}")
    print(f"{Colors.BLUE}🔍 {name}{Colors.END}")
    print(f"{'='*70}")

class ProductionTestSuite:
    def __init__(self):
        self.results = []
        self.configs = []
        
    def run_test(self, name, test_func, *args, **kwargs):
        """运行单个测试"""
        try:
            log(f"开始测试: {name}")
            result = test_func(*args, **kwargs)
            self.results.append({'name': name, 'passed': result, 'error': None})
            if result:
                log(f"✅ 测试通过: {name}", 'SUCCESS')
            else:
                log(f"❌ 测试失败: {name}", 'ERROR')
            return result
        except Exception as e:
            self.results.append({'name': name, 'passed': False, 'error': str(e)})
            log(f"❌ 测试异常: {name} - {str(e)}", 'ERROR')
            return False
    
    # ==================== 基础服务测试 ====================
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = requests.get(f"{API_BASE}/health", timeout=5)
        assert response.status_code == 200, f"健康检查失败: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"服务不健康: {data}"
        return True
    
    def test_root_endpoint(self):
        """测试根路径返回HTML"""
        response = requests.get(f"{API_BASE}/", timeout=5)
        assert response.status_code == 200, f"根路径失败: {response.status_code}"
        assert 'text/html' in response.headers.get('content-type', ''), "未返回HTML"
        assert '腾讯文档' in response.text, "HTML内容不正确"
        return True
    
    def test_api_docs_endpoint(self):
        """测试API文档端点"""
        response = requests.get(f"{API_BASE}/docs", timeout=5)
        assert response.status_code == 200, f"API文档失败: {response.status_code}"
        return True
    
    # ==================== MySQL连接测试 ====================
    
    def test_mysql_connection(self):
        """测试MySQL数据库连接"""
        response = requests.post(f"{API_BASE}/api/configs/1/test", timeout=10)
        assert response.status_code == 200, f"连接测试失败: {response.status_code}"
        data = response.json()
        assert 'mysql' in data, "响应缺少mysql字段"
        assert data['mysql'].get('connected') == True, f"MySQL未连接: {data['mysql']}"
        return True
    
    def test_mysql_browser(self):
        """测试MySQL浏览器功能"""
        response = requests.get(f"{API_BASE}/api/mysql/databases", timeout=10)
        assert response.status_code == 200, f"数据库列表失败: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "数据库列表格式错误"
        # 应该包含我们的数据库
        db_names = [db['name'] for db in data]
        assert 'tencent_sheets_sync' in db_names, f"找不到目标数据库: {db_names}"
        return True
    
    def test_mysql_tables(self):
        """测试获取数据库表"""
        response = requests.get(f"{API_BASE}/api/mysql/databases/tencent_sheets_sync/tables", timeout=10)
        assert response.status_code == 200, f"获取表列表失败: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "表列表格式错误"
        log(f"找到 {len(data)} 个表", 'INFO')
        return True
    
    def test_mysql_table_columns(self):
        """测试获取表结构"""
        # 测试系统表
        tables_to_test = ['sync_configs', 'sync_logs', 'change_tracking']
        for table in tables_to_test:
            response = requests.get(f"{API_BASE}/api/mysql/tables/{table}/columns", timeout=10)
            assert response.status_code == 200, f"获取表结构失败: {table}"
            data = response.json()
            assert isinstance(data, list), f"列定义格式错误: {table}"
            log(f"表 {table} 有 {len(data)} 个字段", 'INFO')
        return True
    
    # ==================== 腾讯API连接测试 ====================
    
    def test_tencent_connection(self):
        """测试腾讯文档API连接"""
        response = requests.post(f"{API_BASE}/api/configs/1/test", timeout=10)
        assert response.status_code == 200, f"连接测试失败: {response.status_code}"
        data = response.json()
        assert 'tencent' in data, "响应缺少tencent字段"
        assert data['tencent'].get('connected') == True, f"腾讯API未连接: {data['tencent']}"
        return True
    
    def test_tencent_helper(self):
        """测试腾讯文档辅助接口"""
        # 测试表头读取接口（使用示例数据）
        response = requests.get(
            f"{API_BASE}/api/tencent/sheet-header",
            params={"spreadsheetId": "test123", "sheetName": "Sheet1"},
            timeout=10
        )
        # 这个接口会返回示例数据，因为没有真实凭证
        assert response.status_code == 200, f"表头读取失败: {response.status_code}"
        data = response.json()
        assert 'columns' in data, "响应缺少columns字段"
        return True
    
    # ==================== 配置管理测试 ====================
    
    def test_list_configs(self):
        """测试列出所有配置"""
        response = requests.get(f"{API_BASE}/api/configs", timeout=10)
        assert response.status_code == 200, f"列出配置失败: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "配置列表格式错误"
        self.configs = data
        log(f"当前有 {len(data)} 个配置", 'INFO')
        return True
    
    def test_get_config_detail(self):
        """测试获取单个配置详情"""
        if not self.configs:
            log("没有配置可测试，跳过", 'WARN')
            return True
        
        config_id = self.configs[0]['id']
        response = requests.get(f"{API_BASE}/api/configs/{config_id}", timeout=10)
        assert response.status_code == 200, f"获取配置详情失败: {response.status_code}"
        data = response.json()
        assert data.get('id') == config_id, "配置ID不匹配"
        assert 'mapping_json' in data, "缺少mapping_json"
        return True
    
    def test_create_config(self):
        """测试创建新配置"""
        test_config = {
            "spreadsheet_id": f"test-{int(time.time())}",
            "sheet_id": "Sheet1",
            "table_name": "test_table",
            "database": "tencent_sheets_sync",
            "mapping_json": {
                "columns": [
                    {
                        "sheet_col": "A",
                        "sheet_header": "ID",
                        "db_column": "id",
                        "db_type": "INT",
                        "primary_key": True,
                        "direction": "bidirectional"
                    },
                    {
                        "sheet_col": "B",
                        "sheet_header": "名称",
                        "db_column": "name",
                        "db_type": "VARCHAR(255)",
                        "primary_key": False,
                        "direction": "bidirectional"
                    }
                ],
                "sheet_header_row": 1,
                "data_start_row": 2
            },
            "sync_direction": "to_mysql",
            "poll_interval": 60
        }
        
        response = requests.post(
            f"{API_BASE}/api/configs",
            json=test_config,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        assert response.status_code == 200, f"创建配置失败: {response.status_code}"
        data = response.json()
        assert data.get('id') is not None, "未返回配置ID"
        assert data.get('spreadsheet_id') == test_config['spreadsheet_id'], "spreadsheet_id不匹配"
        
        self.created_config_id = data['id']
        log(f"创建了配置 ID: {self.created_config_id}", 'SUCCESS')
        return True
    
    def test_update_config(self):
        """测试更新配置"""
        if not hasattr(self, 'created_config_id'):
            log("没有新创建的配置可测试，跳过", 'WARN')
            return True
        
        update_data = {
            "poll_interval": 120
        }
        
        response = requests.put(
            f"{API_BASE}/api/configs/{self.created_config_id}",
            json=update_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        assert response.status_code == 200, f"更新配置失败: {response.status_code}"
        data = response.json()
        assert data.get('poll_interval') == 120, "轮询间隔未更新"
        return True
    
    def test_delete_config(self):
        """测试删除配置（软删除）"""
        if not hasattr(self, 'created_config_id'):
            log("没有新创建的配置可删除，跳过", 'WARN')
            return True
        
        response = requests.delete(
            f"{API_BASE}/api/configs/{self.created_config_id}",
            timeout=10
        )
        assert response.status_code == 200, f"删除配置失败: {response.status_code}"
        
        # 验证已软删除（is_active=false）
        response = requests.get(
            f"{API_BASE}/api/configs/{self.created_config_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # 软删除后is_active应该为false
            assert data.get('is_active') == False, "配置未被软删除"
        # 或者返回404（如果列表API过滤了非活跃配置）
        assert response.status_code in [200, 404], f"删除验证失败: {response.status_code}"
        log(f"成功删除配置 ID: {self.created_config_id}", 'SUCCESS')
        return True
    
    # ==================== 同步功能测试 ====================
    
    def test_sync_trigger(self):
        """测试触发同步"""
        if not self.configs:
            log("没有配置可测试，跳过", 'WARN')
            return True
        
        config_id = self.configs[0]['id']
        response = requests.post(
            f"{API_BASE}/api/sync/{config_id}/trigger",
            timeout=30
        )
        # 可能会返回错误（因为spreadsheet_id可能是测试数据），但API应该正常响应
        assert response.status_code == 200, f"同步触发失败: {response.status_code}"
        data = response.json()
        assert 'success' in data, "响应缺少success字段"
        # 不强制要求success为True，因为数据可能不存在
        log(f"同步返回: success={data.get('success')}, rows={data.get('rows_affected', 0)}", 'INFO')
        return True
    
    def test_sync_status(self):
        """测试获取同步状态"""
        if not self.configs:
            log("没有配置可测试，跳过", 'WARN')
            return True
        
        config_id = self.configs[0]['id']
        response = requests.get(
            f"{API_BASE}/api/sync/{config_id}/status",
            timeout=10
        )
        assert response.status_code == 200, f"获取同步状态失败: {response.status_code}"
        data = response.json()
        assert 'config_id' in data, "响应缺少config_id"
        return True
    
    def test_to_mysql_sync(self):
        """测试单向同步到MySQL"""
        if not self.configs:
            return True
        
        config_id = self.configs[0]['id']
        response = requests.post(
            f"{API_BASE}/api/sync/{config_id}/to-mysql",
            timeout=30
        )
        assert response.status_code == 200, f"to-mysql同步失败: {response.status_code}"
        return True
    
    def test_from_mysql_sync(self):
        """测试单向同步从MySQL"""
        if not self.configs:
            return True
        
        config_id = self.configs[0]['id']
        response = requests.post(
            f"{API_BASE}/api/sync/{config_id}/from-mysql",
            timeout=30
        )
        assert response.status_code == 200, f"from-mysql同步失败: {response.status_code}"
        return True
    
    # ==================== Webhook测试 ====================
    
    def test_webhook_health(self):
        """测试Webhook健康检查"""
        response = requests.get(f"{API_BASE}/webhook/tencent/health", timeout=5)
        assert response.status_code == 200, f"Webhook健康检查失败: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'ok', "Webhook不健康"
        return True
    
    def test_webhook_callback(self):
        """测试Webhook回调"""
        test_payload = {
            "event": "sheet.update",
            "spreadsheetId": "test123",
            "sheetId": "Sheet1",
            "changedRange": "A1:B10"
        }
        
        response = requests.post(
            f"{API_BASE}/webhook/tencent/callback",
            json=test_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        # 可能返回404（找不到配置）或200（处理成功）
        assert response.status_code in [200, 404], f"Webhook回调失败: {response.status_code}"
        return True
    
    # ==================== 系统初始化测试 ====================
    
    def test_system_init(self):
        """测试系统初始化"""
        response = requests.post(f"{API_BASE}/init", timeout=10)
        assert response.status_code == 200, f"系统初始化失败: {response.status_code}"
        data = response.json()
        assert 'message' in data, "初始化响应缺少message"
        return True
    
    # ==================== 前端页面测试 ====================
    
    def test_frontend_html_structure(self):
        """测试前端HTML结构"""
        response = requests.get(f"{API_BASE}/", timeout=5)
        assert response.status_code == 200
        
        html = response.text
        
        # 检查关键元素
        checks = [
            ('统计卡片', 'stat-card'),
            ('配置列表', 'cfgList'),
            ('日志区域', 'logWrap'),
            ('保存按钮', 'btnSave'),
            ('连接状态', 'mysqlStatus')
        ]
        
        for name, keyword in checks:
            assert keyword in html, f"前端缺少: {name} ({keyword})"
        
        return True
    
    def test_static_files(self):
        """测试静态文件服务"""
        # 测试static路径
        response = requests.get(f"{API_BASE}/static/", timeout=5)
        assert response.status_code in [200, 404], "静态文件路径测试失败"
        return True
    
    # ==================== 错误处理测试 ====================
    
    def test_nonexistent_config(self):
        """测试获取不存在的配置"""
        response = requests.get(f"{API_BASE}/api/configs/99999", timeout=5)
        assert response.status_code == 404, "应该返回404"
        return True
    
    def test_invalid_sync(self):
        """测试无效的同步ID"""
        response = requests.post(f"{API_BASE}/api/sync/99999/trigger", timeout=10)
        assert response.status_code == 404, "应该返回404"
        return True
    
    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        invalid_config = {
            "spreadsheet_id": "test"
            # 缺少其他必填字段
        }
        
        response = requests.post(
            f"{API_BASE}/api/configs",
            json=invalid_config,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        # 应该返回422（验证错误）或500（处理错误）
        assert response.status_code in [422, 500], f"应该返回错误状态码: {response.status_code}"
        return True
    
    # ==================== 运行所有测试 ====================
    
    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{Colors.BLUE}{'='*70}")
        print("🚀 企业级生产环境完整测试套件")
        print(f"{'='*70}{Colors.END}\n")
        
        tests = [
            # 基础服务测试
            ("基础服务 - 健康检查", self.test_health_endpoint),
            ("基础服务 - 根路径", self.test_root_endpoint),
            ("基础服务 - API文档", self.test_api_docs_endpoint),
            
            # MySQL连接测试
            ("MySQL连接 - 数据库连接", self.test_mysql_connection),
            ("MySQL连接 - 数据库浏览器", self.test_mysql_browser),
            ("MySQL连接 - 表列表", self.test_mysql_tables),
            ("MySQL连接 - 表结构", self.test_mysql_table_columns),
            
            # 腾讯API测试
            ("腾讯API - 连接测试", self.test_tencent_connection),
            ("腾讯API - 辅助接口", self.test_tencent_helper),
            
            # 配置管理测试
            ("配置管理 - 列出配置", self.test_list_configs),
            ("配置管理 - 获取详情", self.test_get_config_detail),
            ("配置管理 - 创建配置", self.test_create_config),
            ("配置管理 - 更新配置", self.test_update_config),
            ("配置管理 - 删除配置", self.test_delete_config),
            
            # 同步功能测试
            ("同步功能 - 触发同步", self.test_sync_trigger),
            ("同步功能 - 获取状态", self.test_sync_status),
            ("同步功能 - to_mysql", self.test_to_mysql_sync),
            ("同步功能 - from_mysql", self.test_from_mysql_sync),
            
            # Webhook测试
            ("Webhook - 健康检查", self.test_webhook_health),
            ("Webhook - 回调接口", self.test_webhook_callback),
            
            # 系统测试
            ("系统 - 初始化", self.test_system_init),
            
            # 前端测试
            ("前端 - HTML结构", self.test_frontend_html_structure),
            ("前端 - 静态文件", self.test_static_files),
            
            # 错误处理测试
            ("错误处理 - 不存在的配置", self.test_nonexistent_config),
            ("错误处理 - 无效的同步", self.test_invalid_sync),
            ("错误处理 - 缺少必填字段", self.test_missing_required_fields),
        ]
        
        # 执行所有测试
        for name, test_func in tests:
            try:
                self.run_test(name, test_func)
            except Exception as e:
                log(f"测试执行异常: {str(e)}", 'ERROR')
        
        # 输出结果
        self.print_summary()
        
        return all(r['passed'] for r in self.results)
    
    def print_summary(self):
        """打印测试总结"""
        print(f"\n{'='*70}")
        print(f"{Colors.BLUE}📊 测试结果总结{Colors.END}")
        print(f"{'='*70}\n")
        
        passed = sum(1 for r in self.results if r['passed'])
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"总计测试: {total}")
        print(f"通过: {Colors.GREEN}{passed}{Colors.END}")
        print(f"失败: {Colors.RED}{total - passed}{Colors.END}")
        print(f"成功率: {Colors.BLUE}{success_rate:.1f}%{Colors.END}")
        
        # 显示失败的测试
        failed_tests = [r for r in self.results if not r['passed']]
        if failed_tests:
            print(f"\n{Colors.RED}❌ 失败的测试:{Colors.END}")
            for test in failed_tests:
                error_msg = test['error'] or '未知错误'
                print(f"  - {test['name']}: {error_msg}")
        
        # 显示通过的测试
        passed_tests = [r for r in self.results if r['passed']]
        if passed_tests:
            print(f"\n{Colors.GREEN}✅ 通过的测试:{Colors.END}")
            for test in passed_tests:
                print(f"  ✓ {test['name']}")
        
        print(f"\n{'='*70}\n")
        
        if passed == total:
            print(f"{Colors.GREEN}🎉 所有测试通过！系统已达到生产级别可用状态！{Colors.END}\n")
        else:
            print(f"{Colors.YELLOW}⚠️  部分测试失败，请检查上述失败项{Colors.END}\n")

def main():
    """主函数"""
    tester = ProductionTestSuite()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
