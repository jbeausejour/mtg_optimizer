import sys
import os
from app.services.card_service import CardService

# Ensure proper path resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_closest_set_name(input_name):
    closest_name = CardService.get_closest_set_name(input_name)
    print(f"\nInput name: {input_name}")
    print(f"Closest official set name found: {closest_name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_get_closest_set_name.py 'Set Name to Test'")
    else:
        input_name = " ".join(sys.argv[1:])
        test_closest_set_name(input_name)
