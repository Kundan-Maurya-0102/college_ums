import requests
import json
import re
import sys
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
from urllib.parse import quote

class PhoneNumberTracker:
    def __init__(self):
        # Free API keys - aap inhe apne actual keys se replace kar sakte hain
        self.numverify_api_key = "YOUR_NUMVERIFY_API_KEY"
        self.opencage_api_key = "YOUR_OPENCAGE_API_KEY"
        self.abstract_api_key = "YOUR_ABSTRACT_API_KEY"
        self.session = requests.Session()
        
    def validate_phone_number(self, phone_number):
        """Phone number ko validate karta hai using phonenumbers library"""
        try:
            cleaned = re.sub(r'[\s\-\(\)\.]', '', phone_number)
            if not cleaned.startswith('+'):
                if len(cleaned) == 10:
                    cleaned = '+91' + cleaned
                else:
                    cleaned = '+' + cleaned
            
            parsed_number = phonenumbers.parse(cleaned)
            if not phonenumbers.is_valid_number(parsed_number):
                return False, "Invalid phone number format."
            return True, cleaned
        except Exception as e:
            return False, f"Parsing error: {str(e)}"
    
    def get_carrier_info(self, phone_number):
        """Phonenumbers library se actual carrier aur location info nikalta hai"""
        print("\n[!] Fetching information...")
        
        try:
            parsed_number = phonenumbers.parse(phone_number)
            carrier_name = carrier.name_for_number(parsed_number, "en")
            location_name = geocoder.description_for_number(parsed_number, "en")
            time_zones = timezone.time_zones_for_number(parsed_number)
            country_code = phonenumbers.region_code_for_number(parsed_number)
            
            from phonenumbers import PhoneNumberType
            number_type = phonenumbers.number_type(parsed_number)
            line_type = "mobile"
            if number_type == PhoneNumberType.FIXED_LINE:
                line_type = "landline"
            elif number_type == PhoneNumberType.MOBILE:
                line_type = "mobile"
            elif number_type == PhoneNumberType.FIXED_LINE_OR_MOBILE:
                line_type = "fixed or mobile"
            else:
                line_type = "other"

            return {
                'valid': True,
                'number': phone_number,
                'local_format': str(parsed_number.national_number),
                'international_format': phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                'country_prefix': f"+{parsed_number.country_code}",
                'country_code': country_code,
                'country_name': location_name,
                'location': location_name,
                'carrier': carrier_name if carrier_name else "Unknown Carrier",
                'line_type': line_type,
                'timezone': ", ".join(time_zones),
                'error': None
            }
        except Exception as e:
            return {'valid': False, 'error': f"Library Error: {str(e)}"}
    
    def get_geolocation(self, country_name, city_name):
        """OpenCage Geocoder se exact coordinates aur location details"""
        print("[*] Checking geolocation...")
        
        if self.opencage_api_key == "YOUR_OPENCAGE_API_KEY":
            return self._get_mock_geolocation(city_name)
        
        query = quote(f"{city_name}, {country_name}")
        url = f"https://api.opencagedata.com/geocode/v1/json?q={query}&key={self.opencage_api_key}&limit=1"
        
        try:
            response = self.session.get(url, timeout=10)
            data = response.json()
            if data['results']:
                result = data['results'][0]
                geometry = result.get('geometry', {})
                components = result.get('components', {})
                return {
                    'latitude': geometry.get('lat'),
                    'longitude': geometry.get('lng'),
                    'formatted_address': result.get('formatted'),
                    'timezone': result.get('annotations', {}).get('timezone', {}).get('name'),
                    'currency': components.get('currency'),
                    'flag': result.get('annotations', {}).get('flag'),
                    'calling_code': result.get('annotations', {}).get('callingcode'),
                    'confidence': result.get('confidence'),
                    'error': None
                }
            else:
                return {'error': 'Location not found'}
        except requests.exceptions.RequestException as e:
            return {'error': f"Geocoding Error: {str(e)}"}
    
    def _get_mock_geolocation(self, city_name):
        return {
            'latitude': '28.6139',
            'longitude': '77.2090',
            'formatted_address': f'{city_name}, Demo Address',
            'timezone': 'Asia/Kolkata',
            'currency': 'INR',
            'flag': 'IN',
            'calling_code': '+91',
            'confidence': 'High',
            'error': None
        }
    
    def get_ip_geolocation(self):
        """User ki current IP se location estimate karein"""
        print("[*] Checking IP-based location...")
        try:
            response = self.session.get('https://ipapi.co/json/', timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def generate_google_maps_link(self, lat, lng):
        return f"https://www.google.com/maps?q={lat},{lng}"
    
    def display_results(self, phone_data, geo_data, ip_data=None):
        print("\n" + "="*60)
        print("         PHONE NUMBER INTELLIGENCE REPORT")
        print("="*60)
        
        print("\n[+] BASIC INFORMATION")
        print("-" * 40)
        print(f"Number: {phone_data.get('international_format', 'N/A')}")
        print(f"Valid: {'Yes' if phone_data.get('valid') else 'No'}")
        print(f"Type: {phone_data.get('line_type', 'Unknown').upper()}")
        
        print("\n[+] CARRIER INFORMATION")
        print("-" * 40)
        print(f"Carrier: {phone_data.get('carrier', 'Unknown')}")
        print(f"Location: {phone_data.get('location', 'Unknown')}")
        print(f"Timezone: {phone_data.get('timezone', 'Unknown')}")
        
        if not geo_data.get('error'):
            print("\n[+] GEOLOCATION DETAILS")
            print("-" * 40)
            print(f"Address: {geo_data.get('formatted_address', 'N/A')}")
            print(f"Coordinates: {geo_data.get('latitude')}, {geo_data.get('longitude')}")
            
            if geo_data.get('latitude') and geo_data.get('longitude'):
                maps_link = self.generate_google_maps_link(geo_data['latitude'], geo_data['longitude'])
                print(f"Google Maps: {maps_link}")
        
        print("\n" + "="*60)
        print("Disclaimer: Information is based on public carrier databases.")
        print("="*60)
    
    def track(self, phone_number):
        print(f"\n[*] Tracking Number: {phone_number}")
        is_valid, result = self.validate_phone_number(phone_number)
        if not is_valid:
            print(f"[-] Error: {result}")
            return
        
        phone_data = self.get_carrier_info(result)
        if not phone_data.get('valid'):
            print(f"[-] Error: {phone_data.get('error', 'Unknown error')}")
            return
        
        geo_data = self.get_geolocation(phone_data.get('country_name', ''), phone_data.get('location', ''))
        ip_data = self.get_ip_geolocation()
        self.display_results(phone_data, geo_data, ip_data)
        self.save_option(phone_data, geo_data)
    
    def save_option(self, phone_data, geo_data):
        choice = input("\nSave report to JSON? (y/n): ").lower()
        if choice == 'y':
            filename = f"phone_report_{phone_data.get('local_format', 'unknown')}.json"
            report = {
                'phone_data': phone_data,
                'geolocation': geo_data,
                'timestamp': str(__import__('datetime').datetime.now())
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=4, ensure_ascii=False)
            print(f"[+] Report saved: {filename}")


def main():
    print("""
    ============================================
           PHONE NUMBER TRACKER v2.0
    ============================================
    Features:
    - Carrier Detection
    - Country & City Location
    - Line Type (Mobile/Landline)
    - Geolocation Coordinates
    ============================================
    """)
    
    tracker = PhoneNumberTracker()
    
    if len(sys.argv) > 1:
        number = sys.argv[1]
        tracker.track(number)
    else:
        while True:
            print("\nEnter Phone Number (e.g., +91...):")
            number = input(">> ").strip()
            if not number: continue
            if number.lower() in ['exit', 'quit']: break
            tracker.track(number)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBye!")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")