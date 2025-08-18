docker build -t raglibrarian .

docker run --rm -it -e OPENAI_API_KEY="insert-key-here" -e MODEL=gpt-5-nano -e PORT=8989 -e CHROMA_TELEMETRY_ENABLED=false -p 8989:8989 -v smartlib_chroma:/app/chroma_data smart-librarian

[localhost](http://localhost:8989/docs#/default/health_healthz_get)