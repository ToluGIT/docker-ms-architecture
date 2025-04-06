from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi.util import get_remote_address
from typing import List
import time
from .. import models, database
from pydantic import BaseModel
from app.config import limiter
from ..trace_metrics import track_request_for_slo

router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class ItemBase(BaseModel):
    name: str
    description: str = None
    price: float
    is_available: bool = True

class ItemCreate(ItemBase):
    owner_id: int

class ItemResponse(ItemBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True

# Repository integration
try:
    from ..repositories.item_repository import ItemRepository
    repository_available = True
except ImportError:
    repository_available = False

# Helper functions
def get_items(db: Session, skip: int = 0, limit: int = 100):
    if repository_available:
        return ItemRepository.get_items(db, skip, limit)
    else:
        return db.query(models.Item).offset(skip).limit(limit).all()

def get_item_by_id(db: Session, item_id: int):
    if repository_available:
        return ItemRepository.get_item_by_id(db, item_id)
    else:
        return db.query(models.Item).filter(models.Item.id == item_id).first()

def create_user_item(db: Session, item: ItemCreate, user_id: int):
    if repository_available:
        # Extract item data and explicitly set owner_id to avoid duplication
        item_data = item.dict()
        if 'owner_id' in item_data:
            del item_data['owner_id']
        item_data["owner_id"] = user_id
        return ItemRepository.create_item(db, item_data)
    else:
        # Original implementation
        item_data = item.dict()
        if 'owner_id' in item_data:
            del item_data['owner_id']
        db_item = models.Item(**item_data, owner_id=user_id)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

# Endpoints with SLO tracking
@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_item(request: Request, item: ItemCreate, db: Session = Depends(database.get_db)):
    """Create a new item with SLO tracking"""
    start_time = time.time()
    
    try:
        # Check if user exists
        user = db.query(models.User).filter(models.User.id == item.owner_id).first()
        if not user:
            # Track error for SLO
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="create_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create the item
        result = create_user_item(db=db, item=item, user_id=item.owner_id)
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="create_item",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return result
    except Exception as e:
        # Only track here if it's not already tracked above
        if not isinstance(e, HTTPException) or e.status_code != 404:
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="create_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
        raise

@router.get("/", response_model=List[ItemResponse])
@limiter.limit("30/minute")
def read_items(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """Get all items with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get items from database
        items = get_items(db, skip=skip, limit=limit)
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_items",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return items
    except Exception as e:
        # Track error for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_items",
            slo_name="data_access",
            latency=duration,
            is_error=True
        )
        raise

@router.get("/{item_id}", response_model=ItemResponse)
@limiter.limit("30/minute")
def read_item(request: Request, item_id: int, db: Session = Depends(database.get_db)):
    """Get a specific item by ID with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get item from database
        db_item = get_item_by_id(db, item_id=item_id)
        if db_item is None:
            # Track error for SLO
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="read_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="read_item",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return db_item
    except Exception as e:
        # Only track here if it's not already tracked above
        if not isinstance(e, HTTPException) or e.status_code != 404:
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="read_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
        raise

@router.put("/{item_id}", response_model=ItemResponse)
@limiter.limit("15/minute")
def update_item(request: Request, item_id: int, item: ItemCreate, db: Session = Depends(database.get_db)):
    """Update an item with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get item from database
        db_item = get_item_by_id(db, item_id=item_id)
        if db_item is None:
            # Track error for SLO
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="update_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Update item attributes
        for key, value in item.dict().items():
            setattr(db_item, key, value)
        
        db.commit()
        db.refresh(db_item)
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="update_item",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return db_item
    except Exception as e:
        # Only track here if it's not already tracked above
        if not isinstance(e, HTTPException) or e.status_code != 404:
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="update_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
        raise

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_item(request: Request, item_id: int, db: Session = Depends(database.get_db)):
    """Delete an item with SLO tracking"""
    start_time = time.time()
    
    try:
        # Get item from database
        db_item = get_item_by_id(db, item_id=item_id)
        if db_item is None:
            # Track error for SLO
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="delete_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Delete the item
        db.delete(db_item)
        db.commit()
        
        # Track for SLO
        duration = time.time() - start_time
        track_request_for_slo(
            endpoint="delete_item",
            slo_name="data_access",
            latency=duration,
            is_error=False
        )
        
        return None
    except Exception as e:
        # Only track here if it's not already tracked above
        if not isinstance(e, HTTPException) or e.status_code != 404:
            duration = time.time() - start_time
            track_request_for_slo(
                endpoint="delete_item",
                slo_name="data_access",
                latency=duration,
                is_error=True
            )
        raise
