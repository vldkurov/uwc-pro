from environs import Env

env = Env()
env.read_env()

credentials = {
    "type": "service_account",
    "project_id": env.str("GOOGLE_PROJECT_ID"),
    "private_key_id": env.str("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": env.str("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": env.str("GOOGLE_CLIENT_EMAIL"),
    "client_id": env.str("GOOGLE_CLIENT_ID"),
    "auth_uri": env.str("GOOGLE_AUTH_URI"),
    "token_uri": env.str("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": env.str("GOOGLE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": env.str("GOOGLE_CLIENT_CERT_URL"),
}
