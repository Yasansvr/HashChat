import hashlib
import binascii
from nacl.public import PrivateKey, PublicKey, SealedBox
from nacl.signing import SigningKey, VerifyKey
from nacl.secret import SecretBox
import nacl.encoding
import nacl.exceptions
from database import load_db

def get_keys_from_password(password: str):
    # Hash password to get a 32-byte master seed
    master_seed = hashlib.sha256(password.strip().encode('utf-8')).digest()
    
    # Derive distinct sub-keys for encryption and signing to prevent cross-protocol attacks
    enc_seed = hashlib.sha256(master_seed + b"encryption").digest()
    sign_seed = hashlib.sha256(master_seed + b"signing").digest()
    
    # Generate X25519 keypair for encryption
    enc_private_key = PrivateKey(enc_seed)
    enc_public_key = enc_private_key.public_key
    
    # Generate Ed25519 keypair for signing
    sign_private_key = SigningKey(sign_seed)
    sign_public_key = sign_private_key.verify_key
    
    return {
        'enc_priv': enc_private_key,
        'enc_pub': enc_public_key,
        'sign_priv': sign_private_key,
        'sign_pub': sign_public_key
    }

def get_seed_from_input(chat_id: int, user_input: str) -> str:
    """Attempts to treat user_input as a custom password, returning the unlocked seed phrase.
       If decryption fails or it's not a password, assumes the input IS the seed phrase."""
    if not user_input:
        return ""
        
    db = load_db()
    encrypted_seed = None
    
    # Find user's encrypted seed in the database
    for sid, data in db.items():
        if sid == str(chat_id) or (isinstance(data, dict) and data.get('chat_id') == chat_id):
            if isinstance(data, dict) and 'encrypted_seed' in data:
                encrypted_seed = data['encrypted_seed']
            break
            
    if encrypted_seed:
        try:
            # Try to decrypt using the input as the password
            password_hash = hashlib.sha256(user_input.strip().encode('utf-8')).digest()
            box = SecretBox(password_hash)
            decrypted = box.decrypt(binascii.unhexlify(encrypted_seed))
            return decrypted.decode('utf-8')
        except Exception:
            pass
            
    # If decryption fails or not set, assume input is the raw seed phrase
    return user_input.strip()
