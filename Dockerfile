# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app
# Set python unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Copy and install Python dependencies
COPY . .
RUN pip install --no-cache-dir -r requirements.txt &&\
    chown -R 65532:65532 /app

USER 65532:65532
# Copy the bot script

# Run the bot
CMD ["python", "bot_start.py"]