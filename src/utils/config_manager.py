import os
import json

app_data_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'RensaConverter')

if not os.path.exists(app_data_dir):
    try:
        os.makedirs(app_data_dir)
    except:
        pass

CONFIG_FILE = os.path.join(app_data_dir, "rensa_converter_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"show_tutorial": True}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Gagal menyimpan konfigurasi: {e}")
