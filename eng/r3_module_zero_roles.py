"""校验实际 SQLite 提交、独立读回和租户对照。"""

from contextlib import closing
import re
import sqlite3

from r3_module_zero_assets import SQLITE
from verify import require, sha256


MODULES = {
    "Abp.AbpKernelModule", "Abp.EntityFramework.AbpEntityFrameworkCommonModule",
    "Abp.EntityFrameworkCore.AbpEntityFrameworkCoreModule", "Abp.Zero.AbpZeroCommonModule",
    "Abp.Zero.AbpZeroCoreModule", "Abp.Zero.EntityFrameworkCore.AbpZeroCoreEntityFrameworkCoreModule",
    "ModuleZeroProbe.ProbeModule",
}
DB_TRANSACTION = "Microsoft.Data.Sqlite.SqliteTransaction"


def positive(value):
    return type(value) is int and value > 0


def guid(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value))


def work_identity(work, database, tenant):
    require(work.get("tenantId") == tenant and work.get("mayHaveTenant") is True and
            work.get("provider") == SQLITE and work.get("dataSource") == str(database) and
            work.get("store") == "ModuleZeroProbe.RoleStore",
            f"租户 {tenant} 的 SQLite、实际角色存储或 MayHaveTenant 证据不符")
    identity = tuple(work.get(key) for key in ("scopeId", "unitId", "contextId"))
    require(guid(identity[0]) and isinstance(identity[1], str) and
            re.fullmatch(r"[0-9a-f]{32}", identity[1]) and guid(identity[2]),
            f"租户 {tenant} 缺少有效的 DI 作用域、工作单元或 DbContext 证据")
    return identity


def check_roles(probe, database, marker):
    require(probe.get("marker") == marker and probe.get("database") == str(database) and database.is_file(),
            "消费进程缺少当轮独立 SQLite 数据库")
    require(set(probe.get("modules", [])) == MODULES, "实际初始化的 ABP 模块集合不符")
    tenants, writes, reads = (probe.get(name, []) for name in ("tenants", "writes", "reads"))
    require(len(tenants) == len(writes) == len(reads) == 2, "需要两个有效租户、两笔写入与两组独立读回")
    require(all(positive(tenant.get("id")) and tenant.get("isActive") is True for tenant in tenants) and
            len({tenant["id"] for tenant in tenants}) == 2, "SQLite 中应有两个不同且启用的实际租户")

    commits = probe.get("commits", [])
    identities, sequences, role_data, tenant_data, write_transactions = [], [], [], [], []
    for side, tenant, write in zip(("a", "b"), tenants, writes):
        tenant_id = tenant["id"]
        tag = marker[:24]
        name = f"role-{side}-{tag}"
        require(tenant.get("tenancyName") == f"tenant-{side}-{tag}", f"租户 {tenant_id} 的当轮名称不符")
        tenant_data.append((tenant_id, tenant["tenancyName"], 1))
        work = write.get("work", {})
        identities.append(work_identity(work, database, tenant_id))
        role = write.get("role", {})
        require(positive(role.get("id")) and role.get("tenantId") == tenant_id and role.get("name") == name and
                write.get("succeeded") is True and write.get("transactional") is True,
                f"租户 {tenant_id} 角色写入结果或活动事务证据不符")
        role_data.append((role["id"], name, tenant_id, 0))
        transaction = write.get("transactionId")
        require(guid(transaction), f"租户 {tenant_id} 缺少活动 SQLite 事务 ID")
        matching = [event for event in commits if event.get("transactionId") == transaction]
        require(len(matching) == 1 and matching[0].get("contextId") == work["contextId"] and
                matching[0].get("transactionType") == DB_TRANSACTION,
                f"租户 {tenant_id} 缺少同一角色仓储 DbContext 的 SQLite 事务提交")
        write_transactions.append(transaction)
        sequences.extend([write.get("writtenSequence"), matching[0].get("sequence"),
                          write.get("completedSequence"), write.get("returnSequence")])
    require(len(set(write_transactions)) == len({role[0] for role in role_data}) == 2,
            "两笔写入必须有不同 SQLite 事务和角色 ID")

    for index, read in enumerate(reads):
        tenant = tenants[index]["id"]
        own, other = reads[index].get("own", {}), reads[index].get("other", {})
        identities.append(work_identity(read.get("work", {}), database, tenant))
        expected = writes[index]["role"]
        foreign_id = writes[1 - index]["role"]["id"]
        require(type(own.get("requestedId")) is int and own["requestedId"] == expected["id"] and
                own.get("result") == expected, f"租户 {tenant} 缺少正确的本租户角色读回")
        require(type(other.get("requestedId")) is int and other["requestedId"] == foreign_id and
                "result" in other and other["result"] is None,
                f"租户 {tenant} 缺少跨租户角色 {foreign_id} 明确返回 null 的证据")
        sequences.extend([read.get("startedSequence"), read.get("returnSequence")])
    require(all(len(set(entries)) == 4 for entries in zip(*identities)),
            "两笔写入与两组独立读回必须使用各自的作用域、工作单元和 DbContext")
    require(all(positive(seq) for seq in sequences) and sorted(set(sequences)) == sequences,
            "SQLite 事务提交、ABP 工作单元完成与两次独立读回的顺序不符")

    # 独立只读连接核对两侧角色都确实已经写入同一数据库。
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            stored_tenants = connection.execute("SELECT Id, TenancyName, IsActive FROM AbpTenants").fetchall()
            stored_roles = connection.execute("SELECT Id, Name, TenantId, IsDeleted FROM AbpRoles").fetchall()
    except sqlite3.Error as error:
        raise ValueError(f"SQLite 数据库只读复核失败：{error}") from error
    require(sorted(stored_tenants) == sorted(tenant_data) and sorted(stored_roles) == sorted(role_data),
            "SQLite 文件物理持久化的租户、角色或归属与进程证据不符")
    return {"tenants": tenants, "writes": writes, "reads": reads, "transactionCommits": commits,
            "database": {"path": str(database), "sha256": sha256(database),
                         "rows": {"tenants": stored_tenants, "roles": stored_roles}}}
