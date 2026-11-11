@echo off
setlocal
pushd "%~dp0"
java -jar "ym-login-plug-1.1.5.jar" --debug=false
set "PLUGIN_EXIT=%ERRORLEVEL%"
popd
exit /b %PLUGIN_EXIT%
