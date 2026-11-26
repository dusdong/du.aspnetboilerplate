using System.Runtime.InteropServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using AutoMapper;

const string shipment = "shipment";
const string receipt = "return";
var inspectPlans = args is ["--inspect-plans"];
if (!inspectPlans && args.Length != 0)
{
    throw new ArgumentException("未知观测模式");
}

string[] registration = [shipment, receipt];
string[] reverseRegistration = [receipt, shipment];
string[] measurementOrder = [shipment, receipt];
Dictionary<string, BusinessInput> inputs = new()
{
    [shipment] = new("SHP-301", [new(42, 3), new(17, 2)]),
    [receipt] = new("RET-302", [new(17, 1), new(31, 4)])
};
Dictionary<string, BusinessInput> warmup = new()
{
    [shipment] = new("SHP-WARM", [new(12, 1)]),
    [receipt] = new("RET-WARM", [new(24, 2)])
};
var initial = new Snapshot(true, true, "UNSET", [new(999, 1)]);
Dictionary<string, Snapshot> expected = new()
{
    [shipment] = new(true, true, "SHP-301", [new(42, 3), new(17, 2)]),
    [receipt] = new(true, true, "RET-302", [new(17, 1), new(31, 4)])
};
Dictionary<string, Snapshot> warmupExpected = new()
{
    [shipment] = new(true, true, "SHP-WARM", [new(12, 1)]),
    [receipt] = new(true, true, "RET-WARM", [new(24, 2)])
};

var observations = new List<Observation>();
var plans = new List<PlanObservation>();
for (var repeat = 1; repeat <= 3; repeat++)
{
    observations.Add(Observe("cold-shipment-first", repeat, registration, []));
    observations.Add(Observe("cold-return-first", repeat, reverseRegistration, []));
    observations.Add(Observe("warm-shipment-first", repeat, registration, [shipment, receipt]));
    observations.Add(Observe("warm-return-first", repeat, registration, [receipt, shipment]));
}

var assemblies = AssemblyLoadContext.All
    .SelectMany(context => context.Assemblies
        .Where(assembly => assembly.GetName().Name == "AutoMapper")
        .Select(assembly => new
        {
            context = context.Name,
            name = assembly.FullName,
            path = assembly.Location,
            sha256 = Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(assembly.Location)))
        }))
    .ToArray();

Console.WriteLine(JsonSerializer.Serialize(new
{
    runtime = RuntimeInformation.FrameworkDescription,
    architecture = RuntimeInformation.ProcessArchitecture.ToString(),
    runtimePath = typeof(object).Assembly.Location,
    assemblies,
    inputs,
    initial,
    warmup,
    expected,
    warmupExpected,
    measurementOrder,
    observations,
    plans
}, new JsonSerializerOptions { WriteIndented = true }));

Observation Observe(string name, int repeat, string[] registrations, string[] warmups)
{
    var configuration = new MapperConfiguration(cfg =>
    {
        cfg.CreateMap<ItemDraft, ItemView>();
        foreach (var registration in registrations)
        {
            if (registration == shipment)
            {
                cfg.CreateMap<ShipmentDraft, ShipmentView>()
                    .ForMember(view => view.Lines, member => member.MapAtRuntime())
                    .MaxDepth(2);
            }
            else
            {
                cfg.CreateMap<ReturnDraft, ReturnView>()
                    .ForMember(view => view.Lines, member => member.MapAtRuntime());
            }
        }
    });

    var mapper = configuration.CreateMapper();
    var observer = inspectPlans ? new CollectionPlans(configuration) : null;
    observer?.ReadCache("initial", null);
    var warmed = warmups.Select(key => Run(key, warmup[key], warmupExpected[key], "warmup")).ToArray();
    var measured = measurementOrder.Select(key => Run(key, inputs[key], expected[key], "measurement")).ToArray();
    if (observer != null)
    {
        plans.Add(observer.Report(name, repeat));
    }

    return new(name, repeat, registrations, warmups, warmed, measured);

    MapResult Run(string key, BusinessInput input, Snapshot expectation, string stage)
    {
        var result = key == shipment
            ? Map(new ShipmentView(), view => mapper.Map(new ShipmentDraft(input.Number, [.. input.Lines]), view),
                expectation)
            : Map(new ReturnView(), view => mapper.Map(new ReturnDraft(input.Number, [.. input.Lines]), view),
                expectation);
        observer?.ReadCache(stage, key);
        return result;
    }
}

MapResult Map<T>(T target, Func<T, T> map, Snapshot expectation) where T : DocumentView
{
    target.Number = initial.Number;
    target.Lines = [.. initial.Lines];
    var originalLines = target.Lines;
    try
    {
        var mapped = map(target);
        var actual = new Snapshot(ReferenceEquals(mapped, target), ReferenceEquals(mapped.Lines, originalLines),
            mapped.Number, mapped.Lines.ToArray());
        var matches = actual.SameDestination == expectation.SameDestination
            && actual.SameCollection == expectation.SameCollection
            && actual.Number == expectation.Number && actual.Lines.SequenceEqual(expectation.Lines);
        return new(matches, actual, []);
    }
    catch (AutoMapperMappingException exception)
    {
        var errors = new List<MapError>();
        for (Exception? error = exception; error != null; error = error.InnerException)
        {
            errors.Add(new(error.GetType().FullName!, error.Message));
        }
        return new(false, null, errors);
    }
}

record ItemDraft(int Id, int Quantity);
record ItemView(int Id, int Quantity);
record ShipmentDraft(string Number, List<ItemDraft> Lines);
record ReturnDraft(string Number, List<ItemDraft> Lines);
record BusinessInput(string Number, ItemDraft[] Lines);

abstract class DocumentView
{
    public string Number { get; set; } = "";
    public List<ItemView> Lines { get; set; } = [];
}

sealed class ShipmentView : DocumentView;
sealed class ReturnView : DocumentView;

record Snapshot(bool SameDestination, bool SameCollection, string Number, ItemView[] Lines);
record MapError(string Type, string Message);
record MapResult(bool MatchesExpected, Snapshot? Actual, IReadOnlyList<MapError> Exceptions);
record Observation(string Case, int Repeat, string[] Registration, string[] WarmupOrder,
    MapResult[] Warmups, MapResult[] Measurements);
