from flask import Flask, jsonify
from flask_socketio import SocketIO
from redis import Redis
from flask_cors import CORS
import os
import json
from database import Notification, db
import logging


def create_app() -> Flask:
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins='*')

    CORS(app)

    app.secret_key = os.environ.get("SECRET_KEY", 'your_secret_key')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

    r = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    ums_db_name = os.environ.get("UMS_DB_NAME")
    ums_db_username = os.environ.get("UMS_DB_USERNAME")
    ums_db_password = os.environ.get("UMS_DB_PASSWORD")
    ums_db_port = os.environ.get("UMS_DB_PORT", 3306)
    ums_db_ip = os.environ.get("UMS_DB_IP")
    db_uri = f'mysql+pymysql://{ums_db_username}:{ums_db_password}@{ums_db_ip}:{ums_db_port}/{ums_db_name}'

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    db.init_app(app)

    with app.app_context():
        db.create_all()
    
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)

    return app, socketio, r, log

app, socketio, r, log = create_app()


@app.route('/noti/notifications/<user_id>', methods=['GET'])
def get_notifications(user_id):
    notifications = get_unread_notifications(user_id)
    return jsonify([notification.to_dict() for notification in notifications])

def get_unread_notifications(user_id):
    try:
        user_notifications = Notification.query.filter_by(user_id=user_id, read=False).all()
        return user_notifications
    except Exception as e:
        print(f"Error in get_unread_notifications: {str(e)}")
        return []

@app.route('/noti/mark-notifications-as-read/<id>', methods=['POST'])
def mark_notifications_as_read(id):
    try:
        user_notifications = Notification.query.get(id)
        db.session.delete(user_notifications)
        db.session.commit()
        return jsonify({"message": "Notifications marked as read successfully"})
    except Exception as e:
        print(f"Error in mark_notifications_as_read: {str(e)}")
        return jsonify({"error": "Failed to mark notifications as read"}), 500

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

def listen_for_notifications():
    while True:
        _, message = r.blpop('notifications')
        notification_data = json.loads(message)
        log.debug("Received notification: %s", notification_data)
        save_notification(notification_data)
        emit_socket_event()

def save_notification(notification_data):
    for notification_dict in notification_data:
        try:
            new_notification = Notification(
                video_id=notification_dict['video_id'],
                user_id=notification_dict['user_id'],
                read=False
            )
            db.session.add(new_notification)
        except Exception as e:
            print(f"Error in save_notification: {str(e)}")
    db.session.commit()

def emit_socket_event():
    socketio.emit('new-notification', "new noti")
    log.debug("Socket event emitted: %s", "new noti")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8081))
    socketio.start_background_task(target=listen_for_notifications)
    socketio.run(app, port=port, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)
