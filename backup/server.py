import http.server
import socketserver
import json
import pg8000.native
from datetime import datetime
import os
import urllib.parse
import secrets
import hashlib

PORT = 3000
DB_NAME = "afterschool"
DB_USER = "yilunwu"

# Admin password (can be set via environment variable)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Active session tokens (in-memory, will reset on server restart)
active_sessions = set()

def generate_session_token():
    """Generate a secure random session token"""
    return secrets.token_urlsafe(32)

def validate_session(token):
    """Check if a session token is valid"""
    return token in active_sessions

def validate_course_data(data):
    """Validate course data and return list of errors"""
    errors = []
    
    name = data.get('name', '')
    if not name or not isinstance(name, str):
        errors.append('課程名稱為必填')
    elif len(name) > 100:
        errors.append('課程名稱不可超過100字')
    
    price = data.get('price')
    if price is None:
        errors.append('價格為必填')
    else:
        try:
            price_int = int(price)
            if price_int < 0:
                errors.append('價格必須為正整數')
            if price_int > 1000000:
                errors.append('價格不可超過 1,000,000')
        except (ValueError, TypeError):
            errors.append('價格必須為有效數字')
    
    sessions = data.get('sessions')
    if sessions is not None:
        try:
            sessions_int = int(sessions)
            if sessions_int < 1 or sessions_int > 999:
                errors.append('堂數必須在 1-999 之間')
        except (ValueError, TypeError):
            errors.append('堂數必須為有效數字')
    
    capacity = data.get('capacity')
    if capacity is not None:
        try:
            capacity_int = int(capacity)
            if capacity_int < 1 or capacity_int > 999:
                errors.append('容量必須在 1-999 之間')
        except (ValueError, TypeError):
            errors.append('容量必須為有效數字')
    
    return errors

def escape_html(text):
    """Escape HTML special characters to prevent XSS"""
    if text is None:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return pg8000.native.Connection(user=urllib.parse.urlparse(db_url).username, 
                                      password=urllib.parse.urlparse(db_url).password,
                                      host=urllib.parse.urlparse(db_url).hostname,
                                      port=urllib.parse.urlparse(db_url).port or 5432,
                                      database=urllib.parse.urlparse(db_url).path[1:])
    return pg8000.native.Connection(user=DB_USER, database=DB_NAME)

def init_db():
    """Initialize database with normalized schema"""
    try:
        conn = get_db_connection()
        
        # Students table
        conn.run('''CREATE TABLE IF NOT EXISTS students (
                      id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
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
            print("Added is_paid column to registrations table")
        except pg8000.native.DatabaseError as e:
            # Ignore error if column already exists (code 42701)
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
        
        # Insert initial supply data
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

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'OPTIONS, GET, POST, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def check_admin_auth(self):
        """Check if request has valid admin authentication. Returns True if authorized."""
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            return validate_session(token)
        return False
    
    def is_admin_path(self, path):
        """Check if the path requires admin authentication"""
        admin_paths = ['/admin/registrations', '/admin/registration/', '/admin/courses', 
                       '/admin/course/', '/admin/course', '/admin/stats', '/admin/settings']
        return any(path.startswith(p) or path == p for p in admin_paths)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/query-registration':
            query_params = urllib.parse.parse_qs(parsed_path.query)
            name = query_params.get('name', [None])[0]
            
            if not name:
                self.send_error(400, "Missing name parameter")
                return

            try:
                conn = get_db_connection()
                
                # Get latest registration for student
                results = conn.run("""
                    SELECT r.id, s.name, r.class_name, r.created_at
                    FROM registrations r
                    JOIN students s ON r.student_id = s.id
                    WHERE s.name = :name
                    ORDER BY r.created_at DESC
                    LIMIT 1
                """, name=name)
                
                if not results:
                    self.send_json_response(404, {'message': 'Registration not found'})
                    conn.close()
                    return
                
                reg = results[0]
                reg_id = reg[0]
                
                # Get courses for this registration
                course_results = conn.run("""
                    SELECT c.name, c.price
                    FROM registration_courses rc
                    JOIN courses c ON rc.course_id = c.id
                    WHERE rc.registration_id = :reg_id
                """, reg_id=reg_id)
                
                courses = [{'name': row[0], 'price': str(row[1])} for row in course_results]
                
                # Get supplies for this registration
                supply_results = conn.run("""
                    SELECT s.name, s.price
                    FROM registration_supplies rs
                    JOIN supplies s ON rs.supply_id = s.id
                    WHERE rs.registration_id = :reg_id
                """, reg_id=reg_id)
                
                supplies = [{'name': row[0], 'price': str(row[1])} for row in supply_results]
                
                conn.close()
                
                data = {
                    'id': reg_id,
                    'name': reg[1],
                    'class': reg[2] or 'Unspecified',
                    'courses': courses,
                    'supplies': supplies,
                    'totalItems': len(courses) + len(supplies)
                }
                
                self.send_json_response(200, data)
            except Exception as e:
                print(f"Query Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
            
        # Get course availability
        if parsed_path.path == '/api/courses/availability':
            try:
                conn = get_db_connection()
                
                # Get usage count per course
                # capacity default is 30, can be adjusted in DB
                results = conn.run("""
                    SELECT c.name, c.capacity, COUNT(rc.registration_id) as used
                    FROM courses c
                    LEFT JOIN registration_courses rc ON c.id = rc.course_id
                    GROUP BY c.id, c.name, c.capacity
                """)
                
                availability = {}
                for row in results:
                    name = row[0]
                    capacity = row[1] if row[1] is not None else 30
                    used = row[2]
                    remaining = max(0, capacity - used)
                    availability[name] = remaining
                
                conn.close()
                self.send_json_response(200, availability)
            except Exception as e:
                print(f"Availability API Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # Get registration time settings
        if parsed_path.path == '/api/settings/registration-time':
            try:
                conn = get_db_connection()
                
                results = conn.run("""
                    SELECT key, value FROM settings 
                    WHERE key IN ('registration_start', 'registration_end')
                """)
                
                settings = {}
                for row in results:
                    settings[row[0]] = row[1]
                
                conn.close()
                self.send_json_response(200, {
                    'start': settings.get('registration_start', ''),
                    'end': settings.get('registration_end', '')
                })
            except Exception as e:
                print(f"Settings API Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # Get course videos
        if parsed_path.path == '/api/course-videos':
            try:
                conn = get_db_connection()
                results = conn.run("SELECT name, video_url FROM courses WHERE video_url IS NOT NULL AND video_url != ''")
                videos = {row[0]: row[1] for row in results}
                conn.close()
                self.send_json_response(200, videos)
            except Exception as e:
                print(f"Course Videos API Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # ============ ADMIN ENDPOINTS (require authentication) ============
        # Check authentication for all admin paths
        if self.is_admin_path(parsed_path.path):
            if not self.check_admin_auth():
                self.send_json_response(401, {'message': '未授權，請先登入'})
                return

        # Admin: Get all registrations with statistics
        if parsed_path.path == '/admin/registrations':
            try:
                conn = get_db_connection()
                
                # Get all registrations with counts
                results = conn.run("""
                    SELECT 
                        r.id,
                        s.name as student_name,
                        r.class_name,
                        r.created_at,
                        r.updated_at,
                        COUNT(DISTINCT rc.course_id) as course_count,
                        COUNT(DISTINCT rs.supply_id) as supply_count,
                        r.is_paid
                    FROM registrations r
                    JOIN students s ON r.student_id = s.id
                    LEFT JOIN registration_courses rc ON r.id = rc.registration_id
                    LEFT JOIN registration_supplies rs ON r.id = rs.registration_id
                    GROUP BY r.id, s.name, r.class_name, r.created_at, r.updated_at, r.is_paid
                    ORDER BY r.created_at DESC
                """)
                
                registrations = []
                for row in results:
                    registrations.append({
                        'id': row[0],
                        'student_name': row[1],
                        'class_name': row[2],
                        'created_at': row[3].isoformat() if row[3] else None,
                        'updated_at': row[4].isoformat() if row[4] else None,
                        'course_count': row[5],
                        'supply_count': row[6],
                        'is_paid': row[7] # New field
                    })
                
                # Get statistics
                stats_result = conn.run("""
                    SELECT 
                        COUNT(DISTINCT r.id) as total_registrations,
                        COUNT(DISTINCT s.id) as total_students,
                        COUNT(DISTINCT rc.id) as total_course_enrollments,
                        COUNT(DISTINCT rs.id) as total_supply_orders
                    FROM registrations r
                    JOIN students s ON r.student_id = s.id
                    LEFT JOIN registration_courses rc ON r.id = rc.registration_id
                    LEFT JOIN registration_supplies rs ON r.id = rs.registration_id
                """)
                
                stats = stats_result[0]
                statistics = {
                    'totalRegistrations': stats[0],
                    'totalStudents': stats[1],
                    'totalCourseEnrollments': stats[2],
                    'totalSupplyOrders': stats[3]
                }
                
                conn.close()
                
                self.send_json_response(200, {
                    'registrations': registrations,
                    'statistics': statistics
                })
            except Exception as e:
                print(f"Admin Query Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # Admin: Get all courses with capacity info
        if parsed_path.path == '/admin/courses':
            try:
                conn = get_db_connection()
                
                results = conn.run("""
                    SELECT c.id, c.name, c.price, c.sessions, c.frequency, c.capacity, c.description, c.video_url,
                           COUNT(rc.registration_id) as used
                    FROM courses c
                    LEFT JOIN registration_courses rc ON c.id = rc.course_id
                    GROUP BY c.id, c.name, c.price, c.sessions, c.frequency, c.capacity, c.description, c.video_url
                    ORDER BY c.id
                """)
                
                courses = []
                for row in results:
                    capacity = row[5] if row[5] is not None else 30
                    used = row[8]
                    courses.append({
                        'id': row[0],
                        'name': row[1],
                        'price': row[2],
                        'sessions': row[3],
                        'frequency': row[4],
                        'capacity': capacity,
                        'description': row[6] or '',
                        'video_url': row[7] or '',
                        'used': used,
                        'remaining': max(0, capacity - used)
                    })
                
                conn.close()
                self.send_json_response(200, {'courses': courses})
            except Exception as e:
                print(f"Admin Courses Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # Admin: Get single registration detail
        if parsed_path.path.startswith('/admin/registration/'):
            try:
                reg_id = int(parsed_path.path.split('/')[-1])
                conn = get_db_connection()
                
                # Get registration info
                reg_results = conn.run("""
                    SELECT r.id, s.name, r.class_name, r.created_at, r.updated_at
                    FROM registrations r
                    JOIN students s ON r.student_id = s.id
                    WHERE r.id = :id
                """, id=reg_id)
                
                if not reg_results:
                    self.send_json_response(404, {'message': 'Registration not found'})
                    conn.close()
                    return
                
                reg = reg_results[0]
                
                # Get courses
                course_results = conn.run("""
                    SELECT c.name, c.price
                    FROM registration_courses rc
                    JOIN courses c ON rc.course_id = c.id
                    WHERE rc.registration_id = :reg_id
                """, reg_id=reg_id)
                
                courses = [{'name': row[0], 'price': str(row[1])} for row in course_results]
                
                # Get supplies
                supply_results = conn.run("""
                    SELECT s.name, s.price
                    FROM registration_supplies rs
                    JOIN supplies s ON rs.supply_id = s.id
                    WHERE rs.registration_id = :reg_id
                """, reg_id=reg_id)
                
                supplies = [{'name': row[0], 'price': str(row[1])} for row in supply_results]
                
                conn.close()
                
                data = {
                    'id': reg[0],
                    'student_name': reg[1],
                    'class_name': reg[2],
                    'created_at': reg[3].isoformat() if reg[3] else None,
                    'updated_at': reg[4].isoformat() if reg[4] else None,
                    'courses': courses,
                    'supplies': supplies
                }
                
                self.send_json_response(200, data)
            except Exception as e:
                print(f"Admin Detail Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return

        # Default to serving static files
        if self.path == '/':
            self.path = '/ivyApplication.html'
        super().do_GET()

    def do_DELETE(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Check authentication for admin paths
        if self.is_admin_path(parsed_path.path):
            if not self.check_admin_auth():
                self.send_json_response(401, {'message': '未授權，請先登入'})
                return

        # Admin: Delete registration
        if parsed_path.path.startswith('/admin/registration/'):
            try:
                reg_id = int(parsed_path.path.split('/')[-1])
                conn = get_db_connection()
                
                # Delete registration (cascades to junction tables)
                conn.run("DELETE FROM registrations WHERE id = :id", id=reg_id)
                
                conn.close()
                
                print(f"Deleted registration ID: {reg_id}")
                self.send_json_response(200, {'message': 'Deleted successfully'})
            except Exception as e:
                print(f"Delete Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
        
        # Admin: Delete course
        if parsed_path.path.startswith('/admin/course/'):
            try:
                course_id = int(parsed_path.path.split('/')[-1])
                conn = get_db_connection()
                
                # Check if course has associated registrations
                check_result = conn.run(
                    "SELECT COUNT(*) FROM registration_courses WHERE course_id = :id",
                    id=course_id
                )
                if check_result and check_result[0][0] > 0:
                    conn.close()
                    self.send_json_response(400, {
                        'message': f'無法刪除：此課程有 {check_result[0][0]} 筆報名記錄，請先刪除相關報名後再試。'
                    })
                    return
                
                # Delete the course
                conn.run("DELETE FROM courses WHERE id = :id", id=course_id)
                conn.close()
                
                print(f"Deleted course ID: {course_id}")
                self.send_json_response(200, {'message': '課程已刪除'})
            except ValueError:
                self.send_json_response(400, {'message': '無效的課程 ID'})
            except Exception as e:
                print(f"Delete Course Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
        
        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        if self.path == '/submit-registration':
            self.handle_registration(update=False)
        elif self.path == '/update-registration':
            self.handle_registration(update=True)
        elif self.path == '/admin/login':
            self.handle_admin_login()
        elif self.path == '/admin/course':
            # Check auth before creating course
            if not self.check_admin_auth():
                self.send_json_response(401, {'message': '未授權，請先登入'})
                return
            self.handle_create_course()
        else:
            self.send_error(404, "Endpoint not found")
    
    def handle_admin_login(self):
        """Handle admin login and return session token"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            password = data.get('password', '')
            
            if password == ADMIN_PASSWORD:
                token = generate_session_token()
                active_sessions.add(token)
                print(f"Admin login successful, token generated")
                self.send_json_response(200, {
                    'message': '登入成功',
                    'token': token
                })
            else:
                print(f"Admin login failed: wrong password")
                self.send_json_response(401, {'message': '密碼錯誤'})
        except Exception as e:
            print(f"Login Error: {e}")
            self.send_json_response(500, {'message': str(e)})
    
    def handle_create_course(self):
        """Handle creating a new course"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            name = data.get('name')
            price = data.get('price')
            sessions = data.get('sessions')
            frequency = data.get('frequency', '')
            description = data.get('description', '')
            capacity = data.get('capacity', 30)
            
            if not name or price is None:
                self.send_json_response(400, {'message': '課程名稱和價格為必填'})
                return
            
            conn = get_db_connection()
            
            # Check if course name already exists
            existing = conn.run("SELECT id FROM courses WHERE name = :name", name=name)
            if existing:
                conn.close()
                self.send_json_response(400, {'message': '課程名稱已存在'})
                return
            
            # Insert new course
            result = conn.run(
                """INSERT INTO courses (name, price, sessions, frequency, description, capacity) 
                   VALUES (:name, :price, :sessions, :frequency, :description, :capacity) 
                   RETURNING id""",
                name=name, price=int(price), sessions=int(sessions) if sessions else None,
                frequency=frequency, description=description, capacity=int(capacity)
            )
            
            new_id = result[0][0]
            conn.close()
            
            print(f"Created new course: {name} (ID: {new_id})")
            self.send_json_response(200, {'message': '課程新增成功', 'course_id': new_id})
        except Exception as e:
            print(f"Create Course Error: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {'message': str(e)})

    def do_PUT(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Check authentication for admin paths
        if self.is_admin_path(parsed_path.path):
            if not self.check_admin_auth():
                self.send_json_response(401, {'message': '未授權，請先登入'})
                return
        
        # Admin: Update course (full edit or just capacity)
        if parsed_path.path.startswith('/admin/course/'):
            try:
                course_id = int(parsed_path.path.split('/')[-1])
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                conn = get_db_connection()
                
                # Check if course exists
                check_result = conn.run("SELECT id, name FROM courses WHERE id = :id", id=course_id)
                if not check_result:
                    self.send_json_response(404, {'message': '課程不存在'})
                    conn.close()
                    return
                
                # Check if it's a full update or just capacity update
                if 'name' in data:
                    # Full course update
                    name = data.get('name')
                    price = data.get('price')
                    sessions = data.get('sessions')
                    frequency = data.get('frequency', '')
                    description = data.get('description', '')
                    capacity = data.get('capacity', 30)
                    video_url = data.get('video_url', '')
                    
                    if not name or price is None:
                        self.send_json_response(400, {'message': '課程名稱和價格為必填'})
                        conn.close()
                        return
                    
                    # Check if new name conflicts with another course
                    existing = conn.run(
                        "SELECT id FROM courses WHERE name = :name AND id != :id",
                        name=name, id=course_id
                    )
                    if existing:
                        conn.close()
                        self.send_json_response(400, {'message': '課程名稱已被其他課程使用'})
                        return
                    
                    conn.run(
                        """UPDATE courses SET 
                           name = :name, price = :price, sessions = :sessions,
                           frequency = :frequency, description = :description, capacity = :capacity,
                           video_url = :video_url
                           WHERE id = :id""",
                        name=name, price=int(price), sessions=int(sessions) if sessions else None,
                        frequency=frequency, description=description, capacity=int(capacity),
                        video_url=video_url, id=course_id
                    )
                    
                    print(f"Updated course ID {course_id} with full data")
                    self.send_json_response(200, {'message': '課程更新成功'})
                else:
                    # Just capacity update (backward compatibility)
                    new_capacity = data.get('capacity')
                    if new_capacity is None:
                        self.send_json_response(400, {'message': 'Missing capacity parameter'})
                        conn.close()
                        return
                    
                    conn.run(
                        "UPDATE courses SET capacity = :capacity WHERE id = :id",
                        capacity=int(new_capacity), id=course_id
                    )
                    
                    print(f"Updated course ID {course_id} capacity to {new_capacity}")
                    self.send_json_response(200, {'message': 'Capacity updated successfully'})
                
                conn.close()
            except ValueError:
                self.send_json_response(400, {'message': '無效的課程 ID 或參數'})
            except Exception as e:
                print(f"Update Course Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
        
        # Admin: Update registration time settings
        if parsed_path.path == '/admin/settings/registration-time':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                start_time = data.get('start')
                end_time = data.get('end')
                
                if not start_time or not end_time:
                    self.send_json_response(400, {'message': 'Missing start or end time'})
                    return
                
                conn = get_db_connection()
                
                # Update or insert settings
                conn.run(
                    "INSERT INTO settings (key, value) VALUES ('registration_start', :value) ON CONFLICT (key) DO UPDATE SET value = :value",
                    value=start_time
                )
                conn.run(
                    "INSERT INTO settings (key, value) VALUES ('registration_end', :value) ON CONFLICT (key) DO UPDATE SET value = :value",
                    value=end_time
                )
                
                conn.close()
                
                print(f"Updated registration time: {start_time} to {end_time}")
                self.send_json_response(200, {'message': 'Registration time updated successfully'})
            except Exception as e:
                print(f"Update Settings Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
        
            return

        # Admin: Toggle payment status
        if parsed_path.path.endswith('/payment') and '/admin/registration/' in parsed_path.path:
            try:
                # Extract ID from /admin/registration/{id}/payment
                parts = parsed_path.path.split('/')
                # parts might be ['', 'admin', 'registration', '123', 'payment']
                # regex or finding 'registration' index is safer, but split is fine if format is fixed
                # id is at index -2
                reg_id = int(parts[-2])
                
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                paid = data.get('paid', False)
                
                conn = get_db_connection()
                conn.run("UPDATE registrations SET is_paid = :paid, updated_at = :now WHERE id = :id",
                         paid=paid, now=datetime.now(), id=reg_id)
                conn.close()
                
                status_text = '已繳費' if paid else '未繳費'
                print(f"Updated payment status for ID {reg_id}: {status_text}")
                self.send_json_response(200, {'message': f'更新成功，狀態為：{status_text}'})
            except Exception as e:
                print(f"Payment Update Error: {e}")
                self.send_json_response(500, {'message': str(e)})
            return
        
        self.send_error(404, "Endpoint not found")

    def handle_registration(self, update=False):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            
            name = data.get('name')
            class_name = data.get('class')
            courses = data.get('courses', [])
            supplies = data.get('supplies', [])
            
            # Auto-add material fee if elite English course is selected
            has_elite_english = any(c.get('name') == '菁英美語 (限大班)' for c in courses)
            has_material_fee = any(c.get('name') == '菁英美語教材費' for c in courses)
            
            if has_elite_english and not has_material_fee:
                courses.append({
                    'name': '菁英美語教材費',
                    'price': '1500'
                })
            
            conn = get_db_connection()
            
            try:
                # Start transaction
                conn.run("BEGIN")
                
                # Use Python's local time to avoid DB timezone mismatch
                current_time = datetime.now()
                
                if update:
                    reg_id = data.get('id')
                    if not reg_id:
                        raise ValueError("Missing ID for update")
                    
                    # Update registration
                    conn.run(
                        "UPDATE registrations SET class_name=:class_name, updated_at=:now WHERE id=:id",
                        class_name=class_name, now=current_time, id=reg_id
                    )
                    
                    # Delete old course/supply associations
                    conn.run("DELETE FROM registration_courses WHERE registration_id=:id", id=reg_id)
                    conn.run("DELETE FROM registration_supplies WHERE registration_id=:id", id=reg_id)
                    
                    # Re-insert courses with capacity check
                    for course in courses:
                        # Lock the course row to prevent race conditions
                        course_result = conn.run("SELECT id, capacity FROM courses WHERE name=:name FOR UPDATE", name=course['name'])
                        
                        if course_result:
                            course_id = course_result[0][0]
                            capacity = course_result[0][1]
                            
                            # Check capacity if it's set
                            if capacity is not None:
                                count_result = conn.run(
                                    "SELECT COUNT(*) FROM registration_courses WHERE course_id=:cid", 
                                    cid=course_id
                                )
                                current_count = count_result[0][0]
                                
                                if current_count >= capacity:
                                    conn.run("ROLLBACK")
                                    self.send_json_response(400, {'message': f'課程「{course["name"]}」已額滿'})
                                    conn.close()
                                    return

                            conn.run(
                                "INSERT INTO registration_courses (registration_id, course_id) VALUES (:reg_id, :course_id)",
                                reg_id=reg_id, course_id=course_id
                            )
                    
                    # Re-insert supplies
                    for supply in supplies:
                        supply_result = conn.run("SELECT id FROM supplies WHERE name=:name", name=supply['name'])
                        if supply_result:
                            supply_id = supply_result[0][0]
                            conn.run(
                                "INSERT INTO registration_supplies (registration_id, supply_id) VALUES (:reg_id, :supply_id)",
                                reg_id=reg_id, supply_id=supply_id
                            )
                    
                    print(f"Updated registration: {name} (ID: {reg_id})")
                    new_id = reg_id
                    message = 'Update successful!'
                else:
                    # Insert or get student
                    student_result = conn.run("SELECT id FROM students WHERE name=:name", name=name)
                    if student_result:
                        student_id = student_result[0][0]
                    else:
                        # Use python time for student creation too if needed, but defaults are ok usually unless displayed important
                        # Let's keep student default for now or update it? simpler to leave student.
                        student_result = conn.run(
                            "INSERT INTO students (name) VALUES (:name) RETURNING id",
                            name=name
                        )
                        student_id = student_result[0][0]
                    
                    # Create registration with explicit time
                    reg_result = conn.run(
                        "INSERT INTO registrations (student_id, class_name, created_at, updated_at) VALUES (:student_id, :class_name, :now, :now) RETURNING id",
                        student_id=student_id, class_name=class_name, now=current_time
                    )
                    new_id = reg_result[0][0]
                    
                    # Insert courses with capacity check
                    for course in courses:
                        # Lock the course row to prevent race conditions
                        course_result = conn.run("SELECT id, capacity FROM courses WHERE name=:name FOR UPDATE", name=course['name'])
                        
                        if course_result:
                            course_id = course_result[0][0]
                            capacity = course_result[0][1]
                            
                            if capacity is not None:
                                count_result = conn.run(
                                    "SELECT COUNT(*) FROM registration_courses WHERE course_id=:cid", 
                                    cid=course_id
                                )
                                current_count = count_result[0][0]
                                
                                if current_count >= capacity:
                                    conn.run("ROLLBACK")
                                    self.send_json_response(400, {'message': f'課程「{course["name"]}」已額滿'})
                                    conn.close()
                                    return
                            
                            conn.run(
                                "INSERT INTO registration_courses (registration_id, course_id) VALUES (:reg_id, :course_id)",
                                reg_id=new_id, course_id=course_id
                            )
                    
                    # Insert supplies
                    for supply in supplies:
                        supply_result = conn.run("SELECT id FROM supplies WHERE name=:name", name=supply['name'])
                        if supply_result:
                            supply_id = supply_result[0][0]
                            conn.run(
                                "INSERT INTO registration_supplies (registration_id, supply_id) VALUES (:reg_id, :supply_id)",
                                reg_id=new_id, supply_id=supply_id
                            )
                    
                    print(f"New registration: {name} (ID: {new_id})")
                    message = 'Registration successful!'

                conn.run("COMMIT")
                self.send_json_response(200, {'message': message, 'id': new_id})
                
            except Exception as e:
                conn.run("ROLLBACK")
                raise e
            finally:
                conn.close()
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {'message': f'Server Error: {str(e)}'})

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    init_db()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print(f"Python (PostgreSQL) Server running at http://localhost:{PORT}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
