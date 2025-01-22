#!/bin/bash
# Start the ollama server
/bin/ollama serve &
pid=$!
sleep 5

# Install the yq utility for reading the yaml configuration
apt update
apt install wget -y
wget https://github.com/mikefarah/yq/releases/download/v4.2.0/yq_linux_amd64 -O /usr/bin/yq
chmod +x /usr/bin/yq

# Pull the appropriate models listed in config.yaml
readarray -t models < <(
    yq eval '.ollama.embedding_models[]' config.yaml
    yq eval '.ollama.rag_models[]' config.yaml
)
for model in "${models[@]}"; do
    echo "Pulling model[$model]..."
    ollama pull $model
done
echo "Finished pulling model(s)"

wait $pid
