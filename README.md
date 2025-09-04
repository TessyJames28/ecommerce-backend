# Horal

## Overview
This is the backend repository for Horal Technologies ecommerce website

## Technologies Used
- **Python**: 3.12.2
- **Django**: 5.2
- **Django Rest Framework**: 3.16.0
- **JWT**: 5.5.0 (For authentication)

## Installation

1. **Clone the repository:**
 git clone https://github.com/HoralTechnologies/ecommerce-backend.git

2. **Navigate to repository directory:**
 cd ecommerce-backend

3. **Create a virtual environment if not already  created:**
 python3.12 -m venv venv

4. **Activate the virtual environment:**
 - On Windows:
   .\venv\Scripts\activate
 
 - On MacOS/Linux:
   source venv/bin/activate
5. **Install required dependencies:**
 pip install -r requirements.txt


## Setup

1. **Run migration:**
 python manage.py migrate

2. **Create a superuser (optional):**
 python manage.py createsuperuser

3. **Run development server:**
 python manage.py runserver

 Your application will now be running at ``http://127.0.0.1:8000/``

