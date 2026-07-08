    # Use a base Python image
    FROM python:3.11-slim-buster

    # Set the working directory in the container
    WORKDIR /app

    # Copy the requirements.txt file and install dependencies
    COPY devotions/requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy the rest of your application code
    COPY devotions/. .

    # Expose the port your application listens on (adjust if needed)
    EXPOSE 8080

    WORKDIR /app/python

    # Command to run your application (e.g., with Gunicorn).
    # 2 workers x 8 threads: the app is I/O-bound (Firestore, ESV API), so
    # threads absorb slow upstream calls; the default single sync worker let
    # one slow request block everything. Timeout raised 30s -> 60s to cover
    # cold ESV/Firestore calls without killing the worker.
    CMD ["gunicorn", "--workers", "2", "--threads", "8", "--timeout", "60", "--bind", "0.0.0.0:8080", "main:app"]