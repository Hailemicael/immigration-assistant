import json
import re
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImmigrationDataProcessor:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        
    def process_data(self):
        """Process the raw crawled data into structured documents"""
        logger.info(f"Processing data from {self.input_file}")
        
        if not os.path.exists(self.input_file):
            logger.error(f"Input file {self.input_file} not found!")
            return []
            
        processed_documents = []
        line_count = 0
        
        with open(self.input_file, 'r', encoding='utf8') as f:
            for line in f:
                line_count += 1
                try:
                    document = json.loads(line)
                    processed_doc = self._process_document(document)
                    if processed_doc:
                        processed_documents.append(processed_doc)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON at line {line_count}: {e}")
                except Exception as e:
                    logger.error(f"Error processing document at line {line_count}: {e}")
        
        logger.info(f"Processed {len(processed_documents)} documents out of {line_count} lines")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        
        # Write processed documents to output file
        with open(self.output_file, 'w', encoding='utf8') as f:
            json.dump(processed_documents, f, indent=2)
            
        logger.info(f"Saved processed data to {self.output_file}")
        
        return processed_documents
    
    def _process_document(self, document):
        """Process a single document"""
        # Skip if no content
        if not document.get('text') or len(document.get('text', '').strip()) < 50:
            return None
        
        # Structure the document
        structured_doc = {
            'url': document['url'],
            'title': self._clean_text(document.get('title', '')),
            'content': self._clean_text(document.get('text', '')),
            'document_type': self._determine_document_type(document),
            'categories': self._extract_categories(document),
            'forms_mentioned': self._extract_form_numbers(document),
            'costs_mentioned': self._extract_costs(document.get('text', '')),
            'processed_timestamp': datetime.now().isoformat()
        }
        
        # Include original metadata if available
        if 'metadata' in document and document['metadata']:
            structured_doc['original_metadata'] = document['metadata']
        
        return structured_doc
    
    def _clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common HTML artifacts
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        
        return text
    
    def _determine_document_type(self, document):
        """Determine the type of immigration document"""
        url = document['url'].lower()
        title = document.get('title', '').lower()
        
        if 'form' in url or 'form' in title:
            return 'form'
        elif 'policy' in url or 'policy' in title:
            return 'policy'
        elif 'green-card' in url:
            return 'green_card'
        elif 'citizenship' in url:
            return 'citizenship'
        elif 'processing-times' in url:
            return 'processing_time'
        else:
            return 'general'
    
    def _extract_categories(self, document):
        """Extract categories from the document"""
        categories = []
        text = (document.get('title', '') + ' ' + document.get('text', '')).lower()
        
        category_keywords = {
            'family': ['family', 'spouse', 'child', 'parent', 'marriage'],
            'employment': ['employment', 'work', 'job', 'h-1b', 'l-1', 'o-1', 'eb-'],
            'humanitarian': ['asylum', 'refugee', 'humanitarian', 'vawa', 'u visa', 't visa'],
            'citizenship': ['citizenship', 'naturalization', 'n-400'],
            'green_card': ['green card', 'permanent resident', 'i-485'],
            'visa': ['visa', 'nonimmigrant', 'immigrant visa']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        
        return categories
    
    def _extract_form_numbers(self, document):
        """Extract immigration form numbers"""
        text = document.get('text', '')
        
        # Look for form number patterns
        form_patterns = [
            r'I-\d{3}[A-Z]?',
            r'N-\d{3}[A-Z]?',
            r'G-\d{3}[A-Z]?',
            r'Form\s+[A-Z]-\d{3}[A-Z]?'
        ]
        
        forms = []
        for pattern in form_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            forms.extend([m.upper() for m in matches])
        
        # Remove duplicates and clean up
        clean_forms = []
        for form in forms:
            if 'FORM ' in form.upper():
                form = form.upper().replace('FORM ', '')
            clean_forms.append(form.upper())
        
        return list(set(clean_forms))  # Remove duplicates
    
    def _extract_costs(self, text):
        """Extract cost information"""
        if not text:
            return []
            
        # Look for currency patterns
        cost_patterns = [
            r'\$\d+(?:,\d{3})*(?:\.\d{2})?',
            r'fee of \$\d+(?:,\d{3})*(?:\.\d{2})?',
            r'cost(?:s)? (?:is|are) \$\d+(?:,\d{3})*(?:\.\d{2})?'
        ]
        
        costs = []
        for pattern in cost_patterns:
            matches = re.findall(pattern, text)
            costs.extend(matches)
        
        return list(set(costs))  # Remove duplicates

# Simple test function
def process_test():
    processor = ImmigrationDataProcessor(
        input_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/uscis_data.jsonl',
        output_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/processed/immigration_data.json'
    )
    processed_data = processor.process_data()
    print(f"Processed {len(processed_data)} documents")
    
    # Print a sample of what we extracted
    if processed_data:
        sample = processed_data[0]
        print("\nSample processed document:")
        print(f"URL: {sample['url']}")
        print(f"Title: {sample['title']}")
        print(f"Document Type: {sample['document_type']}")
        print(f"Categories: {sample['categories']}")
        print(f"Forms Mentioned: {sample['forms_mentioned']}")
        print(f"Costs Mentioned: {sample['costs_mentioned']}")
        print(f"Content Preview: {sample['content'][:100]}...")

if __name__ == "__main__":
    process_test()