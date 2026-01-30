
import pg8000.native
import urllib.parse
import os
from config import Config

def get_db_connection():
    db_url = Config.DATABASE_URL
    if db_url:
        return pg8000.native.Connection(user=urllib.parse.urlparse(db_url).username, 
                                      password=urllib.parse.urlparse(db_url).password,
                                      host=urllib.parse.urlparse(db_url).hostname,
                                      port=urllib.parse.urlparse(db_url).port or 5432,
                                      database=urllib.parse.urlparse(db_url).path[1:])
    return pg8000.native.Connection(user=Config.DB_USER, database=Config.DB_NAME)

def init_db():
    """Initialize database with normalized schema"""
    try:
        conn = get_db_connection()
        
        # Students table
        conn.run('''CREATE TABLE IF NOT EXISTS students (
                      id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      birthday DATE,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

        # Migration: Add birthday column to students table
        try:
            conn.run("ALTER TABLE students ADD COLUMN IF NOT EXISTS birthday DATE")
        except Exception:
            pass
        
        # Courses table
        conn.run('''CREATE TABLE IF NOT EXISTS courses (
                      id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      price INTEGER NOT NULL,
                      sessions INTEGER,
                      frequency TEXT,
                      description TEXT,
                      capacity INTEGER DEFAULT 30,
                      video_url TEXT
                    )''')
        
        # Migration: Ensure capacity and video_url columns exist for existing tables
        try:
            conn.run("ALTER TABLE courses ADD COLUMN IF NOT EXISTS capacity INTEGER DEFAULT 30")
        except Exception:
            pass
        try:
            conn.run("ALTER TABLE courses ADD COLUMN IF NOT EXISTS video_url TEXT")
        except Exception:
            pass
        
        # Supplies table
        conn.run('''CREATE TABLE IF NOT EXISTS supplies (
                      id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      price INTEGER NOT NULL
                    )''')
        
        # Registrations table
        conn.run('''CREATE TABLE IF NOT EXISTS registrations (
                      id SERIAL PRIMARY KEY,
                      student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
                      class_name TEXT,
                      email TEXT,
                      is_paid BOOLEAN DEFAULT FALSE,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Migration: Ensure email column exists for existing registrations table
        try:
            conn.run("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS email TEXT")
        except Exception:
            pass

        # Migration: Add is_paid column to registrations table
        try:
            conn.run("ALTER TABLE registrations ADD COLUMN is_paid BOOLEAN DEFAULT FALSE")
        except pg8000.native.DatabaseError as e:
            if '42701' not in str(e): 
                pass
        
        # Registration-Courses junction table (many-to-many)
        conn.run('''CREATE TABLE IF NOT EXISTS registration_courses (
                      id SERIAL PRIMARY KEY,
                      registration_id INTEGER REFERENCES registrations(id) ON DELETE CASCADE,
                      course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
                      UNIQUE(registration_id, course_id)
                    )''')
        
        # Registration-Supplies junction table (many-to-many)
        conn.run('''CREATE TABLE IF NOT EXISTS registration_supplies (
                      id SERIAL PRIMARY KEY,
                      registration_id INTEGER REFERENCES registrations(id) ON DELETE CASCADE,
                      supply_id INTEGER REFERENCES supplies(id) ON DELETE CASCADE,
                      UNIQUE(registration_id, supply_id)
                    )''')
        
        # Insert initial course data
        insert_initial_data(conn)
        
        # Settings table for registration time control
        conn.run('''CREATE TABLE IF NOT EXISTS settings (
                      key TEXT PRIMARY KEY,
                      value TEXT NOT NULL
                    )''')
        
        # Insert default registration time settings
        default_settings = [
            ('registration_start', '2026-02-02T16:00'),
            ('registration_end', '2026-02-20T23:59')
        ]
        
        for setting in default_settings:
            try:
                conn.run(
                    "INSERT INTO settings (key, value) VALUES (:key, :value) ON CONFLICT (key) DO NOTHING",
                    key=setting[0], value=setting[1]
                )
            except:
                pass
        
        conn.close()
        print("Connected to PostgreSQL 'afterschool' database and tables ready.")
    except Exception as e:
        print(f"Database Initialization Error: {e}")

def insert_initial_data(conn):
    courses_data = [
        ('幼兒感統 (限小幼班)', 8000, 20, '每週1次，1次1小時', None),
        ('兒童舞蹈 (大中小幼班)', 4400, 20, '每週1次，1次1小時', None),
        ('足球 (中大班)', 5000, 20, '每週1次，1次1小時', None),
        ('足球 (中小班)', 5000, 20, '每週1次，1次1小時', None),
        ('3C3Q積木與桌遊 (大中小)', 5200, 20, '每週1次，1次1小時', None),
        ('幼兒美術 (大中小幼)', 4400, 20, '每週1次，1次1小時', None),
        ('菁英美語 (限大班)', 7000, 40, '每週2次', '教材費另計$1500'),
        ('菁英美語教材費', 1500, None, None, '選修菁英美語者必選')
    ]
    
    for course in courses_data:
        try:
            conn.run(
                "INSERT INTO courses (name, price, sessions, frequency, description) VALUES (:name, :price, :sessions, :frequency, :description) ON CONFLICT (name) DO NOTHING",
                name=course[0], price=course[1], sessions=course[2], frequency=course[3], description=course[4]
            )
        except:
            pass
    
    supplies_data = [
        ('全套舞蹈服裝', 1400),
        ('舞衣', 700),
        ('舞鞋', 250),
        ('舞襪', 150),
        ('舞袋', 300)
    ]
    
    for supply in supplies_data:
        try:
            conn.run(
                "INSERT INTO supplies (name, price) VALUES (:name, :price) ON CONFLICT (name) DO NOTHING",
                name=supply[0], price=supply[1]
            )
        except:
            pass
