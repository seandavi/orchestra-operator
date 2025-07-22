FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy source code
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home --shell /bin/bash operator
USER operator

# Set Python path
ENV PYTHONPATH=/app/src

# Run the operator
CMD ["python", "-m", "main"]
