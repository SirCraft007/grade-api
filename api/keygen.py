import secrets

def generate_api_key(length=32):
    """
    Generate a random API key.
    
    :param length: Length of the bytes. The actual key will be twice as long.
    :return: A random hexadecimal API key string.
    """
    return secrets.token_hex(length)

# Example usage
if __name__ == "__main__":
    length=input("Length of the API key will be 32?")
    api_key = generate_api_key(length=int(length) if length else 32)
    print(f"\nGenerated API key: {api_key}\n")