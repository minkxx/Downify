import os
import sys
import getpass
import threading
import requests
import re
import logging
import json
import time
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from io import BytesIO
from PIL import Image

import yt_dlp
import pytube
import customtkinter as ctk
from customtkinter import filedialog

__VERSION__ = "0.1.1"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Initialize logging
logging.basicConfig(
    filename=resource_path("app.logs"),
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filemode="a"
)

# Create a logger object
logger = logging.getLogger(__name__)

current_windows_username = getpass.getuser()

def create_dir(path):
    if not os.path.exists(path):
        os.mkdir(path)
        logger.info(f"Created: {path}")

def clear_temp():
    temp_path = resource_path("temp")
    for i in os.listdir(temp_path):
        os.remove(os.path.join(temp_path, i))
    logger.info(f"Cleared temp directory: {temp_path}")

def convertToMP3(file_path):
    prt = file_path.split(".")
    ext = prt[-1]
    if ext != "mp3":
        os.rename(file_path, f"{prt[0]}.mp3")
        logger.info(f"Converted {file_path} to MP3.")

def init_settings(path):
    data = {"download_path":"", "appearence":"", "theme":"", "version":__VERSION__}
    if not os.path.exists(path):
        with open(path, 'w') as f:
            json.dump(data, f)
        logger.info(f"Created: 'settings.json'")

def load_settings():
    file = "settings.json"
    init_settings(file)
    with open(file, "r") as f:
        data = json.load(f)
    return data

def save_settings(key, value):
    file = "settings.json"
    data = load_settings()
    data[key] = value
    with open(file, "w") as f:
        json.dump(data, f)

def restart_app():
        logger.info("Restarting application...")
        python = sys.executable
        os.execl(python, python, *sys.argv)

def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloading: {d['_percent_str']} of {d['_total_bytes_str']} at {d['_speed_str']} ETA: {d['_eta_str']}")
    elif d['status'] == 'finished' :
        print("Download completed!")
    elif d['status'] == 'error':
        print("Error during download!")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("600x380")
        self.title("Downify")
        self.resizable(False, False)
        self.iconbitmap(resource_path("assets\\ico_icons\\spotify_512px.ico"))
        if load_settings()["appearence"] == "":
            save_settings("appearence", "system")
        
        ctk.set_appearance_mode(load_settings()["appearence"])

        self.themes = []
        self.themes_path = {}
        themes_dir = resource_path("assets\\themes")
        for i in os.listdir(themes_dir):
            name = i.split(".")[0]
            path = os.path.join(themes_dir, i)
            self.themes.append(name)
            self.themes_path[name] = path

        if load_settings()["theme"] == "":
            save_settings("theme", "Blue")

        ctk.set_default_color_theme(self.themes_path[str(load_settings()["theme"])])

        if load_settings()["download_path"] == "":
            save_settings("download_path", f"C:/Users/{current_windows_username}/Downloads")

        self.download_path = ctk.StringVar(value=load_settings()["download_path"])
        self.output_var = ctk.StringVar()
        self.progress_var = ctk.StringVar(value="0 %")
        self.url_var = ctk.StringVar()

        self.thread_running = False
        self.total_items = 0
        self.processed_items = 0
        self.regex = r"^(https:\/\/open.spotify.com\/)(.*)$"

        self.create_widgets()
        logger.info("Application started.")

    def create_widgets(self):
        # Create the menu bar using tkinter
        menu_bar = tk.Menu(self)
        
        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open path", command=self.browse_path)
        file_menu.add_command(label="Paste clipboard", command=self.paste_path)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        # Settings menu
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        appearance_menu = tk.Menu(settings_menu, tearoff=0)
        appearance_menu.add_radiobutton(label="System", command=lambda: self.set_appearence("system"))
        appearance_menu.add_radiobutton(label="Light", command=lambda: self.set_appearence("light"))
        appearance_menu.add_radiobutton(label="Dark", command=lambda: self.set_appearence("dark"))
        
        theme_menu = tk.Menu(settings_menu, tearoff=0)
        for theme in self.themes:
            theme_menu.add_radiobutton(label=theme, command=lambda t=theme: self.set_theme(t))

        settings_menu.add_cascade(label="Appearance", menu=appearance_menu)
        settings_menu.add_cascade(label="Theme", menu=theme_menu)
        settings_menu.add_command(label="Restart", command=restart_app)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)

        # About Us menu
        about_menu = tk.Menu(menu_bar, tearoff=0)
        about_menu.add_command(label="About Us", command=self.show_about)
        menu_bar.add_cascade(label="About Us", menu=about_menu)

        # Configure the menu bar
        self.config(menu=menu_bar)

        # URL entry
        self.url_entry = ctk.CTkEntry(self, placeholder_text="Enter URL to download", font=("Inter", 12), width=425, textvariable=self.url_var)
        self.url_entry.place(x=50, y=90)

        # Paste button
        self.dir_browse_btn = ctk.CTkButton(self, text="Paste", command=self.paste_path, width=70)
        self.dir_browse_btn.place(x=480, y=90)

        # Download path entry
        self.dir_path_entry = ctk.CTkEntry(self, placeholder_text="Download path", font=("Inter", 12), width=425, textvariable=self.download_path)
        self.dir_path_entry.place(x=50, y=140)

        # Browse button
        self.dir_browse_btn = ctk.CTkButton(self, text="Browse", command=self.browse_path, width=70)
        self.dir_browse_btn.place(x=480, y=140)

        # Download button
        self.download_btn = ctk.CTkButton(self, text="Download", command=self.download, width=100)
        self.download_btn.place(x=250, y=190)

        # Output label
        self.output_label = ctk.CTkLabel(self, text="test", fg_color="transparent", font=("Inter", 12), textvariable=self.output_var)
        self.output_label.place(x=136, y=250)

        # Image label
        self.image_label = ctk.CTkLabel(self, text="")
        self.image_label.place(x=20, y=250)

        # Progress bar
        self.progressbar = ctk.CTkProgressBar(self, width=300, height=10)
        self.progressbar.set(0)

        # Progress label
        self.progress_label = ctk.CTkLabel(self, text="%", fg_color="transparent", font=("Inter", 14), textvariable=self.progress_var)

    # UI functions

    def set_appearence(self, choice):
        save_settings("appearence", choice)
        ctk.set_appearance_mode(load_settings()["appearence"])
        logger.info(f"Appearence changed to: {choice}")

    def set_theme(self, choice):
        save_settings("theme", choice)
        ctk.set_default_color_theme(self.themes_path[str(load_settings()["theme"])])
        logger.info(f"Theme changed to: {choice}")
        time.sleep(1)
        restart_app()

    def browse_path(self):
        try:
            download_directory = filedialog.askdirectory(initialdir=self.download_path.get(), title="Select Download Directory")
            self.download_path.set(download_directory)
            save_settings("download_path", download_directory)
            logger.info(f"User selected download path: {download_directory}")
        except Exception as e:
            logger.error(f"Error browsing path: {e}", exc_info=True)
            self.output_var.set("Error selecting download path.")

    def show_about(self):
        messagebox.showinfo("About Us", f"Downify {load_settings()['version']}\nCreated by Monsur\nVisit us at https://minkxx.is-a.dev")

    def paste_path(self):
        try:
            clipboard_content = self.clipboard_get()
            self.url_var.set(clipboard_content)
            logger.info(f"Pasted URL: {clipboard_content}")
        except Exception as e:
            logger.error(f"Error pasting from clipboard: {e}", exc_info=True)
            self.output_var.set("Error pasting clipboard content.")

    def reset_ui(self):
        self.progressbar.set(0)
        self.progress_var.set("0 %")
        self.url_var.set("")
        self.url_entry.configure(state="normal")
        self.download_btn.configure(state="normal")
        self.progressbar.place_forget()
        self.progress_label.place_forget()
        self.image_label.configure(image=None)
        self.thread_running = False
        clear_temp()

    def update_progress(self):
        if self.total_items > 0:
            progress = (self.processed_items / self.total_items) * 100
            self.progressbar.set(progress / 100)
            self.progress_var.set(f"{int(progress)} %")
            self.update()
            logger.info(f"Progress updated: {int(progress)} %")

    # Download functions

    def download_audio(self, url, output_path):
        ydl_opts = {
            'format': 'bestaudio/best',              # Select best audio
            'extract_audio': True,                   # Extract audio
            'audio_format': 'mp3',                   # Convert to mp3
            'progress_hooks': [progress_hook],       # Attach the progress hook
            'quiet': True,                         # Suppress all other output
            'no_warnings': True,                   # Disable warnings
            'outtmpl': output_path + '/%(title)s.%(ext)s',  # Save to user-defined path
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def download(self):
        create_dir(resource_path("temp"))
        if self.thread_running:
            return

        self.thread_running = True
        self.progressbar.place(x=150, y=300)
        self.progress_label.place(x=460, y=290)
        self.url_entry.configure(state="disabled")
        self.download_btn.configure(state="disabled")

        link = self.url_var.get()
        if not re.search(self.regex, link):
            self.output_var.set("Not a valid Spotify link.")
            logger.warning(f"Invalid Spotify link: {link}")
            self.reset_ui()
            return

        try:
            track_type, track_id = link.split("/")[-2:]
        except ValueError as e:
            logger.error(f"Error parsing Spotify link: {e}", exc_info=True)
            self.output_var.set("Error parsing Spotify link.")
            self.reset_ui()
            return

        if track_type == "track":
            self.start_download_track_thread(track_type, track_id)
        elif track_type == "album":
            self.start_download_album_thread(track_type, track_id)
        elif track_type == "playlist":
            self.start_download_playlist_thread(track_type, track_id)

    

    def download_track(self, track_type, track_id):
        try:
            res = requests.get(f"https://spotipy-api.vercel.app/spotipy?type={track_type}&id={track_id}")
            data = res.json()

            name = data["track_name"]
            artists = data["artists"]

            thumbnail_url = data["images"][1]["url"]
            self.download_thumbnail(thumbnail_url)

            self.output_var.set(f"Downloading : {name} {artists}")
            logger.info(f"Starting download: {name} by {artists}")

            query = pytube.Search(f"{name} {artists}")
            yt = query.results[0]
            yt_url = yt.watch_url

            try:
                self.download_audio(yt_url, self.download_path.get())
                logger.info(f"Downloaded {name} by {artists}.")
            except Exception as e:
                logger.error(f"Error downloading {name}: {e}", exc_info=True)

            self.output_var.set(f"Downloaded : {name} {artists}")
            time.sleep(1)
            self.output_var.set("")

        except Exception as e:
            logger.error(f"Error downloading track: {e}", exc_info=True)
            self.output_var.set("Error downloading track")

        finally:
            self.processed_items += 1
            self.update_progress()
            self.reset_ui()

    def start_download_track_thread(self, track_type, track_id):
        track_thread = threading.Thread(target=self.download_track, args=(track_type, track_id))
        track_thread.start()

    def download_album(self, track_type, track_id):
        try:
            res = requests.get(f"https://spotipy-api.vercel.app/spotipy?type={track_type}&id={track_id}")
            data = res.json()

            album_name = data["album_name"]
            tracks = data["tracks"]
            self.total_items = len(tracks)
            self.processed_items = 0

            thumbnail_url = data["images"][1]["url"]
            self.download_thumbnail(thumbnail_url)

            for track in tracks:
                try:
                    query = pytube.Search(f"{track['track_name']} {track['artists']}")
                    self.output_var.set(f"Downloading : {track['track_name']} {track['artists']}")
                    logger.info(f"Downloading track: {track['track_name']} by {track['artists']}")

                    yt = query.results[0]
                    yt_url = yt.watch_url
                    try:
                        self.download_audio(
                            url=yt_url,
                            output_path=os.path.join(self.download_path.get(), album_name)
                            )
                        logger.info(f"Downloaded {track['track_name']} by {track['artists']}.")
                        
                    except Exception as e:
                        logger.error(f"Error downloading {track['track_name']}: {e}", exc_info=True)

                    self.processed_items += 1
                    self.update_progress()
                except Exception as e:
                    logger.error(f"Error downloading {track['track_name']}: {e}", exc_info=True)
                    self.output_var.set(f"Error downloading {track['track_name']}: {e}")
                    continue

            self.output_var.set("")

        except Exception as e:
            logger.error(f"Error downloading album: {e}", exc_info=True)
            self.output_var.set("Error downloading album")

        finally:
            self.reset_ui()

    def start_download_album_thread(self, track_type, track_id):
        album_thread = threading.Thread(target=self.download_album, args=(track_type, track_id))
        album_thread.start()

    def download_playlist(self, track_type, track_id):
        try:
            res = requests.get(f"https://spotipy-api.vercel.app/spotipy?type={track_type}&id={track_id}")
            data = res.json()
            playlist_name = data["playlist_name"]
            tracks = data["tracks"]
            self.total_items = len(tracks)
            self.processed_items = 0

            for track in tracks:
                try:
                    thumbnail_url = track["images"][1]["url"]
                    self.download_thumbnail(thumbnail_url)

                    query = pytube.Search(f"{track['track_name']} {track['artists']}")
                    self.output_var.set(f"Downloading : {track['track_name']} {track['artists']}")
                    logger.info(f"Downloading track: {track['track_name']} by {track['artists']}")

                    yt = query.results[0]
                    yt_url = yt.watch_url
                    try:
                        self.download_audio(
                            url=yt_url,
                            output_path=os.path.join(self.download_path.get(), playlist_name)
                            )
                        logger.info(f"Downloaded {track['track_name']} by {track['artists']}.")
                        
                    except Exception as e:
                        logger.error(f"Error downloading {track['track_name']}: {e}", exc_info=True)
                            
                    self.processed_items += 1
                    self.update_progress()
                except Exception as e:
                    logger.error(f"Error downloading {track['track_name']}: {e}", exc_info=True)
                    self.output_var.set(f"Error downloading {track['track_name']}: {e}")
                    continue

            self.output_var.set("")

        except Exception as e:
            logger.error(f"Error downloading playlist: {e}", exc_info=True)
            self.output_var.set("Error downloading playlist")

        finally:
            self.reset_ui()

    def start_download_playlist_thread(self, track_type, track_id):
        playlist_thread = threading.Thread(target=self.download_playlist, args=(track_type, track_id))
        playlist_thread.start()

    
    def download_thumbnail(self, image_url):
        current_time = datetime.now()
        time_str = current_time.strftime("%Y%m%d%H%M%S")

        create_dir(resource_path("temp"))
        try:
            response = requests.get(image_url)
            download_path = resource_path(os.path.join("temp", f"{time_str}.png"))

            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.save(download_path)
                my_image = ctk.CTkImage(light_image=Image.open(download_path),dark_image=Image.open(download_path),size=(100, 100))
                self.image_label.configure(image=my_image)
                logger.info(f"Downloaded and displayed thumbnail from {image_url}.")
            else:
                self.image_label.configure(image=None)
                logger.warning(f"Failed to download thumbnail from {image_url}. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading thumbnail: {e}", exc_info=True)
            self.image_label.configure(image=None)

if __name__ == "__main__":
    app = App()
    app.mainloop()