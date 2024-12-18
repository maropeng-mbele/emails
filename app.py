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
import pickle

class EmailComposerAndSender:
    def __init__(self):
        self.setup_session_state()
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        self.sender_email = 'maropeng.mbele@gmail.com'
        
        # Create temp directory for images if it doesn't exist
        if not os.path.exists(self.get_images_folder()):
            os.makedirs(self.get_images_folder())
            
    def get_images_folder(self):
        return os.path.join(tempfile.gettempdir(), 'streamlit_email_images')
        
    def setup_session_state(self):
        if 'images' not in st.session_state:
            st.session_state.images = {}
        if 'image_counter' not in st.session_state:
            st.session_state.image_counter = 0
        if 'content' not in st.session_state:
            st.session_state.content = ""
        if 'subject' not in st.session_state:
            st.session_state.subject = "Type Subject Here"
        if 'credentials' not in st.session_state:
            st.session_state.credentials = None
            
    def create_gui(self):
        st.title("Email Composer and Sender")
        
        # Sidebar
        with st.sidebar:
            st.header("Images")
            uploaded_files = st.file_uploader("Upload Images", 
                                           type=['png', 'jpg', 'jpeg', 'gif'],
                                           accept_multiple_files=True)
            
            if uploaded_files:
                self.handle_uploaded_files(uploaded_files)
                
            # Display uploaded images
            self.display_image_gallery()
        
        # Main content area
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Subject field
            st.session_state.subject = st.text_input("Subject", 
                                                   value=st.session_state.subject)
            
            # Text editor
            st.session_state.content = st.text_area("Email Content", 
                                                  value=st.session_state.content,
                                                  height=400)
            
            # Action buttons
            col3, col4, col5 = st.columns(3)
            with col3:
                if st.button("Save Content"):
                    self.save_content()
            with col4:
                if st.button("Load Content"):
                    self.load_content()
            with col5:
                if st.button("Send Emails"):
                    self.send_emails()
                    
    def handle_uploaded_files(self, files):
        for uploaded_file in files:
            # Save file to temp directory
            file_path = os.path.join(self.get_images_folder(), uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Create image placeholder
            st.session_state.image_counter += 1
            image_id = f"image_{st.session_state.image_counter}"
            st.session_state.images[image_id] = file_path
            
            # Insert placeholder text
            if st.session_state.content:
                st.session_state.content += f"\n[{image_id}]\n"
            else:
                st.session_state.content = f"[{image_id}]\n"
                
    def display_image_gallery(self):
        if st.session_state.images:
            st.write("Click image to insert:")
            cols = st.columns(2)
            for idx, (image_id, image_path) in enumerate(st.session_state.images.items()):
                with cols[idx % 2]:
                    if os.path.exists(image_path):
                        image = Image.open(image_path)
                        st.image(image, width=100)
                        if st.button(f"Insert {image_id}", key=f"btn_{image_id}"):
                            self.insert_image_placeholder(image_id)
                            
    def insert_image_placeholder(self, image_id):
        if st.session_state.content:
            st.session_state.content += f"\n[{image_id}]\n"
        else:
            st.session_state.content = f"[{image_id}]\n"
            
    def authenticate_gmail(self):
        """Modified authentication flow for Streamlit using secrets"""
        creds = None
        
        # Try to load credentials from session state first
        if st.session_state.credentials:
            creds = st.session_state.credentials
            
        # Try to load credentials from pickle file
        elif os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials exist but are invalid or expired
        if creds and not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            else:
                creds = None
                
        # If no valid credentials exist, start OAuth flow
        if not creds:
            try:
                # Create client config dictionary from secrets
                client_config = {
                    "web": {
                        "client_id": st.secrets.google["client_id"],
                        "project_id": st.secrets.google["project_id"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_secret": st.secrets.google["client_secret"],
                        "redirect_uris": ["http://localhost:8501"]
                    }
                }
                
                # Create flow using client config dictionary
                flow = InstalledAppFlow.from_client_config(
                    client_config,
                    self.SCOPES,
                    redirect_uri="http://localhost:8501"
                )
                
                # Generate authorization URL
                auth_url, _ = flow.authorization_url(
                    access_type='offline',
                    include_granted_scopes='true'
                )
                
                # Display authentication instructions
                st.markdown("""
                    ### Gmail Authentication Steps:
                    1. Make sure this Streamlit app is running on port 8501
                    2. Click the link below to authorize
                    3. After authorizing, you'll be redirected back to this app
                    4. If you see a "This site can't be reached" error, copy the full URL and paste it below
                    5. Click the 'Complete Authentication' button
                """)
                
                st.markdown(f"[Click here to authorize]({auth_url})")
                
                # Create columns for better layout
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    authorization_response = st.text_input(
                        "Paste the full redirect URL here:",
                        help="After authorizing, copy and paste the entire URL from your browser"
                    )
                
                with col2:
                    process_auth = st.button("Complete Authentication")
                
                if authorization_response and process_auth:
                    try:
                        # Extract the authorization code from the URL
                        from urllib.parse import urlparse, parse_qs
                        parsed = urlparse(authorization_response)
                        code = parse_qs(parsed.query)['code'][0]
                        
                        # Exchange code for credentials
                        flow.fetch_token(code=code)
                        creds = flow.credentials
                        
                        # Save credentials to session state
                        st.session_state.credentials = creds
                        
                        # Save credentials to pickle file
                        with open('token.pickle', 'wb') as token:
                            pickle.dump(creds, token)
                            
                        st.success("Successfully authenticated!")
                        st.experimental_rerun()
                        
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")
                        st.error("Please make sure you copied the entire URL including the 'code' parameter")
                        return None
                    
            except Exception as e:
                st.error(f"Failed to start authentication flow: {str(e)}")
                return None
                
        return creds
        
    def create_message_with_attachments(self, to, html_content, image_paths):
        message = MIMEMultipart()
        message['From'] = self.sender_email
        message['To'] = to
        message['Subject'] = st.session_state.subject

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
        
    def send_emails(self):
        try:
            # Save content first
            self.save_content()
            
            # Authenticate Gmail
            creds = self.authenticate_gmail()
            if not creds:
                st.warning("Please complete the authentication process first.")
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
                    
                    html_content = self.construct_html(recipient_name)
                    image_paths = [st.session_state.images[img_id] 
                                for img_id in st.session_state.images]
                    
                    message = self.create_message_with_attachments(
                        row['Emails'], html_content, image_paths)
                    
                    try:
                        service.users().messages().send(
                            userId='me', body=message).execute()
                        sent_count += 1
                        progress = (sent_count / total_recipients)
                        progress_bar.progress(progress)
                        status_text.text(
                            f"Sent {sent_count} of {total_recipients} emails")
                    except Exception as e:
                        st.error(f"Failed to send to {row['Emails']}: {str(e)}")
                        
            # Make backup and cleanup
            self.make_backup()
            
            st.success(f"Successfully sent emails to {sent_count} recipients!")
            
        except Exception as e:
            st.error(f"Failed to send emails: {str(e)}")
            
    def construct_html(self, recipient_name):
        content = st.session_state.content
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
        
    def make_backup(self):
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        original_file = 'weekly_digest.txt'
        backup_file = f'weekly_digest_{current_time}.txt'
        shutil.copy(original_file, backup_file)

    def delete_token_file(self):
        if os.path.exists('token.json'):
            os.remove('token.json')
            
    def save_content(self):
        try:
            with open('weekly_digest.txt', 'w', encoding='utf-8') as f:
                f.write(st.session_state.content)
            
            # Save images and subject
            settings = {
                'images': st.session_state.images,
                'subject': st.session_state.subject
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
                    st.session_state.subject = settings.get(
                        'subject', 'Hypebeast Weekly Digest')
            
            if os.path.exists('weekly_digest.txt'):
                with open('weekly_digest.txt', 'r', encoding='utf-8') as f:
                    st.session_state.content = f.read()
            
            st.success("Content loaded successfully!")
            
        except Exception as e:
            st.error(f"Failed to load content: {str(e)}")

def main():
    app = EmailComposerAndSender()
    app.create_gui()

if __name__ == "__main__":
    main()