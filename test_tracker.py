import os
import sys

# Add the directory to path
sys.path.append(os.getcwd())

from phonenew import PhoneNumberTracker

tracker = PhoneNumberTracker()
# Test with a mock number (parsing only)
valid, clean = tracker.validate_phone_number("+919876543210")
print(f"Valid: {valid}, Clean: {clean}")
if valid:
    info = tracker.get_carrier_info(clean)
    print(f"Carrier: {info['carrier']}")
    print(f"Location: {info['location']}")
