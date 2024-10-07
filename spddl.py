import os
import requests
import re
from dataclasses import dataclass
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

# ASCII Art Title
TITLE = r"""                   __    ____
   _________  ____/ /___/ / /
  / ___/ __ \/ __  / __  / / 
 (__  ) /_/ / /_/ / /_/ / /  
/____/ .___/\__,_/\__,_/_/   
    /_/                      
                               
Spotify Direct Download
"""
print(TITLE)
print("Welcome to spddl - Your Spotify Track Saver!")
print("=" * 44)
print()

CUSTOM_HEADER = {
    'Host': 'api.spotifydown.com',
    'Referer': 'https://spotifydown.com/',
    'Origin': 'https://spotifydown.com',
}

NAME_SANITIZE_REGEX = re.compile(r'[<>:\"\/\\|?*\|\']')

@dataclass(init=True, eq=True, frozen=True)
class Song:
    title: str
    artists: str
    album: str
    cover: str
    link: str

def sanitize_filename(name):
    name = re.sub(NAME_SANITIZE_REGEX, '', name)
    name = ' '.join(name.split())
    return name.strip()

def get_track_info(link):
    track_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/download/{track_id}", headers=CUSTOM_HEADER)
    return response.json()

def get_album_info(link):
    album_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/metadata/album/{album_id}", headers=CUSTOM_HEADER)
    response = response.json()
    album_name = response['title']
    album_cover = response.get('cover', '')
    
    print(f"Album: {album_name} by {response['artists']}")
    print("Getting songs from album...")
    
    track_list = []
    response = requests.get(f"https://api.spotifydown.com/tracklist/album/{album_id}", headers=CUSTOM_HEADER)
    response = response.json()
    track_list.extend(response['trackList'])

    return [Song(
        title=sanitize_filename(track['title']),
        artists=sanitize_filename(track['artists']),
        album=album_name,
        cover=album_cover,
        link=f"https://open.spotify.com/track/{track['id']}"
    ) for track in track_list], album_name

def get_playlist_info(link):
    playlist_id = link.split("/")[-1].split("?")[0]
    response = requests.get(f"https://api.spotifydown.com/metadata/playlist/{playlist_id}", headers=CUSTOM_HEADER)
    response = response.json()
    playlist_name = response['title']
    
    print(f"Playlist: {playlist_name} by {response['artists']}")
    print("Getting songs from playlist...")
    
    track_list = []
    response = requests.get(f"https://api.spotifydown.com/tracklist/playlist/{playlist_id}", headers=CUSTOM_HEADER)
    response = response.json()
    track_list.extend(response['trackList'])
    next_offset = response['nextOffset']
    while next_offset:
        response = requests.get(f"https://api.spotifydown.com/tracklist/playlist/{playlist_id}?offset={next_offset}", headers=CUSTOM_HEADER)
        response = response.json()
        track_list.extend(response['trackList'])
        next_offset = response['nextOffset']

    return [Song(
        title=sanitize_filename(track['title']),
        artists=sanitize_filename(track['artists']),
        album=track.get('album', 'Unknown Album'),
        cover=track.get('cover', ''),
        link=f"https://open.spotify.com/track/{track['id']}"
    ) for track in track_list], playlist_name

def download_track_spotifydown(track, outpath):
    trackname = f"{track.title} - {track.artists}"
    print(f"Downloading: {trackname}", end="", flush=True)
    resp = get_track_info(track.link)
    if resp['success'] == False:
        print(f" Error: {resp['message']}")
        return

    if save_audio(trackname, resp['link'], outpath):
        cover_url = track.cover or resp['metadata'].get('cover', '')
        if cover_url:
            cover_art = requests.get(cover_url).content
            attach_cover_art(trackname, cover_art, outpath)
        print(" Downloaded")
    else:
        print(" Skipped (already exists)")

def download_track_yank(track, outpath):
    track_id = track.link.split("/")[-1]
    trackname = f"{track.title} - {track.artists}"
    print(f"Downloading: {trackname}", end="", flush=True)
    yank_url = f"https://yank.g3v.co.uk/track/{track_id}"
    
    if save_audio(trackname, yank_url, outpath):
        print(" Downloaded")
    else:
        print(" Skipped (already exists)")

def attach_cover_art(trackname, cover_art, outpath):
    trackname = sanitize_filename(trackname)
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
        
def save_audio(trackname, link, outpath):
    trackname = sanitize_filename(trackname)
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
    
    print("\nChoose download method:")
    print("1. SpotifyDown - 320 kbps (default)")
    print("2. Yank - 128 kbps")
    choice = input("Enter your choice (1 or 2), or press Enter for default: ")
    
    if choice == "2":
        download_method = "yank"
    else:
        download_method = "spotifydown"
    
    if "album" in url:
        songs, album_name = get_album_info(url)
        print("\nTracks in album:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        album_folder = sanitize_filename(album_name)
        outpath = os.path.join(outpath, album_folder)
        os.makedirs(outpath, exist_ok=True)
        
        for song in selected_songs:
            if download_method == "yank":
                download_track_yank(song, outpath)
            else:
                download_track_spotifydown(song, outpath)
    elif "playlist" in url:
        songs, playlist_name = get_playlist_info(url)
        print("\nTracks in playlist:")
        for i, song in enumerate(songs, 1):
            print(f"{i}. {song.title} - {song.artists}")
        
        selection = input("\nEnter track numbers to download (space-separated) or press Enter to download all: ")
        if selection.strip():
            indices = [int(x) - 1 for x in selection.split()]
            selected_songs = [songs[i] for i in indices if 0 <= i < len(songs)]
        else:
            selected_songs = songs
        
        playlist_folder = sanitize_filename(playlist_name)
        outpath = os.path.join(outpath, playlist_folder)
        os.makedirs(outpath, exist_ok=True)
        
        for song in selected_songs:
            if download_method == "yank":
                download_track_yank(song, outpath)
            else:
                download_track_spotifydown(song, outpath)
    else:  
        if download_method == "yank":
            track_id = url.split("/")[-1].split("?")[0]
            yank_url = f"https://yank.g3v.co.uk/track/{track_id}"
            resp = get_track_info(url)
            if resp['success'] == False:
                print(f"Error: {resp['message']}")
                return
            trackname = f"{resp['metadata']['title']} - {resp['metadata']['artists']}"
            print(f"Downloading: {trackname}", end="", flush=True)
            if save_audio(trackname, yank_url, outpath):
                print(" Downloaded")
            else:
                print(" Skipped (already exists)")
        else:
            resp = get_track_info(url)
            if resp['success'] == False:
                print(f"Error: {resp['message']}")
                return
            trackname = f"{resp['metadata']['title']} - {resp['metadata']['artists']}"
            print(f"Downloading: {trackname}", end="", flush=True)
            if save_audio(trackname, resp['link'], outpath):
                cover_art = requests.get(resp['metadata']['cover']).content
                attach_cover_art(trackname, cover_art, outpath)
                print(" Downloaded")
            else:
                print(" Skipped (already exists)")
    
    print("\nDownload completed!")
    print("Thank you for using spddl!")
    print("=" * 40)

if __name__ == "__main__":
    main()
