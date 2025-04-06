"""
Item repository with traced database operations
"""
from sqlalchemy.orm import Session
from ..models import Item
from typing import List, Optional
from ..db_tracing import traced_db_operation

class ItemRepository:
    """Repository for Item entity with traced database operations"""
    
    @staticmethod
    @traced_db_operation("get_items_list")
    def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[Item]:
        """Get a list of items with tracing"""
        return db.query(Item).offset(skip).limit(limit).all()
    
    @staticmethod
    @traced_db_operation("get_item_by_id")
    def get_item_by_id(db: Session, item_id: int) -> Optional[Item]:
        """Get a single item by ID with tracing"""
        return db.query(Item).filter(Item.id == item_id).first()
    
    @staticmethod
    @traced_db_operation("get_user_items")
    def get_user_items(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Item]:
        """Get items belonging to a user with tracing"""
        return db.query(Item).filter(Item.owner_id == user_id).offset(skip).limit(limit).all()
    
    @staticmethod
    @traced_db_operation("create_item")
    def create_item(db: Session, item_data: dict) -> Item:
        """Create a new item with tracing"""
        db_item = Item(**item_data)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    
    @staticmethod
    @traced_db_operation("update_item")
    def update_item(db: Session, item_id: int, item_data: dict) -> Optional[Item]:
        """Update an item with tracing"""
        db_item = ItemRepository.get_item_by_id(db, item_id)
        if not db_item:
            return None
            
        for key, value in item_data.items():
            if hasattr(db_item, key):
                setattr(db_item, key, value)
                
        db.commit()
        db.refresh(db_item)
        return db_item
    
    @staticmethod
    @traced_db_operation("delete_item")
    def delete_item(db: Session, item_id: int) -> bool:
        """Delete an item with tracing"""
        db_item = ItemRepository.get_item_by_id(db, item_id)
        if not db_item:
            return False
            
        db.delete(db_item)
        db.commit()
        return True
