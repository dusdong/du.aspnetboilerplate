using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using Abp.AspNetCore;
using Abp.AspNetCore.Dependency;
using Abp.Dependency;
using Abp.Domain.Entities;
using Abp.Domain.Repositories;
using Abp.Domain.Uow;
using Abp.EntityFrameworkCore;
using Abp.EntityFrameworkCore.Configuration;
using Abp.EntityFrameworkCore.Repositories;
using Abp.Modules;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;

using var host = Host.CreateDefaultBuilder(args)
    .UseCastleWindsor(IocManager.Instance.IocContainer)
    .ConfigureWebHostDefaults(web => web.UseStartup<Startup>().UseUrls("http://127.0.0.1:0"))
    .Build();
await host.StartAsync();
var address = host.Services.GetRequiredService<IServer>()
    .Features.Get<IServerAddressesFeature>()!.Addresses.Single();
Console.WriteLine("R2_LISTEN " + address);
await host.WaitForShutdownAsync();

public sealed class Startup
{
    public void ConfigureServices(IServiceCollection services)
    {
        services.AddControllers();
        services.AddScoped<RequestScope>();
        services.AddAbpWithoutCreatingServiceProvider<ConsumerModule>();
    }

    public void Configure(IApplicationBuilder app)
    {
        app.UseAbp();
        var options = new DbContextOptionsBuilder<ConsumerDbContext>().UseSqlite(ConsumerModule.Connection);
        using (var db = new ConsumerDbContext(options.Options))
        {
            db.Database.EnsureCreated();
        }

        app.UseRouting();
        app.UseEndpoints(endpoints =>
        {
            endpoints.MapPost("/records", async http =>
            {
                var input = await http.Request.ReadFromJsonAsync<RecordInput>()
                    ?? throw new InvalidOperationException("缺少记录输入。");
                var service = http.RequestServices.GetRequiredService<RecordService>();
                var scope = http.RequestServices.GetRequiredService<RequestScope>();
                var evidence = await service.InsertAsync(input, http.TraceIdentifier, scope.Id);
                http.Response.StatusCode = StatusCodes.Status201Created;
                await http.Response.WriteAsJsonAsync(evidence);
            });
            endpoints.MapGet("/records", async http =>
            {
                var service = http.RequestServices.GetRequiredService<RecordService>();
                var scope = http.RequestServices.GetRequiredService<RequestScope>();
                await http.Response.WriteAsJsonAsync(await service.ReadAsync(http.TraceIdentifier, scope.Id));
            });
        });
    }
}

[DependsOn(typeof(AbpAspNetCoreModule), typeof(AbpEntityFrameworkCoreModule))]
public sealed class ConsumerModule : AbpModule
{
    internal static string Connection => new SqliteConnectionStringBuilder
    {
        DataSource = Path.GetFullPath("consumer.sqlite"),
        Pooling = false
    }.ToString();

    public bool Initialized { get; private set; }

    public override void PreInitialize()
    {
        Configuration.DefaultNameOrConnectionString = Connection;
        Configuration.UnitOfWork.IsolationLevel = System.Transactions.IsolationLevel.Serializable;
        Configuration.Modules.AbpEfCore().AddDbContext<ConsumerDbContext>(
            options => options.DbContextOptions.UseSqlite(options.ConnectionString));
    }

    public override void Initialize() => IocManager.RegisterAssemblyByConvention(typeof(ConsumerModule).Assembly);

    public override void PostInitialize() => Initialized = true;
}

public sealed class ConsumerDbContext(DbContextOptions<ConsumerDbContext> options) : AbpDbContext(options)
{
    public DbSet<StoredRecord> Records => Set<StoredRecord>();
}

public sealed class StoredRecord : Entity<Guid>
{
    public string Value { get; set; } = "";
}

public sealed record RecordInput(Guid Id, string Value);

public sealed class RequestScope
{
    public Guid Id { get; } = Guid.NewGuid();
}

public sealed class RecordService(
    IUnitOfWorkManager units, IRepository<StoredRecord, Guid> repository, ConsumerModule module)
    : ITransientDependency
{
    public async Task<object> InsertAsync(RecordInput input, string request, Guid scope)
    {
        using var handle = units.Begin(new UnitOfWorkOptions { IsTransactional = true });
        var unit = units.Current;
        var unitId = Guid.NewGuid();
        var db = await ((IRepositoryWithDbContext)repository).GetDbContextAsync();
        var transaction = db.Database.CurrentTransaction
            ?? throw new InvalidOperationException("仓储 DbContext 缺少写入事务。");
        await repository.InsertAsync(new StoredRecord { Id = input.Id, Value = input.Value });
        var active = new
        {
            request, unitId, transactionId = transaction.TransactionId,
            transactional = unit.Options.IsTransactional,
            providerTransaction = transaction.GetDbTransaction().GetType().FullName,
            connectionOpen = transaction.GetDbTransaction().Connection?.State == System.Data.ConnectionState.Open
        };
        unit.Items["R2ProbeUnitId"] = unitId;
        object? committed = null;
        unit.Completed += (sender, _) =>
        {
            if (!ReferenceEquals(sender, unit))
                throw new InvalidOperationException("完成事件来自另一工作单元。");
            committed = new
            {
                request, unitId, transactionId = transaction.TransactionId,
                eventName = nameof(unit.Completed), transactionCleared = db.Database.CurrentTransaction is null
            };
        };
        await handle.CompleteAsync();
        if (committed is null)
            throw new InvalidOperationException("工作单元缺少提交完成事件。");
        return new { input.Id, input.Value, request, scope, unitId, contextId = db.ContextId.InstanceId, active, committed };
    }

    public async Task<object> ReadAsync(string request, Guid scope)
    {
        using var handle = units.Begin(new UnitOfWorkOptions { IsTransactional = false });
        var unitId = Guid.NewGuid();
        if (units.Current.Items.ContainsKey("R2ProbeUnitId"))
            throw new InvalidOperationException("读回沿用了写入工作单元。");
        var db = await ((IRepositoryWithDbContext)repository).GetDbContextAsync();
        var records = (await repository.GetAllListAsync()).Select(record => new
        {
            record.Id, record.Value
        }).ToArray();
        var provider = db.Database.ProviderName;
        await handle.CompleteAsync();

        return new
        {
            request, scope, unitId, contextId = db.ContextId.InstanceId, records, provider,
            moduleInitialized = module.Initialized,
            modules = new[] { typeof(ConsumerModule).FullName, typeof(AbpAspNetCoreModule).FullName,
                typeof(AbpEntityFrameworkCoreModule).FullName },
            service = GetType().FullName,
            repository = repository.GetType().FullName,
            runtime = new
            {
                architecture = RuntimeInformation.ProcessArchitecture.ToString(),
                rid = RuntimeInformation.RuntimeIdentifier,
                process = Environment.ProcessPath,
                pid = Environment.ProcessId,
                framework = RuntimeInformation.FrameworkDescription,
                netCore = typeof(object).Assembly.Location,
                aspNetCore = typeof(WebApplication).Assembly.Location
            },
            sqliteVersion = SQLitePCL.raw.sqlite3_libversion().utf8_to_string(),
            sqliteAssembly = Identify(typeof(SqliteConnection).Assembly),
            providerAssembly = Identify(typeof(SqliteDbContextOptionsBuilderExtensions).Assembly),
            nativeSqlite = IdentifyNativeSqlite(),
            frameworkAssemblies = AppDomain.CurrentDomain.GetAssemblies()
                .Where(assembly => assembly.GetName().Name is { } name &&
                    (name == "Abp" || name.StartsWith("Abp.", StringComparison.Ordinal)))
                .Select(Identify).ToArray()
        };
    }

    private static object Identify(Assembly assembly) => new
    {
        assembly.Location, assembly.FullName, sha256 = Digest(assembly.Location)
    };

    private static string Digest(string path)
    {
        using var file = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(file));
    }

    private static object IdentifyNativeSqlite()
    {
        var images = Enumerable.Range(0, (int)NativeImageCount())
            .Select(index => Marshal.PtrToStringUTF8(NativeImageName((uint)index)))
            .Where(path => Path.GetFileName(path) == "libe_sqlite3.dylib")
            .ToArray();
        var path = images.Single()!;
        return new { path, sha256 = Digest(path) };
    }

    [DllImport("libSystem.B.dylib", EntryPoint = "_dyld_image_count")]
    private static extern uint NativeImageCount();

    [DllImport("libSystem.B.dylib", EntryPoint = "_dyld_get_image_name")]
    private static extern IntPtr NativeImageName(uint index);
}
