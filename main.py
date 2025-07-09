from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
import os
from datetime import datetime
from typing import Optional

app = FastAPI()

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

# ---------------------- Helpers ----------------------

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def load_withdraws():
    if os.path.exists(WITHDRAWS_FILE):
        with open(WITHDRAWS_FILE, "r") as f:
            return json.load(f)
    return []

def save_withdraws(data):
    with open(WITHDRAWS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------------------- API Routes ----------------------

@app.post("/signup")
def signup(user: User):
    users = load_users()
    if user.email in users:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    users[user.email] = {
        "name": user.name,
        "password": user.password,
        "balance": 0
    }
    save_users(users)
    return {"message": "Signup successful"}

@app.post("/login")
def login(data: LoginData):
    users = load_users()
    if data.email in users and users[data.email]["password"] == data.password:
        return {"message": "Login successful"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/balance/{email}")
def get_balance(email: str):
    users = load_users()
    if email not in users:
        raise HTTPException(status_code=404, detail="User not found")
    return {"balance": users[email]["balance"]}

@app.post("/add_balance")
def add_balance(data: TransferRequest):
    users = load_users()
    if data.from_email not in users:
        raise HTTPException(status_code=404, detail="User not found")

    users[data.from_email]["balance"] += data.amount
    save_users(users)
    return {"message": f"Rs {data.amount} added to {data.from_email}"}

@app.post("/transfer")
def transfer(data: TransferRequest):
    users = load_users()
    if data.from_email not in users or data.to_email not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if users[data.from_email]["balance"] < data.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    users[data.from_email]["balance"] -= data.amount
    users[data.to_email]["balance"] += data.amount
    save_users(users)
    return {"message": f"Transferred Rs {data.amount} from {data.from_email} to {data.to_email}"}

@app.post("/withdraw")
def withdraw(data: WithdrawRequest):
    users = load_users()
    if data.email not in users:
        raise HTTPException(status_code=404, detail="User not found")
    if users[data.email]["balance"] < data.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    users[data.email]["balance"] -= data.amount
    save_users(users)

    withdraws = load_withdraws()
    withdraws.append({
        "user": data.email,
        "amount": data.amount,
        "status": "Pending",
        "timestamp": datetime.now().isoformat()
    })
    save_withdraws(withdraws)

    return {"message": "Withdraw request sent, status: Pending"}

@app.get("/withdraws")
def get_withdraws(status: Optional[str] = None):
    withdraws = load_withdraws()
    if status:
        return [w for w in withdraws if w["status"].lower() == status.lower()]
    return withdraws

@app.post("/approve_withdraw")
def approve_withdraw(index: int):
    withdraws = load_withdraws()
    if index >= len(withdraws):
        raise HTTPException(status_code=404, detail="Invalid index")
    
    withdraws[index]["status"] = "Approved"
    save_withdraws(withdraws)
    return {"message": "Withdraw approved"}

@app.post("/reject_withdraw")
def reject_withdraw(index: int):
    withdraws = load_withdraws()
    if index >= len(withdraws):
        raise HTTPException(status_code=404, detail="Invalid index")

    users = load_users()
    email = withdraws[index]["user"]
    amount = withdraws[index]["amount"]
    users[email]["balance"] += amount

    withdraws[index]["status"] = "Rejected"
    save_users(users)
    save_withdraws(withdraws)

    return {"message": "Withdraw rejected and refunded"}

@app.get("/stats")
def get_stats():
    users = load_users()
    withdraws = load_withdraws()
    return {
        "total_users": len(users),
        "total_balance": sum(u["balance"] for u in users.values()),
        "total_withdraws": len(withdraws)
    }
