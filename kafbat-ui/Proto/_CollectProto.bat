pushd %~dp0

set FILENAME="_Eclipse_Proto_%DATE%.zip"

zip -r %FILENAME% . -i *.proto

popd

pause