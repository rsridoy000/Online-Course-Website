#!/bin/bash

echo ""
echo "========================================="
echo "Liquid_Triple_R Setup Script (Linux/Mac)"
echo "========================================="
echo ""

echo "Step 1: Creating virtual environment..."
python3 -m venv venv
echo "Virtual environment created!"
echo ""

echo "Step 2: Activating virtual environment..."
source venv/bin/activate
echo "Virtual environment activated!"
echo ""

echo "Step 3: Installing dependencies..."
pip install -r requirements.txt
echo "Dependencies installed!"
echo ""

echo "Step 4: Running migrations..."
python manage.py migrate
echo "Migrations completed!"
echo ""

echo "Step 5: Creating superuser..."
echo "Enter admin credentials:"
python manage.py createsuperuser
echo ""

echo "Step 6: Collecting static files..."
python manage.py collectstatic --noinput
echo "Static files collected!"
echo ""

echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "To start the server, run:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "Then visit: http://127.0.0.1:8000"
echo "Admin: http://127.0.0.1:8000/admin/login/"
echo ""
