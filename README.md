# LLM Translator for POT files

## Overview
This project is designed to translate .pot files into different languages using OpenAI's API. It supports concurrent processing to speed up translations.

## Features
- Load API keys from a `.env` file for security.
- Translate text using OpenAI's API.
- Concurrent processing for faster translations.
- Save progress and handle rate limits gracefully.

## Requirements
- Python 3.8+
- See `requirements.txt` for a list of dependencies.

## Installation

1. Clone the repository:   ```bash
   git clone https://github.com/G2Tech-co/llm-translator.git
   cd llm-translator   ```

2. Create a virtual environment:   ```bash
   python -m venv venv   ```

3. Activate the virtual environment:

   - On Windows:     ```bash
     .\venv\Scripts\activate     ```

   - On macOS and Linux:     ```bash
     source venv/bin/activate     ```

4. Install the dependencies:   ```bash
   pip install -r requirements.txt   ```

5. Create a `.env` file based on `.env.example` and add your API keys.

## Usage

To translate a .pot file, run the following command:


```bash
python translator.py
```

## Contributing
Contributions are welcome! Please open an issue or submit a pull request.

## License
This project is licensed under the MIT License.