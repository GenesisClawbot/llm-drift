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
ENV STRIPE_STARTER_PRICE_ID="price_1TAEMZ7dVu3KiOEDGuyO9mtF"
ENV STRIPE_PRO_PRICE_ID="price_1TAEMa7dVu3KiOEDEgg8hFWf"
ENV SECRET_KEY="change-me-in-production"
ENV PORT=8000
ENV SMTP_FROM="clawgenesis@gmail.com"
ENV SMTP_PASSWORD=""

# Use shell form so $PORT is expanded at runtime
CMD python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
