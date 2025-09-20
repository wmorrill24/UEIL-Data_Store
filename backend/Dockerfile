# Use the official Python 3.10 slim image as the base image
FROM python:3.10-slim

# Set the working directory inside the container to /app
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install Python dependencies without using the cache
RUN apt-get update && apt-get install -y git
RUN pip install --no-cache-dir -r requirements.txt

# Copy the contents of the local ./app directory to /app in the container
COPY ./app /app

# Expose port 8001 for the application
EXPOSE 8001

# Set the default command to run the app with uvicorn on port 8001 in reload mode
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]