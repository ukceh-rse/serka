#!/bin/bash
/bin/ollama serve &
pid=$!
sleep 5
model="tinyllama"
echo "Pulling model[$model]..."
ollama pull $model
echo "Finished pulling model"
wait $pid
