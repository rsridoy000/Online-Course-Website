# Liquid_Triple_R - Quiz Application 🎓

A modern Quiz Application featuring **Gmail OTP verification, a Student Dashboard, and an Admin Control Panel**.

---

## 🚀 How to Run

### Windows Users (Double-Click Method)

1. Extract the project ZIP file.
2. Open the project folder.
3. Double-click the **`set.bat`** file.
4. It will automatically:

   * Create a virtual environment
   * Install the required packages
   * Start the local development server
5. After the server starts, open your browser:

   **Student Portal:**
   http://127.0.0.1:8000

   **Admin Login:**
   http://127.0.0.1:8000/admin-login/

### Linux / macOS Users

1. Open a terminal and navigate to the project folder.
2. Run the following commands:

```bash
chmod +x setup.sh
./setup.sh
source venv/bin/activate
python manage.py runserver
```

Then open:

**Student Portal:**
http://127.0.0.1:8000

**Admin Login:**
http://127.0.0.1:8000/admin-login/

---

## 🔑 Admin Login Credentials

### ⚠️ Important Deployment Note

In the deployed version, **Gmail OTP, SMS OTP, and date-related functionality are currently unavailable/not configured**.

Therefore, to access the Admin Panel, please use the following credentials:

* **Username:** `admin_ridoy`
* **Password:** `730323`

### Admin Login

http://127.0.0.1:8000/admin-login/

> **Note:** The above credentials are intended for testing/demo purposes in the deployed version.

---

## 📦 Sharing the Complete Project

If you want to share the complete project **including the database**, follow these steps:

1. Open a terminal in the project folder.
2. Run:

```bash
python make_zip.py
```

3. The script will automatically create:

```text
deploy_quiz.zip
```

4. The ZIP file will include the project source code and **`db.sqlite3`** database while excluding the **`venv`** folder.

5. You can directly share the generated `deploy_quiz.zip` file with others.

---

## 🗂️ Project Includes

* 🎓 Student Dashboard
* 📝 Quiz System
* 🔐 Admin Control Panel
* 📧 Gmail OTP Verification
* 📱 SMS OTP Support
* 🗄️ SQLite Database
* 👨‍💻 Admin Management
* 📊 Quiz & Student Management

---

## ⚠️ Deployment Limitations

The deployed/demo version currently does not have the required configuration for:

* Gmail OTP
* SMS OTP
* Date-based functionality

Because of these limitations, **Admin Login should be accessed using the provided credentials**:

```text
Username: admin_ridoy
Password: 730323
```

For full OTP functionality, the required Gmail/SMS API and deployment configuration must be properly configured.

---

## 👨‍💻 Project

**Liquid_Triple_R - Quiz Application**

A Django-based quiz platform designed to provide an interactive student quiz experience with administrative controls.
