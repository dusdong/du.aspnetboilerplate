using System.Collections.Concurrent;
using System.Data;
using System.Data.Common;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.RegularExpressions;

internal sealed class RoleRequestObserver(string evidence, Action<string> onResponse)
    : IObserver<DiagnosticListener>, IObserver<KeyValuePair<string, object?>>
{
    private const string Start = "Microsoft.AspNetCore.Hosting.HttpRequestIn.Start";
    private const string Stop = "Microsoft.AspNetCore.Hosting.HttpRequestIn.Stop";
    private const string Executing = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuting";
    private const string Executed = "Microsoft.EntityFrameworkCore.Database.Command.CommandExecuted";
    private const string Failed = "Microsoft.EntityFrameworkCore.Database.Command.CommandError";
    private const string UserPath = "/api/services/app/User/";
    private static readonly Regex UserKey = new(@"(?:\[\w+\]\.)?\[Id\]\s*=\s*(?<parameter>@\w+)", RegexOptions.CultureInvariant);
    private readonly ConditionalWeakTable<Activity, RequestIdentity> requests = new();
    private readonly ConcurrentDictionary<string, string> commands = new();
    private readonly object gate = new();

    public void OnNext(DiagnosticListener listener)
    {
        if (listener.Name == "Microsoft.AspNetCore")
        {
            listener.Subscribe(this, name => name is Start or Stop);
        }
        else if (listener.Name == "Microsoft.EntityFrameworkCore")
        {
            listener.Subscribe(this, name => name is Executing or Executed or Failed);
        }
    }

    public void OnNext(KeyValuePair<string, object?> diagnostic)
    {
        if (diagnostic.Value is not { } payload || Activity.Current is not { } current)
        {
            return;
        }
        if (diagnostic.Key is Start or Stop)
        {
            ObserveRequest(diagnostic.Key, current, payload);
            return;
        }

        RequestIdentity? request = null;
        for (Activity? activity = current; activity is not null && !requests.TryGetValue(activity, out request);
            activity = activity.Parent) { }
        if (request is null || Property(payload, "CommandId")?.ToString() is not { } commandId)
        {
            return;
        }
        if (diagnostic.Key is Executed or Failed)
        {
            if (commands.TryRemove(commandId, out var operation))
            {
                Write(new { kind = diagnostic.Key == Executed ? "completed" : "failed", request, operation, commandId });
            }
            return;
        }

        if (Property(payload, "Command") is not DbCommand command ||
            command.Connection is not { State: ConnectionState.Open } connection)
        {
            return;
        }

        // EF 的写入批次可由 SET NOCOUNT 开头，也可能紧接角色关系的 INSERT 或 DELETE。
        var statements = command.CommandText.Split(';', StringSplitOptions.TrimEntries);
        var update = statements.FirstOrDefault(sql => sql.StartsWith("UPDATE [AbpUsers]", StringComparison.Ordinal));
        var userSql = update ?? statements.FirstOrDefault(sql => sql.Contains("FROM [AbpUsers]", StringComparison.Ordinal));
        var operationKind = update is null ? "lookup" : "write";
        var where = userSql?.IndexOf("WHERE ", StringComparison.Ordinal) ?? -1;
        // 只关联 AbpUsers 主键筛选，排除认证用户读写与同值的其他参数。
        if (userSql is null || where < 0 ||
            !UserKey.Matches(userSql[where..]).Any(match => command.Parameters.Cast<DbParameter>().Any(parameter =>
                parameter.ParameterName.TrimStart('@') == match.Groups["parameter"].Value.TrimStart('@') &&
                parameter.Value is long id && id == request.UserId)))
        {
            return;
        }

        try
        {
            using var probe = connection.CreateCommand();
            probe.Transaction = command.Transaction;
            probe.CommandText = """
                SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')), DB_NAME(), CONVERT(int, DB_ID()),
                       CONVERT(nvarchar(36), database_guid), @@SPID
                FROM sys.database_recovery_status WHERE database_id = DB_ID()
                """;
            using var reader = probe.ExecuteReader();
            if (reader.Read())
            {
                Write(new
                {
                    kind = "connection", request, operation = operationKind, commandId,
                    serverName = reader.GetString(0), database = reader.GetString(1), databaseId = reader.GetInt32(2),
                    databaseGuid = reader.GetString(3), sessionId = reader.GetInt16(4),
                    connectionId = Property(payload, "ConnectionId")?.ToString(),
                    clientConnectionId = Property(connection, "ClientConnectionId")?.ToString(),
                    context = Property(payload, "Context")?.GetType().FullName,
                });
                commands.TryAdd(commandId, operationKind);
            }
        }
        catch (Exception error) when (error is DbException or InvalidCastException)
        {
            // 观测连接异常交由验收报告判定，保留错误类型与代码，业务命令照常运行。
            Write(new { kind = "probeError", request, operation = operationKind, commandId,
                error = error.GetType().Name, errorCode = error.HResult });
        }
    }

    private void ObserveRequest(string phase, Activity activity, object payload)
    {
        var context = Property(payload, "HttpContext");
        if (phase == Stop)
        {
            if (requests.TryGetValue(activity, out var match))
            {
                onResponse(match.RequestId);
                Write(new { kind = "response", request = match, status = Property(Property(context, "Response"), "StatusCode") });
            }
            return;
        }

        var request = Property(context, "Request");
        var method = Property(request, "Method")?.ToString();
        var path = Property(request, "Path")?.ToString();
        if ((method, path) is not (("GET", UserPath + "Get") or ("PUT", UserPath + "Update")))
        {
            return;
        }
        var query = (Property(request, "QueryString")?.ToString() ?? "").TrimStart('?')
            .Split('&').Select(Uri.UnescapeDataString).ToArray();
        var markers = query.Where(field => field.StartsWith("r5RoleRequest=", StringComparison.Ordinal)).ToArray();
        var ids = query.Where(field => field.StartsWith(method == "GET" ? "Id=" : "r5RoleUser=", StringComparison.Ordinal)).ToArray();
        if (markers.Length != 1 || !Guid.TryParseExact(markers[0]["r5RoleRequest=".Length..], "N", out _) ||
            ids.Length != 1 || !long.TryParse(ids[0].Split('=', 2)[1], NumberStyles.None, CultureInfo.InvariantCulture, out var id)
            || id <= 0)
        {
            return;
        }
        var identity = new RequestIdentity(Environment.ProcessId, markers[0]["r5RoleRequest=".Length..], activity.Id,
            method, path, id);
        requests.Add(activity, identity);
        Write(new { kind = "request", request = identity });
    }

    private static object? Property(object? value, string name) => value?.GetType().GetProperty(name)?.GetValue(value);

    private void Write<T>(T row)
    {
        lock (gate)
        {
            File.AppendAllText(evidence, JsonSerializer.Serialize(row, new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            }) + Environment.NewLine);
        }
    }

    public void OnCompleted() { }

    public void OnError(Exception error) { }

    private sealed record RequestIdentity(int Pid, string RequestId, string? ActivityId, string Method, string Path, long UserId);
}
