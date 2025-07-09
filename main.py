from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import json
import os
from datetime import datetime
from typing import Optional
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Banking API", version="1.0.0")

# File paths
USERS_FILE = "users.json"
WITHDRAWS_FILE = "withdraws.json"

# ---------------------- Models ----------------------

class User(BaseModel):
    name: str
    email: str
    password: str

class LoginData(BaseModel):
    email: str
    password: str

class TransferRequest(BaseModel):
    from_email: str
    to_email: str
    amount: float

class WithdrawRequest(BaseModel):
    email: str
    amount: float

# ---------------------- Helper Functions ----------------------

def load_data(file_path: str, default):
    """Generic function to load JSON data from file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"Error loading {file_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load data"
        )

def save_data(file_path: str, data):
    """Generic function to save data to JSON file"""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving to {file_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save data"
        )

def load_users():
    return load_data(USERS_FILE, {})

def save_users(users):
    save_data(USERS_FILE, users)

def load_withdraws():
    return load_data(WITHDRAWS_FILE, [])

def save_withdraws(data):
    save_data(WITHDRAWS_FILE, data)

# ---------------------- API Endpoints ----------------------

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: User):
    """Register a new user"""
    users = load_users()
    
    if user.email in users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    if len(user.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    users[user.email] = {
        "name": user.name,
        "password": user.password,
        "balance": 0.0,
        "created_at": datetime.now().isoformat()
    }
    save_users(users)
    logger.info(f"New user registered: {user.email}")
    return {"message": "Signup successful"}

@app.post("/login")
def login(data: LoginData):
    """Authenticate a user"""
    users = load_users()
    
    if data.email not in users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if users[data.email]["password"] != data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    return {"message": "Login successful"}

@app.get("/balance/{email}")
def get_balance(email: str):
    """Get user balance"""
    users = load_users()
    
    if email not in users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"balance": users[email]["balance"]}

@app.post("/add_balance")
def add_balance(data: TransferRequest):
    """Add money to user account"""
    users = load_users()
    
    if data.from_email not in users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )
    
    users[data.from_email]["balance"] += data.amount
    save_users(users)
    logger.info(f"Added {data.amount} to {data.from_email}")
    return {"message": f"Rs {data.amount} added to {data.from_email}"}

@app.post("/transfer")
def transfer(data: TransferRequest):
    """Transfer money between accounts"""
    users = load_users()
    
    if data.from_email not in users or data.to_email not in users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )
    
    if users[data.from_email]["balance"] < data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance"
        )
    
    users[data.from_email]["balance"] -= data.amount
    users[data.to_email]["balance"] += data.amount
    save_users(users)
    logger.info(f"Transferred {data.amount} from {data.from_email} to {data.to_email}")
    return {
        "message": f"Transferred Rs {data.amount} from {data.from_email} to {data.to_email}",
        "new_balance": users[data.from_email]["balance"]
    }

@app.post("/withdraw")
def withdraw(data: WithdrawRequest):
    """Request a withdrawal"""
    users = load_users()
    
    if data.email not in users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be positive"
        )
    
    if users[data.email]["balance"] < data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance"
        )
    
    users[data.email]["balance"] -= data.amount
    save_users(users)
    
    withdraws = load_withdraws()
    new_withdraw = {
        "user": data.email,
        "amount": data.amount,
        "status": "Pending",
        "timestamp": datetime.now().isoformat(),
        "processed_at": None
    }
    withdraws.append(new_withdraw)
    save_withdraws(withdraws)
    
    logger.info(f"Withdrawal request for {data.amount} from {data.email}")
    return {
        "message": "Withdraw request sent",
        "status": "Pending",
        "request_id": len(withdraws) - 1
    }

@app.get("/withdraws")
def get_withdraws(status: Optional[str] = None):
    """Get withdrawal requests with optional status filter"""
    withdraws = load_withdraws()
    
    if status:
        valid_statuses = ["Pending", "Approved", "Rejected"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        return [w for w in withdraws if w["status"].lower() == status.lower()]
    
    return withdraws

@app.post("/approve_withdraw/{index}")
def approve_withdraw(index: int):
    """Approve a withdrawal request"""
    withdraws = load_withdraws()
    
    if index < 0 or index >= len(withdraws):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid request index"
        )
    
    if withdraws[index]["status"] != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal already processed"
        )
    
    withdraws[index]["status"] = "Approved"
    withdraws[index]["processed_at"] = datetime.now().isoformat()
    save_withdraws(withdraws)
    
    logger.info(f"Approved withdrawal #{index}")
    return {"message": "Withdraw approved"}

@app.post("/reject_withdraw/{index}")
def reject_withdraw(index: int):
    """Reject a withdrawal request and refund"""
    withdraws = load_withdraws()
    users = load_users()
    
    if index < 0 or index >= len(withdraws):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid request index"
        )
    
    if withdraws[index]["status"] != "Pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal already processed"
        )
    
    email = withdraws[index]["user"]
    amount = withdraws[index]["amount"]
    
    users[email]["balance"] += amount
    withdraws[index]["status"] = "Rejected"
    withdraws[index]["processed_at"] = datetime.now().isoformat()
    
    save_users(users)
    save_withdraws(withdraws)
    
    logger.info(f"Rejected withdrawal #{index} and refunded {amount} to {email}")
    return {"message": "Withdraw rejected and amount refunded"}

@app.get("/stats")
def get_stats():
    """Get system statistics"""
    users = load_users()
    withdraws = load_withdraws()
    
    total_approved = sum(w["amount"] for w in withdraws if w["status"] == "Approved")
    total_pending = sum(w["amount"] for w in withdraws if w["status"] == "Pending")
    
    return {
        "total_users": len(users),
        "total_balance": sum(u["balance"] for u in users.values()),
        "total_withdraws": len(withdraws),
        "approved_withdraws": total_approved,
        "pending_withdraws": total_pending
    }

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}
