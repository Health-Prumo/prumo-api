# Encaminha argumentos adicionais ao pytest.
& "$PSScriptRoot/_python.ps1" test @args
exit $LASTEXITCODE
