import os
from datetime import datetime, date
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Attendance API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Models (request/response) ----------
class EmployeeIn(BaseModel):
    name: str
    email: str
    role: Optional[str] = None
    phone: Optional[str] = None

class EmployeeOut(EmployeeIn):
    id: str
    is_active: bool

class AttendanceMarkIn(BaseModel):
    employee_id: str
    lat: Optional[float] = None
    lng: Optional[float] = None

class AttendanceOut(BaseModel):
    id: str
    employee_id: str
    date: str
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_m: Optional[float] = None

# ---------- Helper ----------

def _collection(name: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    return db[name]

OFFICE_LAT = float(os.getenv("OFFICE_LAT", "0"))
OFFICE_LNG = float(os.getenv("OFFICE_LNG", "0"))
GEOFENCE_M = float(os.getenv("GEOFENCE_M", "200"))  # meters

from math import radians, sin, cos, sqrt, atan2

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# ---------- Routes ----------
@app.get("/")
def root():
    return {"message": "Attendance API running"}

@app.get("/test")
def test_database():
    resp = {
        "backend": "running",
        "database": "not-connected",
        "collections": []
    }
    try:
        if db is not None:
            resp["database"] = "connected"
            resp["collections"] = db.list_collection_names()
    except Exception as e:
        resp["database"] = f"error: {str(e)[:80]}"
    return resp

# Employees CRUD
@app.post("/employees", response_model=EmployeeOut)
def create_employee(payload: EmployeeIn):
    data = payload.model_dump()
    data["is_active"] = True
    emp_id = create_document("employee", data)
    return {"id": emp_id, **payload.model_dump(), "is_active": True}

@app.get("/employees", response_model=List[EmployeeOut])
def list_employees(q: Optional[str] = Query(None, description="Search by name or email")):
    coll = _collection("employee")
    filter_q = {"is_active": True}
    if q:
        filter_q["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    docs = list(coll.find(filter_q).sort("created_at", -1))
    result = []
    for d in docs:
        result.append({
            "id": str(d.get("_id")),
            "name": d.get("name"),
            "email": d.get("email"),
            "role": d.get("role"),
            "phone": d.get("phone"),
            "is_active": d.get("is_active", True)
        })
    return result

@app.delete("/employees/{employee_id}")
def remove_employee(employee_id: str):
    coll = _collection("employee")
    try:
        oid = ObjectId(employee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee id")
    res = coll.update_one({"_id": oid}, {"$set": {"is_active": False, "updated_at": datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"status": "ok"}

# Attendance
@app.post("/attendance/mark", response_model=AttendanceOut)
def mark_attendance(payload: AttendanceMarkIn):
    # verify employee exists and is active
    coll_emp = _collection("employee")
    try:
        oid = ObjectId(payload.employee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee id")
    emp = coll_emp.find_one({"_id": oid, "is_active": True})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found or inactive")

    today = date.today().isoformat()
    lat = payload.lat
    lng = payload.lng

    distance = None
    status = "absent"
    if lat is not None and lng is not None and (OFFICE_LAT != 0 or OFFICE_LNG != 0):
        distance = haversine_m(OFFICE_LAT, OFFICE_LNG, lat, lng)
        status = "present" if distance <= GEOFENCE_M else "absent"

    att_data = {
        "employee_id": payload.employee_id,
        "date": today,
        "status": status,
        "lat": lat,
        "lng": lng,
        "distance_m": distance,
    }
    att_id = create_document("attendance", att_data)

    return {
        "id": att_id,
        **att_data
    }

@app.get("/attendance/daily")
def attendance_daily(date_str: Optional[str] = None):
    coll = _collection("attendance")
    day = date_str or date.today().isoformat()
    docs = list(coll.find({"date": day}))
    # join with employees
    emp_coll = _collection("employee")
    result = []
    for d in docs:
        emp = emp_coll.find_one({"_id": ObjectId(d.get("employee_id"))}) if d.get("employee_id") else None
        result.append({
            "id": str(d.get("_id")),
            "employee_id": d.get("employee_id"),
            "employee_name": emp.get("name") if emp else None,
            "status": d.get("status"),
            "date": d.get("date"),
            "distance_m": d.get("distance_m")
        })
    return {"date": day, "records": result}

@app.get("/attendance/summary/{employee_id}")
def attendance_summary(employee_id: str, start: Optional[str] = None, end: Optional[str] = None):
    # summaries for charts
    coll = _collection("attendance")
    q = {"employee_id": employee_id}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    docs = list(coll.find(q))
    present = sum(1 for d in docs if d.get("status") == "present")
    absent = sum(1 for d in docs if d.get("status") == "absent")
    by_date = {}
    for d in docs:
        by_date.setdefault(d.get("date"), {"present": 0, "absent": 0})
        by_date[d.get("date")][d.get("status")] += 1
    series = [{"date": k, **v} for k, v in sorted(by_date.items())]
    return {"present": present, "absent": absent, "series": series}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
