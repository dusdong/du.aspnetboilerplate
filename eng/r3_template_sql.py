"""原版模板专用 SQL Server 测试库的迁移前预检、独立读回和恢复。"""

from contextlib import closing
import posixpath
import re
import uuid

from verify import require, sha256


TENANCY, ADMIN, PERMISSION = "Default", "admin", "Pages.Users"
SUCCESS = 1  # AbpLoginResultType.Success


def sql_literal(value):
    return "N'" + value.replace("'", "''") + "'"


class RuntimeDatabase:
    def __init__(self, config, user, password, run_id):
        import pymssql

        self.client = pymssql
        self.config = config
        self.user = user
        self.password = password
        self.source = f"r3_template_{run_id}_source"
        self.restored = f"r3_template_{run_id}_restore"
        self.name = f"r3_template_{run_id}.bak"
        self.server_backup = posixpath.join(config["sqlBackupDirectory"], self.name)
        self.local_backup = config["localBackupDirectory"] / self.name
        require(re.fullmatch(r"[0-9a-f]{16}", run_id), "SQL Server 本轮标识不符")
        self.commands = []

    def query(self, database, statement, parameters=None):
        record = {"database": database, "statement": statement, "parameters": parameters, "exitCode": None}
        self.commands.append(record)
        try:
            with closing(self.client.connect(
                server="127.0.0.1", port=str(self.config["sqlPort"]), user=self.user,
                password=self.password, database=database, login_timeout=8, timeout=120,
                autocommit=True, encryption="require",
            )) as connection:
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(statement, parameters)
                    rows = cursor.fetchall() if cursor.description is not None else []
        except self.client.Error:
            record["exitCode"] = 1
            raise
        record["exitCode"] = 0
        return rows

    def preflight(self):
        identity, = self.query("master", """
SELECT DB_NAME() AS [database], CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS serverName,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS productVersion,
       CONVERT(nvarchar(128), SERVERPROPERTY('ProductLevel')) AS productLevel,
       CONVERT(nvarchar(128), SERVERPROPERTY('Edition')) AS edition,
       CONVERT(nvarchar(260), SERVERPROPERTY('InstanceDefaultDataPath')) AS dataPath,
       CONVERT(nvarchar(260), SERVERPROPERTY('InstanceDefaultLogPath')) AS logPath,
       HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE DATABASE') AS createDatabase,
       HAS_PERMS_BY_NAME(NULL, NULL, 'CREATE ANY DATABASE') AS createAnyDatabase,
       HAS_PERMS_BY_NAME(NULL, NULL, 'ALTER ANY DATABASE') AS alterAnyDatabase
""")
        require(identity["database"] == "master" and identity["serverName"] == self.config["sqlServerName"],
                f"专用 SQL Server 身份不符：预期 {self.config['sqlServerName']}，"
                f"实际 {identity['serverName']} / {identity['edition']}")
        require(any(identity[key] == 1 for key in ("createDatabase", "createAnyDatabase", "alterAnyDatabase")),
                "专用 SQL Server 缺少 CREATE DATABASE、CREATE ANY DATABASE 或 ALTER ANY DATABASE 权限，"
                "无法创建源库、读取备份标头或恢复新库")
        require(identity["dataPath"] and identity["logPath"], "专用 SQL Server 缺少默认数据或日志文件目录")
        self.identity = identity
        for database in (self.source, self.restored):
            self.require_new_database(database)
        directory = self.query("master", "SELECT file_is_a_directory FROM sys.dm_os_file_exists(%s)",
                               (self.config["sqlBackupDirectory"],))
        require(directory == [{"file_is_a_directory": 1}] and self.local_backup.parent.is_dir(),
                "SQL Server 备份目录或本机映射目录不可用")
        self.require_new_backup()
        for target in self.restore_destinations().values():
            self.require_new_server_file(target, "恢复目标")
        return {**identity, "sourceDatabase": self.source, "restoreDatabase": self.restored,
                "serverBackupDirectory": self.config["sqlBackupDirectory"],
                "localBackupDirectory": str(self.local_backup.parent)}

    def require_new_database(self, database):
        # 目标存在但账号无权访问时，HAS_DBACCESS 返回 0。仅不存在的目标返回 NULL。
        rows = self.query("master", "SELECT HAS_DBACCESS(%s) AS targetAccess", (database,))
        require(len(rows) == 1, f"无法核对本轮目标库：{database}")
        require(rows[0]["targetAccess"] is None, f"本轮要求新建数据库，目标已存在：{database}")

    def require_new_server_file(self, path, label):
        rows = self.query("master", """
SELECT file_exists, file_is_a_directory, parent_directory_exists
FROM sys.dm_os_file_exists(%s)
""", (path,))
        require(len(rows) == 1 and rows[0]["parent_directory_exists"] == 1,
                f"无法核对{label}文件目录：{path}")
        require(rows[0]["file_exists"] == 0 and rows[0]["file_is_a_directory"] == 0,
                f"{label}物理路径已存在：{path}")

    def require_new_backup(self):
        require(not (self.local_backup.exists() or self.local_backup.is_symlink()),
                f"本轮备份文件已存在：{self.name}")
        self.require_new_server_file(self.server_backup, "备份目标")

    def restore_destinations(self):
        return {"D": posixpath.join(self.identity["dataPath"], self.restored + ".mdf"),
                "L": posixpath.join(self.identity["logPath"], self.restored + "_log.ldf")}

    def create_source(self):
        self.require_new_database(self.source)
        self.query("master", f"CREATE DATABASE [{self.source}]")
        source, = self.query(self.source, """
SELECT DB_NAME() AS [database], OBJECT_ID(N'dbo.AbpTenants') AS seedTable,
       HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'BACKUP DATABASE') AS backupDatabase
""")
        require(source["database"] == self.source and source["seedTable"] is None, "新建源库身份不符或已有租户表")
        require(source["backupDatabase"] == 1, f"新建源库缺少 BACKUP DATABASE 权限：{self.source}")
        return source

    def connection_string(self, database):
        def value(field):
            return '"' + field.replace('"', '""') + '"'

        require(database in (self.source, self.restored), f"应用连接超出本轮数据库：{database}")
        return (f"Server=tcp:127.0.0.1,{self.config['sqlPort']};Initial Catalog={database};"
                f"User ID={value(self.user)};Password={value(self.password)};"
                "Encrypt=True;TrustServerCertificate=True;Connect Timeout=15;Application Name=R3TemplateRuntime")

    def seed(self, database, expected_migrations):
        applied = self.query(database, """
SELECT MigrationId AS migrationId, ProductVersion AS productVersion
FROM dbo.__EFMigrationsHistory ORDER BY MigrationId
""")
        observed = [row["migrationId"] for row in applied]
        require(observed == expected_migrations, f"{database} 迁移历史不符，预期 {expected_migrations}，实际 {observed}")
        tenants = self.query(database, """
SELECT Id AS tenantId, TenancyName AS tenancyName
FROM dbo.AbpTenants
WHERE TenancyName = %s AND IsDeleted = 0 AND IsActive = 1 AND NULLIF(ConnectionString, '') IS NULL
""", (TENANCY,))
        require(len(tenants) == 1, f"{database} 缺少唯一、有效的 {TENANCY} 共享库租户种子：{tenants}")
        tenant, = tenants
        accounts = self.query(database, """
SELECT u.Id AS userId, u.UserName AS userName, r.Id AS roleId, r.Name AS roleName, p.Name AS permission
FROM dbo.AbpUsers AS u
JOIN dbo.AbpUserRoles AS ur ON ur.UserId = u.Id AND ur.TenantId = u.TenantId
JOIN dbo.AbpRoles AS r ON r.Id = ur.RoleId AND r.TenantId = u.TenantId AND r.IsDeleted = 0
JOIN dbo.AbpPermissions AS p ON p.RoleId = r.Id AND p.TenantId = u.TenantId AND p.IsGranted = 1
WHERE u.TenantId = %s AND u.UserName = %s AND u.IsDeleted = 0 AND u.IsActive = 1
  AND r.Name = N'Admin' AND p.Name = %s
""", (tenant["tenantId"], ADMIN, PERMISSION))
        require(len(accounts) == 1,
                f"{database} 缺少唯一、有效的 {TENANCY}/{ADMIN} 种子或 {PERMISSION} 授权：{accounts}")
        account, = accounts
        return {"migrations": applied, "tenant": tenant, "account": account}

    def business(self, database, expected_migrations, keyword, expected_user):
        seed = self.seed(database, expected_migrations)
        hits = self.query(database, """
SELECT Id AS id, UserName AS userName
FROM dbo.AbpUsers
WHERE TenantId = %s AND IsDeleted = 0
  AND (CHARINDEX(%s, UserName) > 0 OR CHARINDEX(%s, Name) > 0 OR CHARINDEX(%s, EmailAddress) > 0)
ORDER BY Id
""", (seed["tenant"]["tenantId"], keyword, keyword, keyword))
        require(hits == [expected_user], f"{database} 搜索词 {keyword} 的 SQL Server 命中不符：{hits}")
        return {**seed, "keyword": keyword, "matches": hits}

    def login_count(self, database, baseline):
        rows = self.query(database, """
SELECT COUNT_BIG(*) AS [count]
FROM dbo.AbpUserLoginAttempts
WHERE TenantId = %s AND UserId = %s AND Result = %s
""", (baseline["tenant"]["tenantId"], baseline["account"]["userId"], SUCCESS))
        return rows[0]["count"]

    def backup(self):
        self.require_new_backup()
        self.query("master", f"BACKUP DATABASE [{self.source}] TO DISK = %s WITH COPY_ONLY, CHECKSUM",
                   (self.server_backup,))
        self.query("master", "RESTORE VERIFYONLY FROM DISK = %s WITH CHECKSUM", (self.server_backup,))
        header = self.backup_header()
        return {"database": self.source, "serverPath": self.server_backup, "localPath": str(self.local_backup),
                "size": self.local_backup.stat().st_size, "sha256": sha256(self.local_backup),
                "backupSetId": str(uuid.UUID(str(header["BackupSetGUID"]))),
                "backupFinish": header["BackupFinishDate"].isoformat(),
                "method": "BACKUP DATABASE WITH COPY_ONLY, CHECKSUM; RESTORE VERIFYONLY WITH CHECKSUM"}

    def backup_header(self):
        headers = self.query("master", "RESTORE HEADERONLY FROM DISK = %s", (self.server_backup,))
        require(len(headers) == 1, f"备份介质须只包含本轮备份：{self.name}")
        header = headers[0]
        require(header["DatabaseName"] == self.source and header["BackupType"] == 1
                and header["HasBackupChecksums"] and header["IsCopyOnly"] and not header["IsDamaged"],
                f"备份标头的源库、类型或校验状态不符：{self.name}")
        return header

    def restore(self, backup):
        self.require_new_database(self.restored)
        require(sha256(self.local_backup) == backup["sha256"], f"备份摘要变化：{self.local_backup.name}")
        backup_set_id = str(uuid.UUID(str(self.backup_header()["BackupSetGUID"])))
        require(backup_set_id == backup["backupSetId"], f"恢复介质备份集不符：{backup_set_id}")
        files = self.query("master", "RESTORE FILELISTONLY FROM DISK = %s", (self.server_backup,))
        require(len(files) == 2 and {row["Type"] for row in files} == {"D", "L"},
                f"预期单数据文件和单日志文件：{self.name}")
        destinations = self.restore_destinations()
        moves = []
        for file in files:
            target = destinations[file["Type"]]
            self.require_new_server_file(target, "恢复目标")
            moves.append(f"MOVE {sql_literal(file['LogicalName'])} TO {sql_literal(target)}")
        statement = f"RESTORE DATABASE [{self.restored}] FROM DISK = %s WITH CHECKSUM, RECOVERY, {', '.join(moves)}"
        self.query("master", statement, (self.server_backup,))
        status, = self.query(self.restored, """
SELECT DB_NAME() AS name, CONVERT(nvarchar(60), DATABASEPROPERTYEX(DB_NAME(), 'Status')) AS state_desc
""")
        actual_files = self.query(self.restored, "SELECT type AS fileType, physical_name AS path FROM sys.database_files")
        require(status == {"name": self.restored, "state_desc": "ONLINE"} and len(actual_files) == 2
                and {row["fileType"]: row["path"] for row in actual_files} == {0: destinations["D"], 1: destinations["L"]},
                f"恢复库名称、状态或实际物理文件不符：{status} {actual_files}")
        require(sha256(self.local_backup) == backup["sha256"], f"恢复后备份摘要变化：{self.local_backup.name}")
        return {**status, "backupSetId": backup_set_id, "backupSetIdSource": "RESTORE HEADERONLY",
                "files": destinations}
