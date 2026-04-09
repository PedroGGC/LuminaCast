from slowapi import Limiter
from slowapi.util import get_remote_address

# Define um limiter global usando o IP do cliente como chave
limiter = Limiter(key_func=get_remote_address)
