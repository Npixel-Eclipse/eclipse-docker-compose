FROM python:3.11-slim

WORKDIR /app

# Install uv and Perforce CLI
RUN apt-get update && apt-get install -y wget && \
    wget -qO /usr/local/bin/p4 https://cdist2.perforce.com/perforce/r23.2/bin.linux26x86_64/p4 && \
    chmod +x /usr/local/bin/p4 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install uv

# Copy all project files first
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY .env.example ./.env.example

# Install dependencies (not editable mode in container)
RUN uv pip install --system .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
