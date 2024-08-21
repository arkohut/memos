@echo off

set TYPESENSE_API_KEY=xyz

if not exist "%CD%\typesense-data" mkdir "%CD%\typesense-data"

docker run -d -p 8108:8108 ^
    -v "%CD%\typesense-data:/data" typesense/typesense:26.0 ^
    --add-host=host.docker.internal:host-gateway ^
    --data-dir /data ^
    --api-key=%TYPESENSE_API_KEY% ^
    --enable-cors