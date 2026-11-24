#!/bin/zsh
set -eu
set -o pipefail

if (( $# != 2 )) || [[ $2 != primary && $2 != repeat ]]; then
  print -u2 '用法：zsh reproduce.zsh <现有证据目录> <primary|repeat>'
  exit 2
fi

evidence=${1:A}
input=$2
tools=${0:A:h}
repo=${tools:h:h:h}
commit=6c4580c5e7ea41154696c071a53fd200059a768b
packages=(Abp Abp.AspNetCore Abp.EntityFrameworkCore Abp.Web.Common Abp.EntityFramework.Common)
tests=(Abp.Tests Abp.AspNetCore.Tests Abp.EntityFrameworkCore.Tests)

run() {
  local log=$1
  shift
  local code=0
  {
    print -r -- "cwd=$PWD"
    print -r -- "frameworkCommit=$commit"
    printf 'command='
    printf '%q ' "$@"
    printf '\n'
    "$@" || code=$?
    print -r -- "exitCode=$code"
  } > "$log" 2>&1
  return $code
}

mkdir "$evidence/$input"
cd "$evidence/$input"
git -C "$repo/aspnetboilerplate" archive "$commit" | tar -xf -
if [[ -n $(find . -type d \( -name obj -o -name bin \) -print) ]]; then
  print -u2 '固定源码归档中含有构建目录'
  exit 1
fi

projects=()
for name in "${packages[@]}"; do
  projects+=("src/$name/$name.csproj")
done
for name in "${tests[@]}"; do
  projects+=("test/$name/$name.csproj")
done
config="$evidence/$input.NuGet.Config"
cat > "$config" <<'CONFIG'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>
CONFIG

export NUGET_PACKAGES="$evidence/$input-packages"
run "$evidence/$input-dotnet-info.log" dotnet --info
run "$evidence/$input-new.log" dotnet new sln --name R0
run "$evidence/$input-sln.log" dotnet sln R0.sln add "${projects[@]}"
run "$evidence/$input-sources.log" dotnet nuget list source --configfile "$config" --format short
run "$evidence/$input-restore.log" dotnet restore R0.sln --configfile "$config" \
  --no-http-cache --force -p:Configuration=Release --verbosity normal
python3 "$tools/inventory.py" restore "$PWD" > "$evidence/$input-restore-inventory.json"

if [[ $input == repeat ]]; then
  exit 0
fi

for project in "${packages[@]}"; do
  run "$evidence/$project-msbuild.json.log" dotnet msbuild "src/$project/$project.csproj" \
    -p:Configuration=Release \
    -getProperty:PackageId,PackageVersion,AssemblyName,RootNamespace,TargetFramework,TargetFrameworks,RuntimeIdentifier,TargetPath \
    -getItem:ProjectReference
done
run "$evidence/build.log" dotnet build R0.sln --configuration Release --no-restore --verbosity minimal
mkdir "$evidence/trx"
test_status=0
for project in "${tests[@]}"; do
  run "$evidence/$project-test.log" dotnet test "test/$project/$project.csproj" \
    --configuration Release --no-build --no-restore --logger "trx;LogFileName=$project.trx" \
    --results-directory "$evidence/trx" || test_status=1
done
exit $test_status
