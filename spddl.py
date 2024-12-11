import os
import time
import requests
import re
from dataclasses import dataclass

GREEN = "\033[38;2;44;194;97m"
RED = "\033[38;2;255;0;0m"
ORANGE = "\033[38;2;255;165;0m"
RESET = "\033[0m"

TITLE = f"""{GREEN}                   __    ____
   _________  ____/ /___/ / /
  / ___/ __ \/ __  / __  / / 
 (__  ) /_/ / /_/ / /_/ / /  
/____/ .___/\__,_/\__,_/_/   
    /_/                      
                               
Spotify Direct Download{RESET}
"""
print(TITLE)
print("Welcome to spddl - Your Spotify Track Saver!")
print("=" * 44)
print()

FILENAME_SANITIZATION_PATTERN = re.compile(r'[<>:\"\/\\|?*\|\']')

@dataclass(init=True, eq=True, frozen=True)
class TrackMetadata:
    title: str
    artists: str
    album: str = "Unknown Album"
    tid: str = ""
    cover: str = ""

def normalize_filename(name):
    name = re.sub(FILENAME_SANITIZATION_PATTERN, '', name)
    name = ' '.join(name.split())
    return name.strip()

def fetch_track_metadata(link, max_retries=3):
    track_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://spotapis.vercel.app/track/{track_id}")
            response.raise_for_status()
            data = response.json()
            return TrackMetadata(
                title=normalize_filename(data['title']),
                artists=normalize_filename(data['artist']),
                tid=track_id,
                cover=data.get('cover', '')
            )
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching track metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch track metadata after {max_retries} attempts.")
                return None

def fetch_album_metadata(link, max_retries=3):
    album_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://spotapis.vercel.app/album/{album_id}")
            response.raise_for_status()
            data = response.json()
            
            album_info = data['album_info']
            print(f"Album: {album_info['title']} by {album_info['owner']}")
            print(f"Release Date: {album_info['release']}")
            print(f"Total Tracks: {album_info['total']}")
            print("Getting songs from album...")
            
            return [TrackMetadata(
                title=normalize_filename(track['title']),
                artists=normalize_filename(track['artist']),
                album=album_info['title'],
                tid=track['id']
            ) for track in data['track_list']], album_info['title']
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching album metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch album metadata after {max_retries} attempts.")
                return None, None

def fetch_playlist_metadata(link, max_retries=3):
    playlist_id = link.split("/")[-1].split("?")[0]
    for attempt in range(max_retries):
        try:
            response = requests.get(f"https://spotapis.vercel.app/playlist/{playlist_id}")
            response.raise_for_status()
            data = response.json()
            
            playlist_info = data['playlist_info']
            print(f"Playlist: {playlist_info['title']} by {playlist_info['owner']}")
            print(f"Total Tracks: {playlist_info['total']}")
            print("Getting songs from playlist...")
            
            return [TrackMetadata(
                title=normalize_filename(track['title']),
                artists=normalize_filename(track['artist']),
                tid=track['id']
            ) for track in data['track_list']], playlist_info['title']
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Error fetching playlist metadata. Retrying... (Attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print(f"Failed to fetch playlist metadata after {max_retries} attempts.")
                return None, None

def download_track(track, outpath, max_retries=3):
    trackname = f"{track.title} - {track.artists}"
    print(f"Downloading: {trackname}", end="", flush=True)
    
    for attempt in range(max_retries):
        try:
            if persist_audio_file(trackname, track.tid, outpath):
                print(f"{GREEN} Downloaded{RESET}")
                return True
            else:
                print(f"{ORANGE} Skipped (already exists){RESET}")
                return True
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"{ORANGE} Error downloading. Retrying... (Attempt {attempt + 2}/{max_retries}){RESET}")
                time.sleep(2)
            else:
                print(f"{RED} Failed to download after {max_retries} attempts.{RESET}")
                return False

def persist_audio_file(trackname, tid, outpath):
    trackname = normalize_filename(trackname)
    if os.path.exists(os.path.join(outpath, f"{trackname}.mp3")):
        return False
    
    audio_response = requests.get(f"https://yank.g3v.co.uk/track/{tid}")
    audio_response.raise_for_status()
    
    if audio_response.status_code == 200:
        with open(os.path.join(outpath, f"{trackname}.mp3"), "wb") as file:
            file.write(audio_response.content)
        return True
    return False

def main():
    outpath = os.getcwd()
    
    url = input("Enter Spotify track, album, or playlist URL: ")
    
    if "album" in url:
        songs, album_name = fetch_album_metadata(url)
        if songs is None:
            print(f"{RED}Failed to fetch album. Exiting.{RESET}")
            return
        print("\nTracks in album:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        album_folder = normalize_filename(album_name)
        outpath = os.path.join(outpath, album_folder)
        os.makedirs(outpath, exist_ok=True)
        
        failed_downloads = 0
        for song in selected_songs:
            if not download_track(song, outpath):
                failed_downloads += 1
        
        if failed_downloads == len(selected_songs):
            print(f"\n{RED}Download failed: All tracks failed to download.{RESET}")
        elif failed_downloads > 0:
            print(f"\n{ORANGE}Download partially failed: {failed_downloads} out of {len(selected_songs)} tracks failed to download.{RESET}")
        else:
            print(f"\n{GREEN}Download completed successfully!{RESET}")
    
    elif "playlist" in url:
        songs, playlist_name = fetch_playlist_metadata(url)
        if songs is None:
            print(f"{RED}Failed to fetch playlist. Exiting.{RESET}")
            return
        print("\nTracks in playlist:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        playlist_folder = normalize_filename(playlist_name)
        outpath = os.path.join(outpath, playlist_folder)
        os.makedirs(outpath, exist_ok=True)
        
        failed_downloads = 0
        for song in selected_songs:
            if not download_track(song, outpath):
                failed_downloads += 1
        
        if failed_downloads == len(selected_songs):
            print(f"\n{RED}Download failed: All tracks failed to download.{RESET}")
        elif failed_downloads > 0:
            print(f"\n{ORANGE}Download partially failed: {failed_downloads} out of {len(selected_songs)} tracks failed to download.{RESET}")
        else:
            print(f"\n{GREEN}Download completed successfully!{RESET}")
    
    else:
        track = fetch_track_metadata(url)
        if track is None:
            print(f"{RED}Error: Unable to fetch track metadata.{RESET}")
            return
        if not download_track(track, outpath):
            print(f"\n{RED}Download failed: The track failed to download.{RESET}")
        else:
            print(f"\n{GREEN}Download completed successfully!{RESET}")
    
    print("Thank you for using spddl!")
    print("=" * 26)

if __name__ == "__main__":
    main()
