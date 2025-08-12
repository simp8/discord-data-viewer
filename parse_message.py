

import sqlite3
import json
import os

sqlite_connection = sqlite3.connect('messages.db')
cursor = sqlite_connection.cursor()

# Drop and recreate table to add channel_id column
cursor.execute('''DROP TABLE IF EXISTS messages''')
cursor.execute('''DROP TABLE IF EXISTS channels''')
cursor.execute('''DROP TABLE IF EXISTS guilds''')
cursor.execute('''CREATE TABLE guilds (id INTEGER PRIMARY KEY, name TEXT)''')
cursor.execute('''CREATE TABLE channels (id INTEGER PRIMARY KEY, name TEXT, type TEXT, guild_id INTEGER, FOREIGN KEY(guild_id) REFERENCES guilds(id))''')
cursor.execute('''CREATE TABLE messages (id INTEGER PRIMARY KEY, timestamp TEXT, contents TEXT, attachments TEXT, channel_id INTEGER, FOREIGN KEY(channel_id) REFERENCES channels(id))''')
sqlite_connection.commit()
# Process all directories to populate guilds and channels first
guilds_seen = set()
channels_seen = set()

for item in os.listdir('Messages/'):
    try:
        messages_path = os.path.join('Messages', item, 'messages.json')
        channel_path = os.path.join('Messages', item, 'channel.json')
        
        if os.path.isdir(os.path.join('Messages', item)) and os.path.exists(messages_path):
            # Read channel.json to get channel and guild info
            channel_id = None
            channel_name = None
            channel_type = None
            guild_id = None
            guild_name = None
            
            if os.path.exists(channel_path):
                try:
                    with open(channel_path, 'r', encoding='utf-8') as f:
                        channel_data = json.load(f)
                        channel_id = channel_data.get('id')
                        channel_name = channel_data.get('name')
                        channel_type = channel_data.get('type')
                        
                        # Get guild info if available
                        guild_data = channel_data.get('guild')
                        if guild_data:
                            guild_id = guild_data.get('id')
                            guild_name = guild_data.get('name')
                except Exception as e:
                    print(f"Error reading channel.json in {item}: {e}")
            
          
            
            # If no channel.json, extract from folder name
            if not channel_id:
                if item.startswith('c') and item[1:].isdigit():
                    channel_id = item[1:]
                else:
                    channel_id = item
            
            # Insert guild if not seen before and guild info exists
            if guild_id and guild_id not in guilds_seen:
                try:
                    cursor.execute('''INSERT OR IGNORE INTO guilds (id, name) VALUES (?, ?)''', (guild_id, guild_name))
                    guilds_seen.add(guild_id)
                except Exception as e:
                    print(f"Error inserting guild {guild_id}: {e}")
            
            # Insert channel if not seen before
            if channel_id and channel_id not in channels_seen:
                try:
                    cursor.execute('''INSERT OR IGNORE INTO channels (id, name, type, guild_id) VALUES (?, ?, ?, ?)''', 
                                 (channel_id, channel_name, channel_type, guild_id))
                    channels_seen.add(channel_id)
                except Exception as e:
                    print(f"Error inserting channel {channel_id}: {e}")
            
            # Insert messages
            with open(messages_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for message in data:
                    cursor.execute('''INSERT INTO messages (id, timestamp, contents, attachments, channel_id) VALUES (?, ?, ?, ?, ?)''', 
                                 (message['ID'], message['Timestamp'], message['Contents'], message['Attachments'] if message['Attachments'] else '', channel_id))
            
            sqlite_connection.commit()  # Commit after each directory
            print(f"Processed messages from {item} (Channel ID: {channel_id})")
        else:
            print(f"Skipping {item} - not a directory or no messages.json found")
    except FileNotFoundError:
        print(f"Error: messages.json not found in {item}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {item}/messages.json - {e}")
    except KeyError as e:
        print(f"Error: Missing required field {e} in {item}/messages.json")
    except Exception as e:
        print(f"Error processing {item}: {type(e).__name__} - {e}")

sqlite_connection.close()