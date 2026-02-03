@echo off
pushd %~dp0

:: Convert all YAML files to JSON
for %%f in (*.yaml) do (
  yq -o json . "%%f" > "%%~nf.json"
)

:: Archive all JSON files into a single ZIP
zip "%date%-%time::=-%.zip" *.json

:: Delete temporary JSON files
del *.json

popd
