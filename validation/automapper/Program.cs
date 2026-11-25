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
        if (args.Length != 1)
        {
            Console.Error.WriteLine("用法：AutoMapperProbe <结果文件>");
            return 2;
        }

        var stage = "模块启动及 Castle 解析";
        try
        {
            using var ioc = new IocManager();
            using var bootstrapper = AbpBootstrapper.Create<ProbeModule>(options => options.IocManager = ioc);
            bootstrapper.Initialize();
            using var scope = ioc.CreateScope();
            var mapper = scope.Resolve<IObjectMapper>();
            var configuration = scope.Resolve<AutoMapper.IConfigurationProvider>();
            Require(mapper.GetType() == typeof(AutoMapperObjectMapper), "Castle 应解析真实 AutoMapper 适配器");

            // 固定模板保留重复 CreateMap，走真实的运行映射入口。
            stage = "模板配置扫描和用户更新";
            var user = VerifyUserUpdate(mapper);
            stage = "按键集合";
            var collection = VerifyCollection(mapper);
            stage = "SQLite 查询投影";
            var projection = Projection.Verify(mapper);
            stage = "程序集运行证据";
            var names = new HashSet<string>(StringComparer.Ordinal)
            {
                "Abp", "Abp.AutoMapper", "Abp.Zero.Common", "Abp.ZeroCore", "AutoMapper", "AutoMapper.Collection",
                "Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Relational",
                "Microsoft.EntityFrameworkCore.Sqlite", "Microsoft.Data.Sqlite"
            };
            var loaded = AssemblyLoadContext.All
                .SelectMany(context => context.Assemblies.Where(a => names.Contains(a.GetName().Name!)))
                .OrderBy(a => a.GetName().Name, StringComparer.Ordinal)
                .Select(DescribeAssembly)
                .ToArray();
            Require(loaded.Count(a => a.Name == "AutoMapper") == 1, "全进程应仅加载一个 AutoMapper 实例");
            foreach (var name in new[] { "Abp.AutoMapper", "AutoMapper.Collection", "Abp.Zero.Common",
                         "Microsoft.EntityFrameworkCore.Sqlite", "Microsoft.Data.Sqlite" })
                Require(loaded.Count(a => a.Name == name) == 1, $"全进程应加载一个 {name} 实例");

            using var output = File.Open(args[0], FileMode.CreateNew);
            JsonSerializer.Serialize(output, new
            {
                environment = new
                {
                    RuntimeInformation.FrameworkDescription,
                    RuntimeInformation.ProcessArchitecture,
                    RuntimeInformation.RuntimeIdentifier,
                    processId = Environment.ProcessId
                },
                configuration = new
                {
                    mapper = mapper.GetType().FullName,
                    provider = configuration.GetType().FullName,
                    profile = typeof(UserMapProfile).FullName,
                    bootstrapped = true
                },
                user,
                collection,
                projection,
                assemblies = loaded
            }, new JsonSerializerOptions { WriteIndented = true });
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"{stage}失败\n{error}");
            return 1;
        }
    }

    private static object VerifyUserUpdate(IObjectMapper mapper)
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
        var result = mapper.Map(dto, destination);
        var targetRetained = ReferenceEquals(destination, result);
        var rolesRetained = ReferenceEquals(roles, result.Roles);
        Require(targetRetained, "UserDto 更新应返回已有 User 实例");
        Require(rolesRetained && result.Roles.Count == 1 && ReferenceEquals(result.Roles.Single(), assignment)
                && (assignment.Id, assignment.UserId, assignment.RoleId, assignment.TenantId) ==
                    (46L, userId, role.Id, (int?)tenantId), "Roles 引用、原成员和角色键应保持");
        Require(result.CreationTime == creation, "CreationTime 应保持已有值");
        Require((result.Id, result.Name, result.Surname, result.UserName, result.EmailAddress, result.IsActive) ==
                (userId, dto.Name, dto.Surname, dto.UserName, dto.EmailAddress, dto.IsActive), "普通字段应映射到已有用户");

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
        Require((created.Name, created.Surname, created.UserName, created.EmailAddress, created.IsActive) ==
                ("Created", "FromDto", "created", "create@example.invalid", true) && created.Roles is null,
            "CreateUserDto 重复声明应保持普通映射并忽略 Roles");
        return new
        {
            targetRetained,
            rolesRetained,
            roleMemberRetained = ReferenceEquals(result.Roles.Single(), assignment),
            result.Id,
            result.Name,
            result.Surname,
            result.UserName,
            result.EmailAddress,
            result.IsActive,
            result.CreationTime,
            requestedCreationTime = dto.CreationTime,
            requestedRoles = dto.RoleNames,
            roles = result.Roles.Select(r => new { r.Id, r.UserId, r.RoleId, r.TenantId }),
            createUser = new { created.UserName, created.IsActive, ignoresRoles = created.Roles is null }
        };
    }

    private static object VerifyCollection(IObjectMapper mapper)
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
        var matchingItemRetained = ReferenceEquals(result.Single(item => item.Key == 10), retained);
        var added = result.Single(item => item.Key == 30);
        var newItemCreated = !ReferenceEquals(added, removed) && !ReferenceEquals(added, retained);
        var oldItemRemoved = result.All(item => item.Key != 20 && !ReferenceEquals(item, removed));
        Require(targetRetained && matchingItemRetained && newItemCreated && oldItemRemoved,
            "集合应保留集合与匹配项引用，逐键新增及移除");
        Require(result.Select(item => (item.Key, item.Value)).SequenceEqual([(10, "updated"), (30, "inserted")]),
            "集合的实际键值及顺序应符合原版");
        return new { targetRetained, matchingItemRetained, newItemCreated, oldItemRemoved, items = result };
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
