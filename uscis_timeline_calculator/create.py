import requests
from bs4 import BeautifulSoup
import json
import re
import logging
import time

# Configure logging to show timestamps and log level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class USCISFormScraper:
    """Class to scrape form options, form categories, and service centers from the USCIS website."""
    
    def __init__(self):
        self.base_url = "https://egov.uscis.gov/processing-times/"
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/91.0.4472.124 Safari/537.36"),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive"
        }
        # These attributes will store our scraped data
        self.form_options = []
        self.form_categories = {}   # Will be stored as a dict; key: form number, value: list of categories
        self.service_centers = []   # A list for service centers (field offices)
        
        # Use a session to maintain cookies between requests
        self.session = requests.Session()

        # API endpoints used by the USCIS site to retrieve additional JSON data
        self.form_types_api = "https://egov.uscis.gov/processing-times/api/formtypes"
        self.form_data_api = "https://egov.uscis.gov/processing-times/api/formoffices"

    def scrape_form_options(self):
        """
        Scrape the form options from the USCIS landing page.
        
        Returns:
            list: A list of dictionaries with each dictionary having:
                   - value: the form number (e.g., "I-90")
                   - label: a string with both form number and its description
        """
        try:
            logger.info(f"Attempting to scrape form options from {self.base_url}")
            response = self.session.get(self.base_url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logger.error(f"Failed to retrieve data. Status code: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            form_select = soup.find('select', {'id': 'selectForm'})
            if not form_select:
                logger.error("Could not find the form select element on the page")
                return []

            form_options = []
            for option in form_select.find_all('option'):
                if option.get('value') and option.get('value') != '':
                    text = option.text.strip()
                    if '|' in text:
                        form_number, description = text.split('|', 1)
                        form_number = form_number.strip()
                        description = description.strip()
                    else:
                        # Try using a regular expression if the split format is not found
                        match = re.match(r'([A-Z]-\d+[A-Z]?)\s+(.*)', text)
                        if match:
                            form_number = match.group(1)
                            description = match.group(2)
                        else:
                            form_number = text
                            description = text

                    form_options.append({
                        "value": form_number,
                        "label": f"{form_number} - {description}"
                    })
            logger.info(f"Successfully scraped {len(form_options)} form options")
            self.form_options = form_options
            return form_options

        except Exception as e:
            logger.error(f"Exception during form options scraping: {e}")
            return []

    def scrape_form_categories_and_centers(self, form_number):
        """
        For a given form number, use USCIS API endpoints to retrieve form categories and service centers.
        
        Args:
            form_number (str): e.g., "I-485"
        
        Returns:
            tuple: (categories, service_centers) where:
                   - categories is a list of form categories for the given form
                   - service_centers is a list of service centers available for that form
        """
        try:
            logger.info(f"Scraping categories and centers for form {form_number}")
            # First, retrieve form types to get the form ID corresponding to the form number.
            form_types_response = self.session.get(self.form_types_api, headers=self.headers, timeout=15)
            if form_types_response.status_code != 200:
                logger.error(f"Failed to retrieve form types. Status code: {form_types_response.status_code}")
                return [], []
            form_types_data = form_types_response.json()
            form_id = None
            for form in form_types_data:
                if form.get('formName', '').startswith(form_number):
                    form_id = form.get('formId')
                    break

            if not form_id:
                logger.error(f"Could not find form ID for {form_number}")
                return [], []

            # Next, retrieve form data (categories and service centers) using the form ID.
            form_data_url = f"{self.form_data_api}/{form_id}"
            form_data_response = self.session.get(form_data_url, headers=self.headers, timeout=15)
            if form_data_response.status_code != 200:
                logger.error(f"Failed to retrieve form data. Status code: {form_data_response.status_code}")
                return [], []

            form_data = form_data_response.json()

            # Extract categories
            categories = []
            if 'formSubTypes' in form_data:
                categories = [subtype.get('formSubType', '') for subtype in form_data['formSubTypes']]
            
            # Extract service centers (offices)
            service_centers = []
            if 'offices' in form_data:
                service_centers = [office.get('officeName', '') for office in form_data['offices']]

            logger.info(f"Found {len(categories)} categories and {len(service_centers)} service centers for form {form_number}")

            # Cache the categories per form and add centers to the overall list
            self.form_categories[form_number] = categories
            self.service_centers = list(set(self.service_centers + service_centers))
            return categories, service_centers

        except Exception as e:
            logger.error(f"Exception during categories and centers scraping: {e}")
            return [], []

    def get_all_service_centers(self):
        """
        Scrape multiple common forms to compile a comprehensive list of service centers.
        
        Returns:
            list: Unique service centers (field offices)
        """
        all_centers = set()
        # Ensure form options are loaded first
        if not self.form_options:
            self.scrape_form_options()

        # Use a list of common form numbers to aggregate service centers.
        common_forms = ["I-485", "I-130", "I-765", "N-400", "I-90"]
        for form in common_forms:
            _, centers = self.scrape_form_categories_and_centers(form)
            all_centers.update(centers)
            # Pause briefly to avoid overwhelming the API
            time.sleep(1)
        self.service_centers = list(all_centers)
        return self.service_centers

    def save_data_to_json(self, file_path="uscis_form_data.json"):
        """
        Save the scraped data (form options, categories, and service centers) to a JSON file.
        
        Args:
            file_path (str): File location to store data.
        """
        try:
            data = {
                "form_options": self.form_options,
                "form_categories": self.form_categories,
                "service_centers": self.service_centers
            }
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Data saved successfully to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save data: {e}")
            return False

    def load_data_from_json(self, file_path="uscis_form_data.json"):
        """
        Load previously saved scraped data from a JSON file.
        
        Args:
            file_path (str): File location where the data is stored.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            self.form_options = data.get("form_options", [])
            self.form_categories = data.get("form_categories", {})
            self.service_centers = data.get("service_centers", [])
            logger.info(f"Data loaded successfully from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return False


# Fallback hard-coded data in case scraping fails
def get_hardcoded_form_options():
    """Hard-coded fallback for form options."""
    return [
        {"value": "I-90", "label": "I-90 - Application to Replace Permanent Resident Card"},
        {"value": "I-102", "label": "I-102 - Application for Replacement/Initial Nonimmigrant Arrival-Departure Document"},
        {"value": "I-129", "label": "I-129 - Petition for a Nonimmigrant Worker"},
        {"value": "I-129CW", "label": "I-129CW - Petition for a CNMI-Only Nonimmigrant Transitional Worker"},
        {"value": "I-129F", "label": "I-129F - Petition for Alien Fiancé(e)"},
        {"value": "I-130", "label": "I-130 - Petition for Alien Relative"},
        {"value": "I-131", "label": "I-131 - Application for Travel Documents"},
        {"value": "I-140", "label": "I-140 - Immigrant Petition for Alien Workers"},
        {"value": "I-485", "label": "I-485 - Application to Register Permanent Residence or Adjust Status"},
        {"value": "I-751", "label": "I-751 - Petition to Remove Conditions on Residence"},
        {"value": "I-765", "label": "I-765 - Application for Employment Authorization"},
        {"value": "N-400", "label": "N-400 - Application for Naturalization"}
    ]


def get_hardcoded_form_categories():
    """Hard-coded fallback for form categories per form."""
    return {
        "I-130": [
            "Family-based: Immediate relative",
            "Family-based: F1",
            "Family-based: F2A",
            "Family-based: F2B",
            "Family-based: F3",
            "Family-based: F4"
        ],
        "I-485": [
            "Family-based",
            "Employment-based",
            "Special Immigrant",
            "Asylee/Refugee",
            "VAWA"
        ],
        "I-765": [
            "Initial EAD",
            "Renewal EAD",
            "Replacement EAD"
        ],
        "I-90": [
            "Renewal/Replacement",
            "Biometric Update"
        ],
        "N-400": [
            "Military",
            "Non-Military"
        ]
    }


def get_hardcoded_service_centers():
    """Hard-coded fallback for service centers."""
    return [
        "California Service Center",
        "Nebraska Service Center",
        "Potomac Service Center",
        "Texas Service Center",
        "Vermont Service Center",
        "National Benefits Center",
        "Chicago Lockbox",
        "Dallas Lockbox",
        "Phoenix Lockbox"
    ]


def update_uscis_data():
    """
    Update USCIS form-related data by scraping the official website.
    
    It will attempt scraping first. If that fails, it will try loading previously saved data.
    If both methods fail, fallback to hard-coded data.
    
    Returns:
        dict: A dictionary containing 'form_options', 'form_categories', and 'service_centers'
    """
    scraper = USCISFormScraper()
    
    form_options = scraper.scrape_form_options()
    
    if form_options:
        # Scrape additional data for a more comprehensive data set.
        scraper.get_all_service_centers()
        for form in ["I-130", "I-485", "I-765", "N-400", "I-90"]:
            scraper.scrape_form_categories_and_centers(form)
            time.sleep(1)  # Pause between requests to avoid rate limiting
        scraper.save_data_to_json()
    else:
        if not scraper.load_data_from_json():
            scraper.form_options = get_hardcoded_form_options()
            scraper.form_categories = get_hardcoded_form_categories()
            scraper.service_centers = get_hardcoded_service_centers()
    
    return {
        "form_options": scraper.form_options,
        "form_categories": scraper.form_categories,
        "service_centers": scraper.service_centers
    }


# Example usage: when running this module as a script
if __name__ == "__main__":
    uscis_data = update_uscis_data()

    print("\nForm Options:")
    for form in uscis_data["form_options"]:
        print(f"  {form['value']} - {form['label']}")
    
    print("\nForm Categories:")
    for form, categories in uscis_data["form_categories"].items():
        print(f"  {form}: {categories}")
    
    print("\nService Centers:")
    for center in uscis_data["service_centers"]:
        print(f"  - {center}")
