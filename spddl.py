import os
import requests
import re
from dataclasses import dataclass
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

GREEN = "\033[38;2;44;194;97m"
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

API_REQUEST_HEADERS = {
    'Host': 'api.spotifydown.com',
    'Referer': 'https://spotifydown.com/',
    'Origin': 'https://spotifydown.com',
}

FILENAME_SANITIZATION_PATTERN = re.compile(r'[<>:\"\/\\|?*\|\']')

@dataclass(init=True, eq=True, frozen=True)
class TrackMetadata:
    title: str
    artists: str
    album: str
    cover: str
    link: str

def normalize_filename(name):
    name = re.sub(FILENAME_SANITIZATION_PATTERN, '', name)
    name = ' '.join(name.split())
    return name.strip()

def fetch_track_metadata(link):
    track_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/download/{track_id}", headers=API_REQUEST_HEADERS)
    return response.json()

def fetch_album_metadata(link):
    album_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/metadata/album/{album_id}", headers=API_REQUEST_HEADERS)
    response = response.json()
    album_name = response['title']
    album_cover = response.get('cover', '')
    
    print(f"Album: {album_name} by {response['artists']}")
    print("Getting songs from album...")
    
    track_list = []
    response = requests.get(f"https://api.spotifydown.com/tracklist/album/{album_id}", headers=API_REQUEST_HEADERS)
    response = response.json()
    track_list.extend(response['trackList'])

    return [TrackMetadata(
        title=normalize_filename(track['title']),
        artists=normalize_filename(track['artists']),
        album=album_name,
        cover=album_cover,
        link=f"https://open.spotify.com/track/{track['id']}"
    ) for track in track_list], album_name

def fetch_playlist_metadata(link):
    playlist_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/metadata/playlist/{playlist_id}", headers=API_REQUEST_HEADERS)
    response = response.json()
    playlist_name = response['title']
    
    print(f"Playlist: {playlist_name} by {response['artists']}")
    print("Getting songs from playlist...")
    
    track_list = []
    response = requests.get(f"https://api.spotifydown.com/tracklist/playlist/{playlist_id}", headers=API_REQUEST_HEADERS)
    response = response.json()
    track_list.extend(response['trackList'])
    next_offset = response['nextOffset']
    while next_offset:
        response = requests.get(f"https://api.spotifydown.com/tracklist/playlist/{playlist_id}?offset={next_offset}", headers=API_REQUEST_HEADERS)
        response = response.json()
        track_list.extend(response['trackList'])
        next_offset = response['nextOffset']

    return [TrackMetadata(
        title=normalize_filename(track['title']),
        artists=normalize_filename(track['artists']),
        album=track.get('album', 'Unknown Album'),
        cover=track.get('cover', ''),
        link=f"https://open.spotify.com/track/{track['id']}"
    ) for track in track_list], playlist_name

def fetch_spotify_entity_metadata(link):
    item_type = ""
    if "track" in link:
        item_type = "track"
    elif "album" in link:
        item_type = "album"
    elif "playlist" in link:
        item_type = "playlist"
    else:
        raise ValueError("Invalid Spotify link. Must be a track, album, or playlist URL.")

    item_id = link.split("/")[-1].split("?")[0]
    api_url = f"https://api.spotifydown.com/metadata/{item_type}/{item_id}"

    response = requests.get(api_url, headers=API_REQUEST_HEADERS)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch data: HTTP {response.status_code}")

    data = response.json()

    if not data['success']:
        raise Exception(f"API returned an error: {data.get('message', 'Unknown error')}")

    widget_info = {
        "cover": data.get("cover", ""),
        "title": data.get("title", ""),
        "artist": data.get("artists", ""),
        "releaseDate": data.get("releaseDate", "")
    }

    return widget_info

def download_and_process_track(track, outpath):
    trackname = f"{track.title} - {track.artists}"
    print(f"Downloading: {trackname}", end="", flush=True)
    resp = fetch_track_metadata(track.link)
    if resp['success'] == False:
        print(f" Error: {resp['message']}")
        return

    if persist_audio_file(trackname, resp['link'], outpath):
        cover_url = track.cover or resp['metadata'].get('cover', '')
        if cover_url:
            cover_art = requests.get(cover_url).content
            embed_cover_art(trackname, cover_art, outpath)
        print(" Downloaded")
    else:
        print(" Skipped (already exists)")

def embed_cover_art(trackname, cover_art, outpath):
    trackname = normalize_filename(trackname)
    filepath = os.path.join(outpath, f"{trackname}.mp3")
    try:
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.add(
            APIC(
                encoding=1,
                mime='image/jpeg',
                type=3,
                desc=u'Cover',
                data=cover_art)
            )
        audio.save(filepath, v2_version=3, v1=2)
    except Exception as e:
        print(f"\tError attaching cover art: {e}")
        
def persist_audio_file(trackname, link, outpath):
    trackname = normalize_filename(trackname)
    if os.path.exists(os.path.join(outpath, f"{trackname}.mp3")):
        return False
    
    audio_response = requests.get(link)
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
        
        for song in selected_songs:
            download_and_process_track(song, outpath)
    elif "playlist" in url:
        songs, playlist_name = fetch_playlist_metadata(url)
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
        
        for song in selected_songs:
            download_and_process_track(song, outpath)
    else:  
        resp = fetch_track_metadata(url)
        if resp['success'] == False:
            print(f"Error: {resp['message']}")
            return
        trackname = f"{resp['metadata']['title']} - {resp['metadata']['artists']}"
        print(f"Downloading: {trackname}", end="", flush=True)
        if persist_audio_file(trackname, resp['link'], outpath):
            cover_art = requests.get(resp['metadata']['cover']).content
            embed_cover_art(trackname, cover_art, outpath)
            print(" Downloaded")
        else:
            print(" Skipped (already exists)")
    
    print(f"\n{GREEN}Download completed!{RESET}")
    print("Thank you for using spddl!")
    print("=" * 26)

if __name__ == "__main__":
    main()
