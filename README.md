# Lease Management System - Simplified

A simple lease management system with login, signup, and blank home screen.

## Features

- ✅ User Signup - Create new accounts
- ✅ User Login - Authenticate users  
- ✅ Blank Home Screen - Simple dashboard after login
- ✅ Secure Authentication - bcrypt password hashing

## Quick Start

### Install Dependencies

```bash
pip3 install -r requirements.txt
```

### Start the Application

**Option 1: Using startup script (Recommended)**
```bash
./start.sh
```

**Option 2: Manual start**
```bash
cd lease_application
python3 app.py
```

The application will start on: **http://localhost:5001**

## Usage

1. **Sign Up**: Go to http://localhost:5001/login.html and click "Sign Up" tab
2. **Login**: Enter your username and password
3. **Home Screen**: You'll see a blank home screen after successful login

## Project Structure

```
lease_application/
├── app.py                 # Main Flask application
├── database.py            # Database layer (users only)
├── config/                # Configuration
├── auth/                  # Authentication module
├── frontend/
│   ├── templates/
│   │   ├── login.html     # Login/Signup page
│   │   └── dashboard.html # Blank home screen
│   └── static/
│       ├── css/
│       │   ├── common.css  # Common styles
│       │   └── login.css   # Login page styles
│       └── js/
│           ├── login.js    # Login/Signup logic
│           └── auth.js    # Auth utilities
└── lease_management.db   # SQLite database
```

## API Endpoints

- `POST /api/register` - Create new user
- `POST /api/login` - Login user
- `POST /api/logout` - Logout user
- `GET /api/user` - Get current user

## Notes

- Database is automatically created on first run
- All user passwords are hashed with bcrypt
- Session-based authentication
- Clean, minimal codebase

