import os
import sys

from google.cloud import translate_v2 as translate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from populate.gcloud_key import credentials

translate_client = translate.Client.from_service_account_info(credentials)

result = translate_client.translate("Hello World!", target_language="uk")
print(f"Translated text: {result['translatedText']}")
