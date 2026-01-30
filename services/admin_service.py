
from database import get_db_connection
from datetime import datetime

class AdminService:
    @staticmethod
    def get_dashboard_stats():
        conn = get_db_connection()
        try:
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
                    r.is_paid,
                    s.birthday
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                LEFT JOIN registration_courses rc ON r.id = rc.registration_id
                LEFT JOIN registration_supplies rs ON r.id = rs.registration_id
                GROUP BY r.id, s.name, s.birthday, r.class_name, r.created_at, r.updated_at, r.is_paid
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
                    'is_paid': row[7],
                    'birthday': row[8].strftime('%Y-%m-%d') if row[8] else None
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
            
            return {
                'registrations': registrations,
                'statistics': statistics
            }
        finally:
            conn.close()

    @staticmethod
    def get_courses_stats():
        conn = get_db_connection()
        try:
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
            return courses
        finally:
            conn.close()

    @staticmethod
    def get_registration_detail(reg_id):
        conn = get_db_connection()
        try:
            reg_results = conn.run("""
                SELECT r.id, s.name, r.class_name, r.created_at, r.updated_at, s.birthday
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                WHERE r.id = :id
            """, id=reg_id)
            
            if not reg_results:
                return None
            
            reg = reg_results[0]
            
            course_results = conn.run("""
                SELECT c.name, c.price
                FROM registration_courses rc
                JOIN courses c ON rc.course_id = c.id
                WHERE rc.registration_id = :reg_id
            """, reg_id=reg_id)
            
            courses = [{'name': row[0], 'price': str(row[1])} for row in course_results]
            
            supply_results = conn.run("""
                SELECT s.name, s.price
                FROM registration_supplies rs
                JOIN supplies s ON rs.supply_id = s.id
                WHERE rs.registration_id = :reg_id
            """, reg_id=reg_id)
            
            supplies = [{'name': row[0], 'price': str(row[1])} for row in supply_results]
            
            return {
                'id': reg[0],
                'student_name': reg[1],
                'class_name': reg[2],
                'created_at': reg[3].isoformat() if reg[3] else None,
                'updated_at': reg[4].isoformat() if reg[4] else None,
                'birthday': reg[5].strftime('%Y-%m-%d') if reg[5] else None,
                'courses': courses,
                'supplies': supplies
            }
        finally:
            conn.close()

    @staticmethod
    def delete_registration(reg_id):
        conn = get_db_connection()
        try:
            conn.run("DELETE FROM registrations WHERE id = :id", id=reg_id)
        finally:
            conn.close()

    @staticmethod
    def delete_course(course_id):
        conn = get_db_connection()
        try:
            check_result = conn.run(
                "SELECT COUNT(*) FROM registration_courses WHERE course_id = :id",
                id=course_id
            )
            if check_result and check_result[0][0] > 0:
                raise ValueError(f'無法刪除：此課程有 {check_result[0][0]} 筆報名記錄，請先刪除相關報名後再試。')
            
            conn.run("DELETE FROM courses WHERE id = :id", id=course_id)
        finally:
            conn.close()

    @staticmethod
    def create_course(data):
        name = data.get('name')
        price = data.get('price')
        if not name or price is None:
            raise ValueError('課程名稱和價格為必填')

        conn = get_db_connection()
        try:
            existing = conn.run("SELECT id FROM courses WHERE name = :name", name=name)
            if existing:
                raise ValueError('課程名稱已存在')

            result = conn.run(
                """INSERT INTO courses (name, price, sessions, frequency, description, capacity, video_url) 
                   VALUES (:name, :price, :sessions, :frequency, :description, :capacity, :video_url) 
                   RETURNING id""",
                name=name, price=int(price), 
                sessions=int(data.get('sessions')) if data.get('sessions') else None,
                frequency=data.get('frequency', ''), 
                description=data.get('description', ''), 
                capacity=int(data.get('capacity', 30)),
                video_url=data.get('video_url', '')
            )
            return result[0][0]
        finally:
            conn.close()

    @staticmethod
    def update_course(course_id, data):
        conn = get_db_connection()
        try:
            check_result = conn.run("SELECT id FROM courses WHERE id = :id", id=course_id)
            if not check_result:
                raise ValueError('課程不存在')

            if 'name' in data:
                name = data.get('name')
                price = data.get('price')
                if not name or price is None:
                    raise ValueError('課程名稱和價格為必填')
                
                existing = conn.run(
                    "SELECT id FROM courses WHERE name = :name AND id != :id",
                    name=name, id=course_id
                )
                if existing:
                    raise ValueError('課程名稱已被其他課程使用')

                conn.run(
                    """UPDATE courses SET 
                       name = :name, price = :price, sessions = :sessions,
                       frequency = :frequency, description = :description, capacity = :capacity,
                       video_url = :video_url
                       WHERE id = :id""",
                    name=name, price=int(price), 
                    sessions=int(data.get('sessions')) if data.get('sessions') else None,
                    frequency=data.get('frequency', ''), 
                    description=data.get('description', ''), 
                    capacity=int(data.get('capacity', 30)),
                    video_url=data.get('video_url', ''),
                    id=course_id
                )
            else:
                # Capacity only update
                new_capacity = data.get('capacity')
                if new_capacity is None:
                    raise ValueError('Missing capacity parameter')
                conn.run(
                    "UPDATE courses SET capacity = :capacity WHERE id = :id",
                    capacity=int(new_capacity), id=course_id
                )
        finally:
            conn.close()

    @staticmethod
    def update_settings(start, end):
        conn = get_db_connection()
        try:
            conn.run(
                "INSERT INTO settings (key, value) VALUES ('registration_start', :value) ON CONFLICT (key) DO UPDATE SET value = :value",
                value=start
            )
            conn.run(
                "INSERT INTO settings (key, value) VALUES ('registration_end', :value) ON CONFLICT (key) DO UPDATE SET value = :value",
                value=end
            )
        finally:
            conn.close()

    @staticmethod
    def toggle_payment(reg_id, paid):
        conn = get_db_connection()
        try:
            conn.run("UPDATE registrations SET is_paid = :paid, updated_at = :now WHERE id = :id",
                     paid=paid, now=datetime.now(), id=reg_id)
        finally:
            conn.close()
