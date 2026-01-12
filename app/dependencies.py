"""
Authentication and authorization dependencies
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


async def get_current_device(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate device authentication token and return device_id.
    """
    # TODO: Implement JWT validation
    # - Decode and verify JWT token
    # - Check token is for a device
    # - Return device_id from token claims
    
    token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Placeholder: return a dummy device_id
    return "device_placeholder"


async def get_current_instance(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Validate instance authentication token and return instance_id.
    """
    # TODO: Implement JWT validation
    # - Decode and verify JWT token
    # - Check token is for an instance
    # - Return instance_id from token claims
    
    token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Placeholder: return a dummy instance_id
    return "instance_placeholder"
