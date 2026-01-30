
from flask import Blueprint, request, jsonify, render_template, send_from_directory
from services.registration_service import RegistrationService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/query.html')
def query_page():
    return render_template('query.html')

@main_bp.route('/query-registration', methods=['GET'])
def query_registration():
    name = request.args.get('name')
    if not name:
        return jsonify({'message': 'Missing name parameter'}), 400
    
    try:
        result = RegistrationService.get_registration_by_student(name)
        if result:
            return jsonify(result)
        return jsonify({'message': 'Registration not found'}), 404
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/api/courses/availability', methods=['GET'])
def get_availability():
    try:
        availability = RegistrationService.get_course_availability()
        return jsonify(availability)
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/api/settings/registration-time', methods=['GET'])
def get_registration_time():
    try:
        settings = RegistrationService.get_registration_settings()
        return jsonify(settings)
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/api/course-videos', methods=['GET'])
def get_course_videos():
    try:
        videos = RegistrationService.get_course_videos()
        return jsonify(videos)
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/submit-registration', methods=['POST'])
def submit_registration():
    try:
        data = request.get_json()
        result = RegistrationService.handle_registration(data, update=False)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@main_bp.route('/update-registration', methods=['POST'])
def update_registration():
    try:
        data = request.get_json()
        result = RegistrationService.handle_registration(data, update=True)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception as e:
        return jsonify({'message': str(e)}), 500
