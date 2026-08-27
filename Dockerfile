FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright and ReportLab (fonts/images)
RUN apt-get update && apt-get install -y \
    chromium \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY backend /app/backend
WORKDIR /app/backend

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# Copy frontend build (created by deploy.sh before the image build)
COPY frontend/dist/public /app/frontend_dist

# Set environment variables
ENV PORT=8080
ENV FRONTEND_DIST=/app/frontend_dist

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
