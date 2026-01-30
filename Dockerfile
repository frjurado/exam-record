# Base image matching user's python version closely
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default to /data for SQLite persistence on Fly.io
    DATABASE_URL=sqlite+aiosqlite:////data/exam_record.db

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Copy and setup start script
RUN chmod +x start.sh && \
    sed -i 's/\r$//' start.sh

# Expose port (Fly.io default is 8080)
EXPOSE 8080

# Command to run the application using startup script
CMD ["./start.sh"]
