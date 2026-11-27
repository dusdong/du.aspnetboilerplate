using System.ComponentModel.DataAnnotations.Schema;
using System.Data.Common;
using System.Linq.Expressions;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;
using Abp.Authorization.Users;
using Abp.ObjectMapping;
using AbpCompanyName.AbpProjectName.Authorization.Users;
using AbpCompanyName.AbpProjectName.Users.Dto;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;

namespace AutoMapperProbe;

internal static class Projection
{
    private const string QueryTag = "AutoMapperProbe.UserProjection";
    private static readonly DateTime Creation = new(2022, 4, 13, 12, 0, 0);

    internal static void Verify(IObjectMapper mapper, Action<object> capture, string[]? expectedColumns)
    {
        using var connection = new SqliteConnection("Data Source=:memory:;Pooling=False");
        connection.Open();
        var commands = new SqlCapture();
        var options = new DbContextOptionsBuilder<Users>().UseSqlite(connection).AddInterceptors(commands).Options;
        using var database = new Users(options);
        database.Database.EnsureCreated();
        database.AddRange(
            Seed(11, 6, "alpha", "Ada", "Alpha", true),
            Seed(12, 6, "zulu", "Zoe", "Zulu", true),
            Seed(13, 6, "beta", "Bea", "Beta", true),
            Seed(14, 6, "inactive", "Ian", "Inactive", false),
            Seed(15, 7, "foreign", "Faye", "Foreign", true));
        database.SaveChanges();
        database.ChangeTracker.Clear();

        var tenantId = 6;
        var users = database.Set<User>().AsNoTracking().TagWith(QueryTag)
            .Where(user => user.TenantId == tenantId && user.IsActive)
            .OrderByDescending(user => user.UserName).ThenBy(user => user.Id);
        var query = mapper.ProjectTo<UserDto>(users);
        var expression = query.Expression.ToString();
        var result = query.ToArray();
        var executed = commands.Results.Single();
        object Evidence(object? fullName) => new
        {
            provider = database.Database.ProviderName,
            providerVersion = typeof(SqliteDbContextOptionsBuilderExtensions).Assembly.GetName().Version!.ToString(),
            sqliteVersion = connection.ServerVersion,
            expression,
            fullName,
            executed,
            result
        };
        capture(Evidence(null));
        var fullName = FullNameMember(query.Expression);
        var mappedColumn = database.Model.FindEntityType(typeof(User))!.FindProperty(nameof(User.FullName)) is not null;
        capture(Evidence(new
        {
            location = mappedColumn ? "server" : "client",
            entityMember = fullName.Member.DeclaringType!.FullName + "." + fullName.Member.Name,
            mappedColumn
        }));
        VerifySql(executed, tenantId, expectedColumns ?? ReadExpectedColumns());

        Program.Require(result.Select(user => (user.Id, user.UserName, user.Name, user.Surname, user.FullName))
            .SequenceEqual([(12L, "zulu", "Zoe", "Zulu", "Zoe Zulu"), (13L, "beta", "Bea", "Beta", "Bea Beta"),
                (11L, "alpha", "Ada", "Alpha", "Ada Alpha")]), "SQLite 结果顺序与姓名应符合已知值");
        Program.Require(result.All(user => user.CreationTime == Creation && user.IsActive &&
            user.EmailAddress == user.UserName + "@example.invalid" && user.RoleNames is null && user.LastLoginTime is null),
            "其他投影字段应满足种子预期");
        Program.Require(typeof(User).GetProperty(nameof(User.FullName))!.GetCustomAttribute<NotMappedAttribute>() is not null &&
            !mappedColumn,
            "FullName 应保持为未映射的实体属性");
    }

    private static string[] ReadExpectedColumns()
    {
        using var stream = typeof(Projection).Assembly.GetManifestResourceStream("projection-columns.json")!;
        return JsonSerializer.Deserialize<string[]>(stream)!;
    }

    private static MemberExpression FullNameMember(Expression expression)
    {
        Program.Require(expression is MethodCallExpression { Method.Name: nameof(Queryable.Select) },
            "查询应包含 AutoMapper 的 Select 投影");
        var select = (MethodCallExpression)expression;
        var selector = (LambdaExpression)((UnaryExpression)select.Arguments[1]).Operand;
        var binding = ((MemberInitExpression)selector.Body).Bindings.OfType<MemberAssignment>()
            .Single(member => member.Member.Name == nameof(UserDto.FullName));
        Program.Require(binding.Expression is MemberExpression member &&
            member.Member.Name == nameof(User.FullName) && member.Member.DeclaringType == typeof(AbpUserBase) &&
            member.Expression == selector.Parameters.Single(),
            "FullName 投影应访问已有实体属性");
        return (MemberExpression)binding.Expression;
    }

    private static void VerifySql(ExecutedQuery query, int tenantId, string[] expectedColumns)
    {
        Program.Require(query.Columns.SequenceEqual(expectedColumns),
            $"SQLite 读取列或顺序不同。预期 {string.Join(", ", expectedColumns)}。实际 {string.Join(", ", query.Columns)}");
        var parameter = query.Parameters.Single();
        Program.Require(parameter.DbType == "Int32" && Equals(parameter.Value, tenantId),
            "SQLite 应收到 Int32 租户参数");
        // SQLite 返回原版实体标量列，FullName 由客户端投影访问实体属性计算。
        const string firstQualifier = """(?<alias>"(?:[^"]|"")+")\s*\.\s*""";
        const string qualifier = @"\k<alias>\s*\.\s*";
        var columns = string.Join(@"\s*,\s*", expectedColumns.Select((column, index) =>
            $@"{(index == 0 ? firstQualifier : qualifier)}""{Regex.Escape(column)}"""));
        var sql = $$"""
            \ASELECT\s+{{columns}}\s+FROM\s+"Users"\s+AS\s+\k<alias>
            \s+WHERE\s+{{qualifier}}"TenantId"\s*=\s*{{Regex.Escape(parameter.Name)}}\s+AND\s+{{qualifier}}"IsActive"
            \s+ORDER\s+BY\s+{{qualifier}}"UserName"\s+DESC\s*,\s*{{qualifier}}"Id"(?:\s+ASC)?\s*\z
            """;
        sql = sql.ReplaceLineEndings(string.Empty);
        var select = query.Sql[query.Sql.IndexOf('\n')..].Trim();
        Program.Require(Regex.IsMatch(select, sql, RegexOptions.CultureInvariant | RegexOptions.IgnoreCase),
            "执行 SQL 的取列、租户过滤、活跃条件或排序与原版不同：" + query.Sql);
    }

    private static User Seed(long id, int tenantId, string username, string name, string surname, bool active) => new()
    {
        Id = id,
        TenantId = tenantId,
        UserName = username,
        Name = name,
        Surname = surname,
        EmailAddress = username + "@example.invalid",
        CreationTime = Creation,
        IsActive = active,
        Password = "fixture",
        NormalizedUserName = username.ToUpperInvariant(),
        NormalizedEmailAddress = username.ToUpperInvariant() + "@EXAMPLE.INVALID"
    };

    private sealed class Users(DbContextOptions<Users> options) : DbContext(options)
    {
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            var user = modelBuilder.Entity<User>().ToTable("Users");
            // 投影只需要真实用户实体的标量属性。
            user.Ignore(u => u.Logins).Ignore(u => u.Roles).Ignore(u => u.Claims)
                .Ignore(u => u.Permissions).Ignore(u => u.Settings)
                .Ignore(u => u.CreatorUser).Ignore(u => u.LastModifierUser).Ignore(u => u.DeleterUser);
        }
    }

    private sealed class SqlCapture : DbCommandInterceptor
    {
        internal List<ExecutedQuery> Results { get; } = [];

        public override DbDataReader ReaderExecuted(DbCommand command, CommandExecutedEventData eventData, DbDataReader result)
        {
            if (command.CommandText.StartsWith("-- " + QueryTag, StringComparison.Ordinal))
            {
                var parameters = command.Parameters.Cast<DbParameter>()
                    .Select(p => new SqlParameter(p.ParameterName, p.DbType.ToString(), p.Value)).ToArray();
                Results.Add(new(command.CommandText, parameters, Enumerable.Range(0, result.FieldCount)
                    .Select(result.GetName).ToArray()));
            }
            return result;
        }
    }

    private sealed record ExecutedQuery(string Sql, SqlParameter[] Parameters, string[] Columns);
    private sealed record SqlParameter(string Name, string DbType, object? Value);
}
