# Secrets

Dazpycheck rejects Python projects that import the retired `keyring` or
`securitykeyring` modules or invoke macOS `security(1)` through subprocesses.
Projects should use the public `daz-secrets` SDK, whose private local provider
communicates over stdin/stdout and never opens graphical authentication UI.

Releases read `pypi/api_token` through that SDK and pass it to Twine in-process;
the token never enters environment variables, command-line arguments, files, or
logs.
