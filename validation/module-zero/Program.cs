using System.Globalization;
using System.Text.Json;
using Abp;
using Abp.Dependency;
using Abp.Domain.Repositories;
using Abp.Domain.Uow;
using Abp.EntityFrameworkCore.Repositories;
using Abp.Modules;
using Castle.Windsor.MsDependencyInjection;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace ModuleZeroProbe;

internal static class Program
{
    private static async Task Main(string[] args)
    {
        if (args.Length != 1 || !Guid.TryParseExact(args[0], "N", out _))
            throw new ArgumentException("必须传入当轮验收标识。");
        var marker = args[0];
        var tag = marker[..24];
        Ensure(!File.Exists(ProbeModule.DatabasePath), "SQLite 数据库必须是当轮新文件。");

        using var ioc = new IocManager();
        using var bootstrapper = AbpBootstrapper.Create<ProbeModule>(options => options.IocManager = ioc);
        var services = new ServiceCollection();
        services.AddLogging();
        services.AddSingleton<TransactionLog>();
        services.AddScoped<ScopeIdentity>();
        services.AddAbpIdentity<Tenant, User, Role>().AddAbpRoleStore<RoleStore>();
        var provider = WindsorRegistrationHelper.CreateServiceProvider(ioc.IocContainer, services);
        bootstrapper.Initialize();

        var transactions = provider.GetRequiredService<TransactionLog>();
        var units = provider.GetRequiredService<IUnitOfWorkManager>();
        Tenant[] tenants = [new($"tenant-a-{tag}"), new($"tenant-b-{tag}")];
        using (var scope = provider.CreateScope())
        using (var handle = units.Begin(new UnitOfWorkOptions { IsTransactional = false }))
        {
            var repository = scope.ServiceProvider.GetRequiredService<IRepository<Tenant>>();
            var context = repository.GetDbContext();
            Ensure(await context.Database.EnsureCreatedAsync(), "SQLite schema 已存在。");
            foreach (var tenant in tenants)
                await repository.InsertAsync(tenant);
            await handle.CompleteAsync();
        }

        var first = await Write(provider, units, transactions, tenants[0], $"role-a-{tag}");
        var second = await Write(provider, units, transactions, tenants[1], $"role-b-{tag}");
        var firstRead = await Read(provider, units, transactions, first.Role, second.Role);
        var secondRead = await Read(provider, units, transactions, second.Role, first.Role);

        var modules = ioc.Resolve<IAbpModuleManager>().Modules.Select(module => module.Type.FullName).ToArray();
        var report = new
        {
            marker,
            database = ProbeModule.DatabasePath,
            tenants = tenants.Select(tenant => new { tenant.Id, tenant.TenancyName, tenant.IsActive }).ToArray(),
            writes = new[] { first, second },
            reads = new[] { firstRead, secondRead },
            commits = transactions.Commits,
            modules,
            runtime = RuntimeEvidence.Capture()
        };
        await File.WriteAllTextAsync("probe.json",
            JsonSerializer.Serialize(report, new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true }));
    }

    private static async Task<WriteEvidence> Write(IServiceProvider provider, IUnitOfWorkManager units,
        TransactionLog transactions, Tenant tenant, string name)
    {
        using var scope = provider.CreateScope();
        using var handle = units.Begin(new UnitOfWorkOptions { IsTransactional = true });
        var active = units.Current;
        using var selection = active.SetTenantId(tenant.Id);
        var (store, context, work) = Resolve(scope, active, tenant.Id);
        var transaction = context.Database.CurrentTransaction
            ?? throw new InvalidOperationException("角色仓储缺少活动事务。");
        var role = new Role(tenant.Id, name);
        var result = await store.CreateAsync(role);
        Ensure(result.Succeeded && role.Id > 0, $"角色写入失败：{name}。");

        var written = transactions.Next();
        int completed = 0;
        active.Completed += (_, _) => completed = transactions.Next();
        await handle.CompleteAsync();
        var returned = transactions.Next();
        Ensure(completed > written, $"角色工作单元未发出完成事件：{name}。");
        return new(work, Record(role), result.Succeeded, active.Options.IsTransactional == true,
            transaction.TransactionId, written, completed, returned);
    }

    private static async Task<ReadEvidence> Read(IServiceProvider provider, IUnitOfWorkManager units,
        TransactionLog transactions, RoleRecord own, RoleRecord other)
    {
        using var scope = provider.CreateScope();
        using var handle = units.Begin(new UnitOfWorkOptions { IsTransactional = false });
        var active = units.Current;
        using var selection = active.SetTenantId(own.TenantId);
        var (store, context, work) = Resolve(scope, active, own.TenantId);
        Ensure(!context.ChangeTracker.Entries<Role>().Any(), "读回 DbContext 已跟踪角色。");

        var started = transactions.Next();
        var ownResult = await store.FindByIdAsync(own.Id.ToString(CultureInfo.InvariantCulture));
        var otherResult = await store.FindByIdAsync(other.Id.ToString(CultureInfo.InvariantCulture));
        Ensure(ownResult != null && Record(ownResult) == own, $"本租户角色 {own.Id} 未正确读回。");
        Ensure(otherResult == null, $"跨租户角色 {other.Id} 可见。");
        await handle.CompleteAsync();
        return new(work, started, transactions.Next(), new(own.Id, Record(ownResult!)), new(other.Id, otherResult is null ? null : Record(otherResult)));
    }

    private static (RoleStore, DbContext, WorkEvidence) Resolve(
        IServiceScope scope, IActiveUnitOfWork active, int tenantId)
    {
        var filter = active.IsFilterEnabled(AbpDataFilters.MayHaveTenant);
        Ensure(active.GetTenantId() == tenantId && filter, $"租户 {tenantId} 的 MayHaveTenant 过滤器未启用。");
        var store = (RoleStore)scope.ServiceProvider.GetRequiredService<IRoleStore<Role>>();
        var context = store.Repository.GetDbContext();
        Ensure(context.Database.ProviderName == "Microsoft.EntityFrameworkCore.Sqlite" &&
            context.Database.GetDbConnection().DataSource == ProbeModule.DatabasePath,
            $"租户 {tenantId} 的实际角色仓储或 SQLite 文件不符。");
        var work = new WorkEvidence(scope.ServiceProvider.GetRequiredService<ScopeIdentity>().Id,
            ((UnitOfWorkBase)active).Id, context.ContextId.InstanceId, tenantId, filter,
            context.Database.GetDbConnection().DataSource, context.Database.ProviderName!, typeof(RoleStore).FullName!);
        return (store, context, work);
    }

    private static RoleRecord Record(Role role) =>
        new(role.Id, role.Name, role.TenantId ?? throw new InvalidOperationException("角色归属必须为租户。"));

    private static void Ensure(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException(message);
    }
}

internal sealed record RoleRecord(int Id, string Name, int TenantId);
internal sealed record WorkEvidence(Guid ScopeId, string UnitId, Guid ContextId, int TenantId,
    bool MayHaveTenant, string DataSource, string Provider, string Store);
internal sealed record WriteEvidence(WorkEvidence Work, RoleRecord Role, bool Succeeded, bool Transactional,
    Guid TransactionId, int WrittenSequence, int CompletedSequence, int ReturnSequence);
internal sealed record QueryEvidence(int RequestedId, RoleRecord? Result);
internal sealed record ReadEvidence(WorkEvidence Work, int StartedSequence, int ReturnSequence,
    QueryEvidence Own, QueryEvidence Other);
