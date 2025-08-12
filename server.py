from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import os
import requests
from datetime import datetime
import re
from urllib.parse import urlparse
import mimetypes

app = Flask(__name__)
CORS(app)

# Database configuration
DB_PATH = 'messages.db'


def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def extract_channel_id_from_path(path):
    """Extract channel ID from Messages directory path"""
    # Extract channel ID from path like "Messages/c999471033436356628/"
    match = re.search(r'c(\d+)', path)
    if match:
        return match.group(1)
    return None

def get_file_type(url):
    """Determine file type from URL or filename"""
    if not url:
        return 'unknown'
    
    # Extract filename from URL
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type:
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type.startswith('text/'):
            return 'text'
        else:
            return 'document'
    
    # Fallback based on file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        return 'image'
    elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']:
        return 'video'
    elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
        return 'audio'
    elif ext in ['.txt', '.md', '.json', '.xml', '.html', '.css', '.js']:
        return 'text'
    else:
        return 'document'

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/api/messages')
def get_messages():
    """Get messages with pagination, filtering, and sorting"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)  # Reduced from 50 to 10
    search = request.args.get('search', '')
    channel_id = request.args.get('channel_id', '')
    guild_id = request.args.get('guild_id', '')
    file_type = request.args.get('file_type', '')
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'DESC')
    
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    
    # Build query with filters
    where_conditions = []
    params = []
    
    # Debug logging
    print(f"DEBUG: channel_id={channel_id}, guild_id={guild_id}, search={search}, file_type={file_type}")
    
    if search:
        where_conditions.append("(contents LIKE ? OR attachments LIKE ?)")
        params.extend([f'%{search}%', f'%{search}%'])
    
    if channel_id:
        where_conditions.append("m.channel_id = ?")
        params.append(int(channel_id))
    
    if guild_id:
        where_conditions.append("c.guild_id = ?")
        params.append(int(guild_id))
    
    if file_type and file_type != 'all':
        if file_type == 'image':
            where_conditions.append("(m.attachments LIKE '%.jpg%' OR m.attachments LIKE '%.jpeg%' OR m.attachments LIKE '%.png%' OR m.attachments LIKE '%.gif%' OR m.attachments LIKE '%.webp%' OR m.attachments LIKE '%.bmp%' OR m.attachments LIKE '%.svg%')")
        elif file_type == 'video':
            where_conditions.append("(m.attachments LIKE '%.mp4%' OR m.attachments LIKE '%.avi%' OR m.attachments LIKE '%.mov%' OR m.attachments LIKE '%.webm%' OR m.attachments LIKE '%.mkv%' OR m.attachments LIKE '%.wmv%' OR m.attachments LIKE '%.flv%')")
        elif file_type == 'audio':
            where_conditions.append("(m.attachments LIKE '%.mp3%' OR m.attachments LIKE '%.wav%' OR m.attachments LIKE '%.ogg%' OR m.attachments LIKE '%.flac%' OR m.attachments LIKE '%.m4a%' OR m.attachments LIKE '%.aac%')")
        elif file_type == 'document':
            where_conditions.append("(m.attachments LIKE '%.pdf%' OR m.attachments LIKE '%.doc%' OR m.attachments LIKE '%.docx%' OR m.attachments LIKE '%.txt%' OR m.attachments LIKE '%.zip%' OR m.attachments LIKE '%.rar%' OR m.attachments LIKE '%.7z%')")
        elif file_type == 'text':
            where_conditions.append("(m.attachments LIKE '%.txt%' OR m.attachments LIKE '%.md%' OR m.attachments LIKE '%.json%' OR m.attachments LIKE '%.xml%' OR m.attachments LIKE '%.html%' OR m.attachments LIKE '%.css%' OR m.attachments LIKE '%.js%')")
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # Debug logging
    print(f"DEBUG: where_clause={where_clause}")
    print(f"DEBUG: params={params}")
    
    # Validate sort parameters
    valid_sort_columns = ['id', 'timestamp', 'contents', 'attachments']
    if sort_by not in valid_sort_columns:
        sort_by = 'timestamp'
    
    if sort_order.upper() not in ['ASC', 'DESC']:
        sort_order = 'DESC'
    
    # Get total count
    count_query = f"""
        SELECT COUNT(*) 
        FROM messages m
        LEFT JOIN channels c ON m.channel_id = c.id
        WHERE {where_clause}
    """
    total_count = conn.execute(count_query, params).fetchone()[0]
    
    # Debug logging
    print(f"DEBUG: total_count={total_count}")
    
    # Get messages with sorting and join channel info
    query = f"""
        SELECT m.id, m.timestamp, m.contents, m.attachments, m.channel_id,
               c.name as channel_name, c.type as channel_type,
               g.name as guild_name
        FROM messages m
        LEFT JOIN channels c ON m.channel_id = c.id
        LEFT JOIN guilds g ON c.guild_id = g.id
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_order}
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    
    messages = []
    for row in conn.execute(query, params):
        message = dict(row)
        # Convert IDs to strings to prevent JavaScript number precision issues
        message['id'] = str(message['id'])
        message['channel_id'] = str(message['channel_id']) if message['channel_id'] else None
        
        # Process attachments
        attachments = []
        if message['attachments']:
            try:
                # Try to parse as JSON first
                if message['attachments'].startswith('['):
                    attachment_list = json.loads(message['attachments'])
                    for attachment in attachment_list:
                        if isinstance(attachment, dict):
                            attachments.append({
                                'url': attachment.get('url', ''),
                                'filename': attachment.get('filename', ''),
                                'file_type': get_file_type(attachment.get('url', ''))
                            })
                        else:
                            attachments.append({
                                'url': str(attachment),
                                'filename': os.path.basename(str(attachment)),
                                'file_type': get_file_type(str(attachment))
                            })
                else:
                    # Treat as single URL
                    attachments.append({
                        'url': message['attachments'],
                        'filename': os.path.basename(message['attachments']),
                        'file_type': get_file_type(message['attachments'])
                    })
            except json.JSONDecodeError:
                # Fallback: treat as single URL
                attachments.append({
                    'url': message['attachments'],
                    'filename': os.path.basename(message['attachments']),
                    'file_type': get_file_type(message['attachments'])
                })
        
        message['attachments'] = attachments
        messages.append(message)
    
    conn.close()
    
    return jsonify({
        'messages': messages,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page
        },
        'sorting': {
            'sort_by': sort_by,
            'sort_order': sort_order
        }
    })

@app.route('/api/channels')
def get_channels():
    """Get list of channels with their information, organized by guild"""
    conn = get_db_connection()
    
    # Get all channels with their message counts and guild info
    query = """
        SELECT 
            c.id,
            c.name,
            c.type,
            g.id as guild_id,
            g.name as guild_name,
            COUNT(m.id) as message_count
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
        LEFT JOIN guilds g ON c.guild_id = g.id
        GROUP BY c.id, c.name, c.type, g.id, g.name
        ORDER BY g.name, c.name
    """
    
    channels_by_guild = {}
    try:
        for row in conn.execute(query):
            guild_id = row[3]
            guild_name = row[4] or 'No Guild'
            
            if guild_name not in channels_by_guild:
                            channels_by_guild[guild_name] = {
                'guild_name': guild_name,
                'guild_id': str(guild_id) if guild_id else None,  # Convert to string to prevent JavaScript number precision issues
                'channels': []
            }
            
            channels_by_guild[guild_name]['channels'].append({
                'id': str(row[0]),  # Convert to string to prevent JavaScript number precision issues
                'name': row[1] or f'Channel {row[0]}',
                'type': row[2] or 'GUILD_TEXT',
                'message_count': row[5]
            })
    except Exception as e:
        print(f"Error loading channels: {e}")
        channels_by_guild = {}
    
    conn.close()
    
    return jsonify({'channels_by_guild': channels_by_guild})

@app.route('/api/guilds')
def get_guilds():
    """Get list of guilds with their channel counts"""
    conn = get_db_connection()
    
    query = """
        SELECT 
            g.id,
            g.name,
            COUNT(DISTINCT c.id) as channel_count,
            COUNT(m.id) as message_count
        FROM guilds g
        LEFT JOIN channels c ON g.id = c.guild_id
        LEFT JOIN messages m ON c.id = m.channel_id
        GROUP BY g.id, g.name
        ORDER BY message_count DESC
    """
    
    guilds = []
    try:
        for row in conn.execute(query):
            guilds.append({
                'id': str(row[0]),  # Convert to string to prevent JavaScript number precision issues
                'name': row[1] or 'Unknown Guild',
                'channel_count': row[2],
                'message_count': row[3]
            })
    except Exception as e:
        print(f"Error loading guilds: {e}")
        guilds = []
    
    conn.close()
    
    return jsonify({'guilds': guilds})

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    conn = get_db_connection()
    
    # Total messages
    total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    
    # Messages with attachments
    messages_with_attachments = conn.execute("SELECT COUNT(*) FROM messages WHERE attachments != ''").fetchone()[0]
    
    # Date range
    date_range = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages").fetchone()
    
    # File type breakdown - limit to avoid freezing
    file_types = {}
    for row in conn.execute("SELECT attachments FROM messages WHERE attachments != '' LIMIT 1000"):
        if row['attachments']:
            file_type = get_file_type(row['attachments'])
            file_types[file_type] = file_types.get(file_type, 0) + 1
    
    conn.close()
    
    return jsonify({
        'total_messages': total_messages,
        'messages_with_attachments': messages_with_attachments,
        'date_range': {
            'earliest': date_range[0],
            'latest': date_range[1]
        },
        'file_types': file_types
    })

@app.route('/api/messages/<int:message_id>')
def get_message(message_id):
    """Get a specific message by ID"""
    conn = get_db_connection()
    
    message = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    
    if not message:
        conn.close()
        return jsonify({'error': 'Message not found'}), 404
    
    message_dict = dict(message)
    
    # Process attachments (same logic as in get_messages)
    attachments = []
    if message_dict['attachments']:
        try:
            if message_dict['attachments'].startswith('['):
                attachment_list = json.loads(message_dict['attachments'])
                for attachment in attachment_list:
                    if isinstance(attachment, dict):
                        attachments.append({
                            'url': attachment.get('url', ''),
                            'filename': attachment.get('filename', ''),
                            'file_type': get_file_type(attachment.get('url', ''))
                        })
                    else:
                        attachments.append({
                            'url': str(attachment),
                            'filename': os.path.basename(str(attachment)),
                            'file_type': get_file_type(str(attachment))
                        })
            else:
                attachments.append({
                    'url': message_dict['attachments'],
                    'filename': os.path.basename(message_dict['attachments']),
                    'file_type': get_file_type(message_dict['attachments'])
                })
        except json.JSONDecodeError:
            attachments.append({
                'url': message_dict['attachments'],
                'filename': os.path.basename(message_dict['attachments']),
                'file_type': get_file_type(message_dict['attachments'])
            })
    
    message_dict['attachments'] = attachments
    conn.close()
    
    return jsonify(message_dict)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("Discord Message Viewer Server")
    print("=" * 40)
    print(f"Database: {DB_PATH}")
    print("=" * 40)
    print("Starting server on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
