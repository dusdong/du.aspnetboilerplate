using System.Collections.Concurrent;
using System.Linq.Expressions;
using System.Reflection;
using AutoMapper;
using AutoMapper.Internal;

static class CollectionPlans
{
    private const BindingFlags NonPublicInstance = BindingFlags.NonPublic | BindingFlags.Instance;

    // 只在独立观测进程读取已存在的键，避免取 Lazy.Value 或请求集合计划。
    public static CacheSnapshot ReadCache(string stage, MapperConfiguration configuration)
    {
        var plans = typeof(MapperConfiguration).GetField("_executionPlans", NonPublicInstance)!
            .GetValue(configuration)!;
        var dictionary = (ConcurrentDictionary<MapRequest, Lazy<Delegate>>)plans.GetType()
            .GetField("_dictionary", NonPublicInstance)!.GetValue(plans)!;
        var keys = dictionary.Keys
            .Select(key => new CacheKey(Display(key.RequestedTypes), Display(key.RuntimeTypes)))
            .OrderBy(key => key.RequestedTypes, StringComparer.Ordinal)
            .ThenBy(key => key.RuntimeTypes, StringComparer.Ordinal)
            .ToArray();
        return new(stage, keys);

        static string Display(TypePair pair) => $"{pair.SourceType} -> {pair.DestinationType}";
    }

    public static CollectionPlanObservation Observe(string name, int repeat, MapperConfiguration configuration,
        IReadOnlyList<CacheSnapshot> cache)
    {
        var order = ReadMember<OrderDraft, OrderView>(configuration);
        var invoice = ReadMember<InvoiceDraft, InvoiceView>(configuration);
        return new(name, repeat, cache, order.Plan, invoice.Plan,
            ReferenceEquals(order.Lambda, invoice.Lambda),
            ReferenceEquals(order.Block, invoice.Block));
    }

    private static (MemberPlan Plan, LambdaExpression Lambda, BlockExpression Block)
        ReadMember<TSource, TDestination>(MapperConfiguration configuration)
    {
        var map = configuration.Internal().FindTypeMapFor<TSource, TDestination>();
        var member = map.PropertyMaps.Single(property => property.DestinationName == nameof(DocumentView.Lines));
        var lambda = map.MapExpression;
        var inspector = new PlanInspector();
        inspector.Visit(lambda);
        var block = inspector.CollectionBlocks.Single();
        var memberInspector = new PlanInspector();
        memberInspector.Visit(block);
        var debugView = typeof(Expression).GetProperty("DebugView", NonPublicInstance)!;
        var plan = new MemberPlan(member.SourceType.ToString(), member.DestinationType.ToString(),
            inspector.ContextCalls.ToArray(), memberInspector.ContextCalls.ToArray(),
            (string)debugView.GetValue(block)!);
        return (plan, lambda, block);
    }

    private sealed class PlanInspector : ExpressionVisitor
    {
        public List<BlockExpression> CollectionBlocks { get; } = [];
        public List<string> ContextCalls { get; } = [];

        protected override Expression VisitBlock(BlockExpression node)
        {
            // 固定 v14 的内建 CollectionMapper 为此集合成员生成这两个局部变量。
            if (node.Variables.Count == 2 &&
                node.Variables[0].Name == "collectionDestination" &&
                node.Variables[1].Name == "passedDestination" &&
                node.Type == typeof(List<LineView>))
            {
                CollectionBlocks.Add(node);
            }
            return base.VisitBlock(node);
        }

        protected override Expression VisitMethodCall(MethodCallExpression node)
        {
            if (node.Method.DeclaringType == typeof(ResolutionContext))
            {
                ContextCalls.Add(node.Method.ToString()!);
            }
            return base.VisitMethodCall(node);
        }
    }
}

record CollectionPlanObservation(string Case, int Repeat, IReadOnlyList<CacheSnapshot> Cache,
    MemberPlan Order, MemberPlan Invoice, bool SameParentLambda, bool SameCollectionBlock);
record CacheSnapshot(string Stage, CacheKey[] Keys);
record CacheKey(string RequestedTypes, string RuntimeTypes);
record MemberPlan(string SourceType, string DestinationType, string[] ParentContextCalls,
    string[] CollectionContextCalls, string CollectionExpression);
