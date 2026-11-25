using Abp;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Xml.Linq;
using Abp.AspNetCore;
using Abp.AspNetCore.Dependency;
using Abp.AspNetCore.SignalR;
using Abp.AspNetCore.SignalR.Hubs;
using Abp.AspNetCore.SignalR.Notifications;
using Abp.Castle.Logging.Log4Net;
using Abp.Dependency;
using Abp.Modules;
using Abp.Notifications;
using Abp.RealTime;
using Abp.Runtime.Security;
using Castle.Facilities.Logging;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.Extensions.Options;

return await Consumer.RunAsync(args);

internal static class Consumer
{
    private const string NotificationName = "Du.Abp.R3.SignalR";
    private const string Category = "Du.Abp.R3.Castle";
    internal const long UserId = 17025;

    internal static async Task<int> RunAsync(string[] args)
    {
        var evidence = new Dictionary<string, object?>();
        var stopping = new Dictionary<string, object?>();
        evidence["shutdown"] = stopping;
        var marker = Guid.NewGuid().ToString("D");
        var noticeId = Guid.NewGuid();
        var logPath = Path.GetFullPath("castle.log");
        ConfigureLog(logPath);
        var ticket = new TestTicket(Convert.ToHexString(RandomNumberGenerator.GetBytes(32)));
        var exit = 0;
        using var host = Host.CreateDefaultBuilder(args)
            .UseCastleWindsor(IocManager.Instance.IocContainer)
            .ConfigureServices(services => services.AddSingleton(ticket))
            .ConfigureWebHostDefaults(web => web.UseStartup<Startup>().UseUrls("http://127.0.0.1:0"))
            .Build();
        var lifetime = host.Services.GetRequiredService<IHostApplicationLifetime>();
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(lifetime.ApplicationStopping);
        deadline.CancelAfter(TimeSpan.FromSeconds(25));
        var token = deadline.Token;
        HubConnection? client = null;
        try
        {
            await host.StartAsync(token);
            var address = host.Services.GetRequiredService<IServer>()
                .Features.Get<IServerAddressesFeature>()!.Addresses.Single();
            evidence["address"] = address;
            Console.WriteLine("R3_LISTEN " + address);
            var signalr = new Dictionary<string, object?>();
            evidence["signalr"] = signalr;
            signalr["expected"] = new { userId = UserId, notificationId = noticeId, name = NotificationName, marker };
            var received = new TaskCompletionSource<JsonElement>(TaskCreationOptions.RunContinuationsAsynchronously);
            client = new HubConnectionBuilder().WithUrl(address + "/signalr", options =>
            {
                options.Headers["X-R3-Ticket"] = ticket.Value;
            }).Build();
            using var subscription = client.On<JsonElement>("getNotification", payload => received.TrySetResult(payload.Clone()));
            await client.StartAsync(token);
            var connectionId = client.ConnectionId ?? throw new InvalidOperationException("缺少实际 SignalR 连接 ID");
            signalr["connectionId"] = connectionId;
            var ioc = IocManager.Instance;
            using var online = ioc.ResolveAsDisposable<IOnlineClientManager>();
            var onlineRecord = await WaitForOnlineAsync(online.Object, connectionId, expected: true, token);
            signalr["online"] = new { onlineRecord!.ConnectionId, onlineRecord.UserId, onlineRecord.TenantId };
            if (onlineRecord.ConnectionId != connectionId || onlineRecord.UserId != UserId || onlineRecord.TenantId != null)
            {
                throw new InvalidOperationException("OnConnectedAsync 在线身份不符");
            }

            await client.InvokeAsync("Register", token);
            signalr["register"] = true;
            using var configuration = ioc.ResolveAsDisposable<INotificationConfiguration>();
            var notifierType = configuration.Object.Notifiers.SingleOrDefault(type => type == typeof(SignalRRealTimeNotifier))
                ?? throw new InvalidOperationException("通知配置缺少 SignalRRealTimeNotifier");
            signalr["configuredNotifier"] = notifierType.FullName;
            using (var notifier = ioc.ResolveAsDisposable<IRealTimeNotifier>(notifierType))
            {
                signalr["resolvedNotifier"] = notifier.Object.GetType().FullName;
                var notification = new TenantNotification
                {
                    Id = noticeId, NotificationName = NotificationName, Data = new NotificationData()
                };
                notification.Data["marker"] = marker;
                await notifier.Object.SendNotificationsAsync(
                    [new UserNotification { Id = Guid.NewGuid(), UserId = UserId, Notification = notification }])
                    .WaitAsync(token);
            }

            JsonElement payload;
            try
            {
                payload = await received.Task.WaitAsync(TimeSpan.FromSeconds(8), token);
            }
            catch (TimeoutException ex)
            {
                throw new InvalidOperationException("客户端未收到 getNotification", ex);
            }
            signalr["received"] = payload;
            var delivered = payload.GetProperty("notification");
            if (payload.GetProperty("userId").GetInt64() != UserId ||
                delivered.GetProperty("id").GetGuid() != noticeId ||
                delivered.GetProperty("notificationName").GetString() != NotificationName ||
                delivered.GetProperty("data").GetProperty("properties").GetProperty("marker").GetString() != marker)
            {
                throw new InvalidOperationException("getNotification 负载不符");
            }

            await client.StopAsync(token);
            await WaitForOnlineAsync(online.Object, connectionId, expected: false, token);
            signalr["removed"] = new { connectionId, absent = true };

            var message = "R3 Castle " + marker;
            var expectedLine = $"INFO|{Category}|{message}";
            using var loggerFactory = ioc.ResolveAsDisposable<Castle.Core.Logging.ILoggerFactory>();
            loggerFactory.Object.Create(Category).Info(message);
            var actualLine = File.Exists(logPath)
                ? File.ReadLines(logPath).SingleOrDefault(line => line.Contains(marker, StringComparison.Ordinal))
                : null;
            evidence["log4net"] = new { path = logPath, expectedLine, actualLine };
            if (actualLine != expectedLine)
            {
                throw new InvalidOperationException("Castle 日志文件缺少完整等级、类别与消息");
            }

            var assemblies = new[] { typeof(AbpKernelModule).Assembly, typeof(AbpAspNetCoreModule).Assembly,
                typeof(Abp.Web.AbpWebCommonModule).Assembly, typeof(AbpAspNetCoreSignalRModule).Assembly,
                typeof(AbpCastleLog4NetModule).Assembly, typeof(log4net.LogManager).Assembly };
            evidence["runtime"] = new
            {
                pid = Environment.ProcessId,
                architecture = RuntimeInformation.ProcessArchitecture.ToString(),
                rid = RuntimeInformation.RuntimeIdentifier,
                dotnet = Environment.ProcessPath,
                shared = new Dictionary<string, string>
                {
                    ["Microsoft.NETCore.App"] = typeof(object).Assembly.Location,
                    ["Microsoft.AspNetCore.App"] = typeof(Microsoft.AspNetCore.SignalR.Hub).Assembly.Location
                },
                assemblies = assemblies.ToDictionary(assembly => assembly.GetName().Name!, LoadedAssembly)
            };
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex);
            evidence["failure"] = ex.Message;
            exit = 1;
        }
        finally
        {
            if (client != null)
            {
                try
                {
                    using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                    await client.StopAsync(stop.Token);
                    await client.DisposeAsync().AsTask().WaitAsync(stop.Token);
                    stopping["clientStopped"] = client.State == HubConnectionState.Disconnected;
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine(ex);
                    stopping["clientFailure"] = ex.Message;
                    exit = 1;
                }
            }

            try
            {
                using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(5));
                await host.StopAsync(stop.Token);
                stopping["hostStopped"] = lifetime.ApplicationStopped.IsCancellationRequested;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex);
                stopping["hostFailure"] = ex.Message;
                exit = 1;
            }
            File.WriteAllText("host.json", JsonSerializer.Serialize(evidence, new JsonSerializerOptions(JsonSerializerDefaults.Web)
            {
                WriteIndented = true
            }) + Environment.NewLine);
        }
        return exit;
    }

    private static async Task<IOnlineClient?> WaitForOnlineAsync(
        IOnlineClientManager manager, string connectionId, bool expected, CancellationToken token)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(token);
        deadline.CancelAfter(TimeSpan.FromSeconds(5));
        try
        {
            while (true)
            {
                var client = await manager.GetByConnectionIdOrNullAsync(connectionId).WaitAsync(deadline.Token);
                if ((client != null) == expected)
                {
                    return client;
                }
                await Task.Delay(50, deadline.Token);
            }
        }
        catch (OperationCanceledException) when (!token.IsCancellationRequested)
        {
            throw new InvalidOperationException(expected
                ? $"OnConnectedAsync 未登记连接 {connectionId}"
                : $"OnDisconnectedAsync 未移除连接 {connectionId}");
        }
    }

    private static object LoadedAssembly(Assembly assembly)
    {
        using var stream = File.OpenRead(assembly.Location);
        return new
        {
            path = assembly.Location, identity = assembly.FullName,
            target = assembly.GetCustomAttribute<System.Runtime.Versioning.TargetFrameworkAttribute>()?.FrameworkName,
            sha256 = Convert.ToHexStringLower(SHA256.HashData(stream))
        };
    }

    private static void ConfigureLog(string path)
    {
        new XElement("log4net",
            new XElement("appender", new XAttribute("name", "ProbeFile"),
                new XAttribute("type", "log4net.Appender.FileAppender"),
                new XElement("file", new XAttribute("value", path)),
                new XElement("appendToFile", new XAttribute("value", "false")),
                new XElement("layout", new XAttribute("type", "log4net.Layout.PatternLayout"),
                    new XElement("conversionPattern", new XAttribute("value", "%level|%logger|%message%newline")))),
            new XElement("root", new XElement("level", new XAttribute("value", "INFO")),
                new XElement("appender-ref", new XAttribute("ref", "ProbeFile"))))
            .Save("log4net.config");
    }
}

public sealed class Startup
{
    public void ConfigureServices(IServiceCollection services)
    {
        services.AddAuthentication(TestTicket.Scheme)
            .AddScheme<AuthenticationSchemeOptions, TestAuthentication>(TestTicket.Scheme, _ => { });
        services.AddAuthorization();
        services.AddDataProtection().UseEphemeralDataProtectionProvider();
        services.AddControllers();
        services.AddSignalR();
        services.AddAbpWithoutCreatingServiceProvider<ConsumerModule>(options =>
            options.IocManager.IocContainer.AddFacility<LoggingFacility>(facility =>
                facility.UseAbpLog4Net().WithConfig(Path.GetFullPath("log4net.config"))));
    }

    public void Configure(IApplicationBuilder app)
    {
        app.UseAbp(options => options.UseAbpRequestLocalization = false);
        app.UseRouting();
        app.UseAuthentication();
        app.UseAuthorization();
        app.UseEndpoints(endpoints => endpoints.MapHub<AbpCommonHub>("/signalr").RequireAuthorization());
    }
}

[DependsOn(typeof(AbpAspNetCoreModule), typeof(AbpAspNetCoreSignalRModule), typeof(AbpCastleLog4NetModule))]
public sealed class ConsumerModule : AbpModule;

public sealed record TestTicket(string Value)
{
    public const string Scheme = "R3Test";
}

public sealed class TestAuthentication(
    IOptionsMonitor<AuthenticationSchemeOptions> options,
    Microsoft.Extensions.Logging.ILoggerFactory logger, UrlEncoder encoder, TestTicket ticket)
    : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (Request.Headers["X-R3-Ticket"] != ticket.Value)
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        var identity = new ClaimsIdentity([new Claim(AbpClaimTypes.UserId, Consumer.UserId.ToString())], TestTicket.Scheme);
        return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), TestTicket.Scheme)));
    }
}
