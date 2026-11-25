using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using Abp;
using Abp.AutoMapper;
using Abp.Dependency;
using Abp.ObjectMapping;
using AutoMapperProbe;

internal static class Program
{
    private static int Main(string[] args)
    {
        if (args.Length != 1 && !(args.Length == 2 && args[1] == "--duplicate-context"))
        {
            Console.Error.WriteLine("用法：AutoMapperMinimal <结果文件> [--duplicate-context]");
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
            var config = scope.Resolve<AutoMapper.IConfigurationProvider>();
            var input = new CollectionInput { Key = 10, Value = "updated" };
            var mapped = mapper.Map<CollectionItem>(input);
            Require(mapper.GetType() == typeof(AutoMapperObjectMapper) && (mapped.Key, mapped.Value) == (10, "updated"),
                "Castle 应解析可执行映射的真实适配器");

            stage = "静态映射";
#pragma warning disable CS0618
            var staticItem = AbpEmulateAutoMapper.Mapper.Map<CollectionItem>(input);
#pragma warning restore CS0618
            Require((staticItem.Key, staticItem.Value) == (10, "updated"), "静态入口应执行普通映射");

            stage = "按键集合";
            var retained = new CollectionItem { Key = 10, Value = "previous" };
            var removed = new CollectionItem { Key = 20, Value = "remove" };
            var target = new List<CollectionItem> { retained, removed };
            var result = mapper.Map(new List<CollectionInput> { input, new() { Key = 30, Value = "inserted" } }, target);
            Require(ReferenceEquals(target, result) && ReferenceEquals(retained, result[0]) &&
                    !ReferenceEquals(removed, result[1]) &&
                    result.Select(item => (item.Key, item.Value)).SequenceEqual([(10, "updated"), (30, "inserted")]),
                "按键映射应保留集合及匹配项引用，并分别更新、插入和移除");

            stage = "程序集加载";
            if (args.Length == 2)
            {
                var duplicate = new AssemblyLoadContext("diagnostic-duplicate", isCollectible: true);
                duplicate.LoadFromAssemblyPath(typeof(AutoMapper.Mapper).Assembly.Location);
            }

            string[] requiredAssemblies = ["Abp", "Abp.AutoMapper", "AutoMapper", "AutoMapper.Collection"];
            var assemblies = AssemblyLoadContext.All.SelectMany(context => context.Assemblies)
                .Where(assembly => requiredAssemblies.Contains(assembly.GetName().Name, StringComparer.OrdinalIgnoreCase))
                .Distinct<Assembly>(ReferenceEqualityComparer.Instance)
                .Select(DescribeAssembly)
                .OrderBy(row => row.Name, StringComparer.Ordinal).ThenBy(row => row.LoadContext, StringComparer.Ordinal)
                .ToArray();
            var resultReport = new
            {
                environment = new
                {
                    RuntimeInformation.FrameworkDescription,
                    RuntimeInformation.ProcessArchitecture,
                    RuntimeInformation.RuntimeIdentifier,
                    processId = Environment.ProcessId,
                    coreRuntimePath = typeof(object).Assembly.Location
                },
                mapping = new
                {
                    castle = mapper.GetType().FullName,
                    provider = config.GetType().FullName,
                    staticMapped = staticItem,
                    collection = result
                },
                assemblies
            };
            using var output = File.Open(args[0], FileMode.CreateNew);
            JsonSerializer.Serialize(output, resultReport, new JsonSerializerOptions { WriteIndented = true });
            foreach (var name in requiredAssemblies)
            {
                var instances = assemblies.Where(row => string.Equals(row.Name, name, StringComparison.OrdinalIgnoreCase)).ToArray();
                Require(instances.Length == 1, $"{name} 实例数预期 1，实际 {instances.Length}："
                    + string.Join("; ", instances.Select(row => $"{row.FullName} @ {row.LoadContext}: {row.Path} ({row.Sha256})")));
            }
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"{stage}失败\n{error}");
            return 1;
        }
    }

    private static LoadedAssembly DescribeAssembly(Assembly assembly)
    {
        using var stream = File.OpenRead(assembly.Location);
        return new(assembly.GetName().Name!, assembly.FullName!, AssemblyLoadContext.GetLoadContext(assembly)?.Name,
            assembly.Location, Convert.ToHexStringLower(SHA256.HashData(stream)));
    }

    private static void Require(bool valid, string message)
    {
        if (!valid)
            throw new InvalidOperationException(message);
    }

    private sealed record LoadedAssembly(string Name, string FullName, string? LoadContext, string Path, string Sha256);
}
