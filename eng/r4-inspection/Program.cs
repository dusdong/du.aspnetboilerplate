using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

if (args[0] == "--symbol")
{
    using var image = new PEReader(File.OpenRead(args[1]));
    var entries = image.ReadDebugDirectory();
    var view = entries.Single(entry => entry.Type == DebugDirectoryEntryType.CodeView);
    var pointer = image.ReadCodeViewDebugDirectoryData(view);
    var checksum = image.ReadPdbChecksumDebugDirectoryData(
        entries.Single(entry => entry.Type == DebugDirectoryEntryType.PdbChecksum));
    if (!view.IsPortableCodeView || pointer.Age != 1 || checksum.AlgorithmName != "SHA256" ||
        checksum.Checksum.Length != 32)
    {
        throw new InvalidDataException("DLL 缺少 Portable PDB 的 CodeView 或 SHA-256 调试校验信息。");
    }

    var digest = Convert.ToHexString(checksum.Checksum.AsSpan());
    if (args.Length == 3)
    {
        var payload = File.ReadAllBytes(args[2]);
        using var portable = MetadataReaderProvider.FromPortablePdbStream(new MemoryStream(payload));
        var header = portable.GetMetadataReader().DebugMetadataHeader!;
        var id = new BlobContentId(header.Id);
        if (id.Guid != pointer.Guid || id.Stamp != view.Stamp)
        {
            throw new InvalidDataException("Portable PDB 的 GUID 或时间戳与 DLL CodeView 不符。");
        }

        // 编译器先对零填充的 PDB ID 计算校验和，再写入实际 ID。
        payload.AsSpan(header.IdStartOffset, header.Id.Length).Clear();
        if (!SHA256.HashData(payload).AsSpan().SequenceEqual(checksum.Checksum.AsSpan()))
        {
            throw new InvalidDataException("Portable PDB 与 DLL 的调试校验和不符。");
        }
    }

    Console.WriteLine(JsonSerializer.Serialize(new
    {
        name = pointer.Path.Split('/', '\\').Last(),
        guid = pointer.Guid.ToString("N").ToUpperInvariant(),
        stamp = view.Stamp,
        age = pointer.Age,
        checksum = $"{checksum.AlgorithmName}:{digest}"
    }));
    return 0;
}

using var dll = new PEReader(File.OpenRead(args[0]));
using var pdb = MetadataReaderProvider.FromPortablePdbStream(File.OpenRead(args[1]));
var debugId = new BlobContentId(pdb.GetMetadataReader().DebugMetadataHeader!.Id);
var codeView = dll.ReadDebugDirectory().Single(entry => entry.Type == DebugDirectoryEntryType.CodeView);
var codeViewData = dll.ReadCodeViewDebugDirectoryData(codeView);
var assemblyMetadata = dll.GetMetadataReader();

var framework = assemblyMetadata.GetAssemblyDefinition().GetCustomAttributes().Select(attributeHandle =>
{
    var attribute = assemblyMetadata.GetCustomAttribute(attributeHandle);
    if (attribute.Constructor.Kind != HandleKind.MemberReference)
    {
        return null;
    }

    var parent = assemblyMetadata.GetMemberReference((MemberReferenceHandle)attribute.Constructor).Parent;
    if (parent.Kind != HandleKind.TypeReference)
    {
        return null;
    }

    var type = assemblyMetadata.GetTypeReference((TypeReferenceHandle)parent);
    if (assemblyMetadata.GetString(type.Name) != "TargetFrameworkAttribute" ||
        assemblyMetadata.GetString(type.Namespace) != "System.Runtime.Versioning")
    {
        return null;
    }

    var value = assemblyMetadata.GetBlobReader(attribute.Value);
    if (value.ReadUInt16() != 1)
    {
        throw new InvalidDataException("无法读取目标框架属性。");
    }
    return value.ReadSerializedString();
}).Single(name => name != null);

var pdbMetadata = pdb.GetMetadataReader();
var sourceLinkKind = Guid.Parse("CC110556-A091-4D38-9FEC-25AB9A351A6A");
var sourceLink = pdbMetadata.CustomDebugInformation.Select(pdbMetadata.GetCustomDebugInformation)
    .Single(record => pdbMetadata.GetGuid(record.Kind) == sourceLinkKind);
var embeddedSourceKind = Guid.Parse("0E8A571B-6926-466E-B4AD-8AB04611F5FE");
var documents = pdbMetadata.Documents.Select(handle =>
{
    var document = pdbMetadata.GetDocument(handle);
    return new
    {
        path = pdbMetadata.GetString(document.Name),
        hashAlgorithm = pdbMetadata.GetGuid(document.HashAlgorithm),
        hash = Convert.ToHexStringLower(pdbMetadata.GetBlobBytes(document.Hash)),
        embedded = pdbMetadata.GetCustomDebugInformation(handle).Select(pdbMetadata.GetCustomDebugInformation)
            .Any(record => pdbMetadata.GetGuid(record.Kind) == embeddedSourceKind)
    };
});

static object? VersionInformation(string path)
{
    var version = System.Diagnostics.FileVersionInfo.GetVersionInfo(path);
    return new { version.FileVersion, version.ProductVersion };
}

using var sourceLinkJson = JsonDocument.Parse(pdbMetadata.GetBlobBytes(sourceLink.Value));
Console.WriteLine(JsonSerializer.Serialize(new
{
    targetFramework = framework,
    fileVersion = VersionInformation(args[0]),
    baselineFileVersion = args.Length > 2 ? VersionInformation(args[2]) : null,
    sourceLink = sourceLinkJson.RootElement,
    documents,
    codeViewData.Path,
    dllGuid = codeViewData.Guid,
    dllStamp = codeView.Stamp,
    dllAge = codeViewData.Age,
    pdbGuid = debugId.Guid,
    pdbStamp = debugId.Stamp
}));
return 0;
