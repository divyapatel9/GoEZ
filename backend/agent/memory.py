"""
MongoDB-backed conversation memory for the Health Agent.
Provides persistent storage of conversation history across sessions.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from langchain_core.messages import (
    BaseMessage, 
    HumanMessage, 
    AIMessage, 
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from .config import settings


class MongoDBMemory:
    """
    Stores and retrieves conversation history from MongoDB Atlas.
    
    Each user has their conversations stored with:
    - Session-based message history
    - Metadata for retrieval and context
    """
    
    def __init__(
        self, 
        mongo_uri: Optional[str] = None,
        database_name: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        Initialize MongoDB memory.
        
        Args:
            mongo_uri: MongoDB connection string
            database_name: Database name
            user_id: User identifier for scoping conversations
        """
        self.mongo_uri = mongo_uri or settings.mongodb_uri
        self.database_name = database_name or settings.mongodb_database
        self.collection_name = settings.conversations_collection
        self.user_id = user_id
        
        self._sync_client = None
        self._async_client = None
    
    @property
    def sync_client(self) -> MongoClient:
        if self._sync_client is None:
            self._sync_client = MongoClient(self.mongo_uri)
        return self._sync_client
    
    @property
    def async_client(self) -> AsyncIOMotorClient:
        if self._async_client is None:
            self._async_client = AsyncIOMotorClient(self.mongo_uri)
        return self._async_client
    
    def _get_sync_collection(self):
        return self.sync_client[self.database_name][self.collection_name]
    
    def _get_async_collection(self):
        return self.async_client[self.database_name][self.collection_name]
    
    # ==================== ASYNC METHODS ====================
    
    async def load_history(self, session_id: str) -> List[BaseMessage]:
        """
        Load conversation history for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            List of messages from the session
        """
        collection = self._get_async_collection()
        
        doc = await collection.find_one({
            "session_id": session_id,
            "user_id": self.user_id,
        })
        
        if doc and "messages" in doc:
            return messages_from_dict(doc["messages"])
        return []
    
    async def save_message(self, session_id: str, message: BaseMessage):
        """
        Save a new message to the session history.
        
        Args:
            session_id: The session identifier
            message: The message to save
        """
        collection = self._get_async_collection()
        
        message_dict = messages_to_dict([message])[0]
        
        await collection.update_one(
            {
                "session_id": session_id,
                "user_id": self.user_id,
            },
            {
                "$push": {"messages": message_dict},
                "$set": {
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "session_id": session_id,
                    "user_id": self.user_id,
                }
            },
            upsert=True
        )
    
    async def save_messages(self, session_id: str, messages: List[BaseMessage]):
        """
        Save multiple messages to the session history.
        
        Args:
            session_id: The session identifier
            messages: List of messages to save
        """
        collection = self._get_async_collection()
        
        message_dicts = messages_to_dict(messages)
        
        await collection.update_one(
            {
                "session_id": session_id,
                "user_id": self.user_id,
            },
            {
                "$push": {"messages": {"$each": message_dicts}},
                "$set": {
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "session_id": session_id,
                    "user_id": self.user_id,
                }
            },
            upsert=True
        )
    
    async def get_recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get user's recent conversation sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summaries
        """
        collection = self._get_async_collection()
        
        cursor = collection.find(
            {"user_id": self.user_id},
            {
                "session_id": 1,
                "created_at": 1,
                "updated_at": 1,
                "messages": {"$slice": 1}  # Get first message for preview
            }
        ).sort("updated_at", -1).limit(limit)
        
        sessions = []
        async for doc in cursor:
            preview = ""
            if doc.get("messages"):
                first_msg = doc["messages"][0]
                if "data" in first_msg and "content" in first_msg["data"]:
                    preview = first_msg["data"]["content"][:100]
            
            sessions.append({
                "session_id": doc["session_id"],
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "preview": preview,
            })
        
        return sessions
    
    async def clear_session(self, session_id: str):
        """Delete a specific session's history."""
        collection = self._get_async_collection()
        await collection.delete_one({
            "session_id": session_id,
            "user_id": self.user_id,
        })
    
    # ==================== SYNC METHODS ====================
    
    def load_history_sync(self, session_id: str) -> List[BaseMessage]:
        """Synchronous version of load_history."""
        collection = self._get_sync_collection()
        
        doc = collection.find_one({
            "session_id": session_id,
            "user_id": self.user_id,
        })
        
        if doc and "messages" in doc:
            return messages_from_dict(doc["messages"])
        return []
    
    def save_message_sync(self, session_id: str, message: BaseMessage):
        """Synchronous version of save_message."""
        collection = self._get_sync_collection()
        
        message_dict = messages_to_dict([message])[0]
        
        collection.update_one(
            {
                "session_id": session_id,
                "user_id": self.user_id,
            },
            {
                "$push": {"messages": message_dict},
                "$set": {
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                    "session_id": session_id,
                    "user_id": self.user_id,
                }
            },
            upsert=True
        )
    
    def close(self):
        """Close MongoDB connections."""
        if self._sync_client:
            self._sync_client.close()
        if self._async_client:
            self._async_client.close()


def get_mongodb_checkpointer():
    """
    Get a LangGraph MongoDB checkpointer for state persistence.
    
    Returns:
        MongoDBSaver instance configured for the application
    """
    try:
        from langgraph.checkpoint.mongodb import MongoDBSaver
        
        client = MongoClient(settings.mongodb_uri)
        
        return MongoDBSaver(
            client=client,
            db_name=settings.mongodb_database,
            collection_name=settings.checkpoint_collection,
        )
    except ImportError:
        # Fallback to memory saver if MongoDB checkpointer not available
        from langgraph.checkpoint.memory import MemorySaver
        print("Warning: langgraph-checkpoint-mongodb not installed, using memory saver")
        return MemorySaver()


async def get_async_mongodb_checkpointer():
    """
    Get an async LangGraph MongoDB checkpointer.
    
    Returns:
        AsyncMongoDBSaver instance
    """
    try:
        from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
        
        client = AsyncIOMotorClient(settings.mongodb_uri)
        
        return AsyncMongoDBSaver(
            client=client,
            db_name=settings.mongodb_database,
            collection_name=settings.checkpoint_collection,
        )
    except ImportError:
        from langgraph.checkpoint.memory import MemorySaver
        print("Warning: langgraph-checkpoint-mongodb not installed, using memory saver")
        return MemorySaver()
