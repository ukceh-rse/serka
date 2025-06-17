#!/bin/bash
# Start the ollama server
/bin/ollama serve &
pid=$!
sleep 5

# Install the yq utility for reading the YAML configuration
apt update
apt install wget -y
wget https://github.com/mikefarah/yq/releases/download/v4.2.0/yq_linux_amd64 -O /usr/bin/yq
chmod +x /usr/bin/yq

# Pull the appropriate models listed in config.yml
readarray -t models < <(
    yq eval '.embedding_models[]' config.yml
    yq eval '.rag_models[]' config.yml
)
for model in "${models[@]}"; do
    echo "Pulling model[$model]..."
    ollama pull $model
done
echo "Finished pulling model(s)"

wait $pid
