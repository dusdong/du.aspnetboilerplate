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
                if (Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_REQUESTS") is { } requests)
                {
                    DiagnosticListener.AllListeners.Subscribe(new UserQueryObserver(requests));
                }
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

    private sealed class UserQueryObserver(string evidence)
        : IObserver<DiagnosticListener>, IObserver<KeyValuePair<string, object?>>
    {
        private const string RequestStart = "Microsoft.AspNetCore.Hosting.HttpRequestIn.Start";
        private const string RequestStop = "Microsoft.AspNetCore.Hosting.HttpRequestIn.Stop";
        private const string CommandExecuting = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuting";
        private const string CommandExecuted = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuted";
        private const string UserListPath = "/api/services/app/User/GetAll";
        private readonly Dictionary<string, string> expected = SearchRequests();
        private readonly bool failList = Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_FAIL_LIST") == "1";
        private readonly ConditionalWeakTable<Activity, SearchRequest> requests = new();
        private readonly System.Collections.Concurrent.ConcurrentDictionary<string, string> commands = new();
        private readonly object gate = new();

        public void OnNext(DiagnosticListener listener)
        {
            if (listener.Name == "Microsoft.AspNetCore")
            {
                listener.Subscribe(this, name => name is RequestStart or RequestStop);
            }
            else if (listener.Name == "Microsoft.EntityFrameworkCore")
            {
                listener.Subscribe(this, name => name is CommandExecuting or CommandExecuted);
            }
        }

        public void OnNext(KeyValuePair<string, object?> diagnostic)
        {
            if (diagnostic.Value is not { } payload || Activity.Current is not { } current)
            {
                return;
            }

            if (diagnostic.Key is RequestStart or RequestStop)
            {
                ObserveRequest(diagnostic.Key, payload, current);
                return;
            }

            Activity? request = current;
            SearchRequest? match = null;
            while (request is not null && !requests.TryGetValue(request, out match))
            {
                request = request.Parent;
            }

            if (request is null || match is null || Property(payload, "CommandId")?.ToString() is not { } commandId)
            {
                return;
            }

            var pid = Environment.ProcessId;
            var activityId = request.Id;
            var (requestId, keyword) = match;
            if (diagnostic.Key == CommandExecuted)
            {
                if (commands.TryRemove(commandId, out var completedStep))
                {
                    Write(new { kind = "completed", pid, requestId, activityId, step = completedStep, commandId });
                }
                return;
            }

            if (Property(payload, "Command") is not DbCommand command
                || command.Connection is not { State: ConnectionState.Open } connection
                || !command.CommandText.Contains("FROM [AbpUsers]", StringComparison.Ordinal))
            {
                return;
            }

            // 只跟踪关键词分页的计数和取数。权限、会话等访问 AbpUsers 的命令不带该筛选。
            if (!command.Parameters.Cast<DbParameter>().Any(parameter =>
                parameter.Value is string value && value.Contains(keyword, StringComparison.Ordinal)))
            {
                return;
            }
            var step = command.CommandText.Contains("COUNT(", StringComparison.OrdinalIgnoreCase) ? "count" : "list";

            // 在该 EF 命令实际使用的连接及事务内读取服务器身份。
            using (var probe = connection.CreateCommand())
            {
                probe.Transaction = command.Transaction;
                probe.CommandText = "SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')), DB_NAME(), @@SPID";
                using var reader = probe.ExecuteReader();
                if (!reader.Read())
                {
                    return;
                }
                Write(new
                {
                    kind = "connection", pid, requestId, activityId, step, commandId,
                    serverName = reader.GetString(0), database = reader.GetString(1), sessionId = reader.GetInt16(2),
                    connectionId = Property(payload, "ConnectionId")?.ToString(),
                    clientConnectionId = Property(connection, "ClientConnectionId")?.ToString(),
                    context = Property(payload, "Context")?.GetType().FullName,
                });
            }

            commands.TryAdd(commandId, step);
            if (failList && step == "list")
            {
                throw new InvalidOperationException("R3 回退诊断：关键词用户列表命令失败");
            }
        }

        private void ObserveRequest(string phase, object payload, Activity activity)
        {
            var context = Property(payload, "HttpContext");
            var pid = Environment.ProcessId;
            var activityId = activity.Id;
            if (phase == RequestStop)
            {
                if (requests.TryGetValue(activity, out var match))
                {
                    var status = Property(Property(context, "Response"), "StatusCode");
                    Write(new { kind = "response", pid, requestId = match.Id, activityId, status });
                }
                return;
            }

            var request = Property(context, "Request");
            var method = Property(request, "Method")?.ToString();
            var path = Property(request, "Path")?.ToString();
            if (method != "GET" || path != UserListPath)
            {
                return;
            }

            var query = Property(request, "QueryString")?.ToString() ?? "";
            var fields = query.TrimStart('?').Split('&').Select(Uri.UnescapeDataString).ToArray();
            const string marker = "r3RollbackRequest=";
            var ids = fields.Where(field => field.StartsWith(marker, StringComparison.Ordinal)).ToArray();
            if (ids.Length != 1)
            {
                return;
            }
            var requestId = ids[0][marker.Length..];
            if (!expected.TryGetValue(requestId, out var keyword)
                || fields.Count(field => field == $"Keyword={keyword}") != 1)
            {
                return;
            }
            requests.Add(activity, new SearchRequest(requestId, keyword));
            Write(new { kind = "request", pid, requestId, activityId, method, path, keyword });
        }

        private static Dictionary<string, string> SearchRequests()
        {
            if (Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_SEARCHES") is { } searches)
            {
                return JsonSerializer.Deserialize<Dictionary<string, string>>(searches)
                    ?? throw new InvalidOperationException("缺少模板搜索请求登记");
            }

            var requestId = Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_REQUEST_ID");
            var keyword = Environment.GetEnvironmentVariable("R3_TEMPLATE_OBSERVER_KEYWORD");
            return string.IsNullOrEmpty(requestId) || string.IsNullOrEmpty(keyword)
                ? new Dictionary<string, string>()
                : new Dictionary<string, string> { [requestId] = keyword };
        }

        private sealed record SearchRequest(string Id, string Keyword);

        private static object? Property(object? value, string name) => value?.GetType().GetProperty(name)?.GetValue(value);

        private void Write<T>(T row)
        {
            lock (gate)
            {
                File.AppendAllText(evidence, JsonSerializer.Serialize(row) + Environment.NewLine);
            }
        }

        public void OnCompleted() { }

        public void OnError(Exception error) { }
    }
}
