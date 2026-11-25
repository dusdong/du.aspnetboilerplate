using System.Data.Common;
using Abp.Authorization.Roles;
using Abp.Authorization.Users;
using Abp.Domain.Repositories;
using Abp.Domain.Uow;
using Abp.EntityFrameworkCore.Configuration;
using Abp.Modules;
using Abp.MultiTenancy;
using Abp.Zero.EntityFrameworkCore;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;

namespace ModuleZeroProbe;

[DependsOn(typeof(AbpZeroCoreEntityFrameworkCoreModule))]
public sealed class ProbeModule : AbpModule
{
    internal static string DatabasePath => Path.GetFullPath("roles.sqlite");

    public override void PreInitialize()
    {
        Configuration.MultiTenancy.IsEnabled = true;
        Configuration.BackgroundJobs.IsJobExecutionEnabled = false;
        Configuration.DefaultNameOrConnectionString = new SqliteConnectionStringBuilder
        {
            DataSource = DatabasePath,
            Pooling = false
        }.ToString();
        Configuration.UnitOfWork.IsolationLevel = System.Transactions.IsolationLevel.Serializable;
        Configuration.Modules.AbpEfCore().AddDbContext<ProbeDbContext>(options =>
        {
            if (options.ExistingConnection is { } connection)
                options.DbContextOptions.UseSqlite(connection);
            else
                options.DbContextOptions.UseSqlite(options.ConnectionString);

            options.DbContextOptions.AddInterceptors(IocManager.Resolve<TransactionLog>());
        });
    }

    public override void Initialize() => IocManager.RegisterAssemblyByConvention(typeof(ProbeModule).Assembly);
}

public sealed class ProbeDbContext(DbContextOptions<ProbeDbContext> options)
    : AbpZeroDbContext<Tenant, Role, User, ProbeDbContext>(options);

public sealed class Tenant : AbpTenant<User>
{
    private Tenant() { }

    public Tenant(string name) : base(name, name) => IsActive = true;
}

public sealed class Role : AbpRole<User>
{
    public Role() { }

    public Role(int tenantId, string name) : base(tenantId, name, name) { }
}

public sealed class User : AbpUser<User>;

public sealed class RoleStore : AbpRoleStore<Role, User>
{
    internal IRepository<Role> Repository { get; }

    public RoleStore(IUnitOfWorkManager units, IRepository<Role> roles,
        IRepository<RolePermissionSetting, long> permissions) : base(units, roles, permissions)
    {
        Repository = roles;
    }
}

public sealed class ScopeIdentity
{
    public Guid Id { get; } = Guid.NewGuid();
}

public sealed class TransactionLog : DbTransactionInterceptor
{
    private int _sequence;
    public List<CommitEvent> Commits { get; } = [];

    public int Next() => ++_sequence;

    public override void TransactionCommitted(DbTransaction transaction, TransactionEndEventData eventData) =>
        RecordCommit(transaction, eventData);

    public override Task TransactionCommittedAsync(
        DbTransaction transaction, TransactionEndEventData eventData, CancellationToken cancellationToken = default)
    {
        RecordCommit(transaction, eventData);
        return Task.CompletedTask;
    }

    private void RecordCommit(DbTransaction transaction, TransactionEndEventData eventData) =>
        Commits.Add(new(Next(), eventData.TransactionId,
            eventData.Context!.ContextId.InstanceId, transaction.GetType().FullName!));
}

public sealed record CommitEvent(int Sequence, Guid TransactionId, Guid ContextId, string TransactionType);
