import sys
from app.services.card_service import CardService
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_single_name(input_name):
    normalized_candidates = CardService._normalize_set_name(input_name)
    print(f"\nInput name: {input_name}")
    print("Normalized candidates:")
    for candidate in normalized_candidates:
        print(f" - {candidate}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_set_name_normalization.py 'Set Name to Test'")
    else:
        input_name = " ".join(sys.argv[1:])
        test_single_name(input_name)
