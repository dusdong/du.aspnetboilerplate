using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Text.Json;

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
