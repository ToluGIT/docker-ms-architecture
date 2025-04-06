from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import models, database
from app.security.credentials import CredentialManager


# Get JWT configuration from credential manager
jwt_settings = CredentialManager.get_jwt_settings()
SECRET_KEY = jwt_settings["secret_key"]
ALGORITHM = jwt_settings["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = jwt_settings["access_token_expire_minutes"]

# Token URL is where the client will send username/password to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def authenticate_user(db: Session, username: str, password: str):
    """Verify username and password"""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    
    # First try: Standard bcrypt verification
    try:
        if models.User.verify_password(password, user.hashed_password):
            return user
    except Exception as e:
        # If error occurs with password hash, try direct comparison for sample data
        # Check if this is one of the sample passwords (ends with '_hashed')
        if user.hashed_password.endswith('_hashed'):
            plain_password = user.hashed_password.replace('_hashed', '')
            if password == plain_password:
                # Update with proper hash for future logins
                user.hashed_password = models.User.get_password_hash(password)
                db.commit()
                return user
        # Special case for admin
        elif user.username == 'admin' and password == 'admin123':
            # Update admin with proper hash
            user.hashed_password = models.User.get_password_hash(password)
            db.commit()
            return user
    
    return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    """Dependency to get the current user from a JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Get the user from the database
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
        
    return user