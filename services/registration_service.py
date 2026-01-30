
from database import get_db_connection
from datetime import datetime
import json

class RegistrationService:
    @staticmethod
    def get_registration_by_student(student_name):
        conn = get_db_connection()
        try:
            # Get latest registration for student
            results = conn.run("""
                SELECT r.id, s.name, r.class_name, r.created_at, s.birthday
                FROM registrations r
                JOIN students s ON r.student_id = s.id
                WHERE s.name = :name
                ORDER BY r.created_at DESC
                LIMIT 1
            """, name=student_name)
            
            if not results:
                return None
            
            reg = results[0]
            reg_id = reg[0]
            
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
            
            birthday = reg[4].strftime('%Y-%m-%d') if reg[4] else ''

            return {
                'id': reg_id,
                'name': reg[1],
                'birthday': birthday,
                'class': reg[2] or 'Unspecified',
                'courses': courses,
                'supplies': supplies,
                'totalItems': len(courses) + len(supplies)
            }
        finally:
            conn.close()

    @staticmethod
    def handle_registration(data, update=False):
        name = data.get('name')
        birthday = data.get('birthday')  # Format: YYYY-MM-DD
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
            conn.run("BEGIN")
            current_time = datetime.now()
            
            if update:
                reg_id = data.get('id')
                if not reg_id:
                    raise ValueError("Missing ID for update")
                
                # Fetch student_id
                student_res = conn.run("SELECT student_id FROM registrations WHERE id=:id", id=reg_id)
                if student_res:
                    student_id = student_res[0][0]
                    # Update student birthday if provided
                    if birthday:
                         conn.run("UPDATE students SET birthday=:birthday WHERE id=:id", birthday=birthday, id=student_id)

                conn.run(
                    "UPDATE registrations SET class_name=:class_name, updated_at=:now WHERE id=:id",
                    class_name=class_name, now=current_time, id=reg_id
                )
                
                conn.run("DELETE FROM registration_courses WHERE registration_id=:id", id=reg_id)
                conn.run("DELETE FROM registration_supplies WHERE registration_id=:id", id=reg_id)
                new_id = reg_id
                message = 'Update successful!'
            else:
                # Insert or get student
                student_result = conn.run("SELECT id FROM students WHERE name=:name", name=name)
                if student_result:
                    student_id = student_result[0][0]
                    # Update birthday for existing student
                    if birthday:
                         conn.run("UPDATE students SET birthday=:birthday WHERE id=:id", birthday=birthday, id=student_id)
                else:
                    student_result = conn.run(
                        "INSERT INTO students (name, birthday) VALUES (:name, :birthday) RETURNING id",
                        name=name, birthday=birthday
                    )
                    student_id = student_result[0][0]
                
                # Create registration
                reg_result = conn.run(
                    "INSERT INTO registrations (student_id, class_name, created_at, updated_at) VALUES (:student_id, :class_name, :now, :now) RETURNING id",
                    student_id=student_id, class_name=class_name, now=current_time
                )
                new_id = reg_result[0][0]
                message = 'Registration successful!'

            # Insert courses with capacity check
            for course in courses:
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
                        
                        # For updates, we just deleted our own registration, so the count doesn't include us.
                        # So simply checking count >= capacity is correct for both new and updates 
                        # (for update, we were removed, so we are like a new addition).
                        if current_count >= capacity:
                            conn.run("ROLLBACK")
                            raise ValueError(f'課程「{course["name"]}」已額滿')

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
            
            conn.run("COMMIT")
            return {'message': message, 'id': new_id}
            
        except Exception as e:
            conn.run("ROLLBACK")
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_course_availability():
        conn = get_db_connection()
        try:
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
            return availability
        finally:
            conn.close()

    @staticmethod
    def get_registration_settings():
        conn = get_db_connection()
        try:
            results = conn.run("""
                SELECT key, value FROM settings 
                WHERE key IN ('registration_start', 'registration_end')
            """)
            
            settings = {}
            for row in results:
                settings[row[0]] = row[1]
            return {
                'start': settings.get('registration_start', ''),
                'end': settings.get('registration_end', '')
            }
        finally:
            conn.close()

    @staticmethod
    def get_course_videos():
        conn = get_db_connection()
        try:
            results = conn.run("SELECT name, video_url FROM courses WHERE video_url IS NOT NULL AND video_url != ''")
            return {row[0]: row[1] for row in results}
        finally:
            conn.close()
