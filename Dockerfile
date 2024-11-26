# Pull base image
FROM python:latest
LABEL authors="vokur"

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/uwc

# Set work directory
WORKDIR /uwc

# Install system dependencies
RUN apt-get update && apt-get install -y gettext
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY . .