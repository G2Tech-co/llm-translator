import polib
from openai import OpenAI
import os
import concurrent.futures
from threading import Lock
import time
import json
from itertools import cycle
from dotenv import load_dotenv

class APIKeyManager:
    def __init__(self):
        self.api_keys = self.load_api_keys()
        self.key_cycle = cycle(self.api_keys)
        self.lock = Lock()
        
    def load_api_keys(self):
        """Load API keys from .env file"""
        try:
            # Load environment variables from .env file
            load_dotenv()
            
            # Get API keys from environment variable
            env_keys = os.getenv('GROQ_API_KEYS')
            if env_keys:
                # Remove brackets and split the string into a list
                keys = env_keys.strip('[]').replace(' ', '').split(',')
                print(f"API keys: {keys}")
                if keys:
                    return keys
                    
            print("No API keys found in .env file, falling back to api_keys.json")
            
            # Fall back to json file if .env is not set up
            if os.path.exists('api_keys.json'):
                with open('api_keys.json', 'r') as f:
                    data = json.load(f)
                    return data.get('api_keys', [])
                    
            return ["YOUR_DEFAULT_API_KEY"]  # Replace with your default key
            
        except Exception as e:
            print(f"Error loading API keys: {e}")
            return ["YOUR_DEFAULT_API_KEY"]  # Replace with your default key
    
    def get_next_key(self):
        """Get next API key in rotation"""
        with self.lock:
            return next(self.key_cycle)

class TranslationManager:
    def __init__(self, pot_file, output_file):
        self.pot_file = pot_file
        self.output_file = output_file
        self.lock = Lock()
        self.processed_count = 0
        self.skipped_count = 0
        self.total_entries = len(pot_file)
        self.api_key_manager = APIKeyManager()
        
    def save_progress(self):
        with self.lock:
            self.pot_file.save(self.output_file)
            
    def update_progress(self, skipped=False):
        with self.lock:
            self.processed_count += 1
            if skipped:
                self.skipped_count += 1
            progress = (self.processed_count / self.total_entries) * 100
            print(f"Progress: {self.processed_count}/{self.total_entries} entries processed ({progress:.1f}%)")
    
    def get_next_api_key(self):
        return self.api_key_manager.get_next_key()

def translate_text(text, target_language="es", max_retries=3, api_key=None):
    """
    Translate text using OpenAI's API with rate limit handling.
    :param text: Text to translate
    :param target_language: Target language code (e.g., 'es' for Spanish)
    :param max_retries: Maximum number of retries for rate limit errors
    :param api_key: API key to use for this request
    :return: Translated text
    """
    for attempt in range(max_retries):
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=api_key
            )
            
            response = client.chat.completions.create(
                model="gemma2-9b-it",
                messages=[
                        {
                            "role": "system", 
                            "content": f"You are a translation assistant. Translate the text to {target_language} with these rules:\n"
                                f"Provide ONLY the translation\n"
                                f"No greetings, no questions, no explanations\n"
                                f"No additional words or sentences before/after translation\n"
                                f"Match the original text's exact formatting\n"
                                f"No suggestions or alternatives\n"
                                f"No confirmation questions\n"
                                f"No 'Here's the translation' type phrases"
                        },                    
                        {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_message = str(e).lower()
            if any(phrase in error_message for phrase in ['rate limit', 'too many requests', '429']):
                if attempt < max_retries - 1:
                    wait_time = 60  # Wait for 1 minute
                    print(f"\nRate limit reached for API key. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
            print(f"Error translating text: {e}")
            return text
    return text

def translate_entry(args):
    """
    Translate a single entry with the given parameters
    """
    entry, target_language, manager = args
    try:
        if entry.msgstr.strip() == "":
            api_key = manager.get_next_api_key()
            translated_text = translate_text(entry.msgid, target_language, max_retries=3, api_key=api_key)
            entry.msgstr = translated_text
            manager.update_progress()
        else:
            manager.update_progress(skipped=True)
            
        manager.save_progress()
        return entry.msgid, entry.msgstr
    except Exception as e:
        print(f"Error processing entry: {e}")
        return entry.msgid, ""

def translate_pot_file(file_path, target_language="es", output_file="translated.po", max_workers=3):
    """
    Translate a .pot file into the specified language using concurrent processing.
    :param file_path: Path to the .pot file
    :param target_language: Target language code
    :param output_file: Path to save the translated .po file
    :param max_workers: Maximum number of concurrent translation workers
    """
    try:
        # Load the .pot file
        pot_file = polib.pofile(file_path)
        
        # Try to load existing translations
        existing_translations = {}
        try:
            if os.path.exists(output_file):
                print(f"Found existing translation file: {output_file}")
                existing_po = polib.pofile(output_file)
                existing_translations = {entry.msgid: entry.msgstr for entry in existing_po}
                print(f"Loaded {len(existing_translations)} existing translations")
                
                # Apply existing translations to pot_file
                applied_count = 0
                for entry in pot_file:
                    if entry.msgid in existing_translations and existing_translations[entry.msgid].strip():
                        entry.msgstr = existing_translations[entry.msgid]
                        applied_count += 1
                print(f"Applied {applied_count} existing translations from previous run")
        except Exception as e:
            print(f"Could not load existing translations: {e}")

        # Create translation manager
        manager = TranslationManager(pot_file, output_file)
        
        # Prepare entries for translation
        entries_to_translate = []
        for entry in pot_file:
            # Only add entries that don't have translations or have empty translations
            if not entry.msgstr.strip():
                entries_to_translate.append((entry, target_language, manager))

        if not entries_to_translate:
            print("All entries are already translated. Nothing to do.")
            return

        print(f"Found {len(entries_to_translate)} entries that need translation")
        
        # Process translations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(translate_entry, args) for args in entries_to_translate]
            concurrent.futures.wait(futures)

        print(f"\nTranslation completed. File saved as: {output_file}")
        print(f"Summary: {manager.processed_count} total entries - {manager.skipped_count} skipped - {manager.processed_count - manager.skipped_count} newly translated")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        try:
            pot_file.save(output_file)
            print("Partial progress has been saved.")
        except:
            pass

if __name__ == "__main__":
    # File paths
    input_pot_file = "base.pot"  # Replace with your .pot file
    output_po_file = "fa.po"

    # Target language
    language_code = "fa"  # Replace 'es' with your desired language code (e.g., 'fr', 'de')

    # Calculate optimal number of workers based on number of API keys
    api_key_manager = APIKeyManager()
    # recommended_workers = len(api_key_manager.api_keys)
    recommended_workers = 4
    print(f"Using {recommended_workers} workers based on available API keys")

    # Translate the file with concurrent processing
    translate_pot_file(input_pot_file, target_language=language_code, output_file=output_po_file, max_workers=recommended_workers)
