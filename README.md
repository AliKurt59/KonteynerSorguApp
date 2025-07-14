# Port Container Management System

A comprehensive port container management application built with PyQt5 and PostgreSQL, designed for efficient tracking and management of container operations in port facilities.

## ✨ Features

- 🔐 **Secure Login System** - Encrypted user authentication
- 📦 **Container Tracking** - Real-time container status monitoring
- 🚢 **Port Operations** - Comprehensive operation management
- 📊 **Reporting System** - Detailed analysis and reports
- 🎨 **Theme Support** - Dark/Light theme options
- 🗄️ **Database Integration** - PostgreSQL support
- 🔒 **Security** - Input validation and SQL injection protection
- 📝 **Logging** - Comprehensive activity logging

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+

### Installation

1. **Install required packages:**
```bash
pip install -r requirements.txt
```

2. **Create PostgreSQL database:**
```sql
CREATE DATABASE port_db;
```

3. **Set up environment variables (optional):**
```bash
# Create .env file from example
copy .env.example .env
# Edit with your database credentials
```

4. **Run the application:**
```bash
python main_pyqt.py
```

## 🔧 Configuration

You can configure the application in two ways:

### Method 1: Environment Variables (.env file)
```env
DB_NAME=port_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### Method 2: Configuration File (app.ini)
The application automatically creates an `app.ini` file on first run with default settings.

## 👤 Default Users

The application creates default users on first run:

- **Admin User:**
  - Username: `admin`
  - Password: `adminpass`
  - Role: `admin`

- **Operator User:**
  - Username: `operator`
  - Password: `oppass`
  - Role: `operator`

## 📁 Project Structure

```
├── main_pyqt.py         # Main application file
├── gui_pyqt.py          # GUI components
├── db_operations.py     # Database operations
├── config.py            # Configuration management
├── reports.py           # Reporting system
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables example
├── .gitignore          # Git ignore rules
├── LICENSE             # MIT License
└── README.md           # This file
```
## 📋 Requirements
- PyQt5 >= 5.15.0
- psycopg2-binary >= 2.9.0
- pandas >= 1.3.0

## 📜 License
 MIT License
