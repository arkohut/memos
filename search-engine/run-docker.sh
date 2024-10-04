export TYPESENSE_API_KEY=xyz

mkdir "$(pwd)"/typesense-data

docker run -d -p 8108:8108 \
	--restart always \
	-v"$(pwd)"/typesense-data:/data typesense/typesense:27.0 \
	--add-host=host.docker.internal:host-gateway \
	--data-dir /data \
	--api-key=$TYPESENSE_API_KEY \
	--enable-cors
