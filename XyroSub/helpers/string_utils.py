import secrets
import string


def generate_secure_random_characters(ctr: int = 4):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(ctr))