using System.Data;
using System.Data.Common;
using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;

internal static class StartupHook
{
    public static void Initialize()
    {
        var evidence = Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_EVIDENCE")
            ?? throw new InvalidOperationException("缺少模板进程证据路径");
        switch (Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_MODE"))
        {
            case "host":
                new AssemblyObserver(evidence).Start();
                break;
            case "migrator":
                DiagnosticListener.AllListeners.Subscribe(new MigrationObserver(evidence));
                if (Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_ASSEMBLIES") is { } assemblies)
                {
                    new AssemblyObserver(assemblies).Start();
                }
                break;
            default:
                throw new InvalidOperationException("模板进程证据模式不符");
        }
    }

    private sealed class AssemblyObserver(string evidence)
    {
        private readonly object gate = new();
        private readonly ConditionalWeakTable<Assembly, object> seen = new();
        private readonly ConditionalWeakTable<AssemblyLoadContext, ContextIdentity> contexts = new();
        private readonly List<LoadedAssembly> loaded = new();
        private int nextContext;

        public void Start()
        {
            AppDomain.CurrentDomain.AssemblyLoad += RecordAssembly;
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Record(assembly);
            }

            AppDomain.CurrentDomain.ProcessExit += (_, _) => WriteAssemblies();
        }

        private void RecordAssembly(object? sender, AssemblyLoadEventArgs args) => Record(args.LoadedAssembly);

        private void Record(Assembly assembly)
        {
            lock (gate)
            {
                if (seen.TryGetValue(assembly, out _))
                {
                    return;
                }

                seen.Add(assembly, gate);
                var context = AssemblyLoadContext.GetLoadContext(assembly);
                var identity = context is null ? null : contexts.GetValue(context, _ => new ContextIdentity(++nextContext));
                // 保存观测值，不持有程序集或加载上下文以免阻止卸载。
                loaded.Add(new LoadedAssembly(assembly.GetName().Name, assembly.FullName,
                    assembly.ManifestModule.ModuleVersionId, identity?.Id ?? 0, context?.Name,
                    context == AssemblyLoadContext.Default, assembly.IsDynamic ? "" : assembly.Location));
            }
        }

        private void WriteAssemblies()
        {
            AppDomain.CurrentDomain.AssemblyLoad -= RecordAssembly;
            LoadedAssembly[] assemblies;
            lock (gate)
            {
                assemblies = loaded.ToArray();
            }

            // 只读取已经观测到的磁盘文件，PE 元数据读取不会加载程序集。
            using var output = new FileStream(evidence, FileMode.CreateNew);
            var rows = assemblies.Select(assembly =>
            {
                using var file = assembly.Path.Length == 0 ? null : File.OpenRead(assembly.Path);
                return new
                {
                    name = assembly.Name,
                    fullName = assembly.FullName,
                    diskFullName = file is null ? null : AssemblyName.GetAssemblyName(assembly.Path).FullName,
                    moduleVersionId = assembly.ModuleVersionId,
                    contextId = assembly.ContextId,
                    context = assembly.Context,
                    isDefaultContext = assembly.IsDefaultContext,
                    path = assembly.Path,
                    sha256 = file is null ? null : Convert.ToHexString(SHA256.HashData(file)).ToLowerInvariant(),
                };
            }).ToArray();
            JsonSerializer.Serialize(output, new { pid = Environment.ProcessId, assemblies = rows });
        }

        private sealed record ContextIdentity(int Id);

        private sealed record LoadedAssembly(string? Name, string? FullName, Guid ModuleVersionId, int ContextId,
            string? Context, bool IsDefaultContext, string Path);
    }

    private sealed class MigrationObserver(string evidence)
        : IObserver<DiagnosticListener>, IObserver<KeyValuePair<string, object?>>
    {
        private const string Executing = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuting";

        public void OnNext(DiagnosticListener listener)
        {
            if (listener.Name == "Microsoft.EntityFrameworkCore")
            {
                listener.Subscribe(this, name => name == Executing);
            }
        }

        public void OnNext(KeyValuePair<string, object?> diagnostic)
        {
            if (diagnostic.Key != Executing || diagnostic.Value is not object payload)
            {
                return;
            }

            var type = payload.GetType();
            if (type.GetProperty("Command")?.GetValue(payload) is not DbCommand migrationCommand
                || migrationCommand.Connection is not { State: ConnectionState.Open } connection
                || !migrationCommand.CommandText.Contains("__EFMigrationsHistory", StringComparison.Ordinal))
            {
                return;
            }

            var frames = new StackTrace().GetFrames().Select(frame => frame.GetMethod()).ToArray();
            var migrator = frames.FirstOrDefault(method =>
                method?.DeclaringType?.FullName == "Microsoft.EntityFrameworkCore.Migrations.Internal.Migrator");
            if (migrator is null)
            {
                return;
            }

            // 在迁移命令即将执行的同一连接和事务内读取服务器值。
            using var probe = connection.CreateCommand();
            probe.Transaction = migrationCommand.Transaction;
            probe.CommandText = "SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')), DB_NAME(), @@SPID";
            using var reader = probe.ExecuteReader();
            if (!reader.Read())
            {
                return;
            }

            var row = new
            {
                pid = Environment.ProcessId,
                serverName = reader.GetString(0),
                database = reader.GetString(1),
                sessionId = reader.GetInt16(2),
                connectionId = type.GetProperty("ConnectionId")?.GetValue(payload)?.ToString(),
                commandId = type.GetProperty("CommandId")?.GetValue(payload)?.ToString(),
                clientConnectionId = connection.GetType().GetProperty("ClientConnectionId")?.GetValue(connection)?.ToString(),
                migrator = migrator.DeclaringType!.FullName + "." + migrator.Name,
                context = type.GetProperty("Context")?.GetValue(payload)?.GetType().FullName,
                eventName = diagnostic.Key,
            };
            File.AppendAllText(evidence, JsonSerializer.Serialize(row) + Environment.NewLine);
        }

        public void OnCompleted() { }

        public void OnError(Exception error) { }
    }
}
