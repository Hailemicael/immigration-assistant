# Immigration Assistant (MAIA) Setup Guide

This guide provides instructions for setting up the Immigration Assistant application including PostgreSQL with pgvector extension, database configuration, and running the application.

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 14 or higher
- pip package manager
- Access to terminal/command line

## Required Python Dependencies

```bash
# Install required Python packages
pip install flask
pip install asyncpg
pip install langgraph
pip install langchain_ollama
pip install sentence-transformers
pip install transformers
pip install typing-extensions
pip install langchain-core
pip install googletrans
pip install torch
pip install pydantic
pip install pandas
pip install evaluate
pip install pydantic-core
pip install huggingface-hub
pip install bcrypt
pip install PyYAML
```

## 1. Installing PostgreSQL and pgvector

### Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install development packages required for pgvector
sudo apt install postgresql-server-dev-all build-essential git

# Clone and install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
cd ..
```

### macOS (using Homebrew)

```bash
# Install PostgreSQL
brew install postgresql

# Start PostgreSQL service
brew services start postgresql

# Install pgvector
brew install pgvector
```

### Windows

1. Download PostgreSQL installer from https://www.postgresql.org/download/windows/
2. Run the installer and follow the instructions
3. Install pgvector:
    - Download from https://github.com/pgvector/pgvector/releases
    - Follow installation instructions in the README

## 2. Configuring PostgreSQL

### Create User and Set Password

```bash
# Connect to PostgreSQL as the postgres superuser
sudo -u postgres psql

# Inside PostgreSQL console, create user and set password
CREATE USER postgres WITH PASSWORD '12345';
ALTER USER postgres WITH SUPERUSER;

# Exit PostgreSQL console
\q
```

### Create the Database

```bash
# Connect to PostgreSQL as postgres user
sudo -u postgres psql

# Create the database
CREATE DATABASE maia;

# Connect to the new database
\c maia

# Enable pgvector extension
CREATE EXTENSION vector;

# Exit PostgreSQL console
\q
```

## 3. Restore Database Dump

```bash
# Restore database from dump file
sudo -u postgres pg_restore -d maia database.dump
```

## 4. Configure the Application

Create or modify `config.yaml` in your project directory with the following content:

```yaml
secret_key: "comp-710-is-the-best!"
session_lifetime_days: 30

database:
  dsn: "postgresql://postgres:12345@localhost:5432"
  database: "maia"
  pool_size: [10, 10]

paths:
  templates: "./templates"
  user_reg_sql: "./user-registration/sql"
  rag_sql: "./rag/sql"
  faqs: "./rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json"
  forms: "./rag/uscis-crawler/documents/forms"
  legislation: "./rag/uscis-crawler/documents/legislation"

relevance:
  threshold: 0.65

reasoning:
  endpoint: "https://apc68c0a4ml2min4.us-east-1.aws.endpoints.huggingface.cloud"
  api_token: "your-api-token"
```

Make sure to replace `"your-api-token"` with your actual API token for the reasoning service.

## System Architecture Overview

The Immigration Assistant is a modular system composed of several specialized agents:

- **UserRegistration**: Handles user authentication and session management
- **TranslatorAgent**: Provides translation services for multilingual support
- **SummaryAgent**: Creates concise summaries of complex documents
- **RelevanceAgent**: Determines the relevance of information to user queries
- **ReasoningAgent**: Performs logical reasoning about immigration cases
- **RAGAgent**: Retrieval-Augmented Generation for finding relevant information
- **TimelineAgent**: Creates and manages immigration process timelines
- **RMAIA**: Main orchestration component that coordinates all agents

The system uses a PostgreSQL database with pgvector extension to store and query vector embeddings for semantic search functionality.

## 5. Running the Application

Navigate to the parent directory of the `immigration_assistant` package and run:

```bash
python3 -m immigration_assistant.flask_app --config path/to/config.yaml
```

### Command-line Options

- `--config`: Path to config file (default: `config.yaml`)
- `--host`: Host to run the Flask server (default: `0.0.0.0`)
- `--port`: Port to run the Flask server (default: `5011`)
- `--debug`: Enable Flask debug mode
- `--init-database`: Initialize schemas for database
- `--clear-database`: Truncate and repopulate the database
- `--populate-database`: Populate all tables in the RAG database

### Examples

Initialize database and start the application:
```bash
python3 -m immigration_assistant.flask_app --config config.yaml --init-database
```

Clear and repopulate database before starting:
```bash
python3 -m immigration_assistant.flask_app --config config.yaml --clear-database --populate-database
```

Run on specific port with debug mode:
```bash
python3 -m immigration_assistant.flask_app --config config.yaml --port 8080 --debug
```

## 6. Accessing the Application

Once the application is running, access it through your browser at:
```
http://localhost:5011
```

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL service is running
- Verify connection string in config.yaml
- Check that user has appropriate permissions
- Ensure pgvector extension is properly installed in the database

### Python Dependencies
- If you encounter ModuleNotFoundError, install the missing dependency:
  ```bash
  pip install [missing-module-name]
  ```
- Ensure correct versions of dependencies are installed:
  ```bash
  pip list | grep [package-name]
  ```
- For torch installation issues on different platforms, refer to the PyTorch official documentation

### Application Errors
- Check console output for error messages
- Ensure all dependencies are installed
- Verify file paths in config.yaml
- For embedding model errors, ensure you have sufficient RAM available

## Additional Notes

- The application uses sentence-transformers for embedding generation
- LangGraph is used for orchestrating the different components of the system
- Flask provides the web interface for interacting with the application
- AsyncPG is used for asynchronous PostgreSQL connections
- LangChain components provide integration with local LLM models via Ollama
- Vector database capabilities support semantic search functionality
- The application includes a translation service using GoogleTrans
- Hugging Face Hub integration allows access to models for summarization
- Ensure you have sufficient memory for running embedding models
- For production use, consider changing the default password