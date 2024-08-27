#!/bin/bash

# Start Redis
sudo service redis-server start

# Start Celery worker
python run_celery.py &

# Start Flask backend
flask run &

# Start frontend
cd ../frontend  # adjust this path as needed
npm start

# Wait for all background processes
wait