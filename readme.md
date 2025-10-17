# Aegis Backend

[![Build Status](https://img.shields.io/travis/com/your-username/aegis_backend.svg?style=flat-square)](https://travis-ci.com/your-username/aegis_backend)
[![Coverage Status](https://img.shields.io/coveralls/github/your-username/aegis_backend.svg?style=flat-square)](https://coveralls.io/github/your-username/aegis_backend?branch=main)
[![License](https://img.shields.io/github/license/your-username/aegis_backend.svg?style=flat-square)](LICENSE)

Aegis is a Django-based backend system designed to manage and respond to emergencies. It provides a platform for civilians to report incidents, for officials to manage them, and for administrators to oversee the system.

## Table of Contents

- [Key Features](#key-features)
- [Technologies Used](#technologies-used)s
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [License](#license)

## Key Features

- **User Management:** Role-based access control for civilians, officials, and administrators.
- **Profile Management:** Users can manage their profiles with details like address, blood group, and emergency medical notes.
- **Emergency Reporting:** Civilians can report emergencies with location data and media attachments.
- **Incident Management:** Officials can view, manage, and update the status of emergencies.
- **Evidence Management:** Upload and store media evidence (images, audio, video) related to incidents.
- **Incident Reporting:** Officials can file detailed incident reports.
- **Learning Center:** A repository of learning resources for users.
- **Notifications:** A system for sending out emergency-related notifications.
- **RESTful API:** A comprehensive API for all features, built with Django Rest Framework.

## Technologies Used

- **Backend:** Django, Django Rest Framework
- **Database:** SQLite3 (for development). The project also includes dependencies for MongoDB (`djongo`), which can be configured for production.
- **Image Handling:** Pillow
- **File Storage:** `django-storages` for flexible file storage (e.g., local, cloud).

## Project Structure

The project is organized into two main Django apps:

- `accounts`: Handles user authentication, profiles, and role management.
- `aegis`: Contains the core application logic for emergency and incident management.

The main project directory is `aegisB`, which contains the project-level settings, URLs, and WSGI configuration.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd aegis_backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Apply the database migrations:**
    ```bash
    python aegisB/manage.py migrate
    ```

5.  **Create a superuser to access the admin panel:**
    ```bash
    python aegisB/manage.py createsuperuser
    ```

## Running the Application

1.  **Start the Django development server:**
    ```bash
    python aegisB/manage.py runserver
    ```

2.  The application will be available at `http://127.0.0.1:8000/`.

## API Endpoints

The API is built with Django Rest Framework and is available under the `/api/` prefix.

### Authentication

-   `/api/accounts/register/`: User registration.
-   `/api/accounts/login/`: User login to obtain an auth token.
-   `/api/accounts/logout/`: User logout.

### Users

-   `/api/accounts/profile/`: View and update user profiles.
-   `/api/accounts/users/`: List all users (admin only).

### Aegis Core

-   `/api/aegis/emergencies/`: Create and list emergencies.
-   `/api/aegis/emergencies/<id>/`: Retrieve, update, or delete an emergency.
-   `/api/aegis/incidents/`: Create and list incident reports.
-   `/api/aegis/media/`: Upload media files.
-   `/api/aegis/resources/`: Access learning resources.

For a detailed list of all available API endpoints and their usage, please refer to the `aegis/urls.py` and `accounts/urls.py` files. You can also explore the browsable API at `http://127.0.0.1:8000/api/`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.