using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using Abp;
using Abp.Authorization.Users;
using Abp.AutoMapper;
using Abp.Dependency;
using Abp.ObjectMapping;
using AbpCompanyName.AbpProjectName.Authorization.Roles;
using AbpCompanyName.AbpProjectName.Authorization.Users;
using AbpCompanyName.AbpProjectName.Users.Dto;

namespace AutoMapperProbe;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args.Length is < 1 or > 2)
        {
            Console.Error.WriteLine("用法：AutoMapperProbe <结果文件> [预期取列 JSON]");
            return 2;
        }

        var publicRun = args.Length == 2;
        var stages = new Dictionary<string, string>
        {
            ["user"] = "not_run",
            ["collection"] = "not_run",
            ["projection"] = "not_run"
        };
        var report = new Dictionary<string, object?>
        {
            ["environment"] = new
            {
                RuntimeInformation.FrameworkDescription,
                RuntimeInformation.ProcessArchitecture,
                RuntimeInformation.RuntimeIdentifier,
                processArchitectureName = RuntimeInformation.ProcessArchitecture.ToString(),
                coreRuntimePath = typeof(object).Assembly.Location,
                processId = Environment.ProcessId
            }
        };
        if (publicRun)
            report["scenarios"] = stages;

        var stage = "模块启动及 Castle 解析";
        Exception? failure = null;
        try
        {
            var expectedColumns = publicRun ? JsonSerializer.Deserialize<string[]>(File.ReadAllText(args[1])) : null;
            Require(!publicRun || expectedColumns is { Length: > 0 }, "缺少预期 SQLite 取列");
            using var ioc = new IocManager();
            using var bootstrapper = AbpBootstrapper.Create<ProbeModule>(options => options.IocManager = ioc);
            bootstrapper.Initialize();
            using var scope = ioc.CreateScope();
            var mapper = scope.Resolve<IObjectMapper>();
            var configuration = scope.Resolve<AutoMapper.IConfigurationProvider>();
            Require(mapper.GetType() == typeof(AutoMapperObjectMapper), "Castle 应解析真实 AutoMapper 适配器");
            report["configuration"] = new
            {
                mapper = mapper.GetType().FullName,
                provider = configuration.GetType().FullName,
                profile = typeof(UserMapProfile).FullName,
                bootstrapped = true
            };

            // 固定模板保留重复 CreateMap，走真实的运行映射入口。
            RunScenario("user", capture => VerifyUserUpdate(mapper, capture));
            RunScenario("collection", capture => VerifyCollection(mapper, capture));
            RunScenario("projection", capture => Projection.Verify(mapper, capture, expectedColumns));
        }
        catch (Exception error)
        {
            failure = error;
            if (stages.ContainsKey(stage))
                stages[stage] = "failed";
            report["failure"] = new { stage, error = error.ToString() };
            Console.Error.WriteLine($"{stage}失败\n{error}");
        }

        if (failure is null || publicRun)
        {
            try
            {
                var loaded = DescribeLoadedAssemblies();
                report["assemblies"] = loaded;
                foreach (var name in new[] { "AutoMapper", "Abp.AutoMapper", "AutoMapper.Collection", "Abp.Zero.Common",
                             "Microsoft.EntityFrameworkCore.Sqlite", "Microsoft.Data.Sqlite" })
                    Require(loaded.Count(a => a.Name == name) == 1, $"全进程应加载一个 {name} 实例");
            }
            catch (Exception error)
            {
                failure ??= error;
                report["assemblyFailure"] = error.ToString();
                Console.Error.WriteLine($"程序集运行证据失败\n{error}");
            }
        }

        if (failure is null || publicRun)
        {
            using var output = File.Open(args[0], FileMode.CreateNew);
            JsonSerializer.Serialize(output, report, new JsonSerializerOptions { WriteIndented = true });
        }
        return failure is null ? 0 : 1;

        void RunScenario(string name, Action<Action<object>> execute)
        {
            stage = name;
            execute(actual => report[name] = actual);
            stages[name] = "passed";
        }
    }

    private static LoadedAssembly[] DescribeLoadedAssemblies()
    {
        var names = new HashSet<string>(StringComparer.Ordinal)
        {
            "Abp", "Abp.AutoMapper", "Abp.Zero.Common", "Abp.ZeroCore", "AutoMapper", "AutoMapper.Collection",
            "Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Relational",
            "Microsoft.EntityFrameworkCore.Sqlite", "Microsoft.Data.Sqlite"
        };
        return AssemblyLoadContext.All
            .SelectMany(context => context.Assemblies.Where(a => names.Contains(a.GetName().Name!)))
            .OrderBy(a => a.GetName().Name, StringComparer.Ordinal)
            .Select(DescribeAssembly)
            .ToArray();
    }

    private static void VerifyUserUpdate(IObjectMapper mapper, Action<object> capture)
    {
        const int tenantId = 4;
        const long userId = 27;
        var role = new Role(tenantId, "Auditor", "Auditor") { Id = 37 };
        var assignment = new UserRole(tenantId, userId, role.Id) { Id = 46 };
        var roles = new List<UserRole> { assignment };
        var creation = new DateTime(2020, 12, 31, 23, 57, 0, DateTimeKind.Utc);
        var destination = new User
        {
            Id = userId,
            TenantId = tenantId,
            Name = "Previous",
            Surname = "Surname",
            UserName = "previous",
            EmailAddress = "previous@example.invalid",
            IsActive = false,
            Roles = roles,
            CreationTime = creation
        };
        var dto = new UserDto
        {
            Id = userId,
            Name = "New",
            Surname = "User",
            UserName = "newuser",
            EmailAddress = "new@example.invalid",
            IsActive = true,
            CreationTime = creation.AddYears(2),
            RoleNames = ["DifferentRole"]
        };
        var initialIsActive = destination.IsActive;
        var result = mapper.Map(dto, destination);
        var targetRetained = ReferenceEquals(destination, result);
        var rolesRetained = ReferenceEquals(roles, result.Roles);
        var created = mapper.Map<User>(new CreateUserDto
        {
            Name = "Created",
            Surname = "FromDto",
            UserName = "created",
            EmailAddress = "create@example.invalid",
            IsActive = true,
            Password = "local-fixture",
            RoleNames = ["DifferentRole"]
        });
        var roleMemberRetained = result.Roles is { Count: 1 } && ReferenceEquals(result.Roles.Single(), assignment);
        capture(new
        {
            targetRetained,
            rolesRetained,
            roleMemberRetained,
            initialIsActive,
            requestedIsActive = dto.IsActive,
            result.Id,
            result.Name,
            result.Surname,
            result.UserName,
            result.EmailAddress,
            result.IsActive,
            result.CreationTime,
            requestedCreationTime = dto.CreationTime,
            requestedRoles = dto.RoleNames,
            roles = result.Roles?.Select(r => new { r.Id, r.UserId, r.RoleId, r.TenantId }),
            createUser = new { created.UserName, created.IsActive, ignoresRoles = created.Roles is null }
        });
        Require(!initialIsActive && result.IsActive, "已有用户的 IsActive 应从 false 更新为 true");
        Require(targetRetained, "UserDto 更新应返回已有 User 实例");
        Require(rolesRetained && roleMemberRetained
                && (assignment.Id, assignment.UserId, assignment.RoleId, assignment.TenantId) ==
                    (46L, userId, role.Id, (int?)tenantId), "Roles 引用、原成员和角色键应保持");
        Require(result.CreationTime == creation, "CreationTime 应保持已有值");
        Require((result.Id, result.Name, result.Surname, result.UserName, result.EmailAddress, result.IsActive) ==
                (userId, dto.Name, dto.Surname, dto.UserName, dto.EmailAddress, dto.IsActive), "普通字段应映射到已有用户");
        Require((created.Name, created.Surname, created.UserName, created.EmailAddress, created.IsActive) ==
                ("Created", "FromDto", "created", "create@example.invalid", true) && created.Roles is null,
            "CreateUserDto 重复声明应保持普通映射并忽略 Roles");
    }

    private static void VerifyCollection(IObjectMapper mapper, Action<object> capture)
    {
        var retained = new CollectionItem { Key = 10, Value = "previous" };
        var removed = new CollectionItem { Key = 20, Value = "remove" };
        var destination = new List<CollectionItem> { removed, retained };
        var input = new List<CollectionInput>
        {
            new() { Key = 30, Value = "inserted" },
            new() { Key = 10, Value = "updated" }
        };
        var result = mapper.Map(input, destination);
        var targetRetained = ReferenceEquals(result, destination);
        var matchingItemRetained = ReferenceEquals(result.FirstOrDefault(item => item.Key == 10), retained);
        var added = result.FirstOrDefault(item => item.Key == 30);
        var newItemCreated = added is not null && !ReferenceEquals(added, removed) && !ReferenceEquals(added, retained);
        var oldItemRemoved = result.All(item => item.Key != 20 && !ReferenceEquals(item, removed));
        capture(new { targetRetained, matchingItemRetained, newItemCreated, oldItemRemoved, items = result });
        Require(targetRetained && matchingItemRetained && newItemCreated && oldItemRemoved,
            "集合应保留集合与匹配项引用，逐键新增及移除");
        Require(result.Select(item => (item.Key, item.Value)).SequenceEqual([(10, "updated"), (30, "inserted")]),
            "集合的实际键值及顺序应符合原版");
    }

    private static LoadedAssembly DescribeAssembly(Assembly assembly)
    {
        using var stream = File.OpenRead(assembly.Location);
        return new(assembly.GetName().Name!, assembly.FullName!, AssemblyLoadContext.GetLoadContext(assembly)?.Name,
            assembly.Location, Convert.ToHexStringLower(SHA256.HashData(stream)));
    }

    internal static void Require(bool valid, string message)
    {
        if (!valid)
            throw new InvalidOperationException(message);
    }

    private sealed record LoadedAssembly(string Name, string FullName, string? LoadContext, string Path, string Sha256);
}
