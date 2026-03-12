FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy application code
COPY core/ ./core/
COPY backend/ ./backend/
COPY data/ ./data/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 9000

# Environment (override via Railway/Docker env)
ENV ANTHROPIC_API_KEY=""
ENV STRIPE_SECRET_KEY=""
ENV STRIPE_PUBLISHABLE_KEY=""
ENV STRIPE_WEBHOOK_SECRET=""
ENV STRIPE_STARTER_PRICE_ID=""
ENV STRIPE_PRO_PRICE_ID=""
ENV PORT=9000

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9000"]
