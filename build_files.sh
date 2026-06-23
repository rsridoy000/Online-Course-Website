# build_files.sh
echo "Building the project..."
python3 -m pip install -r requirements.txt --break-system-packages
python3 manage.py collectstatic --noinput --clear
# Run migrations with a timeout to prevent Vercel build hangs if Neon PostgreSQL is sleeping/slow
if command -v timeout >/dev/null 2>&1; then
    timeout 15 python3 manage.py migrate --noinput || echo "Database migration timed out or failed. Skipping migration step during build."
else
    python3 manage.py migrate --noinput || echo "Database migration failed. Skipping..."
fi
echo "Build complete."

