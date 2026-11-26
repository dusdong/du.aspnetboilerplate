using System.Runtime.InteropServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using AutoMapper;

const string order = "order";
const string invoice = "invoice";
const string lines = "lines";
const string invoiceNumber = "INV-301";
var inspectPlans = args is ["--inspect-plans"];
if (!inspectPlans && args.Length != 0)
{
    throw new ArgumentException("未知观测模式");
}

string[] registration = [lines, order, invoice];
string[] reversedRegistration = [lines, invoice, order];

LineInput[] input = [new(42, 3), new(17, 2)];
LineView[] initialLines = [new(999, 1)];
var expected = new Snapshot(true, invoiceNumber, [new(42, 3), new(17, 2)]);

var results = new List<Observation>();
var plans = new List<CollectionPlanObservation>();
for (var repeat = 1; repeat <= 3; repeat++)
{
    results.Add(Observe("warm-order-first", repeat, registration, [order, invoice]));
    results.Add(Observe("warm-invoice-first", repeat, registration, [invoice, order]));
    results.Add(Observe("cold-order-first", repeat, registration, []));
    results.Add(Observe("cold-invoice-first", repeat, reversedRegistration, []));
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
    input = new { number = invoiceNumber, lines = input },
    initial = new { number = "UNSET", lines = initialLines },
    warmup = new { orderNumber = "ORD-WARM", invoiceNumber = "INV-WARM", line = new LineInput(12, 1) },
    expected,
    observations = results,
    plans
}, new JsonSerializerOptions { WriteIndented = true }));

Observation Observe(string name, int repeat, string[] registrations, string[] warmups)
{
    var configuration = new MapperConfiguration(cfg =>
    {
        foreach (var registration in registrations)
        {
            switch (registration)
            {
                case lines:
                    cfg.CreateMap<LineInput, LineView>();
                    break;
                case order:
                    cfg.CreateMap<OrderDraft, OrderView>().MaxDepth(2);
                    break;
                case invoice:
                    cfg.CreateMap<InvoiceDraft, InvoiceView>();
                    break;
            }
        }
    });

    var mapper = configuration.CreateMapper();
    var cache = new List<CacheSnapshot>();
    RecordCache("initial");
    var warmupResults = new List<MapResult>();
    foreach (var warmup in warmups)
    {
        var number = warmup == order ? "ORD-WARM" : "INV-WARM";
        var line = new LineInput(12, 1);
        var warmExpected = new Snapshot(true, number, [new(12, 1)]);
        warmupResults.Add(warmup == order
            ? Map(warmExpected, new OrderView(), target => mapper.Map(new OrderDraft(number, [line]), target))
            : Map(warmExpected, new InvoiceView(), target => mapper.Map(new InvoiceDraft(number, [line]), target)));
        RecordCache($"warmup-{warmup}");
    }

    MapResult MeasureInvoice() => Map(expected,
        new InvoiceView { Number = "UNSET", Lines = [.. initialLines] },
        target => mapper.Map(new InvoiceDraft(invoiceNumber, [.. input]), target));

    var first = MeasureInvoice();
    RecordCache("measurement-1");
    var second = MeasureInvoice();
    RecordCache("measurement-2");
    if (inspectPlans)
    {
        plans.Add(CollectionPlans.Observe(name, repeat, configuration, cache));
    }

    return new Observation(name, repeat, registrations, warmups, warmupResults,
        [first, second]);

    void RecordCache(string stage)
    {
        if (inspectPlans)
        {
            cache.Add(CollectionPlans.ReadCache(stage, configuration));
        }
    }
}

static MapResult Map<T>(Snapshot expected, T initial, Func<T, T> map) where T : DocumentView
{
    try
    {
        var mapped = map(initial);
        var actual = new Snapshot(ReferenceEquals(mapped, initial), mapped.Number, mapped.Lines.ToArray());
        var matches = actual.SameDestination == expected.SameDestination && actual.Number == expected.Number
            && actual.Lines.SequenceEqual(expected.Lines);
        return new MapResult(matches, actual, []);
    }
    catch (Exception exception)
    {
        var errors = new List<MapError>();
        for (Exception? error = exception; error != null; error = error.InnerException)
        {
            errors.Add(new MapError(error.GetType().FullName!, error.Message));
        }
        return new MapResult(false, null, errors);
    }
}

record LineInput(int Id, int Quantity);
record LineView(int Id, int Quantity);
record OrderDraft(string Number, List<LineInput> Lines);
record InvoiceDraft(string Number, List<LineInput> Lines);

abstract class DocumentView
{
    public string Number { get; set; } = "";
    public List<LineView> Lines { get; set; } = [];
}

sealed class OrderView : DocumentView;
sealed class InvoiceView : DocumentView;

record Snapshot(bool SameDestination, string Number, LineView[] Lines);
record MapError(string Type, string Message);
record MapResult(bool MatchesExpected, Snapshot? Actual, IReadOnlyList<MapError> Exceptions);
record Observation(string Case, int Repeat, string[] Registration, string[] WarmupOrder,
    IReadOnlyList<MapResult> Warmups, MapResult[] Measurements);
