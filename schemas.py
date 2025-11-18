"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

# Example schemas (replace with your own):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Attendance app schemas

class Employee(BaseModel):
    """
    Employees collection schema
    Collection: "employee"
    """
    name: str = Field(..., description="Employee full name")
    email: str = Field(..., description="Employee email")
    role: Optional[str] = Field(None, description="Job title/role")
    phone: Optional[str] = Field(None, description="Contact number")
    is_active: bool = Field(True, description="Whether the employee is active")

class Attendance(BaseModel):
    """
    Attendance collection schema
    Collection: "attendance"
    """
    employee_id: str = Field(..., description="Reference to employee _id as string")
    status: Literal["present", "absent"] = Field(..., description="Attendance status based on location")
    date: str = Field(..., description="ISO date (YYYY-MM-DD) for the attendance record")
    lat: Optional[float] = Field(None, description="Latitude captured when marking attendance")
    lng: Optional[float] = Field(None, description="Longitude captured when marking attendance")
    distance_m: Optional[float] = Field(None, description="Distance to office in meters")

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
