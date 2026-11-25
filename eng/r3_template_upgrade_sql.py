"""模板升级的行级写入、SQL Server 目录和恢复点观测。"""

from copy import copy
import posixpath

from r3_template_sql import RuntimeDatabase, SUCCESS
from verify import require


CATALOG = {
    "columns": """
SELECT s.name AS [schema], t.name AS [table], c.column_id AS ordinal, c.name AS [column],
       SCHEMA_NAME(ty.schema_id) AS typeSchema, ty.name AS [type], c.max_length AS maxLength,
       c.precision, c.scale, c.collation_name AS collation, c.is_nullable AS nullable,
       c.is_identity AS [identity], CONVERT(nvarchar(128), ic.seed_value) AS identitySeed,
       CONVERT(nvarchar(128), ic.increment_value) AS identityIncrement,
       dc.name AS defaultName, dc.definition AS defaultDefinition,
       cc.definition AS computedDefinition, cc.is_persisted AS persisted,
       c.is_rowguidcol AS rowGuid, c.is_sparse AS sparse, c.generated_always_type_desc AS generated
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
LEFT JOIN sys.identity_columns AS ic ON ic.object_id = c.object_id AND ic.column_id = c.column_id
LEFT JOIN sys.default_constraints AS dc ON dc.object_id = c.default_object_id
LEFT JOIN sys.computed_columns AS cc ON cc.object_id = c.object_id AND cc.column_id = c.column_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id
""",
    "keys": """
SELECT s.name AS [schema], t.name AS [table], k.name AS [key], k.type_desc AS [type],
       ic.key_ordinal AS ordinal, c.name AS [column], ic.is_descending_key AS descending
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.key_constraints AS k ON k.parent_object_id = t.object_id
JOIN sys.index_columns AS ic ON ic.object_id = t.object_id AND ic.index_id = k.unique_index_id
JOIN sys.columns AS c ON c.object_id = t.object_id AND c.column_id = ic.column_id
WHERE t.is_ms_shipped = 0 AND ic.key_ordinal > 0
ORDER BY s.name, t.name, k.name, ic.key_ordinal
""",
    "indexes": """
SELECT s.name AS [schema], t.name AS [table], i.name AS [index], i.type_desc AS [type],
       i.is_unique AS [unique], i.is_primary_key AS primaryKey, i.is_unique_constraint AS uniqueConstraint,
       i.is_disabled AS disabled, i.ignore_dup_key AS ignoreDuplicateKey, i.has_filter AS hasFilter,
       i.filter_definition AS filterDefinition, ic.index_column_id AS indexOrdinal,
       ic.key_ordinal AS keyOrdinal, ic.partition_ordinal AS partitionOrdinal, c.name AS [column],
       ic.is_descending_key AS descending, ic.is_included_column AS included
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.indexes AS i ON i.object_id = t.object_id
LEFT JOIN sys.index_columns AS ic ON ic.object_id = t.object_id AND ic.index_id = i.index_id
LEFT JOIN sys.columns AS c ON c.object_id = t.object_id AND c.column_id = ic.column_id
WHERE t.is_ms_shipped = 0 AND i.index_id > 0 AND i.is_hypothetical = 0
ORDER BY s.name, t.name, i.name, ic.index_column_id
""",
    "foreignKeys": """
SELECT s.name AS [schema], t.name AS [table], fk.name AS foreignKey,
       fkc.constraint_column_id AS ordinal, c.name AS [column], rs.name AS referencedSchema,
       rt.name AS referencedTable, rc.name AS referencedColumn,
       fk.delete_referential_action_desc AS deleteAction, fk.update_referential_action_desc AS updateAction,
       fk.is_disabled AS disabled, fk.is_not_trusted AS notTrusted, fk.is_not_for_replication AS notForReplication
FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.foreign_keys AS fk ON fk.parent_object_id = t.object_id
JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns AS c ON c.object_id = t.object_id AND c.column_id = fkc.parent_column_id
JOIN sys.tables AS rt ON rt.object_id = fkc.referenced_object_id
JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
JOIN sys.columns AS rc ON rc.object_id = rt.object_id AND rc.column_id = fkc.referenced_column_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, fk.name, fkc.constraint_column_id
""",
}


def verify_login_start(rows, candidate, control, count, *, expected=None):
    counts = {database: len(records) for database, records in rows.items()}
    require(counts == {candidate: count, control: 1},
            f"业务起点登录记录预期 {candidate}={count} / {control}=1，实际 {counts}")
    if expected is not None:
        require(rows == expected, f"业务起点未保留登记的登录行：预期 {expected}，实际 {rows}")


def added_login(before, after, candidate, control):
    before_ids = {row["id"] for row in before[candidate]}
    preserved = [row for row in after[candidate] if row["id"] in before_ids]
    added = [row for row in after[candidate] if row["id"] not in before_ids]
    require(after[control] == before[control] and preserved == before[candidate] and len(added) == 1,
            f"登录写入目标或行增量不符：预期 {candidate} 保留原行且新增 1，{control} 保持原行，"
            f"实际前 {before} / 后 {after}")
    return added[0]


class UpgradeDatabase(RuntimeDatabase):
    def __init__(self, config, user, password, run_id, *, frozen_backup=None):
        super().__init__(config, user, password, run_id, frozen_backup=frozen_backup)
        self.prefix = f"r3_template_{run_id}"

    def preflight(self, *, frozen_backup=None):
        identity = super().preflight(frozen_backup=frozen_backup)
        require("Developer" in identity["edition"],
                f"专用 SQL Server 预期 Developer，实际 {identity['edition']}")
        return identity

    def successful_logins(self, database, business):
        return self.query(database, """
SELECT Id AS id, CONVERT(nvarchar(33), CreationTime, 126) AS creationTime, Result AS result,
       TenantId AS tenantId, UserId AS userId, TenancyName AS tenancyName,
       UserNameOrEmailAddress AS loginName
FROM dbo.AbpUserLoginAttempts
WHERE TenantId = %s AND UserId = %s AND Result = %s
ORDER BY Id
""", (business["tenant"]["tenantId"], business["account"]["userId"], SUCCESS))

    def state_identity(self, database):
        row, = self.query(database, """
SELECT DB_NAME() AS [database], DB_ID() AS databaseId,
       CONVERT(nvarchar(36), database_guid) AS databaseGuid,
       CONVERT(nvarchar(36), family_guid) AS familyGuid,
       CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')) AS serverName
FROM sys.database_recovery_status WHERE database_id = DB_ID()
""")
        require(row["database"] == database and row["databaseGuid"]
                and row["serverName"] == self.identity["serverName"],
                f"数据库实际身份不符：{row}")
        row["files"] = self.query(database, "SELECT type_desc AS [type], physical_name AS path "
                                            "FROM sys.database_files ORDER BY file_id")
        return row

    def catalog(self, database):
        catalog = {kind: self.query(database, statement) for kind, statement in CATALOG.items()}
        require(all(catalog.values()) and {"AbpUsers", "AbpTenants", "AbpUserLoginAttempts", "__EFMigrationsHistory"}
                <= {row["table"] for row in catalog["columns"] if row["schema"] == "dbo"},
                "SQL Server 系统目录缺少模板业务表、迁移历史或约束")
        return catalog

    def checkpoint(self, label):
        require(label in ("before_upgrade", "after_upgrade"), f"未知恢复点：{label}")
        # 复用备份及恢复门禁，独立分配介质和恢复库，保留同一 SQL 命令流。
        medium = copy(self)
        medium.restored = f"{self.prefix}_{label}"
        medium.name = medium.restored + ".bak"
        medium.backup_source = self.source
        medium.server_backup = posixpath.join(self.config["sqlBackupDirectory"], medium.name)
        medium.local_backup = self.config["localBackupDirectory"] / medium.name
        return medium

    def restore_diagnostic_start(self, backup):
        # 在隔离诊断轮使用正式轮的介质，新库的名字和物理路径仍归诊断轮。
        self.require_new_database(self.source)
        medium = copy(self)
        medium.name = posixpath.basename(backup["serverPath"])
        medium.backup_source = backup["database"]
        medium.server_backup = posixpath.join(self.config["sqlBackupDirectory"], medium.name)
        medium.local_backup = self.config["localBackupDirectory"] / medium.name
        return medium.restore(backup, database=self.source)
