using System.Collections.Concurrent;
using System.Linq.Expressions;
using System.Reflection;
using AutoMapper;
using AutoMapper.Internal;

sealed class CollectionPlans
{
    private const BindingFlags NonPublicInstance = BindingFlags.NonPublic | BindingFlags.Instance;

    private readonly string _shipmentExpression;
    private readonly string _returnExpression;
    private readonly MapRequest _shipmentRequest;
    private readonly MapRequest _returnRequest;
    private readonly ConcurrentDictionary<MapRequest, Lazy<Delegate>> _cache;
    private readonly Dictionary<Delegate, int> _delegateIds = new(ReferenceEqualityComparer.Instance);
    private readonly List<CacheSnapshot> _snapshots = [];

    public CollectionPlans(MapperConfiguration configuration)
    {
        (_shipmentRequest, _shipmentExpression) = ReadMember<ShipmentDraft, ShipmentView>(configuration);
        (_returnRequest, _returnExpression) = ReadMember<ReturnDraft, ReturnView>(configuration);
        var executionPlans = typeof(MapperConfiguration).GetField("_executionPlans", NonPublicInstance)!
            .GetValue(configuration)!;
        _cache = (ConcurrentDictionary<MapRequest, Lazy<Delegate>>)executionPlans.GetType()
            .GetField("_dictionary", NonPublicInstance)!.GetValue(executionPlans)!;
    }

    public void ReadCache(string stage, string? parent)
    {
        var entries = new List<CacheEntry>();
        foreach (var (key, lazy) in _cache)
        {
            // 只读取自然 Map 已生成的委托。
            var plan = lazy.IsValueCreated ? lazy.Value : null;
            if (plan != null && !_delegateIds.ContainsKey(plan))
            {
                _delegateIds.Add(plan, _delegateIds.Count + 1);
            }

            entries.Add(new(Display(key.RequestedTypes), Display(key.RuntimeTypes),
                key.MemberMap?.TypeMap?.SourceType.Name, key.MemberMap?.DestinationName,
                key.Equals(_shipmentRequest), key.Equals(_returnRequest),
                plan == null ? null : _delegateIds[plan], plan?.Method.Name));
        }
        _snapshots.Add(new(stage, parent, entries
            .OrderBy(entry => entry.RequestedTypes, StringComparer.Ordinal)
            .ThenBy(entry => entry.RuntimeTypes, StringComparer.Ordinal)
            .ToArray()));

        static string Display(TypePair pair) => $"{pair.SourceType} -> {pair.DestinationType}";
    }

    public PlanObservation Report(string name, int repeat) =>
        new(name, repeat, _shipmentExpression, _returnExpression, _snapshots);

    private static (MapRequest Request, string Expression) ReadMember<TSource, TDestination>(
        MapperConfiguration configuration)
    {
        var map = configuration.Internal().FindTypeMapFor<TSource, TDestination>();
        var member = map.PropertyMaps.Single(property => property.DestinationName == nameof(DocumentView.Lines));
        var calls = new MemberCalls(member);
        calls.Visit(map.MapExpression);
        var call = calls.CollectionCalls.Single();
        var types = call.Method.GetGenericArguments();
        var pair = new TypePair(types[0], types[1]);
        // 两个成员传入的源和已有目标都使用各自的具体 List 类型。
        return (new MapRequest(pair, pair, member), call.ToString());
    }

    private sealed class MemberCalls(MemberMap member) : ExpressionVisitor
    {
        public List<MethodCallExpression> CollectionCalls { get; } = [];

        protected override Expression VisitMethodCall(MethodCallExpression node)
        {
            if (node.Method.DeclaringType == typeof(ResolutionContext) && node.Method.Name == "MapInternal"
                && node.Arguments[^1] is ConstantExpression argument && ReferenceEquals(argument.Value, member))
            {
                CollectionCalls.Add(node);
            }
            return base.VisitMethodCall(node);
        }
    }
}

record PlanObservation(string Case, int Repeat, string ShipmentExpression, string ReturnExpression,
    IReadOnlyList<CacheSnapshot> Cache);
record CacheSnapshot(string Stage, string? Parent, CacheEntry[] Entries);
record CacheEntry(string RequestedTypes, string RuntimeTypes, string? PopulatedBySourceType,
    string? PopulatedByMember, bool MatchesShipmentRequest, bool MatchesReturnRequest, int? Delegate,
    string? Method);
