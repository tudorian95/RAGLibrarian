# RAG Librarian

This RAG Librarian application parses a request from the end user via OpenAI's API and then uses a local vector database (ChromaDB in our case) to further refine the answer based on an already existing corpus of whitelisted literature.

## Setup

In order to build and run the application you need to have docker installed and running, since it will be started from a local container, with all the dependencies self included.

After you clone the repository in any local folder of your choosing via:

```bash
git clone https://github.com/tudorian95/RAGLibrarian.git
```

Then open a terminal window in said folder and execute the following commands:

```bash
docker build -t raglibrarian .
```

```bash
docker run --rm -it -e OPENAI_API_KEY="insert-key-here" -e MODEL=gpt-5-nano -e PORT=8989 -e CHROMA_TELEMETRY_ENABLED=false -p 8989:8989 -v smartlib_chroma:/app/chroma_data raglibrarian
```

You need to provide an OpenAI API key in order to run the app via changing the `insert-key-here` part of the command with an actually valid key.

Access the application at: [localhost:8989](http://localhost:8989)