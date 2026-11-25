using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text.Json;
using NuGet.Versioning;

if (args.Length >= 2 && args[0] == "--internal-ranges")
{
    var candidate = NuGetVersion.Parse(args[1]);
    var invalid = args.Skip(2)
        .Where(text => !VersionRange.TryParse(text, allowFloating: false, out var range) ||
            !range.IsMinInclusive ||
            !VersionComparer.VersionRelease.Equals(range.MinVersion, candidate) ||
            !range.Satisfies(candidate))
        .ToArray();
    Console.WriteLine(JsonSerializer.Serialize(invalid));
    return;
}

if (args is ["--satisfies-range", var version, var constraint])
{
    Console.WriteLine(JsonSerializer.Serialize(
        NuGetVersion.TryParse(version, out var selected) &&
        VersionRange.TryParse(constraint, allowFloating: false, out var range) &&
        range.Satisfies(selected)));
    return;
}

foreach (var path in args)
{
    using var stream = File.OpenRead(path);
    using var pe = new PEReader(stream);
    var reader = pe.GetMetadataReader();
    var attributes = reader.GetAssemblyDefinition().GetCustomAttributes();
    var targets = new List<string>();
    foreach (var handle in attributes)
    {
        var attribute = reader.GetCustomAttribute(handle);
        if (attribute.Constructor.Kind != HandleKind.MemberReference)
            continue;
        var constructor = reader.GetMemberReference((MemberReferenceHandle)attribute.Constructor);
        if (constructor.Parent.Kind != HandleKind.TypeReference)
            continue;
        var type = reader.GetTypeReference((TypeReferenceHandle)constructor.Parent);
        if (!reader.StringComparer.Equals(type.Namespace, "System.Runtime.Versioning") ||
            !reader.StringComparer.Equals(type.Name, "TargetFrameworkAttribute"))
            continue;
        var value = reader.GetBlobReader(attribute.Value);
        if (value.ReadUInt16() != 1)
            throw new BadImageFormatException($"TargetFrameworkAttribute: {path}");
        targets.Add(value.ReadSerializedString() ?? "");
    }
    Console.WriteLine(JsonSerializer.Serialize(new { path, targets }));
}
