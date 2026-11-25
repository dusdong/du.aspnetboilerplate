using Abp.AutoMapper;
using Abp.Modules;
using AutoMapper.EquivalencyExpression;

namespace AutoMapperProbe;

[DependsOn(typeof(AbpAutoMapperModule))]
public sealed class ProbeModule : AbpModule
{
    public override void PreInitialize() => Configuration.BackgroundJobs.IsJobExecutionEnabled = false;

    public override void Initialize()
    {
        var thisAssembly = typeof(ProbeModule).Assembly;
        IocManager.RegisterAssemblyByConvention(thisAssembly);
        // 沿用固定模板 ApplicationModule 的 Profile 扫描入口，并启用独立集合用例。
        Configuration.Modules.AbpAutoMapper().Configurators.Add(cfg => cfg.AddMaps(thisAssembly));
        Configuration.Modules.AbpAutoMapper().Configurators.Add(cfg => cfg.AddCollectionMappers());
    }
}

[AutoMapTo(typeof(CollectionItem))]
public sealed class CollectionInput
{
    [AutoMapKey]
    public int Key { get; init; }
    public string Value { get; init; }
}

public sealed class CollectionItem
{
    public int Key { get; set; }
    public string Value { get; set; }
}
