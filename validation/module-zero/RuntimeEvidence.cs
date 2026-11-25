using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Identity;
using Microsoft.Data.Sqlite;

namespace ModuleZeroProbe;

internal static partial class RuntimeEvidence
{
    internal static object Capture()
    {
        var assemblies = AppDomain.CurrentDomain.GetAssemblies();
        string[] names = ["Abp", "Abp.EntityFramework.Common", "Abp.EntityFrameworkCore",
            "Abp.Zero.Common", "Abp.ZeroCore", "Abp.ZeroCore.EntityFrameworkCore",
            "Microsoft.EntityFrameworkCore", "Microsoft.EntityFrameworkCore.Relational",
            "Microsoft.EntityFrameworkCore.Sqlite", "Microsoft.Data.Sqlite",
            "SQLitePCLRaw.core", "SQLitePCLRaw.provider.e_sqlite3",
            "SQLitePCLRaw.batteries_v2"];
        var selected = names.ToDictionary(name => name,
            name => Describe(assemblies.Single(assembly => assembly.GetName().Name == name)));
        using var connection = new SqliteConnection("Data Source=:memory:");
        connection.Open();
        var sqliteVersion = connection.ServerVersion;

        // 取得已经由 SQLite 的实际调用加载的动态库。
        var images = Enumerable.Range(0, checked((int)ImageCount()))
            .Select(index => Marshal.PtrToStringUTF8(ImageName((uint)index)))
            .Where(path => Path.GetFileName(path) == "libe_sqlite3.dylib");
        var native = images.Single()!;
        return new
        {
            pid = Environment.ProcessId,
            dotnet = Environment.ProcessPath,
            architecture = RuntimeInformation.ProcessArchitecture.ToString(),
            rid = RuntimeInformation.RuntimeIdentifier,
            framework = RuntimeInformation.FrameworkDescription,
            assemblies = selected,
            sqliteVersion,
            sqliteNative = new { path = native, sha256 = Digest(native) },
            shared = new Dictionary<string, string>
            {
                ["Microsoft.NETCore.App"] = typeof(object).Assembly.Location,
                ["Microsoft.AspNetCore.App"] = typeof(IRoleStore<>).Assembly.Location
            }
        };
    }

    private static object Describe(Assembly assembly) => new
    {
        path = assembly.Location,
        identity = assembly.FullName,
        target = assembly.GetCustomAttribute<TargetFrameworkAttribute>()?.FrameworkName,
        informationalVersion = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion,
        sha256 = Digest(assembly.Location)
    };

    private static string Digest(string path) =>
        Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

    [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "_dyld_image_count")]
    private static extern uint ImageCount();

    [DllImport("/usr/lib/libSystem.B.dylib", EntryPoint = "_dyld_get_image_name")]
    private static extern IntPtr ImageName(uint index);
}
