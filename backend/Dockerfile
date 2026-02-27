# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# libgl1-mesa-glx may be needed for some image processing libraries if used
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create the uploads directory
RUN mkdir -p uploads

# Expose the port the app runs on
EXPOSE 8874

# Command to run the application
# Use the correct import path for the module
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8874"]