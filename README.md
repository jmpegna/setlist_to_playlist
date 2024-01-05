# Setlist to Playlist

Create Spotify playlists from a list of concerts described in CSV files.

## Table of Contents

- [Setlist to Playlist](#setlist-to-playlist)
  - [Table of Contents](#table-of-contents)
  - [About the Project](#about-the-project)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Usage](#usage)

## About the Project

This project includes a Python program that supports two main commands:

1. **Read a file in CSV format and download setlists:** The program reads a CSV file containing a list of artists and the dates of their corresponding shows. Subsequently, it looks up the concert on setlist.fm and utilizes its API to download the setlist in JSON format.

2. **Create a Spotify playlist:** The program creates a Spotify playlist by adding all the songs included in the previously downloaded JSON files, which contain the setlists of the shows.

## Getting Started

Instructions for setting up and running your project.

### Prerequisites

- Python 3.x installed
- spotipy installed (pip install spotipy)
- Other packages used: requests, datetime, json, pandas, os, pathlib, configparser, logging, sys, argparse

### Installation

The program expects the file setlist_to_playlist.properties to exist in the same location as the program itself.

The program requires replacing the values of the properties enclosed with {} in the file setlist_to_playlist.properties, like below (remove the {} after replacing):

[GLOBAL_CONFIG]  
concerts_dir = {PROGRAM LOCATION}/concerts  
setlists_dir = {PROGRAM LOCATION}/setlists  

[SETLIST.FM]  
setlist_api_key={KEY from setlist.fm API. More info https://api.setlist.fm/docs/1.0/index.html }  
setlist_base_url=https://api.setlist.fm/rest/1.0/  
setlist_search_endpoint=search/setlists  
setlist_num_retries=5  
setlist_retriable_errors=Too Many Requests  

[SPOTIFY]  
spotify_client_id={YOUR SPOTIFY CLIENT ID}  
spotify_client_secret={YOUR SPOTIFY CLIENT SECRET}  
spotify_redirect_uri={YOUR SPOTIFY REDIRECT URL}  


The program looks up the concerts file specified as argument from the concerts_dir, and it will place the setlists in JSON format in the setlists_dir.
The program uses setlist_api_key to call the setlist.fm API.
The program uses spotify_client_id, spotify_client_secret and spotify_redirect_uri to use Spotify API.

The program will create the "log" directory under the same location as the program itself, and it will place 2 logs: SetlistClient.log and SpotifyClient.log

## Usage

**Read a file in CSV format and download setlists:**  
```bash
python setlist_to_playlist.py download_setlists --concerts_file Concerts.csv --output_dir 2023_concerts --debug True
```

The CSV file should have the following columns:

**Day**: day of the concert to look up  
**Month**: day of the concert to look up  
**Year**: day of the concert to look up  
**Group**: group to look up  
**JSON_Day**: alternative day for the concert  
**JSON_Month**: alternative day for the concert  
**JSON_Year**: alternative day for the concert  

Day, Month, Year, and Group are mandatory values in each row. If there is no actual setlist for a date (sometimes nobody has created the entry for a given concert), specify a different date in Day, Month, and Year to find it. You can also use JSON_Day, JSON_Month, and JSON_Year to date back or forward the JSON file name (JSON_Day, JSON_Month, and JSON_Year can be empty if you do not want to date back/forward the file name).

**Create a Spotify playlist:**  
```bash
python setlist_to_playlist.py create_playlist --input_dir 2023_concerts --playlist_name My_2023_concerts --debug True
```
