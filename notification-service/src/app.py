from flask import Flask, jsonify
from flask_socketio import SocketIO
from redis import Redis
from flask_cors import CORS
import os
import json
from flask_sqlalchemy import SQLAlchemy
from database import Notification

app = Flask(__name__)
socketio = SocketIO(app)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", 'your_secret_key')
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

r = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
db = SQLAlchemy(app)

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

@app.route('/noti/mark-notifications-as-read/<user_id>', methods=['POST'])
def mark_notifications_as_read(user_id):
    try:
        user_notifications = Notification.query.filter_by(user_id=user_id, read=False).all()

        for notification in user_notifications:
            notification.read = True

        db.session.commit()
    except Exception as e:
        print(f"Error in mark_notifications_as_read: {str(e)}")

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
        emit_socket_event(notification_data)

def emit_socket_event(notification_data):
    socketio.emit('new-notification', {'notification': notification_data}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8081))
    socketio.start_background_task(target=listen_for_notifications)
    socketio.run(app, port=port, debug=True, host='0.0.0.0')
