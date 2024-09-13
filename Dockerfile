# Use the official Python image from the Docker Hub
FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Make port 5555 available to the world outside this container
EXPOSE 5555

# Define environment variable
ENV FLASK_APP=app.py

# Run Flask when the container launches
CMD ["flask", "run", "--host=0.0.0.0", "--port=5555"]