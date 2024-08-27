import time
from app import create_app
from app.tasks.optimization_tasks import cleanup_old_scans, test_task

app, celery = create_app()

def test_simple_task():
    result = test_task.delay()
    print(f"Test task ID: {result.id}")
    task_result = result.get(timeout=10)
    print(f"Test task result: {task_result}")

def test_cleanup_old_scans():
    result = cleanup_old_scans.delay()
    print(f"Cleanup task ID: {result.id}")
    
    timeout = time.time() + 60  # 60 second timeout
    while time.time() < timeout:
        if result.ready():
            task_result = result.get()
            print(f"Cleanup task result: {task_result}")
            return
        else:
            print(f"Task status: {result.status}, Info: {result.info}")
            time.sleep(5)  # Wait for 5 seconds before checking again
    
    print("Cleanup task timed out")

if __name__ == "__main__":
    print("Testing simple task:")
    test_simple_task()

    print("\nTesting cleanup_old_scans task:")
    test_cleanup_old_scans()

    print("\nTesting cleanup_old_scans task:")
    test_cleanup_old_scans()
