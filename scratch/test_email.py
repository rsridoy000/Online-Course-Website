import smtplib
from email.mime.text import MIMEText

host = 'smtp.gmail.com'
port = 587
user = 'liquidtripler@gmail.com'
password = 'ysomlbnbstogfxdv'

try:
    print(f"Connecting to {host}:{port}...")
    server = smtplib.SMTP(host, port, timeout=10)
    server.starttls()
    print("Logging in...")
    server.login(user, password)
    print("✅ Gmail SMTP Authentication SUCCESSFUL!")
    server.quit()
except Exception as e:
    print(f"❌ Gmail SMTP Error: {type(e).__name__}: {str(e)}")
