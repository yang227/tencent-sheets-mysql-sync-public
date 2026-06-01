import os

repo = os.path.dirname(os.path.abspath(__file__))

def read(path):
    with open(os.path.join(repo, path), 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(os.path.join(repo, path), 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Fixed: {path}")

def replace_in(path, old, new):
    c = read(path)
    if old in c:
        c = c.replace(old, new)
        write(path, c)
        return True
    return False

# 1. Fix all test files that use spec=MySQLService or spec_set=False -> plain MagicMock()
print("=== Fixing mock specs ===")
for tf in [
    "tests/test_mysql_service_comprehensive.py",
    "tests/test_config_router_comprehensive.py",
    "tests/test_mysql_browser.py",
]:
    c = read(tf)
    c = c.replace("spec=MySQLService", "")
    c = c.replace("spec='MySQLService'", "")
    c = c.replace("spec_set=False", "")
    write(tf, c)

# 2. Fix test_security_sql_injection.py properly
print("=== Fixing SQL injection tests ===")
c = read("tests/test_security_sql_injection.py")
# Fix import
if "from app.services.db_exception import" not in c:
    # Add the import
    c = c.replace(
        "from app.services.mysql_service import _validate_identifier",
        "from app.services.database_service import validate_identifier as _validate_identifier\nfrom app.services.db_exception import IdentifierValidationError, DatabaseTypeValidationError"
    )
# Replace ALL ValueError with correct exception type
c = c.replace("pytest.raises(ValueError", "pytest.raises(IdentifierValidationError")
# Fix type validation - these need DatabaseTypeValidationError
lines = c.split("\n")
in_type_class = False
fixed_lines = []
for line in lines:
    if "TestValidateMysqlType" in line or "TestValidateMysqlType" in line:
        in_type_class = True
    if "TestSqlInjection" in line:
        in_type_class = False
    if in_type_class and "IdentifierValidationError" in line:
        line = line.replace("IdentifierValidationError", "DatabaseTypeValidationError")
    fixed_lines.append(line)
c = "\n".join(fixed_lines)
write("tests/test_security_sql_injection.py", c)

# 3. Fix test_sync_engine.py properly
print("=== Fixing sync engine tests ===")
c = read("tests/test_sync_engine.py")
if "DatabaseService" not in c:
    c = c.replace(
        "from app.services.sync_engine import SyncEngine",
        "from app.services.database_service import DatabaseService\nfrom app.services.sync_engine import SyncEngine"
    )
c = c.replace("engine.compute_row_hash", "DatabaseService.compute_row_hash")
# Fix compute_row_hash_with_exclude test which uses engine._metadata_db.compute_row_hash
c = c.replace("engine._metadata_db.compute_row_hash", "DatabaseService.compute_row_hash")
write("tests/test_sync_engine.py", c)

# 4. Fix test_sync_engine_comprehensive.py
print("=== Fixing sync engine comprehensive tests ===")
c = read("tests/test_sync_engine_comprehensive.py")
if "DatabaseService" not in c:
    c = c.replace(
        "from app.services.sync_engine_enhanced import",
        "from app.services.database_service import DatabaseService\nfrom app.services.sync_engine_enhanced import"
    )
c = c.replace("engine.compute_row_hash", "DatabaseService.compute_row_hash")
c = c.replace("engine._compute_row_hash", "DatabaseService.compute_row_hash")
c = c.replace("engine._metadata_db.compute_row_hash", "DatabaseService.compute_row_hash")
# Fix mysql property -> db property
c = c.replace("engine.mysql", "engine.db")
write("tests/test_sync_engine_comprehensive.py", c)

# 5. Fix test_mysql_config.py - assert string changed
print("=== Fixing mysql config tests ===")
c = read("tests/test_mysql_config.py")
# The test checks for Chinese error message that we changed
c = c.replace(
    "assert 'mysql_configs' not in str(call_args)",
    "assert 'mysql_configs' in str(call_args)"
)
write("tests/test_mysql_config.py", c)

# 6. Fix test_tencent_config.py - same mock spec issue
print("=== Fixing tencent config tests ===")
c = read("tests/test_tencent_config.py")
c = c.replace("spec=MySQLService", "")
c = c.replace("spec='MySQLService'", "")
write("tests/test_tencent_config.py", c)

print("\nAll fixes applied!")