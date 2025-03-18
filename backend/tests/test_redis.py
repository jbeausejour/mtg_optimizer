import json

import redis

# Define Redis connection details
REDIS_HOST = "192.168.68.15"
REDIS_PORT = 6379
REDIS_DB = 0

try:
    # Connect to Redis
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

    # Test connection
    if redis_client.ping():
        print("✅ Successfully connected to Redis!")

    # List all keys in Redis
    keys = redis_client.keys("*")
    if keys:
        print(f"\n🔍 Found {len(keys)} keys in Redis:")
        for key in keys:
            print(f"   - {key}")
    else:
        print("\n⚠️ No keys found in Redis.")

    # Check Celery tasks
    task_keys = redis_client.keys("celery-task-meta-*")
    if task_keys:
        print(f"\n📋 Found {len(task_keys)} Celery task(s):")
        for key in task_keys:
            task_data = redis_client.get(key)
            if task_data:
                try:
                    task_json = json.loads(task_data)
                    print(f"\n📝 Task: {key}")
                    print(f"   - Status: {task_json.get('status', 'Unknown')}")
                    print(f"   - Result: {task_json.get('result', 'No result')}")
                    print(f"   - Traceback: {task_json.get('traceback', 'None')}")
                except json.JSONDecodeError:
                    print(f"   ⚠️ Failed to decode JSON for task {key}. Raw data: {task_data}")
            else:
                print(f"   ❌ Could not retrieve data for task {key}.")
    else:
        print("\n⚠️ No Celery task metadata found in Redis.")

except redis.ConnectionError as e:
    print(f"❌ Failed to connect to Redis: {e}")
