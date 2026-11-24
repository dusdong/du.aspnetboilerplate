#!/bin/zsh
set -eu
set -o pipefail

if (( $# < 2 || $# > 5 )) || [[ $2 != primary && $2 != repeat ]]; then
  print -u2 '用法：zsh reproduce.zsh <现有证据目录> <primary|repeat>'
  exit 2
fi

evidence=${1:A}
input=$2
phase=${3:-legacy}
work=${4:-$evidence}
work=${work:A}
suite=${5:-}
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

materialize() {
  mkdir "$work/$input"
  git -C "$repo/aspnetboilerplate" archive "$commit" | tar -xf - -C "$work/$input"
  if [[ -n $(find "$work/$input" -type d \( -name obj -o -name bin \) -print) ]]; then
    print -u2 '固定源码归档中含有构建目录'
    return 1
  fi
}

config="$evidence/$input.NuGet.Config"
export NUGET_PACKAGES="$work/$input-packages"

restore() {
  cd "$work/$input"
  mkdir "$NUGET_PACKAGES"
  local -a projects
  local name
  for name in "${packages[@]}"; do
    projects+=("src/$name/$name.csproj")
  done
  for name in "${tests[@]}"; do
    projects+=("test/$name/$name.csproj")
  done
  cat > "$config" <<'CONFIG'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>
CONFIG
  run "$evidence/$input-dotnet-info.log" dotnet --info
  run "$evidence/$input-new.log" dotnet new sln --name R0
  run "$evidence/$input-sln.log" dotnet sln R0.sln add "${projects[@]}"
  run "$evidence/$input-sources.log" dotnet nuget list source --configfile "$config" --format short
  run "$evidence/$input-restore.log" dotnet restore R0.sln --configfile "$config" \
    --no-http-cache --force -p:Configuration=Release --verbosity normal
  run "$evidence/$input-inventory.log" python3 "$tools/inventory.py" restore "$PWD" \
    --output "$evidence/$input-restore-inventory.json" --packages-root "$NUGET_PACKAGES"
}

identity() {
  cd "$work/$input"
  local project
  for project in "${packages[@]}"; do
    run "$evidence/$project-msbuild.json.log" dotnet msbuild "src/$project/$project.csproj" \
      -p:Configuration=Release \
      -getProperty:PackageId,PackageVersion,AssemblyName,RootNamespace,TargetFramework,TargetFrameworks,RuntimeIdentifier,TargetPath \
      -getItem:ProjectReference
  done
}

build() {
  cd "$work/$input"
  run "$evidence/build.log" dotnet build R0.sln --configuration Release --no-restore --verbosity minimal
}

run_test() {
  cd "$work/$input"
  mkdir -p "$evidence/trx"
  local project=$1
  run "$evidence/$project-test.log" dotnet test "test/$project/$project.csproj" \
    --configuration Release --no-build --no-restore --logger "trx;LogFileName=$project.trx" \
    --results-directory "$evidence/trx"
}

case "$phase" in
  legacy)
    materialize
    restore
    if [[ $input == primary ]]; then
      identity
      build
      test_status=0
      for project in "${tests[@]}"; do
        run_test "$project" || test_status=1
      done
      exit $test_status
    fi
    ;;
  inputs)
    print -r -- "$commit"
    printf '%s\n' "${packages[@]}"
    print -r -- --
    printf '%s\n' "${tests[@]}"
    ;;
  materialize) materialize ;;
  restore) restore ;;
  identity|build|test)
    if [[ $input != primary || ($phase == test && ${tests[(Ie)$suite]} == 0) ]]; then
      print -u2 '构建、身份求值和套件运行需要已还原的 primary 和已知套件名'
      exit 2
    fi
    if [[ $phase == test ]]; then
      run_test "$suite"
    else
      "$phase"
    fi
    ;;
  *)
    print -u2 -- "未知复验阶段：$phase"
    exit 2
    ;;
esac
