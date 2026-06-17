import jwt
import requests
from fastapi import HTTPException, Header, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import CLERK_PUBLIC_KEY

security_scheme = HTTPBearer()

def decode_clerk_jwt(token: str) -> dict:
    """
    Decodes the Clerk JWT using the public Clerk key configuration (RS256).
    """
    if not CLERK_PUBLIC_KEY:
        raise HTTPException(
            status_code=500, 
            detail="Clerk Auth public key is not set. CLERK_PUBLIC_KEY env variable is required."
        )
        
    try:
        # Real Clerk JWT decoding (using PEM formatted CLERK_PUBLIC_KEY)
        payload = jwt.decode(
            token, 
            CLERK_PUBLIC_KEY, 
            algorithms=["RS256"], 
            options={"verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="JWT token has expired.")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {e}")

def get_current_agent(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """
    Dependency to validate user credentials and return agent properties.
    Expected JWT claims:
      - tenant_id: string
      - authority_level: integer (0-5)
      - name: string (optional)
    """
    token = credentials.credentials
    payload = decode_clerk_jwt(token)
    
    tenant_id = payload.get("tenant_id")
    authority_level = payload.get("authority_level")
    
    if tenant_id is None or authority_level is None:
        raise HTTPException(
            status_code=401, 
            detail="Token is missing required tenant_id or authority_level claims."
        )
        
    try:
        auth_level = int(authority_level)
    except ValueError:
        raise HTTPException(status_code=401, detail="authority_level must be an integer.")
        
    if not (0 <= auth_level <= 5):
        raise HTTPException(status_code=401, detail="authority_level must be between 0 and 5.")
        
    return {
        "tenant_id": tenant_id,
        "authority_level": auth_level,
        "name": payload.get("name", "anonymous")
    }

class PermissionChecker:
    """Dependency helper to enforce minimum L0-L5 authority levels."""
    def __init__(self, min_level: int):
        self.min_level = min_level
        
    def __call__(self, agent: dict = Depends(get_current_agent)) -> dict:
        if agent["authority_level"] < self.min_level:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient authority level. Required: L{self.min_level}, got L{agent['authority_level']}"
            )
        return agent
