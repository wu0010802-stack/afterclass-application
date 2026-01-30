
from flask import Blueprint, request, jsonify, render_template, abort
from services.admin_service import AdminService
from config import Config
import secrets

admin_bp = Blueprint('admin', __name__)

# Simple in-memory session store
active_sessions = set()

def generate_session_token():
    return secrets.token_urlsafe(32)

def validate_session(token):
    return token in active_sessions

def check_auth():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        if validate_session(token):
            return True
    return False

@admin_bp.before_request
def require_auth():
    # Allow login and page load without auth check (page load handles redirect in JS usually, 
    # but strictly API endpoints should be protected. 
    # The original server protected all /admin* paths except maybe the static file itself? 
    # Actually server.py line 251 checks is_admin_path for auth.
    # We will exempt login route.
    if request.method == 'OPTIONS':
        return
    
    if request.endpoint == 'admin.login':
        return
        
    if request.endpoint == 'admin.admin_page':
        # We can serve the page, but let frontend handle redirect if no token.
        # Or we can protect it? Original behavior: /admin paths check auth.
        # But serving the HTML might be better open so JS can check token.
        # server.py line 565 serves static files for /, but /admin* were protected?
        # server.py line 394: check_admin_auth for admin paths.
        # If I request /admin.html, does it go through is_admin_path? 
        # is_admin_path list: ['/admin/registrations', ...]. It does NOT include /admin.html explicitly if it's served as static.
        # But let's verify.
        return

    # For API endpoints
    if not check_auth():
        return jsonify({'message': '未授權，請先登入'}), 401

@admin_bp.route('/admin.html')
@admin_bp.route('/admin')
def admin_page():
    return render_template('admin.html')

@admin_bp.route('/admin/login', methods=['POST'])
def login():
    data = request.get_json()
    password = data.get('password', '')
    
    if password == Config.ADMIN_PASSWORD:
        token = generate_session_token()
        active_sessions.add(token)
        return jsonify({'message': '登入成功', 'token': token})
    else:
        return jsonify({'message': '密碼錯誤'}), 401

@admin_bp.route('/admin/registrations', methods=['GET'])
def get_registrations():
    try:
        data = AdminService.get_dashboard_stats()
        return jsonify(data)
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/courses', methods=['GET'])
def get_courses():
    try:
        courses = AdminService.get_courses_stats()
        return jsonify({'courses': courses})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/registration/<int:reg_id>', methods=['GET'])
def get_registration_detail(reg_id):
    try:
        data = AdminService.get_registration_detail(reg_id)
        if data:
            return jsonify(data)
        return jsonify({'message': 'Registration not found'}), 404
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/registration/<int:reg_id>', methods=['DELETE'])
def delete_registration(reg_id):
    try:
        AdminService.delete_registration(reg_id)
        return jsonify({'message': 'Deleted successfully'})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/course', methods=['POST'])
def create_course():
    try:
        data = request.get_json()
        new_id = AdminService.create_course(data)
        return jsonify({'message': '課程新增成功', 'course_id': new_id})
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/course/<int:course_id>', methods=['PUT'])
def update_course(course_id):
    try:
        data = request.get_json()
        AdminService.update_course(course_id, data)
        return jsonify({'message': 'Update successful'})
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/course/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    try:
        AdminService.delete_course(course_id)
        return jsonify({'message': '課程已刪除'})
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/settings/registration-time', methods=['POST'])
def update_settings():
    try:
        data = request.get_json()
        start = data.get('start')
        end = data.get('end')
        if not start or not end:
            return jsonify({'message': 'Missing start or end time'}), 400
            
        AdminService.update_settings(start, end)
        return jsonify({'message': 'Registration time updated successfully'})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@admin_bp.route('/admin/registration/<int:reg_id>/payment', methods=['PUT'])
def toggle_payment(reg_id):
    try:
        data = request.get_json()
        paid = data.get('paid', False)
        AdminService.toggle_payment(reg_id, paid)
        status = '已繳費' if paid else '未繳費'
        return jsonify({'message': f'更新成功，狀態為：{status}'})
    except Exception as e:
        return jsonify({'message': str(e)}), 500
