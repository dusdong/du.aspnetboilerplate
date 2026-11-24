using System.Collections.Immutable;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Encodings.Web;
using System.Text.Json;

if (args.Length != 1)
{
    Console.Error.WriteLine("用法：ApiInventory <assembly.dll>");
    return 2;
}

using var stream = File.OpenRead(args[0]);
var sha256 = Convert.ToHexStringLower(SHA256.HashData(stream));
stream.Position = 0;
using var pe = new PEReader(stream);
var reader = pe.GetMetadataReader();
var assembly = reader.GetAssemblyDefinition();
var publicKey = reader.GetBlobBytes(assembly.PublicKey);
var token = publicKey.Length == 0
    ? null
    : Convert.ToHexStringLower(SHA1.HashData(publicKey).TakeLast(8).Reverse().ToArray());

var inventory = new
{
    extractorVersion = 1,
    sha256,
    assembly = new
    {
        name = reader.GetString(assembly.Name),
        version = assembly.Version.ToString(),
        culture = assembly.Culture.IsNil ? "neutral" : reader.GetString(assembly.Culture),
        publicKeyToken = token
    },
    types = new ApiReader(reader).ReadTypes(),
    resources = reader.ManifestResources
        .Select(handle => reader.GetString(reader.GetManifestResource(handle).Name))
        .Order(StringComparer.Ordinal)
};
Console.WriteLine(JsonSerializer.Serialize(inventory, new JsonSerializerOptions
{
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
}));
return 0;

sealed class ApiReader(MetadataReader reader)
{
    private readonly SignatureNames names = new();

    public SortedDictionary<string, string[]> ReadTypes()
    {
        var types = new SortedDictionary<string, string[]>(StringComparer.Ordinal);
        foreach (var handle in reader.TypeDefinitions.Where(IsVisibleType))
        {
            var type = reader.GetTypeDefinition(handle);
            types.Add(names.GetTypeFromDefinition(reader, handle, 0), ReadType(type));
        }
        return types;
    }

    private bool IsVisibleType(TypeDefinitionHandle handle)
    {
        var type = reader.GetTypeDefinition(handle);
        return (type.Attributes & TypeAttributes.VisibilityMask) switch
        {
            TypeAttributes.Public => true,
            TypeAttributes.NestedPublic or TypeAttributes.NestedFamily or TypeAttributes.NestedFamORAssem
                => IsVisibleType(type.GetDeclaringType()),
            _ => false
        };
    }

    private string[] ReadType(TypeDefinition type)
    {
        var members = new List<string>();
        foreach (var method in type.GetMethods().Select(reader.GetMethodDefinition).Where(IsVisible))
        {
            var signature = method.DecodeSignature(names, null);
            var parameters = method.GetParameters().Select(reader.GetParameter)
                .ToDictionary(parameter => (int)parameter.SequenceNumber);
            var inputs = signature.ParameterTypes.Select((input, i) =>
            {
                var value = Parameter(parameters, i + 1, input);
                return i == signature.RequiredParameterCount ? "..., " + value : value;
            });
            members.Add($"method [{method.Attributes}] {reader.GetString(method.Name)}" +
                $"{Generics(method.GetGenericParameters())}({string.Join(", ", inputs)})" +
                $" -> {Parameter(parameters, 0, signature.ReturnType)} [{signature.Header.CallingConvention}]");
        }

        foreach (var field in type.GetFields().Select(reader.GetFieldDefinition).Where(IsVisible))
        {
            members.Add($"field [{field.Attributes}] {reader.GetString(field.Name)}" +
                $" : {field.DecodeSignature(names, null)}{Constant(field.GetDefaultValue())}");
        }

        foreach (var property in type.GetProperties().Select(reader.GetPropertyDefinition))
        {
            var accessors = property.GetAccessors();
            if (VisibleAccessors(accessors.Getter, accessors.Setter, accessors.Others) is not { } access)
                continue;

            var signature = property.DecodeSignature(names, null);
            members.Add($"property [{access}] {reader.GetString(property.Name)}" +
                $"({string.Join(", ", signature.ParameterTypes)}) -> {signature.ReturnType}");
        }

        foreach (var @event in type.GetEvents().Select(reader.GetEventDefinition))
        {
            var accessors = @event.GetAccessors();
            if (VisibleAccessors(accessors.Adder, accessors.Remover, accessors.Others.Add(accessors.Raiser))
                is not { } access)
                continue;

            members.Add($"event [{access}] {reader.GetString(@event.Name)} : {TypeName(@event.Type)}");
        }

        var interfaces = type.GetInterfaceImplementations()
            .Select(handle => TypeName(reader.GetInterfaceImplementation(handle).Interface))
            .Order(StringComparer.Ordinal);
        var declaration = $"type [{type.Attributes}]{Generics(type.GetGenericParameters())}";
        if (!type.BaseType.IsNil)
            declaration += $" : {TypeName(type.BaseType)}";

        var implemented = string.Join(", ", interfaces);
        if (implemented.Length != 0)
            declaration += $" implements {implemented}";

        members.Sort(StringComparer.Ordinal);
        members.Insert(0, declaration);
        return [.. members];
    }

    private static bool IsVisible(MethodDefinition method) =>
        (method.Attributes & MethodAttributes.MemberAccessMask) is MethodAttributes.Public
            or MethodAttributes.Family or MethodAttributes.FamORAssem;

    private static bool IsVisible(FieldDefinition field) =>
        (field.Attributes & FieldAttributes.FieldAccessMask) is FieldAttributes.Public
            or FieldAttributes.Family or FieldAttributes.FamORAssem;

    private string? VisibleAccessors(
        MethodDefinitionHandle first, MethodDefinitionHandle second, ImmutableArray<MethodDefinitionHandle> others)
    {
        var methods = others.Add(first).Add(second)
            .Where(handle => !handle.IsNil)
            .Select(reader.GetMethodDefinition)
            .Where(IsVisible)
            .Select(method => $"{reader.GetString(method.Name)}: {method.Attributes & MethodAttributes.MemberAccessMask}")
            .Order(StringComparer.Ordinal)
            .ToArray();
        return methods.Length == 0 ? null : string.Join(", ", methods);
    }

    private string Parameter(IReadOnlyDictionary<int, Parameter> parameters, int index, string type)
    {
        if (!parameters.TryGetValue(index, out var parameter))
            return type;

        var name = parameter.Name.IsNil ? "" : $" {reader.GetString(parameter.Name)}";
        var flags = parameter.Attributes == ParameterAttributes.None ? "" : $" [{parameter.Attributes}]";
        return type + name + flags + Constant(parameter.GetDefaultValue());
    }

    private string Constant(ConstantHandle handle)
    {
        if (handle.IsNil)
            return "";
        var value = reader.GetConstant(handle);
        var blob = reader.GetBlobReader(value.Value);
        var literal = blob.ReadConstant(value.TypeCode);
        if (literal is float real && !float.IsFinite(real))
            return " = " + real.ToString(System.Globalization.CultureInfo.InvariantCulture);
        if (literal is double number && !double.IsFinite(number))
            return " = " + number.ToString(System.Globalization.CultureInfo.InvariantCulture);
        return " = " + JsonSerializer.Serialize(literal);
    }

    private string Generics(GenericParameterHandleCollection handles)
    {
        if (handles.Count == 0)
            return "";

        var parameters = handles.Select(reader.GetGenericParameter).OrderBy(parameter => parameter.Index)
            .Select(parameter =>
            {
                var constraints = parameter.GetConstraints()
                    .Select(handle => TypeName(reader.GetGenericParameterConstraint(handle).Type))
                    .Order(StringComparer.Ordinal);
                return $"{reader.GetString(parameter.Name)} [{parameter.Attributes}]" +
                    string.Concat(constraints.Select(constraint => " : " + constraint));
            });
        return $"<{string.Join(", ", parameters)}>";
    }

    private string TypeName(EntityHandle handle) => handle.Kind switch
    {
        HandleKind.TypeDefinition => names.GetTypeFromDefinition(reader, (TypeDefinitionHandle)handle, 0),
        HandleKind.TypeReference => names.GetTypeFromReference(reader, (TypeReferenceHandle)handle, 0),
        HandleKind.TypeSpecification => names.GetTypeFromSpecification(reader, null, (TypeSpecificationHandle)handle, 0),
        _ => throw new BadImageFormatException($"Unsupported type handle: {handle.Kind}")
    };
}

sealed class SignatureNames : ISignatureTypeProvider<string, object?>
{
    public string GetArrayType(string elementType, ArrayShape shape)
    {
        var bounds = Enumerable.Range(0, shape.Rank).Select(index =>
        {
            var lower = index < shape.LowerBounds.Length ? shape.LowerBounds[index].ToString() : "";
            var size = index < shape.Sizes.Length ? shape.Sizes[index].ToString() : "";
            return $"{lower}..{size}";
        });
        return $"{elementType}[{string.Join(",", bounds)}]";
    }

    public string GetByReferenceType(string elementType) => elementType + "&";

    public string GetFunctionPointerType(MethodSignature<string> signature)
    {
        var parameters = signature.ParameterTypes.Select((parameter, index) =>
            index == signature.RequiredParameterCount ? "..., " + parameter : parameter);
        return $"fnptr[{signature.Header.RawValue:X2}]({string.Join(", ", parameters)}) -> {signature.ReturnType}";
    }

    public string GetGenericInstantiation(string genericType, ImmutableArray<string> typeArguments) =>
        $"{genericType}<{string.Join(", ", typeArguments)}>";

    public string GetGenericMethodParameter(object? context, int index) => $"!!{index}";
    public string GetGenericTypeParameter(object? context, int index) => $"!{index}";

    public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired) =>
        $"{unmodifiedType} mod{(isRequired ? "req" : "opt")}({modifier})";

    public string GetPinnedType(string elementType) => elementType + " pinned";
    public string GetPointerType(string elementType) => elementType + "*";
    public string GetPrimitiveType(PrimitiveTypeCode typeCode) => $"System.{typeCode}";
    public string GetSZArrayType(string elementType) => elementType + "[]";

    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte rawTypeKind)
    {
        var type = reader.GetTypeDefinition(handle);
        var name = reader.GetString(type.Name);
        var declaring = type.GetDeclaringType();
        return declaring.IsNil
            ? Qualified(reader.GetString(type.Namespace), name)
            : $"{GetTypeFromDefinition(reader, declaring, 0)}+{name}";
    }

    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte rawTypeKind)
    {
        var type = reader.GetTypeReference(handle);
        var name = reader.GetString(type.Name);
        return type.ResolutionScope.Kind switch
        {
            HandleKind.TypeReference => $"{GetTypeFromReference(reader, (TypeReferenceHandle)type.ResolutionScope, 0)}+{name}",
            HandleKind.AssemblyReference => $"[{reader.GetString(reader.GetAssemblyReference((AssemblyReferenceHandle)type.ResolutionScope).Name)}]" +
                Qualified(reader.GetString(type.Namespace), name),
            _ => Qualified(reader.GetString(type.Namespace), name)
        };
    }

    public string GetTypeFromSpecification(MetadataReader reader, object? context, TypeSpecificationHandle handle, byte rawTypeKind) =>
        reader.GetTypeSpecification(handle).DecodeSignature(this, context);

    private static string Qualified(string @namespace, string name) =>
        @namespace.Length == 0 ? name : $"{@namespace}.{name}";
}
