import streamlit as st
import os
import base64
import shutil
import csv
import json
from PIL import Image
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import tempfile
import webbrowser
import socket
import subprocess
import platform

class StreamlitEmailComposer:
    def __init__(self):
        self.setup_session_state()
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        self.sender_email = 'maropeng.mbele@gmail.com'
        
        # Create temp directory for images
        self.temp_dir = tempfile.mkdtemp()
        self.images_folder = os.path.join(self.temp_dir, 'images')
        os.makedirs(self.images_folder, exist_ok=True)
        
    def setup_session_state(self):
        if 'images' not in st.session_state:
            st.session_state.images = {}
        if 'image_counter' not in st.session_state:
            st.session_state.image_counter = 0
        if 'content' not in st.session_state:
            st.session_state.content = ""
            
    def create_gui(self):
        st.title("Email Composer and Sender")
        
        # Subject input
        subject = st.text_input("Subject", value="Hypebeast Weekly Digest")
        
        # Create columns for editor and image sidebar
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Text editor
            content = st.text_area("Email Content", 
                                 value=st.session_state.content,
                                 height=400)
            st.session_state.content = content
            
            # Save and load buttons
            col1_1, col1_2, col1_3 = st.columns(3)
            with col1_1:
                if st.button("Save Content"):
                    self.save_content(content, subject)
            with col1_2:
                if st.button("Load Content"):
                    self.load_content()
            with col1_3:
                if st.button("Send Emails"):
                    self.send_emails(content, subject)
        
        with col2:
            # Image uploader
            uploaded_files = st.file_uploader("Upload Images", 
                                           type=['png', 'jpg', 'jpeg', 'gif'],
                                           accept_multiple_files=True)
            
            if uploaded_files:
                self.handle_uploaded_files(uploaded_files)
            
            # Display uploaded images
            self.display_images()
    
    def handle_uploaded_files(self, files):
        for file in files:
            # Save file to temp directory
            file_path = os.path.join(self.images_folder, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getvalue())
            
            # Create image placeholder
            st.session_state.image_counter += 1
            image_id = f"image_{st.session_state.image_counter}"
            st.session_state.images[image_id] = file_path
            
            # Show success message
            st.success(f"Image {file.name} uploaded successfully!")
    
    def display_images(self):
        for image_id, image_path in st.session_state.images.items():
            if os.path.exists(image_path):
                img = Image.open(image_path)
                st.image(img, caption=f"Click to copy ID: [{image_id}]", width=150)
    
    def find_browser(self):
        """Enhanced browser detection with fallback options."""
        system = platform.system().lower()
        
        # First try webbrowser module's default browser
        try:
            if webbrowser.get():
                return 'default'
        except:
            pass

        # System-specific browser paths
        if system == 'windows':
            browsers = {
                'chrome': [
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                ],
                'firefox': [
                    r'C:\Program Files\Mozilla Firefox\firefox.exe',
                    r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe',
                ],
                'edge': [
                    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                ]
            }
            
            # Check Windows Registry for browser paths
            try:
                import winreg
                for browser in ['chrome', 'firefox', 'edge']:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                          rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{browser}.exe') as key:
                            path = winreg.QueryValue(key, None)
                            if os.path.exists(path):
                                return path
                    except:
                        continue
            except:
                pass

        elif system == 'darwin':  # macOS
            browsers = {
                'chrome': [
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    '~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                ],
                'firefox': [
                    '/Applications/Firefox.app/Contents/MacOS/firefox',
                    '~/Applications/Firefox.app/Contents/MacOS/firefox'
                ],
                'safari': [
                    '/Applications/Safari.app/Contents/MacOS/Safari'
                ]
            }
        else:  # Linux
            browsers = {
                'chrome': ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'],
                'firefox': ['firefox', 'firefox-esr'],
                'edge': ['microsoft-edge']
            }

        # Try finding browsers based on system
        if system in ['darwin', 'windows']:
            for browser_paths in browsers.values():
                for path in browser_paths:
                    expanded_path = os.path.expanduser(path)
                    if os.path.exists(expanded_path):
                        return expanded_path
        else:  # Linux and others
            for browser_cmds in browsers.values():
                for cmd in browser_cmds:
                    try:
                        browser_path = subprocess.check_output(['which', cmd], 
                                                            stderr=subprocess.STDOUT).decode().strip()
                        if browser_path:
                            return browser_path
                    except:
                        continue

        # Final fallback: try xdg-open on Linux
        if system == 'linux':
            try:
                xdg_path = subprocess.check_output(['which', 'xdg-open'], 
                                                stderr=subprocess.STDOUT).decode().strip()
                if xdg_path:
                    return xdg_path
            except:
                pass

        return None

    def authenticate_gmail(self):
        """Enhanced Gmail authentication with improved browser handling."""
        try:
            creds = None
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Get client config from secrets
                    client_config = json.loads(st.secrets["google"]["client_config"])
                    
                    # Save config to temporary file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
                        json.dump(client_config, config_file)
                        config_file_path = config_file.name

                    try:
                        # Find available browser
                        browser_path = self.find_browser()
                        
                        def browser_opener(url):
                            try:
                                if browser_path == 'default':
                                    webbrowser.open(url)
                                elif platform.system().lower() == 'linux' and 'xdg-open' in browser_path:
                                    subprocess.run(['xdg-open', url])
                                elif platform.system().lower() != 'windows':
                                    subprocess.run([browser_path, url])
                                else:
                                    subprocess.run([browser_path, url], shell=True)
                                
                                st.info(f"""
                                If a browser window didn't open automatically, please manually copy and paste this URL:
                                {url}
                                """)
                            except Exception as e:
                                st.error(f"Failed to open browser automatically: {str(e)}")
                                st.info(f"""
                                Please manually copy and paste this URL in your browser:
                                {url}
                                """)

                        # Configure the flow with the custom browser opener
                        flow = InstalledAppFlow.from_client_secrets_file(
                            config_file_path, 
                            self.SCOPES,
                            redirect_uri='http://localhost:0'
                        )
                        
                        # Try to run the local server with increased timeout
                        flow.run_local_server(
                            port=0,
                            browser_opener=browser_opener,
                            timeout_seconds=300
                        )
                        creds = flow.credentials

                        # Save the credentials
                        with open('token.json', 'w') as token:
                            token.write(creds.to_json())

                    finally:
                        # Clean up temporary config file
                        os.unlink(config_file_path)

            return creds

        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            st.info("""
            If you're having trouble with authentication:
            1. Make sure you have a web browser installed
            2. Try clearing your browser cache and cookies
            3. Check if you have a working internet connection
            4. Ensure you're using a supported browser (Chrome, Firefox, Edge, or Safari)
            """)
            raise
    
    def create_message_with_attachments(self, to, html_content, image_paths, subject):
        message = MIMEMultipart()
        message['From'] = self.sender_email
        message['To'] = to
        message['Subject'] = subject

        html_part = MIMEText(html_content, 'html')
        message.attach(html_part)

        for i, image_path in enumerate(image_paths):
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                subtype = os.path.splitext(image_path)[1][1:]
                image_mime = MIMEImage(img_data, _subtype=subtype)
                image_mime.add_header('Content-ID', f'<image{i + 1}>')
                image_mime.add_header('Content-Disposition', 'inline', 
                                    filename=os.path.basename(image_path))
                message.attach(image_mime)

        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
    
    def construct_html(self, content, recipient_name):
        html_content = "<html><body>"
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Replace recipient placeholders
            line = line.replace("{full name}", recipient_name['full'])
            line = line.replace("{first name}", recipient_name['first'])
            line = line.replace("{last name}", recipient_name['last'])
            
            # Check for image placeholders
            match = re.search(r'\[image_(\d+)\]', line)
            if match:
                image_id = f"image_{match.group(1)}"
                if image_id in st.session_state.images:
                    html_content += f'<img src="cid:image{list(st.session_state.images.keys()).index(image_id) + 1}" style="width:100%;max-width:600px;"><br><br>'
            elif line.startswith("# "):
                html_content += f'<h1>{line[2:]}</h1>'
            elif line.startswith("## "):
                html_content += f'<h2>{line[3:]}</h2>'
            elif line.startswith("### "):
                html_content += f'<h3>{line[4:]}</h3>'
            else:
                html_content += f'<p>{line}</p><br>'
        
        html_content += "</body></html>"
        return html_content
    
    def send_emails(self, content, subject):
        try:
            # Save current content
            self.save_content(content, subject)
            
            # Show authentication message
            st.info("Please authenticate with Google when the browser window opens...")
            
            # Authenticate Gmail with enhanced error handling
            creds = self.authenticate_gmail()
            if not creds:
                st.error("Authentication failed. Please try again.")
                return
                
            service = build('gmail', 'v1', credentials=creds)
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Read recipient list
            with open('list.csv', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                total_recipients = sum(1 for _ in reader)
                csvfile.seek(0)
                next(reader)  # Skip header row
                
                sent_count = 0
                for row in reader:
                    first_name = row['Names'].split()[0]
                    last_name = row['Names'].split()[-1]
                    recipient_name = {
                        'full': row['Names'],
                        'first': first_name,
                        'last': f"{first_name[0]}. {last_name}"
                    }
                    
                    html_content = self.construct_html(content, recipient_name)
                    image_paths = list(st.session_state.images.values())
                    
                    message = self.create_message_with_attachments(
                        row['Emails'], html_content, image_paths, subject)
                    
                    try:
                        service.users().messages().send(
                            userId='me', body=message).execute()
                        sent_count += 1
                        
                        # Update progress
                        progress = (sent_count / total_recipients)
                        progress_bar.progress(progress)
                        status_text.text(
                            f"Sent {sent_count} of {total_recipients} emails...")
                        
                    except Exception as e:
                        st.error(f"Failed to send to {row['Emails']}: {str(e)}")
            
            # Show success message
            st.success(f"Successfully sent emails to {sent_count} recipients!")
            
            # Cleanup
            if os.path.exists('token.json'):
                os.remove('token.json')
            
        except Exception as e:
            st.error(f"Failed to send emails: {str(e)}")
            st.info("If you're having authentication issues, try clearing your browser cache and cookies, then try again.")
    
    def save_content(self, content, subject):
        try:
            # Save content
            with open('weekly_digest.txt', 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Save images and subject
            settings = {
                'images': st.session_state.images,
                'subject': subject
            }
            
            with open('image_mappings.json', 'w') as f:
                json.dump(settings, f)
            
            st.success("Content saved successfully!")
            
        except Exception as e:
            st.error(f"Failed to save content: {str(e)}")
    
    def load_content(self):
        try:
            if os.path.exists('image_mappings.json'):
                with open('image_mappings.json', 'r') as f:
                    settings = json.load(f)
                    st.session_state.images = settings.get('images', {})
            
            if os.path.exists('weekly_digest.txt'):
                with open('weekly_digest.txt', 'r', encoding='utf-8') as f:
                    st.session_state.content = f.read()
            
            st.success("Content loaded successfully!")
            
        except Exception as e:
            st.error(f"Failed to load content: {str(e)}")

def main():
    app = StreamlitEmailComposer()
    app.create_gui()

if __name__ == "__main__":
    main()