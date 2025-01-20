#!/bin/bash
/bin/ollama serve &
pid=$!
sleep 5
echo "Pulling model[$OLLAMA_MODEL]..."
ollama pull $OLLAMA_MODEL
echo "Finished pulling model"
echo "Pulling model[$OLLAMA_EMBEDDING_MODEL]..."
ollama pull $OLLAMA_EMBEDDING_MODEL
echo "Finished pulling model"
wait $pid
