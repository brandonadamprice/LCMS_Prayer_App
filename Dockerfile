    # Use a base Python image
    FROM python:3.9-slim-buster

    # Set the working directory in the container
    WORKDIR /app

    # Copy the requirements.txt file and install dependencies
    COPY devotions/requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy the rest of your application code
    COPY devotions/. .

    # Expose the port your application listens on (adjust if needed)
    EXPOSE 8080

    # Command to run your application (e.g., with Gunicorn)
    CMD ["gunicorn", "--bind", "0.0.0.0:8080", "evening_devotion:app"]