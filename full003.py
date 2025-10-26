
import streamlit as st
import pydeck as pdk
import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pandas
from datetime import datetime, timedelta
from streamlit_lottie import st_lottie
from typing import Optional, Dict, Any, Tuple, Literal
import time
import json 
import os
import sqlite3
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from decimal import Decimal
from zoneinfo import ZoneInfo
import openpyxl
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import stripe
import logging
from fastapi.responses import HTMLResponse
from typing import List
import html.parser
from contextlib import asynccontextmanager
import uvicorn
import threading


# --- Combined App ---
# This single file contains both the FastAPI backend and the Streamlit frontend.
# To run it, simply execute `streamlit run full.py` in your terminal.

# ==============================================================================
# --- 1. BACKEND (FastAPI) CODE ---
# ==============================================================================

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# --- In-Memory Cache for Parking Data ---
parking_data_cache = {}
cache_status: Dict[str, str] = {} # To track loading status (e.g., "loading", "ready")
bay_to_kerbside_map: Dict[int, int] = {} # To map bayid to kerbsideid
CACHE_DURATION = timedelta(minutes=10)

# --- Robust File Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.path.join(BASE_DIR, "parking.db")
JSON_PATH = os.path.join(BASE_DIR, "on-street-parking-bay-sensors.json")
HTML_PATH = os.path.join(BASE_DIR, "parking2.html")
EXCEL_PATH = os.path.join(BASE_DIR, "melbourne_parking_bay_sensors.csv")
FEES_CSV_PATH = os.path.join(BASE_DIR, "on-street-with-fees.csv")

# --- Lifespan Manager for Startup Actions ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend server starting up...")
    # --- Database Initialization ---
    db = sqlite3.connect(DATABASE_URL)
    cursor = db.cursor()
    # Create users table with a 'role' column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            name TEXT,
            phone TEXT,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            stripe_customer_id TEXT
        )
    """)
    # Create bookings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            spot_id TEXT,
            booking_time TEXT,
            amount INTEGER,
            status TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Create activity_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Create vehicles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nickname TEXT NOT NULL,
            make TEXT,
            model TEXT,
            license_plate TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Create favorite_spots table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_spots (
            user_id INTEGER NOT NULL,
            spot_id TEXT NOT NULL,
            nickname TEXT,
            added_on TEXT NOT NULL,
            PRIMARY KEY (user_id, spot_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Drop and recreate the fees table on startup to ensure schema is always fresh
    cursor.execute("DROP TABLE IF EXISTS parking_fees")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parking_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            kerbside_id INTEGER UNIQUE NOT NULL,
            area_type TEXT,
            weekday_peak REAL,
            weekday_offpeak REAL,
            weekend_rate REAL,
            notes TEXT,
            rate_type TEXT
        )
    """)

    # --- Simple Migration: Add 'role' column to users if it doesn't exist ---
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'role' not in columns:
        logger.info("Adding 'role' column to 'users' table.")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if 'stripe_customer_id' not in columns:
        logger.info("Adding 'stripe_customer_id' column to 'users' table.")
        cursor.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")

    # --- Load parking fee data from the new CSV on startup ---
    try:
        fees_df = pandas.read_csv(FEES_CSV_PATH)
        fees_df.rename(columns={
            'KerbsideID': 'kerbside_id',
            'area_type': 'area_type',
            'weekday_peak_aud_per_hr': 'weekday_peak',
            'weekday_offpeak_aud_per_hr': 'weekday_offpeak',
            'weekend_aud_per_hr': 'weekend_rate',
            'rate_type': 'rate_type'
        }, inplace=True)
        
        for _, row in fees_df.iterrows():
            if pandas.notna(row.get('kerbside_id')):
                cursor.execute("""
                    INSERT OR IGNORE INTO parking_fees (city, kerbside_id, area_type, weekday_peak, weekday_offpeak, weekend_rate, rate_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("melbourne", int(row['kerbside_id']), row.get('area_type'), row.get('weekday_peak'), row.get('weekday_offpeak'), row.get('weekend_rate'), row.get('rate_type')))
        
        db.commit()
        logger.info(f"Successfully loaded or verified {len(fees_df)} parking fee records from {os.path.basename(FEES_CSV_PATH)}.")
    except FileNotFoundError:
        logger.warning(f"'{os.path.basename(FEES_CSV_PATH)}' not found. No fee data will be loaded.")
    except Exception as e:
        logger.error(f"Failed to load parking fee data from CSV: {e}")

    # --- Load the bayid to kerbsideid mapping on startup ---
    global bay_to_kerbside_map
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            sensor_data = json.load(f)
        for item in sensor_data:
            bay_id = item.get("bayid")
            kerbside_id = item.get("kerbsideid")
            if bay_id and kerbside_id:
                bay_to_kerbside_map[int(bay_id)] = int(kerbside_id)
        logger.info(f"Successfully loaded {len(bay_to_kerbside_map)} bay ID to kerbside ID mappings.")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Could not load or parse bay ID mapping from {JSON_PATH}: {e}")

    # --- Create a default admin user if one doesn't exist ---
    cursor.execute("SELECT username FROM users WHERE username = ?", ("YogeshP",))
    if not cursor.fetchone():
        admin_password = "Aqiguj@700"
        hashed_password = get_password_hash(admin_password)
        cursor.execute(
            "INSERT INTO users (username, email, name, hashed_password, role) VALUES (?, ?, ?, ?, ?)",
            ("YogeshP", "admin@example.com", "Admin User", hashed_password, "admin")
        )
        logger.info(f"Default admin user 'YogeshP' with password '{admin_password}' created.")

    db.commit()
    db.close()
    logger.info("Database tables verified/created successfully.")
    logger.info("Parking data will be loaded on the first request for each city.")
    yield
    logger.info("Backend server shutting down.")

backend_app = FastAPI(lifespan=lifespan)

# --- Middleware ---
backend_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Environment & Security Setup ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret-key-if-not-set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# --- Database Connection ---
def get_db():
    db = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()

# --- User & Token Models ---
class User(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    role: str = 'user'

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    password: str

class BookingRequest(BaseModel):
    payment_method_id: str

class Booking(BaseModel):
    id: int
    user_id: int
    spot_id: str
    booking_time: datetime
    amount: int
    status: str

class DonationRequest(BaseModel):
    amount: int  # Amount in cents
    payment_method_id: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ActivityLogRequest(BaseModel):
    action: str
    details: Optional[Dict] = None

class ActivityLogEntry(BaseModel):
    username: str
    action: str
    details: Optional[str] = None
    timestamp: datetime

class ParkingFee(BaseModel):
    city: str
    street_name: str
    zone: Optional[str] = None
    peak_fee: Optional[float] = None
    off_peak_fee: Optional[float] = None
    shoulder_fee: Optional[float] = None
    notes: Optional[str] = None

class Vehicle(BaseModel):
    id: int
    user_id: int
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    license_plate: str

class VehicleCreate(BaseModel):
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    license_plate: str

class FavoriteSpotCreate(BaseModel):
    nickname: Optional[str] = None

class FavoriteSpot(BaseModel):
    user_id: int
    spot_id: str
    nickname: Optional[str]
    added_on: datetime

class PaymentIntentRequest(BaseModel):
    spot_id: str
    amount: int # Amount in cents

class PaymentMethod(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool

# --- Email Configuration ---
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", "noreply@example.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=None,
)

async def send_confirmation_email(email_to: str, username: str):
    """Sends a welcome email to a new user."""
    html = f"""
    <p>Hi {username},</p>
    <p>Welcome to Express Parking Australia! We're excited to have you on board.</p>
    <p>Happy parking!</p>
    """
    message = MessageSchema(subject="Welcome to Express Parking Australia!", recipients=[email_to], body=html, subtype=MessageType.html)
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_password_reset_email(email_to: str, username: str, token: str):
    """Sends a password reset email to a user."""
    reset_link = f"http://localhost:8501?reset_token={token}"
    html = f"""
    <p>Hi {username},</p>
    <p>You requested a password reset. Click the link below to reset your password. This link is valid for 15 minutes.</p>
    <p><a href="{reset_link}">Reset Password</a></p>
    <p>If you did not request a password reset, please ignore this email.</p>
    """
    message = MessageSchema(
        subject="Password Reset Request", recipients=[email_to], body=html, subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)

# --- Paginated Data Fetching & City-Specific Logic ---
def fetch_paginated_data(base_url: str, city_name: str) -> List[dict]:
    """Generic function to fetch all records from a paginated API."""
    all_records = []
    offset = 0
    limit = 100
    while True:
        try:
            params = {"limit": limit, "offset": offset}
            response = requests.get(base_url, params=params, timeout=40)
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                logger.info(f"Finished fetching all {city_name} data. Total records: {len(all_records)}")
                break

            all_records.extend(results)
            logger.info(f"Fetched {len(results)} {city_name} records... Total so far: {len(all_records)}")
            offset += limit
            time.sleep(0.25)
        except requests.RequestException as e:
            logger.error(f"API request failed during {city_name} pagination: {e}.")
            break
    return all_records

def _fetch_melbourne_data() -> List[dict]:
    """Fetches and processes all parking data for Melbourne."""
    url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/on-street-parking-bay-sensors/records"
    api_records = fetch_paginated_data(url, "Melbourne")
    
    processed_data = []
    au_tz = ZoneInfo("Australia/Sydney")
    in_tz = ZoneInfo("Asia/Kolkata")
    current_time = datetime.now(in_tz)

    if api_records:
        for item in api_records:
            location = item.get("location", {})
            lat, lng = float(location.get("lat", 0)), float(location.get("lon", 0))
            if lat != 0 or lng != 0:
                processed_data.append(
                    {
                        "city": "melbourne", "lat": lat, "lng": lng,
                        "name": str(item.get("bayid", f"spot_{current_time.timestamp()}")),
                        "street": item.get("st_marker_id", "Unknown"),
                        "occupied": item.get("status_description", "").lower() == "present",
                        "status_note": "Data from Live API", "last_updated": item.get("last_updated", current_time.isoformat()),
                        "kerbsideid": item.get("kerbsideid"), "zone_number": item.get("zone_number")
                    }
                )
        return processed_data

    logger.warning("Melbourne API fetch failed. Falling back to local JSON.")
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        for item in json_data:
            location = item.get("location", {})
            lat, lng = float(location.get("lat", 0)), float(location.get("lon", 0))
            if lat != 0 or lng != 0:
                processed_data.append({
                     "city": "melbourne", "lat": lat, "lng": lng,
                    "name": str(item.get("kerbsideid", f"spot_{current_time.timestamp()}")), "street": "Unknown",
                    "occupied": item.get("status_description", "").lower() == "present", "status_note": "Data from JSON file",
                    "last_updated": item.get("lastupdated", current_time.isoformat()), "fee": 2.5,
                    "auTime": current_time.astimezone(au_tz).strftime("%H:%M %d/%m/%Y"), "inTime": current_time.strftime("%H:%M %d/%m/%Y")
                })
        return processed_data
    except Exception as e:
        logger.error(f"Melbourne JSON fallback failed: {e}")
        return []

def _fetch_brisbane_data() -> List[dict]:
    """Fetches and processes all real-time parking facility data for Brisbane."""
    url = "https://www.data.brisbane.qld.gov.au/api/explore/v2.1/catalog/datasets/real-time-parking-data/records"
    api_records = fetch_paginated_data(url, "Brisbane")
    
    processed_data = []
    au_tz = ZoneInfo("Australia/Sydney")
    in_tz = ZoneInfo("Asia/Kolkata")
    current_time = datetime.now(in_tz)

    if api_records:
        for item in api_records:
            lat = item.get("latitude")
            lng = item.get("longitude")
            
            if lat is not None and lng is not None:
                try:
                    vacancies = int(item.get("vacancies", 0))
                    capacity = int(item.get("capacity", 0))
                except (ValueError, TypeError):
                    vacancies = 0
                    capacity = 0

                processed_data.append({
                    "city": "brisbane", 
                    "lat": float(lat), 
                    "lng": float(lng),
                    "name": item.get("facility_name", f"facility_{current_time.timestamp()}"),
                    "street": item.get("address", "Unknown"),
                    "occupied": vacancies <= 0,
                    "status_note": f"Vacancies: {vacancies}/{capacity}",
                    "last_updated": item.get("date", current_time.isoformat()),
                    "fee": 5.0,
                    "auTime": current_time.astimezone(au_tz).strftime("%H:%M %d/%m/%Y"),
                    "inTime": current_time.strftime("%H:%M %d/%m/%Y")
                })
    return processed_data

def _get_fee_for_spot(db: sqlite3.Connection, city: str, kerbside_id: int) -> Dict:
    """Helper to get fee data for a spot based on its Kerbside ID and the current time."""
    city_lower = city.lower()
    
    if city_lower == "melbourne":
        query = "SELECT * FROM parking_fees WHERE city = ? AND kerbside_id = ?"
        fee_data = db.execute(query, (city_lower, kerbside_id)).fetchone()
        if fee_data:
            now_melbourne = datetime.now(ZoneInfo("Australia/Melbourne"))
            weekday = now_melbourne.weekday()  # Monday is 0, Sunday is 6
            hour = now_melbourne.hour

            current_fee = None
            fee_type = "Off-Peak"
            if weekday < 5:  # Weekday (Mon-Fri)
                if 7 <= hour < 19: # 7 AM to 7 PM
                    current_fee = fee_data['weekday_peak']
                    fee_type = "Peak"
                else:
                    current_fee = fee_data['weekday_offpeak']
            else:  # Weekend
                current_fee = fee_data['weekend_rate']
                fee_type = "Weekend"
            
            return {"current_fee": current_fee, "fee_type": fee_type, "area_type": fee_data['area_type']}
    return {}

def _update_cache(city: str):
    """The actual data fetching logic, designed to be run in the background."""
    city_lower = city.lower()
    logger.info(f"BACKGROUND: Starting fresh data fetch for '{city_lower}'.")
    cache_status[city_lower] = "loading"
    
    processed_data = []
    db_conn = sqlite3.connect(DATABASE_URL)
    db_conn.row_factory = sqlite3.Row
    try:
        if city_lower == "melbourne":
            processed_data = _fetch_melbourne_data()
        elif city_lower == "brisbane":
            processed_data = _fetch_brisbane_data()
        else:
            logger.warning(f"BACKGROUND: No data source configured for city: {city}")
        
        for spot in processed_data:
            try:
                bay_id = int(spot.get("name"))
                if kerbside_id := spot.get('kerbsideid'):
                    spot['kerbsideid'] = kerbside_id
                    spot['zone_number'] = spot.get('zone_number', 'N/A')
                    fee_info = _get_fee_for_spot(db_conn, city_lower, kerbside_id)
                    spot.update(fee_info)
            except (ValueError, TypeError):
                continue # Skip spots with non-integer names (like generated ones)
    finally:
        db_conn.close()

    if processed_data:
        parking_data_cache[city_lower] = (processed_data, datetime.now())
        cache_status[city_lower] = "ready"
        logger.info(f"BACKGROUND: Cached {len(processed_data)} spots for '{city_lower}'.")
    else:
        cache_status[city_lower] = "failed"
        logger.error(f"BACKGROUND: Failed to fetch or process data for '{city_lower}'.")

def load_data(city: str, background_tasks: BackgroundTasks) -> List[dict]:
    """Main data loading function. Returns cached data or triggers a background update."""
    city_lower = city.lower()
    
    if city_lower in parking_data_cache:
        data, timestamp = parking_data_cache[city_lower]
        if datetime.now() - timestamp < CACHE_DURATION:
            logger.info(f"✅ Serving '{city_lower}' data from cache.")
            return data

    if cache_status.get(city_lower) != "loading":
        logger.info(f"Cache miss for '{city_lower}'. Triggering background fetch.")
        background_tasks.add_task(_update_cache, city)
    
    return parking_data_cache.get(city_lower, ([], None))[0]

# --- Authentication Functions ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user(db: sqlite3.Connection, username: str):
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user:
        return UserInDB(**user)
    return None

def get_user_by_email(db: sqlite3.Connection, email: str):
    """Checks if a user exists with the given email."""
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user:
        return UserInDB(**user)
    return None

async def get_current_user(token: str = Depends(oauth2_scheme), db: sqlite3.Connection = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
    return dict(user)

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure the current user is an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: requires admin privileges."
        )
    return current_user

def _get_osrm_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, steps: bool = False):
    """
    Helper function to fetch a route from OSRM, including turn-by-turn steps.
    Raises exceptions on failure.
    """
    url_params = f"overview=full&geometries=geojson{'&steps=true' if steps else ''}"
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?{url_params}"
    logger.info(f"Requesting OSRM route: {url}")
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    data = response.json()
    
    if not data.get('routes'):
        raise ValueError("No routes found in OSRM response")

    route = data['routes'][0]
    
    if 'geometry' not in route or 'coordinates' not in route['geometry']:
         raise ValueError("Geometry or coordinates missing in OSRM response")

    geometry_coords = route['geometry']['coordinates']
    route_geometry = [[coord[1], coord[0]] for coord in geometry_coords]

    if not steps:
        return {"geometry": route_geometry, "steps": [], "summary": {}}

    # Process steps if requested
    route_steps = []
    if route.get('legs') and route['legs'][0].get('steps'):
        for step in route['legs'][0]['steps']:
            maneuver = step.get('maneuver', {})
            instruction = maneuver.get('instruction')
            if not instruction:
                maneuver_type = maneuver.get('type', 'continue').replace('_', ' ').title()
                road_name = step.get('name', 'the road')
                if maneuver_type.lower() == 'arrive':
                    instruction = f"You will arrive at your destination."
                else:
                    instruction = f"{maneuver_type} onto {road_name}"
            
            distance = step.get('distance', 0)
            route_steps.append({"instruction": instruction, "distance_meters": distance})

    route_summary = {
        "total_distance_meters": route.get('distance', 0),
        "total_duration_seconds": route.get('duration', 0)
    }
    
    return {"geometry": route_geometry, "steps": route_steps, "summary": route_summary}

def get_route_with_fallback(start_lat: float, start_lon: float, end_lat: float, end_lon: float, steps: bool = False) -> Dict[str, Any]:
    """
    Tries to get a route using _get_osrm_route, if it fails, returns an empty route.
    """
    try:
        return _get_osrm_route(start_lat, start_lon, end_lat, end_lon, steps=steps)
    except Exception as e:
        logger.error(f"OSRM routing failed: {e}")
        # Return an empty route instead of raising an exception
        return {"geometry": [], "steps": [], "summary": {}}


# --- API Endpoints ---
@backend_app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: sqlite3.Connection = Depends(get_db)):
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@backend_app.post("/register")
async def register_user(user: UserCreate, background_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    if get_user(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if user.email and get_user_by_email(db, user.email): 
        raise HTTPException(status_code=400, detail="Email already in use")
    
    # Create a Stripe Customer
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            description=f"Customer for username: {user.username}"
        )
        stripe_customer_id = customer.id
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create Stripe customer for {user.username}: {e}")
        raise HTTPException(status_code=500, detail="Could not set up payment profile.")

    hashed_password = get_password_hash(user.password)
    db.execute("INSERT INTO users (username, email, name, hashed_password, stripe_customer_id) VALUES (?, ?, ?, ?, ?)",
               (user.username, user.email, user.name, hashed_password, stripe_customer_id))
    db.commit()
    if user.email:
        background_tasks.add_task(send_confirmation_email, user.email, user.username)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"message": "User created successfully"})

@backend_app.post("/api/log-activity")
async def log_activity(activity: ActivityLogRequest, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    details_json = json.dumps(activity.details) if activity.details else None
    db.execute("INSERT INTO activity_log (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
               (user_id, activity.action, details_json, datetime.now()))
    db.commit()
    return {"status": "ok"}

@backend_app.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    user = get_user_by_email(db, request.email)
    if user:
        reset_token_expires = timedelta(minutes=15)
        reset_token = create_access_token(
            data={"sub": user.username, "scope": "password_reset"},
            expires_delta=reset_token_expires
        )
        background_tasks.add_task(send_password_reset_email, user.email, user.username, reset_token)
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@backend_app.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: sqlite3.Connection = Depends(get_db)):
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != "password_reset":
            raise HTTPException(status_code=401, detail="Invalid token scope")
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    hashed_password = get_password_hash(request.new_password)
    db.execute("UPDATE users SET hashed_password = ? WHERE username = ?", (hashed_password, username))
    db.commit()
    return {"message": "Password has been reset successfully."}

@backend_app.get("/api/admin/activity-log", response_model=List[ActivityLogEntry])
async def get_activity_log(admin_user: dict = Depends(get_current_admin_user), db: sqlite3.Connection = Depends(get_db)):
    """Admin-only endpoint to fetch the activity log."""
    query = """
        SELECT u.username, a.action, a.details, a.timestamp
        FROM activity_log a JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
    """
    log_entries = db.execute(query).fetchall()
    return [dict(row) for row in log_entries]

@backend_app.get("/api/fees/{city}", response_model=Optional[ParkingFee])
async def get_parking_fee(city: str, street: str, db: sqlite3.Connection = Depends(get_db)):
    """Endpoint to get parking fee information for a specific street."""
    query = "SELECT * FROM parking_fees WHERE city = ? AND street_name LIKE ?"
    fee_data = db.execute(query, (city.lower(), f"%{street}%")).fetchone()
    if fee_data:
        return dict(fee_data)
    return None

@backend_app.get("/api/parking/{city}")
def get_parking(city: str, background_tasks: BackgroundTasks):
    try:
        return load_data(city, background_tasks)
    except Exception as e:
        logger.error(f"API error for /api/parking/{city}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@backend_app.get("/api/path/{city}/{lat}/{lng}")
def get_path(city: str, lat: float, lng: float, background_tasks: BackgroundTasks, top: int = 5):
    spots = load_data(city, background_tasks)
    available_spots = [s for s in spots if not s.get('occupied')]
    if not available_spots:
        return {"nearest": {}, "alternatives": []}
    
    current = (lat, lng)
    sorted_spots = sorted(available_spots, key=lambda x: geodesic(current, (x['lat'], x['lng'])).km)
    top_spots = sorted_spots[:top]
    
    for spot in top_spots:
        try:
            route_data = get_route_with_fallback(current[0], current[1], spot['lat'], spot['lng'], steps=False)
            spot['route'] = route_data['geometry']
        except Exception as e:
            logger.warning(f"Could not calculate route for spot {spot.get('name')}: {e}")
            spot['route'] = []

    return {"nearest": top_spots[0] if top_spots else {}, "alternatives": top_spots[1:]}

@backend_app.get("/api/route")
def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, steps: bool = False):
    try:
        return get_route_with_fallback(start_lat, start_lon, end_lat, end_lon, steps=steps)
    except (requests.RequestException, ValueError) as e:
         logger.error(f"All routing services failed: {e}")
         raise HTTPException(status_code=503, detail=f"All routing services are unavailable or failed: {e}")

@backend_app.post("/book-parking/{spot_id}")
async def book_parking(spot_id: str, booking_request: BookingRequest, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    try:
        intent = stripe.PaymentIntent.create(
            amount=250,  # Amount in cents ($2.50)
            currency="aud",
            payment_method=booking_request.payment_method_id,
            description=f"Parking for spot {spot_id} by user {current_user['id']}",
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"}
        )

        db.execute("INSERT INTO bookings (user_id, spot_id, booking_time, amount, status) VALUES (?, ?, ?, ?, ?)",
                   (current_user['id'], spot_id, datetime.now(), intent.amount, intent.status))
        db.commit()
        return {"message": "Booking successful!", "payment_intent_id": intent.id, "status": intent.status}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Booking error for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@backend_app.post("/create-payment-intent")
async def create_payment_intent(request: PaymentIntentRequest, current_user: dict = Depends(get_current_user)):
    customer_id = current_user.get("stripe_customer_id")
    if not customer_id:
        # This case should be rare if customers are created at registration.
        raise HTTPException(status_code=404, detail="Stripe customer profile not found for this user.")

    try:
        intent = stripe.PaymentIntent.create(
            amount=request.amount,
            currency="aud",
            customer=customer_id,
            setup_future_usage='on_session',
            automatic_payment_methods={"enabled": True},
            description=f"Booking for spot {request.spot_id} by user {current_user['id']}",
            metadata={'spot_id': request.spot_id, 'user_id': current_user['id']}
        )
        return {"clientSecret": intent.client_secret}
    except Exception as e:
        logger.error(f"Could not create PaymentIntent: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@backend_app.get("/payment-success", response_class=HTMLResponse)
async def payment_success(spot_id: str):
    # This is a simple success page. In a real app, you'd confirm the payment status
    # with Stripe webhooks before showing this.
    return f"""
    <html>
        <head><title>Payment Successful</title></head>
        <body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>
            <h1>✅ Payment Successful!</h1>
            <p>Your booking for spot <strong>{spot_id}</strong> is confirmed.</p>
            <p><a href="http://localhost:8501?payment_success=true&spot_id={spot_id}">Return to the app</a></p>
        </body>
    </html>
    """

@backend_app.get("/api/my-bookings", response_model=List[Booking])
async def get_my_bookings(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    bookings = db.execute("SELECT * FROM bookings WHERE user_id = ?", (current_user['id'],)).fetchall()
    return [dict(row) for row in bookings]

@backend_app.get("/api/me", response_model=User)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@backend_app.post("/api/me/update")
async def update_user_profile(user_update: UserUpdate, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    fields_to_update = user_update.dict(exclude_unset=True)
    
    if not fields_to_update:
        raise HTTPException(status_code=400, detail="No fields to update.")

    set_clause = ", ".join([f"{key} = ?" for key in fields_to_update.keys()])
    values = list(fields_to_update.values()) + [user_id]
    
    db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", tuple(values))
    db.commit()
    return {"message": "Profile updated successfully."}

@backend_app.post("/donate")
async def make_donation(donation_request: DonationRequest, token: Optional[str] = Depends(oauth2_scheme_optional), db: sqlite3.Connection = Depends(get_db)):
    if donation_request.amount < 100: # Minimum donation of $1.00
        raise HTTPException(status_code=400, detail="Donation amount must be at least $1.00.")

    description = "Anonymous donation"
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username and (user := get_user(db, username=username)):
                description = f"Donation from user {user.username} (ID: {user.id})"
        except JWTError:
            pass # Token is invalid, proceed as anonymous

    try:
        intent = stripe.PaymentIntent.create(
            amount=donation_request.amount,
            currency="aud",
            payment_method=donation_request.payment_method_id,
            description=description,
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"}
        )
        return {"message": "Thank you for your generous donation!", "payment_intent_id": intent.id, "status": intent.status}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Donation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during donation.")

@backend_app.post("/api/vehicles", response_model=Vehicle)
async def add_vehicle(vehicle: VehicleCreate, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    cursor = db.cursor()
    cursor.execute("INSERT INTO vehicles (user_id, nickname, make, model, license_plate) VALUES (?, ?, ?, ?, ?)",
                   (user_id, vehicle.nickname, vehicle.make, vehicle.model, vehicle.license_plate))
    db.commit()
    new_vehicle_id = cursor.lastrowid
    new_vehicle = db.execute("SELECT * FROM vehicles WHERE id = ?", (new_vehicle_id,)).fetchone()
    return dict(new_vehicle)

@backend_app.get("/api/vehicles", response_model=List[Vehicle])
async def get_vehicles(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    vehicles = db.execute("SELECT * FROM vehicles WHERE user_id = ?", (user_id,)).fetchall()
    return [dict(row) for row in vehicles]

@backend_app.post("/api/favorites/{spot_id}", response_model=FavoriteSpot)
async def add_favorite(spot_id: str, favorite: FavoriteSpotCreate, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    try:
        cursor = db.cursor()
        cursor.execute("INSERT INTO favorite_spots (user_id, spot_id, nickname, added_on) VALUES (?, ?, ?, ?)",
                       (user_id, spot_id, favorite.nickname, datetime.now()))
        db.commit()
        new_fav = db.execute("SELECT * FROM favorite_spots WHERE user_id = ? AND spot_id = ?", (user_id, spot_id)).fetchone()
        return dict(new_fav)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Spot is already in favorites.")

@backend_app.get("/api/favorites", response_model=List[FavoriteSpot])
async def get_favorites(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    favorites = db.execute("SELECT * FROM favorite_spots WHERE user_id = ?", (user_id,)).fetchall()
    return [dict(row) for row in favorites]

@backend_app.delete("/api/favorites/{spot_id}")
async def delete_favorite(spot_id: str, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    db.execute("DELETE FROM favorite_spots WHERE user_id = ? AND spot_id = ?", (user_id, spot_id))
    db.commit()
    return {"message": "Favorite spot removed successfully."}

@backend_app.post("/api/payment-methods/setup")
async def create_setup_intent(current_user: dict = Depends(get_current_user)):
    """Creates a SetupIntent to save a new payment method."""
    customer_id = current_user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="Stripe customer profile not found for this user.")
    try:
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
        )
        return {"clientSecret": setup_intent.client_secret}
    except Exception as e:
        logger.error(f"Could not create SetupIntent for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@backend_app.get("/api/payment-methods", response_model=List[PaymentMethod])
async def list_payment_methods(current_user: dict = Depends(get_current_user)):
    """Lists saved payment methods for the current user."""
    customer_id = current_user.get("stripe_customer_id")
    if not customer_id:
        return []
    try:
        payment_methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
        default_pm = stripe.Customer.retrieve(customer_id).invoice_settings.default_payment_method
        
        cards = []
        for pm in payment_methods.data:
            cards.append(PaymentMethod(id=pm.id, brand=pm.card.brand, last4=pm.card.last4, exp_month=pm.card.exp_month, exp_year=pm.card.exp_year, is_default=(pm.id == default_pm)))
        return cards
    except Exception as e:
        logger.error(f"Could not list payment methods for customer {customer_id}: {e}")
        return []

@backend_app.delete("/api/payment-methods/{pm_id}")
async def delete_payment_method(pm_id: str, current_user: dict = Depends(get_current_user)):
    stripe.PaymentMethod.detach(pm_id)
    return {"message": "Payment method removed successfully."}

@backend_app.get("/api/cache-status/{city}")
def get_cache_status(city: str):
    """Endpoint for the frontend to poll the data loading status."""
    return {"city": city, "status": cache_status.get(city.lower(), "none")}

@backend_app.get("/config")
def get_config():
    return {"publishableKey": os.getenv("STRIPE_PUBLISHABLE_KEY")}

@backend_app.get("/payment.html", response_class=HTMLResponse)
async def get_payment_page():
    payment_html_path = os.path.join(BASE_DIR, "payment.html")
    try:
        with open(payment_html_path, "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="payment.html not found")

@backend_app.get("/add_card.html", response_class=HTMLResponse)
async def get_add_card_page():
    add_card_html_path = os.path.join(BASE_DIR, "add_card.html")
    try:
        with open(add_card_html_path, "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="add_card.html not found")


# ==============================================================================
# --- 2. FRONTEND (Streamlit) CODE ---
# ==============================================================================

# --- Constants ---
CITY_CENTERS = {
    "brisbane": [-27.4698, 153.0251],
    "sydney": [-33.8688, 151.2093],
    "melbourne": [-37.8136, 144.9631]
}
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def run_frontend():
    """
    This function contains the entire Streamlit frontend application.
    """
    import folium
    from streamlit_folium import st_folium

    st.set_page_config(layout="wide")

    def init_session_state():
        """Initialize session state variables."""
        defaults = {
            'token': None,
            'user': None,
            'spots': [],
            'path_data': None,
            'selected_spot': None,
            'viewing_bookings': False,
            'dark_theme': True,
            'viewing_settings': False,
            'navigation_active': False,
            'profile_page': 'menu', # 'menu', 'profile', 'vehicles', 'add_vehicle', 'favorites', 'payment', 'help', 'settings'
            'viewing_admin': False,
            'location_set_by_user': False,
            'selected_city': 'melbourne',
            'current_lat': CITY_CENTERS["melbourne"][0],
            'current_lng': CITY_CENTERS["melbourne"][1],
            'dest_lat': None,
            'dest_lng': None,
            'leg1_route': None,
            'leg2_route': None,
            'leg2_steps': None,
            'leg2_summary': None,
            'direct_route': None,
            'stripe_pk': None,
            'first_login_refresh_done': False,
        } 
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    init_session_state()

    # Check for payment success in URL
    query_params = st.query_params
    if "payment_success" in query_params and "spot_id" in query_params:
        spot_id = query_params["spot_id"]
        st.success(f"✅ Payment successful! Your booking for spot {spot_id} is confirmed.")
        st.query_params.clear()
    
    if "card_saved" in query_params:
        st.success("✅ Your new payment method has been saved successfully!")
        st.session_state.profile_page = 'payment' # Navigate to the payment methods page
        st.query_params.clear()

    # Check for password reset token in URL
    if "reset_token" in query_params:
        st.session_state.show_reset_password_form = True
        st.session_state.reset_token = query_params["reset_token"]
        st.query_params.clear()

    # --- API & Data Helper Functions ---
    def api_request(
        method: Literal["GET", "POST", "DELETE"],
        path: str,
        **kwargs: Any
    ) -> Optional[requests.Response]:
        """A small wrapper for API requests with error handling."""
        try:
            kwargs.setdefault('timeout', 60)
            url = f"{API_BASE_URL}{path}"
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            st.error(f"API Error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Connection Error: Could not connect to the backend. Is the server running?")
        except requests.exceptions.RequestException as e:
            st.error(f"An unexpected error occurred: {e}")
        return None

    def handle_set_destination():
        destination_address = st.session_state.get("dest_address_input")
        if destination_address:
            with st.spinner("Geocoding..."):
                geolocator = Nominatim(user_agent="parking_finder")
                location = geolocator.geocode(destination_address)
                if location:
                    st.session_state.dest_lat, st.session_state.dest_lng = location.latitude, location.longitude
                    st.session_state.destination_address_str = location.address
                    st.success(f"Destination set to: {location.address}. Click 'Find Spots' to continue.")
                    st.rerun()
                else:
                    st.error("Could not find the destination.")
        else: st.warning("Please enter a destination address.")

    @st.cache_data(ttl=3600) # Cache for 1 hour
    def get_address_from_coords(lat: float, lon: float) -> str:
        """Reverse geocode coordinates to get an address."""
        try:
            geolocator = Nominatim(user_agent="parking_finder_app")
            location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
            return location.address if location else "Unknown Location"
        except Exception:
            return f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    def render_loading_screen(message: str):
        """Displays a full-screen Lottie animation and a loading message."""
        try:
            with open("loading_animation.json", "r") as f:
                lottie_json = json.load(f)
                st_lottie(lottie_json, speed=1, height=200, key="loading_animation_file")
        except (FileNotFoundError, json.JSONDecodeError):
            st.warning("Could not load animation file.")
        
        st.markdown(f"<h3 style='text-align: center;'>{message}</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>This may take a moment on the first load...</p>", unsafe_allow_html=True)

    # --- UI Rendering Functions ---
    def render_navigation_view():
        st.header("Navigation")
        if st.button("Exit Navigation", key="exit_nav_btn", use_container_width=True):
            st.session_state.navigation_active = False
            st.session_state.leg1_route = None
            st.session_state.leg2_route = None
            st.session_state.leg2_steps = None
            st.session_state.leg2_summary = None
            st.session_state.direct_route = None
            st.rerun()
        
        st.subheader("Parking to Destination")
        if st.session_state.leg2_summary:
            summary = st.session_state.leg2_summary
            distance_km = summary['total_distance_meters'] / 1000
            duration_min = summary['total_duration_seconds'] / 60
            st.metric("Total Distance", f"{distance_km:.2f} km")
            st.metric("Estimated Time", f"{duration_min:.1f} minutes")

        if st.session_state.leg2_steps:
            with st.expander("Show Turn-by-Turn Directions"):
                for i, step in enumerate(st.session_state.leg2_steps):
                    st.write(f"{i+1}. {step['instruction']} ({step['distance_meters']:.0f} m)")

    def render_bookings_view():
        st.header("My Bookings")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}    
        response = api_request("GET", "/api/my-bookings", headers=headers, timeout=10)
        if response and response.status_code == 200:
            bookings = response.json()
            if bookings:
                for booking in sorted(bookings, key=lambda x: x['booking_time'], reverse=True):
                    booking_time = datetime.fromisoformat(booking['booking_time']).strftime('%Y-%m-%d %H:%M')
                    with st.expander(f"Spot: {booking['spot_id']} on {booking_time}"):
                        st.write(f"**Booking ID:** {booking['id']}")
                        st.write(f"**Amount Paid:** ${booking['amount']/100:.2f}")
                        st.write(f"**Status:** {booking['status']}")
            else:
                st.info("You have no past bookings.")

        if st.button("⬅️ Back to Map Controls", key="exit_bookings_btn", use_container_width=True):
            st.session_state.viewing_bookings = False
            st.rerun()

    def render_vehicles_view():
        st.subheader("My Vehicles")
        
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/vehicles", headers=headers)

        if response and response.status_code == 200:
            vehicles = response.json()
            if vehicles:
                for v in vehicles:
                    with st.container(border=True):
                        st.write(f"**{v['nickname']}**")
                        st.write(f"{v.get('make', '')} {v.get('model', '')}")
                        st.code(v['license_plate'])
            else:
                st.info("You haven't added any vehicles yet.")
        
        if st.button("＋ Add New Vehicle", use_container_width=True):
            st.session_state.profile_page = 'add_vehicle'
            st.rerun()

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_add_vehicle_view():
        st.subheader("Add a New Vehicle")
        with st.form("add_vehicle_form"):
            nickname = st.text_input("Nickname (e.g., 'My Honda')")
            license_plate = st.text_input("License Plate")
            make = st.text_input("Make (Optional)")
            model = st.text_input("Model (Optional)")
            
            submitted = st.form_submit_button("Save Vehicle")
            if submitted:
                if not nickname or not license_plate:
                    st.error("Nickname and License Plate are required.")
                else:
                    payload = {"nickname": nickname, "license_plate": license_plate, "make": make, "model": model}
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    response = api_request("POST", "/api/vehicles", headers=headers, json=payload)
                    if response and response.status_code == 200:
                        st.success("Vehicle added!")
                        st.session_state.profile_page = 'vehicles'
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to add vehicle.")

        if st.button("⬅️ Back to My Vehicles", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'vehicles'
            st.rerun()

    def render_favorites_view():
        st.subheader("❤️ My Favorite Spots")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/favorites", headers=headers)

        if response and response.status_code == 200:
            favorites = response.json()
            if favorites:
                for fav in sorted(favorites, key=lambda x: x['added_on'], reverse=True):
                    spot_id = fav['spot_id']
                    nickname = fav.get('nickname') or f"Spot {spot_id}"
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{nickname}**")
                            st.caption(f"Spot ID: {spot_id}")
                        with col2:
                            if st.button("❌", key=f"del_fav_{spot_id}", help="Remove from favorites"):
                                del_resp = api_request("DELETE", f"/api/favorites/{spot_id}", headers=headers)
                                if del_resp and del_resp.status_code == 200:
                                    st.success("Favorite removed.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to remove favorite.")
            else:
                st.info("You haven't added any favorite spots yet. Select a spot on the map to add it!")

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_payment_methods_view():
        st.subheader("💳 My Payment Methods")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/payment-methods", headers=headers)

        if response and response.status_code == 200:
            payment_methods = response.json()
            if payment_methods:
                for pm in payment_methods:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{pm['brand'].title()}** ending in **** {pm['last4']}")
                            st.caption(f"Expires {pm['exp_month']}/{pm['exp_year']}")
                        with col2:
                            if st.button("Delete", key=f"del_pm_{pm['id']}", type="secondary"):
                                del_resp = api_request("DELETE", f"/api/payment-methods/{pm['id']}", headers=headers)
                                if del_resp and del_resp.status_code == 200:
                                    st.success("Payment method removed.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to remove payment method.")
            else:
                st.info("You have no saved payment methods.")

        if not st.session_state.stripe_pk:
            pk_response = api_request("GET", "/config")
            if pk_response and pk_response.status_code == 200 and pk_response.json().get("publishableKey"):
                st.session_state.stripe_pk = pk_response.json().get("publishableKey")

        if st.session_state.stripe_pk:
            add_card_url = f"http://localhost:8000/add_card.html?token={st.session_state.token}&pk={st.session_state.stripe_pk}"
            st.link_button("＋ Add New Card", url=add_card_url, use_container_width=True)
        else:
            st.error("Payment gateway is not configured. Cannot add new cards.")

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_profile_update_view():
        st.subheader("Update Profile")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        user_resp = api_request("GET", "/api/me", headers=headers)
        
        if user_resp and user_resp.status_code == 200:
            user_data = user_resp.json()
            
            with st.form("profile_form"):
                st.write(f"**Username:** {user_data.get('username')}")
                email = st.text_input("Email", value=user_data.get('email', ''))
                name = st.text_input("Name", value=user_data.get('name', ''))
                
                submitted = st.form_submit_button("Update Profile")
                if submitted:
                    update_payload = {"email": email, "name": name}
                    update_resp = api_request("POST", "/api/me/update", headers=headers, json=update_payload)
                    if update_resp and update_resp.status_code == 200:
                        st.success("Profile updated successfully!")
                        time.sleep(1)
                        st.session_state.profile_page = 'menu'
                        st.rerun()
                    else:
                        st.error("Failed to update profile.")
        
        if st.button("⬅️ Back to Profile Menu", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_settings_view():
        st.header("Profile")

        # Main Profile Menu
        if st.session_state.profile_page == 'menu':
            if st.button("👤 Edit Profile", use_container_width=True):
                st.session_state.profile_page = 'profile'
                st.rerun()
            if st.button("🚗 My Vehicles", use_container_width=True):
                st.session_state.profile_page = 'vehicles'
                st.rerun()
            if st.button("❤️ My Favorites", use_container_width=True):
                st.session_state.profile_page = 'favorites'
                st.rerun()
            if st.button("💳 Payment Methods", use_container_width=True):
                st.session_state.profile_page = 'payment'
                st.rerun()
            if st.button("❓ Help Center", use_container_width=True):
                st.info("Help Center is coming soon!")
            
            st.markdown("---")
            st.subheader("Settings")
            st.selectbox("Language", ["English", "Spanish (coming soon)"], disabled=True)
            st.toggle("Push Notifications", disabled=True)
            st.toggle("Email Notifications", disabled=True)
            st.toggle("Dark Mode", key="dark_theme")
            st.markdown("---")

            if st.button("Logout", key="logout_btn_settings", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        # "Edit Profile" Sub-page
        elif st.session_state.profile_page == 'profile':
            render_profile_update_view()

        # "My Vehicles" Sub-page
        elif st.session_state.profile_page == 'vehicles':
            render_vehicles_view()

        # "Add Vehicle" Sub-page
        elif st.session_state.profile_page == 'add_vehicle':
            render_add_vehicle_view()
        
        # "My Favorites" Sub-page
        elif st.session_state.profile_page == 'favorites':
            render_favorites_view()
        
        # "Payment Methods" Sub-page
        elif st.session_state.profile_page == 'payment':
            render_payment_methods_view()


    def render_admin_view():
        """Renders the admin dashboard to view user activity."""
        st.header("👑 Admin Dashboard")
        st.subheader("User Activity Log")

        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/admin/activity-log", headers=headers)

        if response and response.status_code == 200:
            activities = response.json()
            if activities:
                df = pandas.DataFrame(activities)
                df['timestamp'] = pandas.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No user activity has been logged yet.")
        elif response and response.status_code == 403:
            st.error("You do not have permission to view this page.")
        else:
            st.error("Failed to load activity log.")

        if st.button("⬅️ Back to Map", key="exit_admin_btn", use_container_width=True):
            st.session_state.viewing_admin = False
            st.rerun()

    def handle_find_spots(top_n):
        """Logic for the 'Find Spots' button, refactored for clarity."""
        if not st.session_state.dest_lat:
            st.warning("Please set a destination first using 'Set Destination'.")
            return

        with st.spinner("Finding nearest spots and calculating routes..."):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            api_request("POST", "/api/log-activity", headers=headers, json={"action": "find_spots", "details": {"destination_lat": st.session_state.dest_lat, "destination_lng": st.session_state.dest_lng, "top_n": top_n}})

            start_loc = (st.session_state.current_lat, st.session_state.current_lng)
            dest_loc = (st.session_state.dest_lat, st.session_state.dest_lng)
            
            params = {"start_lat": start_loc[0], "start_lon": start_loc[1], "end_lat": dest_loc[0], "end_lon": dest_loc[1], "steps": "false"}
            response = api_request("GET", "/api/route", params=params)
            if response and response.status_code == 200:
                st.session_state.direct_route = response.json().get('geometry')
            else:
                st.warning("Could not calculate direct route to destination.")
            
            target_lat = st.session_state.dest_lat
            target_lng = st.session_state.dest_lng
            response = api_request("GET", f"/api/path/{st.session_state.selected_city}/{target_lat}/{target_lng}", params={'top': top_n})
            if response and response.status_code == 200:
                st.session_state.path_data = response.json()
                st.info("Found nearest spots. Map is now showing results.")
            
            st.session_state.navigation_active = False
            st.session_state.leg1_route = None
            st.session_state.leg2_route = None
            st.session_state.leg2_steps = None
            st.session_state.leg2_summary = None
            st.rerun()

    # --- Main Application Logic ---
    if st.session_state.get('show_reset_password_form', False):
        st.title("Reset Your Password")
        reset_cols = st.columns([1, 2, 1])
        with reset_cols[1]:
            with st.form("reset_password_form"):
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                submitted = st.form_submit_button("Reset Password")

                if submitted:
                    if not new_password or new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        token = st.session_state.get("reset_token")
                        if not token:
                            st.error("Reset token is missing. Please request a new link.")
                        else:
                            response = api_request(
                                "POST",
                                "/reset-password",
                                json={"token": token, "new_password": new_password}
                            )
                            if response and response.status_code == 200:
                                st.success("Password reset successfully! You can now log in with your new password.")
                                st.session_state.show_reset_password_form = False
                                st.session_state.reset_token = None
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Password reset failed. The link may have expired or is invalid.")

    elif 'token' not in st.session_state or st.session_state.token is None:
        st.title("Express Parking Australia")
        st.info("Please log in or register to access parking features. The map below is for demonstration only.")
        
        main_cols = st.columns([1, 2])
        with main_cols[0]:
            logo_cols = st.columns([1, 2, 1])
            with logo_cols[1]:
                st.image("symball.jpeg", width=150)

            st.header("Welcome")
            tab1, tab2 = st.tabs(["Login", "Register"])
            with tab1:
                with st.form("login_form"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Login")
                    if submitted:
                        response = api_request("POST", "/token", data={"username": username, "password": password})
                        if response and response.status_code == 200:
                            st.session_state.token = response.json()["access_token"]
                            st.session_state.user = username
                            headers = {"Authorization": f"Bearer {st.session_state.token}"}
                            api_request("POST", "/api/log-activity", headers=headers, json={"action": "login"})
                            st.session_state.first_login_refresh_done = False
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
            
            if st.button("Forgot Password?"):
                st.session_state.show_forgot_password = True

            if st.session_state.get('show_forgot_password'):
                with st.form("forgot_password_form"):
                    st.subheader("Request Password Reset")
                    email = st.text_input("Enter your account email")
                    submitted = st.form_submit_button("Send Reset Link")
                    if submitted:
                        response = api_request("POST", "/forgot-password", json={"email": email})
                        if response:
                            st.success("If an account with that email exists, a password reset link has been sent.")
                            st.session_state.show_forgot_password = False
            
            with tab2:
                with st.form("register_form"):
                    reg_username = st.text_input("Choose Username")
                    reg_name = st.text_input("Full Name")
                    reg_email = st.text_input("Email")
                    reg_password = st.text_input("Choose Password", type="password")
                    reg_submitted = st.form_submit_button("Register")
                    if reg_submitted:
                        response = api_request("POST", "/register", json={"username": reg_username, "name": reg_name, "password": reg_password, "email": reg_email})
                        if response and response.status_code == 201:
                            st.success("Registration successful! Please log in.")
                        else:
                            error_detail = response.json().get('detail', 'Unknown error') if response else 'Server Error'
                            if "Username already registered" in error_detail:
                                st.error("Username already exists. Please choose another one.")
                            elif "Email already in use" in error_detail:
                                st.error("This email is already in use. Please use a different email.")
                            else:
                                st.error(f"Registration failed: {error_detail}")
        
        with main_cols[1]:
            m = folium.Map(location=CITY_CENTERS["melbourne"], zoom_start=12, tiles="cartodbdark_matter" if st.session_state.dark_theme else "cartodbpositron", zoom_control=False)
            st_folium(m, width='100%', height=600)

    else:
        # --- LOGGED-IN STATE ---
        # If it's the first time after login or spots are empty, trigger the data load and poll for completion.
        if not st.session_state.get('first_login_refresh_done', False):
            # This call triggers the backend to start caching data in the background
            api_request("GET", f"/api/parking/{st.session_state.selected_city}")

            with st.spinner(f"Finding parking spots in {st.session_state.selected_city.title()}... This may take a moment."):
                max_wait_time = 120  # Wait for up to 2 minutes
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    status_resp = api_request("GET", f"/api/cache-status/{st.session_state.selected_city}", timeout=5)
                    if status_resp and status_resp.json().get("status") == "ready":
                        break
                    time.sleep(2) # Poll every 2 seconds

            final_response = api_request("GET", f"/api/parking/{st.session_state.selected_city}")
            if final_response and final_response.status_code == 200:
                st.session_state.spots = final_response.json()
            else:
                st.error("Failed to retrieve data from the server after loading.")
            
            st.session_state.first_login_refresh_done = True
            st.rerun()

        with st.container():
            top_bar_cols = st.columns([1, 4, 1, 1, 1, 1])

            with top_bar_cols[0]:
                cities = list(CITY_CENTERS.keys())
                try:
                    default_index = cities.index(st.session_state.selected_city)
                except ValueError:
                    default_index = cities.index('melbourne') 
                st.selectbox("City", cities, index=default_index, key='selected_city', label_visibility="collapsed")

            selected_city_coords = CITY_CENTERS[st.session_state.selected_city]
            if not st.session_state.location_set_by_user:
                if (st.session_state.current_lat != selected_city_coords[0] or 
                    st.session_state.current_lng != selected_city_coords[1]):
                    st.session_state.current_lat = selected_city_coords[0]
                    st.session_state.current_lng = selected_city_coords[1]
                    st.rerun()
            
            with top_bar_cols[1]:
                if not st.session_state.dest_lat:
                    destination_address = st.text_input("Enter Destination Address", placeholder="Search for destination or spot address", label_visibility="collapsed", key="dest_address_input")
                else:
                    # Show the set destination address, but disable input
                    st.text_input("Destination", value=st.session_state.get('destination_address_str', 'Destination Set'), label_visibility="collapsed", disabled=True)
            
            with top_bar_cols[2]:
                if not st.session_state.dest_lat:
                    if st.button("Set Destination", key="set_dest_btn", use_container_width=True):
                        handle_set_destination()
                else:
                    btn_cols = st.columns(2)
                    if btn_cols[0].button("Change", use_container_width=True, help="Change Destination"):
                        st.session_state.dest_lat = None
                        st.session_state.dest_lng = None
                        st.rerun()
                    if btn_cols[1].button("Clear", use_container_width=True, help="Clear Destination"):
                        st.session_state.dest_lat = None
                        st.session_state.dest_lng = None
                        st.session_state.path_data = None
                        st.session_state.direct_route = None
                        st.rerun()
            
            with top_bar_cols[3]:
                if st.button(f"Find Spots", key="find_spots_btn", use_container_width=True, disabled=not st.session_state.dest_lat):
                    handle_find_spots(3) # Using a fixed value of 3 for simplicity

            with top_bar_cols[4]:
                if st.button(f"Refresh Data", key="refresh_data_btn", use_container_width=True):
                    with st.spinner(f"Fetching data for {st.session_state.selected_city.title()}..."):
                        st.session_state.path_data = None
                        st.session_state.selected_spot = None
                        st.session_state.dest_lat = None
                        st.session_state.dest_lng = None
                        st.session_state.direct_route = None
                        response = api_request("GET", f"/api/parking/{st.session_state.selected_city}", timeout=120)
                        if response and response.status_code == 200:
                            st.session_state.spots = response.json()
                            st.success(f"Found {len(st.session_state.spots)} spots.")
            
            with top_bar_cols[5]:
                menu_cols = st.columns(5)
                with menu_cols[0]:
                    if st.button("📖", key="view_bookings_btn", help="View My Bookings", use_container_width=True):
                        st.session_state.viewing_bookings = True
                        st.session_state.viewing_settings = False
                        st.session_state.viewing_admin = False
                        st.rerun()
                with menu_cols[1]:
                    if st.button("👑", key="view_admin_btn", help="Admin Dashboard", use_container_width=True):
                        st.session_state.viewing_admin = True
                        st.session_state.viewing_bookings = False
                        st.session_state.viewing_settings = False
                        st.rerun()
                with menu_cols[2]:
                    if st.session_state.viewing_settings:
                        if st.button("✕", help="Close Menu", use_container_width=True):
                            st.session_state.viewing_settings = False
                            st.rerun()
                    else:
                        if st.button("☰", help="Profile & Settings", use_container_width=True):
                            st.session_state.viewing_settings = True
                            st.rerun()
                with menu_cols[3]:
                    if st.button("⌖", key="recenter_btn", help="Recenter on your location", use_container_width=True):
                        st.session_state.recenter_map = True
                        st.rerun()


        map_target = st.container()

        if st.session_state.navigation_active:
            nav_cols = st.columns([3, 1])
            with nav_cols[1]:
                render_navigation_view()
            map_target = nav_cols[0]
        
        elif st.session_state.viewing_bookings:
            book_cols = st.columns([3, 1])
            with book_cols[1]:
                render_bookings_view()
            map_target = book_cols[0]

        elif st.session_state.viewing_settings:
            settings_cols = st.columns([3, 1])
            with settings_cols[1]:
                render_settings_view() # This function now handles its own sub-pages
            map_target = settings_cols[0]
        
        elif st.session_state.viewing_admin:
            admin_cols = st.columns([3, 1])
            with admin_cols[1]:
                render_admin_view()
            map_target = admin_cols[0]

        with map_target:
            if not st.session_state.get('location_set_by_user', False):
                st.warning("Please click your starting location on the map to enable route finding.")
            else:
                with st.spinner("Fetching address..."):
                    address = get_address_from_coords(st.session_state.current_lat, st.session_state.current_lng)
                    st.success(f"Start Location: {address}")

            if st.session_state.spots:
                total_spots = len(st.session_state.spots)
                occupied_spots = len([s for s in st.session_state.spots if s.get('occupied')])
                available_spots = total_spots - occupied_spots 

                if total_spots > 0:
                    # Calculate percentages
                    # available_percent = available_spots / total_spots
                    
                    # Display stats in columns
                    st.markdown(f"""
                    <div style="display: flex; gap: 20px; align-items: center; justify-content: flex-start; height: 100%; padding-bottom: 10px;">
                        <span title="Available"><span style="color: #28a745;">●</span> Available: {available_spots}</span>
                        <span title="Occupied"><span style="color: #dc3545;">●</span> Occupied: {occupied_spots}</span>
                        <span title="Total Spots"><strong>Σ</strong> Total: {total_spots}</span>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---",)

            map_center = CITY_CENTERS.get(st.session_state.selected_city, CITY_CENTERS["melbourne"])
            m = folium.Map(location=map_center, zoom_start=14, tiles="cartodbdark_matter" if st.session_state.dark_theme else "cartodbpositron")
            from folium.plugins import Fullscreen
            Fullscreen().add_to(m)
            folium.LayerControl().add_to(m)
            
            bounds = []
            if st.session_state.path_data and not st.session_state.navigation_active:
                nearest_spot = st.session_state.path_data.get('nearest', {})
                if nearest_spot and nearest_spot.get('route'):
                    route_line = folium.PolyLine(nearest_spot['route'], color="blue", weight=5, opacity=0.8, tooltip="Route to nearest spot")
                    route_line.add_to(m)
                    bounds.extend(route_line.get_bounds())

            if st.session_state.direct_route:
                direct_line = folium.PolyLine(st.session_state.direct_route, color="green", weight=5, opacity=0.7, dash_array='10, 5', tooltip="Direct Route to Destination")
                direct_line.add_to(m)
                bounds.extend(direct_line.get_bounds())

            if st.session_state.navigation_active:
                if st.session_state.leg1_route:
                    leg1_line = folium.PolyLine(st.session_state.leg1_route, color="blue", weight=7, opacity=0.8, tooltip="Leg 1: To Parking")
                    leg1_line.add_to(m)
                    bounds.extend(leg1_line.get_bounds())
                
                if st.session_state.leg2_route:
                    leg2_line = folium.PolyLine(st.session_state.leg2_route, color="red", weight=7, opacity=0.8, tooltip="Leg 2: To Destination")
                    leg2_line.add_to(m)
                    bounds.extend(leg2_line.get_bounds())
            
            spots_to_display = []
            if st.session_state.path_data:
                nearest = st.session_state.path_data.get('nearest')
                if nearest: spots_to_display.append(nearest)
                spots_to_display.extend(st.session_state.path_data.get('alternatives', []))
            elif st.session_state.spots:
                spots_to_display = st.session_state.spots
            
            now_melbourne = datetime.now(ZoneInfo("Australia/Melbourne"))
            weekday = now_melbourne.weekday()
            hour = now_melbourne.hour

            current_fee = 2.00 # Default/fallback fee
            fee_type = "Off-Peak"
            if weekday < 5:
                if 7 <= hour < 19:
                    current_fee = 4.00
                    fee_type = "Peak"
            else:
                fee_type = "Weekend"

            for spot in spots_to_display:
                is_occupied = spot.get('occupied', False)
                color = "red" if is_occupied else "green"
                last_updated_str = spot.get('last_updated', 'N/A')
                if 'Z' in last_updated_str: last_updated_str = last_updated_str.replace('Z', '+00:00')
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated_str).strftime('%d %b, %I:%M %p')
                except (ValueError, TypeError):
                    last_updated_dt = "N/A"
                
                # Only perform reverse geocoding if we have a small, filtered list of spots.
                if st.session_state.path_data:
                    address = get_address_from_coords(spot.get('lat'), spot.get('lng'))
                else:
                    address = spot.get('street', 'N/A')

                kerbside_id = spot.get('kerbsideid')
                zone_number = spot.get('zone_number')
                #  print(spot)
                #  print(kerbside_id, zone_number)
                popup_html = f"""
                <div style="font-family: sans-serif; font-size: 14px;">
                    <b>Spot ID: {spot.get('name', 'N/A')}</b><br>
                    <b>Kerbside: {kerbside_id or 'N/A'}</b><br>
                    <b>Zone: {zone_number or 'N/A'}</b><br>
                    <b>Status: {'Occupied' if is_occupied else 'Available'}</b><br>
                    <b>Address:</b> {address}<br>

                    <b>⚠️ Important Notice:
                    Please double-check the fee amount before proceeding. The fees shown here are based on publicly available notices found online and may not reflect the most current or official pricing. The price displayed at the parking location will be considered final and authoritative.
                    </b><br>
                    <i>{spot.get('status_note', 'N/A')}</i><br>
                    Last Updated: {last_updated_dt}<br>
                    <hr style="margin: 5px 0;">
                    <div class="spot-id" style="display:none;">{spot.get('name')}</div>
                    <button onclick="parent.document.getElementById('select-spot-{spot.get('name')}').click();" style="width: 100%; border: none; background-color: #007bff; color: white; padding: 8px; border-radius: 4px; cursor: pointer;">Book</button>
                </div>
                """
                folium.Marker(location=[spot['lat'], spot['lng']], popup=folium.Popup(popup_html, max_width=250), tooltip=f"ID: {spot.get('name', 'N/A')}", icon=folium.Icon(color=color, icon='car', prefix='fa')).add_to(m)

            folium.Marker(location=[st.session_state.current_lat, st.session_state.current_lng], popup="Your Current Location (Click map to move)", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
            
            if st.session_state.dest_lat and st.session_state.dest_lng:
                folium.Marker(location=[st.session_state.dest_lat, st.session_state.dest_lng], popup="Your Destination", icon=folium.Icon(color='orange', icon='flag')).add_to(m)

            if bounds:
                m.fit_bounds(bounds, padding=(50, 50))

            map_data = st_folium(m, width='100%', height=700, returned_objects=['last_object_clicked', 'last_clicked'])

            if map_data and map_data.get("last_clicked") and not st.session_state.path_data:
                st.session_state.current_lat = map_data['last_clicked']['lat']
                st.session_state.current_lng = map_data['last_clicked']['lng']
                st.session_state.location_set_by_user = True
                st.rerun()

            if map_data and map_data.get("last_object_clicked_popup"):
                popup_content = map_data['last_object_clicked_popup']
                if popup_content:
                    try:
                        spot_id_search = '<div class="spot-id" style="display:none;">'
                        if spot_id_search in popup_content:
                            spot_id = popup_content.split(spot_id_search)[1].split('</div>')[0]
                            selected = next((s for s in st.session_state.spots if str(s.get('name')) == str(spot_id)), None)
                            if selected and (st.session_state.selected_spot is None or st.session_state.selected_spot.get('name') != selected.get('name')):
                                st.session_state.selected_spot = selected
                                st.rerun()
                    except (IndexError, StopIteration):
                        pass

        if st.session_state.spots:
            unique_spots = []
            seen_names = set()
            for spot in st.session_state.spots:
                if spot.get('name') not in seen_names:
                    unique_spots.append(spot)
                    seen_names.add(spot.get('name'))

        if st.session_state.selected_spot:
            st.markdown("---")
            spot_details = st.session_state.selected_spot
            st.subheader(f"Details for: {spot_details.get('name')}")
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Status", "Occupied" if spot_details.get('occupied') else "Available")
            with col_b:
                if spot_details.get('current_fee') is not None:
                    st.metric(f"Current {spot_details.get('fee_type', '')} Rate", f"${spot_details['current_fee']:.2f}/hr")
                else:
                    st.metric("Fee", f"${spot_details.get('fee', 0.0):.2f}/hr")
            with col_c:
                st.metric("Area Type", spot_details.get('area_type', 'N/A'))

            st.write(f"**Location:** {spot_details.get('street', 'N/A')}")
            st.caption("""
                Disclaimer: Parking rates are provided for informational purposes only and are based on public data. Rates are subject to change and may not be guaranteed. Please verify all pricing and restrictions on the official parking meters or signage before parking.
            """)
            st.info(f"**Note:** {spot_details.get('status_note', 'No additional information.')}")
            
            last_updated_str = spot_details.get('last_updated')
            if last_updated_str:
                try:
                    if 'Z' in last_updated_str: last_updated_str = last_updated_str.replace('Z', '+00:00')
                    dt_object = datetime.fromisoformat(last_updated_str)
                    st.caption(f"Last updated: {dt_object.strftime('%d %b %Y, %I:%M %p %Z')}")
                except (ValueError, TypeError):
                    st.caption(f"Last updated: {last_updated_str}")

            button_cols = st.columns(4)
            with button_cols[0]:
                if st.session_state.dest_lat:
                    if st.button("Start Navigation", disabled=not st.session_state.location_set_by_user, use_container_width=True, key="start_nav_btn"):
                        with st.spinner("Calculating full journey..."):
                            start_loc = (st.session_state.current_lat, st.session_state.current_lng)
                            parking_loc = (spot_details['lat'], spot_details['lng'])
                            dest_loc = (st.session_state.dest_lat, st.session_state.dest_lng)
                            
                            st.session_state.leg1_route = None
                            st.session_state.leg2_route = None
                            st.session_state.leg2_steps = None
                            st.session_state.leg2_summary = None

                            params1 = {"start_lat": start_loc[0], "start_lon": start_loc[1], "end_lat": parking_loc[0], "end_lon": parking_loc[1], "steps": "false"}
                            response1 = api_request("GET", "/api/route", params=params1)
                            if response1 and response1.status_code == 200:
                                leg1_data = response1.json()
                                st.session_state.leg1_route = leg1_data.get('geometry')

                            params2 = {"start_lat": parking_loc[0], "start_lon": parking_loc[1], "end_lat": dest_loc[0], "end_lon": dest_loc[1], "steps": "true"}
                            response2 = api_request("GET", "/api/route", params=params2)
                            if response2 and response2.status_code == 200:
                                leg2_data = response2.json()
                                st.session_state.leg2_route = leg2_data.get('geometry')
                                st.session_state.leg2_steps = leg2_data.get('steps')
                                st.session_state.leg2_summary = leg2_data.get('summary')
                            
                            if st.session_state.leg1_route or st.session_state.leg2_route:
                                st.session_state.navigation_active = True
                                st.rerun()
                            else:
                                st.error("Could not calculate routes for this journey. Please check your connection and try again.")

            with button_cols[1]:
                if st.session_state.selected_spot and not st.session_state.selected_spot.get('occupied'):
                    if not st.session_state.stripe_pk:
                        pk_response = api_request("GET", "/config")
                        if pk_response and pk_response.status_code == 200 and pk_response.json().get("publishableKey"):
                            st.session_state.stripe_pk = pk_response.json().get("publishableKey")

                    if st.session_state.stripe_pk:
                        booking_fee_cents = int(spot_details.get('fee', 2.5) * 100)
                        payment_url = f"http://localhost:8000/payment.html?spot_id={spot_details.get('name')}&amount={booking_fee_cents}&token={st.session_state.token}&pk={st.session_state.stripe_pk}"
                        st.link_button(f"Pay ${spot_details.get('fee', 2.5):.2f} and Book", url=payment_url, use_container_width=True, type="primary")
                    else:
                        st.error("Stripe is not configured. Please add keys to the .env file.")

            with button_cols[2]:
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                if st.button("❤️ Add to Favorites", use_container_width=True):
                    fav_resp = api_request("POST", f"/api/favorites/{spot_details.get('name')}", headers=headers, json={"nickname": spot_details.get('street')})
                    if fav_resp and fav_resp.status_code == 200:
                        st.success(f"Added Spot {spot_details.get('name')} to your favorites!")
                    elif fav_resp and fav_resp.status_code == 409:
                        st.warning("This spot is already in your favorites.")
                    time.sleep(1.5)

            with button_cols[3]:
                if st.button("Deselect Spot", key="deselect_spot_btn", use_container_width=True):
                    st.session_state.selected_spot = None
                    st.rerun()

        google_maps_css = """
            <style>
                /* --- General App Styling --- */
                #MainMenu, footer, header { visibility: hidden; }
                .stApp { margin-top: 0; }

                /* --- Android-style Buttons --- */
                div[data-testid="stButton"] > button {
                    border-radius: 20px; /* Fully rounded corners */
                    padding: 10px 20px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    transition: all 0.2s ease-in-out;
                    border: none;
                    background-color: #4285F4; /* Google Blue */
                    color: white;
                }
                /* Hover and active states for a tactile feel */
                div[data-testid="stButton"] > button:hover:not(:disabled) {
                    box-shadow: 0 4px 8px rgba(0,0,0,0.25);
                    transform: translateY(-1px);
                    background-color: #5a95f5;
                }
                div[data-testid="stButton"] > button:active:not(:disabled) {
                    transform: translateY(1px);
                    box-shadow: 0 1px 2px rgba(0,0,0,0.2);
                }
                /* Style for secondary/less important buttons */
                div[data-testid="stButton"] > button[kind="secondary"] {
                    background-color: #f1f3f4; /* Light gray */
                    color: #202124; /* Dark gray text */
                }
                div[data-testid="stButton"] > button[kind="secondary"]:hover:not(:disabled) {
                    background-color: #e8eaed;
                }
                /* Disabled button style */
                div[data-testid="stButton"] > button:disabled {
                    background-color: #f1f3f4;
                    color: #bdc1c6;
                    cursor: not-allowed;
                }
            </style>
        """
        
        st.markdown(google_maps_css, unsafe_allow_html=True)
        st.markdown("""
            <style>
            .leaflet-marker-icon.green, .leaflet-marker-icon.red { animation: fadeIn 0.5s ease-in-out, pulse 2s infinite 1s; }
            .leaflet-polyline { animation: fadeIn 2s ease-in-out; }
            @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
            @keyframes fadeIn { 0% { opacity: 0; } 100% { opacity: 1; } }
            </style>
        """, unsafe_allow_html=True)

# ==============================================================================
# --- 3. APP RUNNER ---
# ==============================================================================

def run_backend():
    """Runs the FastAPI backend server."""
    uvicorn.run(backend_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # Check if the backend is already running (e.g., in a Streamlit rerun)
    try:
        requests.get("http://localhost:8000/docs", timeout=1)
        logger.info("Backend is already running.")
    except requests.ConnectionError:
        logger.info("Backend not found, starting it in a new thread.")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        time.sleep(2) # Give the backend a moment to start

    # Run the Streamlit frontend
    run_frontend()
