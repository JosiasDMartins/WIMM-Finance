<div align="center">
  <img src="finances/static/finances/images/logo.png" alt="SweetMoney Logo" width="200">
  <p><strong>A family-oriented personal finance management application</strong></p>
</div>

---

## Overview
SweetMoney is a Django-based web application designed to help families manage their finances collaboratively. The application organizes expenses, income, and investments into customizable flow groups, making it easy to track financial activity across different family members.

### DEMO Server

Now, you can try SweetMoney at our [Demo Server](https://demo.sweetmoney.ca):
- **Address:** demo.sweetmoney.ca

- Some functions are locked, like add/edit/delete users.
- Database will be deleted and recreated every night

Users:
- **Admin user**: admin
- **Parent**: Fred
- **Parent**: Wilma
- **Child**: Pebbles
- **Password** for all: MySweetMoney

### Key Features

- **Multi-Currency Support**: Track finances in your own currency
- **Flow Groups**: Organize expenses by categories, purposes, or family members
- **Role-Based Access Control**: Three user roles (Admin, Parent, Child) with appropriate permissions
- **Period-Based Tracking**: Monthly, bi-weekly, or weekly financial periods
- **Investment Tracking**: Monitor investments separately from regular cash flow
- **Bank Reconciliation**: Compare expected vs actual bank balances with tolerance settings
- **Notifications System**: Get alerts for important financial events
- **Dark Mode**: Full dark mode support for comfortable viewing
- **Progressive Web App**: Install on mobile/desktop devices for app-like experience
- **Auto-Updates**: Built-in system for applying updates (requires admin privileges)

## Development Setup

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Dependencies

Install required packages:

```bash
pip install Django
pip install python-dateutil
pip install django-money==3.4.1
pip install py-moneyed==3.0
pip install requests
pip install whitenoise
pip install django-pwa
```

Or install all at once:

```bash
pip install Django python-dateutil django-money==3.4.1 py-moneyed==3.0 requests whitenoise django-pwa
```

### Running Locally

1. Clone the repository
2. Install dependencies (see above)
3. Run migrations:
   ```bash
   python manage.py migrate
   ```
4. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```
6. Access the application at `http://localhost:8000`

### Production Deployment

For production deployment, SweetMoney includes Docker support. See our WIKI for more details.

---

<div align="center">
  <p>Made with ❤️ for families who want to take control of their finances</p>
</div>
