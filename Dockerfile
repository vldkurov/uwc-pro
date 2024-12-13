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

# Install system dependencies, including PostgreSQL client
RUN apt-get update && apt-get install -y \
    gettext \
    postgresql-client && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Set the command to start Gunicorn
CMD ["gunicorn", "django_project.wsgi:application", "--bind", "0.0.0.0:8000"]