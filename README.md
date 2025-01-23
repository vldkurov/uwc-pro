# UWC Project - README

## Project Overview

UWC is a non-profit web application designed for content management and donations.

### 1. Prerequisites

Before getting started, ensure the following software is installed on your machine:
	•	Docker and Docker Compose
	•	Git
	•	Python 3.10+ (for optional tools outside Docker)
	•	Make (optional, for simplified commands)

### 2. Installation and Setup

#### Step 1: Clone the Repository
    
git clone <repository-url>
cd uwc_pro
    
#### Step 2: Create Environment Variables (.env)

##### 1.	Copy the example configuration file:
    
cp .env.example .env
    
##### 2.	Fill in the required environment variables in the .env file, including your API keys (e.g., Google Maps, PayPal).
    
#### Step 3: Build and Start the Containers
    
For Development:
    
docker-compose -f docker-compose.yml up --build
    
For Production:
    
docker-compose -f docker-compose-prod.yml up --build -d
    
Note:
        
•	The file docker-compose-prod.yml.example should be copied to docker-compose-prod.yml and configured for your server.
•	Enable SSL certificates and use secure environment variables in production.
    
#### Step 4: Apply Migrations and Collect Static Files

##### Step 1: Create Database Migrations
    
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

##### Step 2: Load Demo Data

docker-compose exec web python manage.py loaddata fixtures/data.json

##### Step 3: Collect Static Files

docker-compose exec web python manage.py collectstatic --noinput
    
#### Step 5: Create a Superuser
    
docker-compose exec web python manage.py createsuperuser
    
#### Step 6: Access the Application
•	Development: http://localhost:8000
    
Test Logins:
    
•	Admin: admin@mail.com / testpass123
•	Editor: editor@mail.com / testpass123
•	Viewer: viewer@mail.com / testpass123

### 3. Database Management (PostgreSQL)

Connect to the Database in the Container:

docker-compose exec db psql -U postgres

Create a Database Backup:

docker-compose exec db pg_dump -U postgres postgres > backup.sql

### 4. Running Tests
    
docker-compose exec web python manage.py test

### 5. Useful Commands

Stop All Containers:
    
docker-compose down

View Container Logs:

docker-compose logs -f

Rebuild Project After Changes:

docker-compose build

### 6. Project Structure

uwc_pro/
├── accounts/                # User management module
├── payments/                # Payment systems (Stripe, PayPal)
├── locations/               # Location management
├── hub/                     # Content management system (CMS)
├── pages/                   # Public content
├── templates/               # HTML templates
├── static/                  # Static files
├── fixtures/                # Demo data (data.json)
├── locale/                  # Translation files for i18n
├── Dockerfile               # Docker image build configuration
├── docker-compose.yml       # Docker development configuration
├── docker-compose-prod.yml  # Docker production configuration
├── manage.py                # Django project management
└── README.md                # Documentation

### 7. Security Guidelines

Important Notes:
	1.	Always use secure environment variables in production.
	2.	Configure SSL certificates to secure connections.
	3.	Regularly update dependencies to the latest versions.

### 8. Environment Variables

Important:

1.	Copy the example environment file:

	cp .env.example .env

2. Open the .env file and update it with your specific values (e.g. API keys, database settings).
3. Ensure the .env file is not included in version control to protect sensitive information.

### 9. Contact and Support

For any questions or suggestions, please contact the developer at: volodymyr.kurov.dev@gmail.com.