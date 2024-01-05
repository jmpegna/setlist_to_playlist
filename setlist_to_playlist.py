import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import datetime
import json
import pandas as pd
from os.path import isfile, join
from os import listdir
import pathlib
import os
import configparser
import logging
import sys
import argparse

# Global variables
g_config_file = "setlist_to_playlist.properties"
g_setlists_dir_property = "setlists_dir"
g_concerts_dir_property = "concerts_dir"

# Global functions

def list_dirs(directory):
    """Returns all directories in a given directory
    """
    return [f for f in pathlib.Path(directory).iterdir() if f.is_dir()]

def list_files(directory, ext):
    """Returns all files in a given directory
    """
    onlyfiles = [join(directory, f) for f in listdir(directory) if isfile(join(directory, f)) and f.endswith(ext)]
    return onlyfiles

def checkDirAndCreate(directory_label, directory_path):
    """
    Checks if a directory exists. If it does not exist, it creates it

    Parameters
    ----------
    directory_label: str
        the label (logical name) of the directory. Only for log purposes
    directory_path: str
        the path of the directory to check and create
    """

    if os.path.exists(directory_path):
        print("{} dir {} already exists".format(directory_label, directory_path))
    else:
        print("Creating {} dir {}".format(directory_label, directory_path))
        os.makedirs(directory_path) 

class GenericClient:
    """
    Abstract class to handle calls to APIs
    ...

    Attributes
    ----------
    _logger : Logger
        an instance to the logger to manage traces 
    """

    def __init__(self, debug = False):
        """
        Initializes the object
        
        Parameters
        ----------
        debug: bool
            whether or nor DEBUG traces are going to be included int the logs
        """

        self._config = None

        # Create logger
        self._logger = self.__configureLogger(logger_name=self.__class__.__name__, logger_file_name=self.__class__.__name__, debug=debug)
        
        # Load configuration from .ini file
        self.__loadConfiguration()

    def __loadConfiguration(self):
        """
        Loads the configuration from the setlist_to_playlist.ini file
        """

        # Check .ini file
        config_file = "{}/{}".format(os.path.dirname(os.path.abspath(__file__)), g_config_file)
        if os.path.exists(config_file):
            self._logger.info("Reading configuration from {}".format(config_file))
        else:
            self._logger.error("Confiruration file {} not found".format(config_file))
            sys.exit()

        # Read configuration from .ini file
        self._config = configparser.ConfigParser()
        self._config.read(config_file)

    def __configureLogger(self, logger_name, logger_file_name, debug=False):
        """
        Initializes and configures the logger(s)

        Parameters
        ----------
        logger_name: str
            a string representing the logical name of the logger
        logger_file_name: str
            a string representing the name of the file created for the logger
        debug: bool
            a boolean to indicate whether or not to produce DEBUG traces

        Returns
        -------
        Logger
            the logger just created
        """
        # Configuring the logger
        log_level = logging.DEBUG if debug == True else logging.INFO

        # Create logger with the name passed as argument
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
        logger.propagate = False

        log_dir = "{}/logs".format(os.path.dirname(os.path.abspath(__file__)))
        checkDirAndCreate("Logs", log_dir)

        log_file = "{}/{}.log".format(log_dir, logger_file_name)
       
        # Create file handler which logs even debug messages
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s %(levelname)s %(message)s')
        
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        logger.info("Logger activated")

        return logger

class SetlistClient(GenericClient):
    """
    Class to handle calls to setlist.fm API and read/write setlists from/to JSON files
    ...

    Attributes
    ----------
    _setlists_dir : str
        a string representing the base dir where the setlists will be placed once they are read from setlist.fm
    _setlist_api_key : str
        a string representing API key for setlist.fm
    _setlist_base_url : str
        a string representing the URL to execute setlist.fm APIs
    _setlist_search_endpoint : str
        a string representing the API endpoint to search a concert on setlist.fm
    _concerts_dir : str
        a string representing the base dir where the script will read the concerts file
    _concerts_file : str
        a string representing the concerts file to read concert information from
    _setlist_retriable_errors : set
        a set of retriable errors when calling the API
    _setlist_num_retries : int
        a integer representing the number of retries for retriable errors when calling the API
    _headers : dict
        a dictionary representing the headers that will be included in each API call against setlist.fm 
    """

    def __init__(self, debug = False):
        """
        Initializes the object with the API client from .ini file
        
        Parameters
        ----------
        debug: bool
            whether or nor DEBUG traces are going to be included int the logs
        """

        self._setlists_dir = None
        self._setlist_api_key = None
        self._setlist_base_url = None
        self._setlist_search_endpoint = None
        self._concerts_dir = None
        self._concerts_file = None
        self._headers = None
        self._setlist_retriable_errors = None
        self._setlist_num_retries = None
   
        super().__init__(debug)
        
        # Load configuration from .ini file
        self.__completeConfiguration()

        self._headers = {
            "Accept": "application/json",
            "x-api-key": self._setlist_api_key
        }

    def __completeConfiguration(self):
        """
        Loads the configuration from the setlist_to_playlist.ini file
        """

        global_config = dict(self._config._sections['GLOBAL_CONFIG'])
        setlist_config = dict(self._config._sections['SETLIST.FM'])

        self._setlists_dir = global_config["setlists_dir"]
        self._concerts_dir = global_config["concerts_dir"]

        self._setlist_api_key = setlist_config["setlist_api_key"]
        self._setlist_base_url = setlist_config["setlist_base_url"]
        self._setlist_search_endpoint = setlist_config["setlist_search_endpoint"]
        self._setlist_num_retries = int(setlist_config["setlist_num_retries"])
        self._setlist_retriable_errors = set(setlist_config["setlist_retriable_errors"].split(","))

        self._logger.debug("setlists_dir={}".format(self._setlists_dir))
        self._logger.debug("concerts_dir={}".format(self._concerts_dir))
        self._logger.debug("setlist_api_key={}".format(self._setlist_api_key))
        self._logger.debug("setlist_base_url={}".format(self._setlist_base_url))
        self._logger.debug("setlist_search_endpoint={}".format(self._setlist_search_endpoint))
        self._logger.debug("setlist_num_retries={}".format(self._setlist_num_retries))
        self._logger.debug("setlist_retriable_errors={}".format(self._setlist_retriable_errors))
        
    def __get_setlist(self, artist_name, concert_date):
        """
        Initializes and configures the logger(s)

        Parameters
        ----------
        artist_name: str
            a string representing th artist to search
        concert_date: date
            the date of the concert to search

        Returns
        -------
        JSON
            a JSON object containing the setlist of the concert by the artist on the concert date, or return an error
        """
 
        # Format date to match setlist.fm's format (YYYY-MM-DD)
        formatted_date = concert_date.strftime("%d-%m-%Y")

        # API parameters
        params = {
            "artistName": artist_name,
            "date": formatted_date
        }

        # Retry logic
        num_retries = 0
        while num_retries <= self._setlist_num_retries:
            # Make API request
            response = requests.get("{}{}".format(self._setlist_base_url, self._setlist_search_endpoint), headers=self._headers, params=params)

            # Get response
            if response.status_code == 200:
                setlist_json = response.json()
                setlists = setlist_json["setlist"]
                if (setlists) and (len(setlists[0]["sets"]["set"]) > 0):
                    return setlist_json
                else:
                    self._logger.error("No setlist found for {} on {}".format(artist_name, formatted_date))
                    return None
            else:
                # If the error is retriable, retry
                if response.reason in self._setlist_retriable_errors:
                    num_retries += 1
                    self._logger.info("Error for {} on {}. Retriable error = {}. Retry #{}".format(artist_name, formatted_date, response.reason, num_retries))
                else:
                    self._logger.error("Error: '{}' for {} on {}".format(response.reason, artist_name, formatted_date))
                    return None
                
        self._logger.error("Error: Maximum number of retries reached for {} on {}".format(artist_name, formatted_date))
        return None

    def __write_setlist_to_json(self, setlist_name, setlist_dir, setlist_object):
        """
        Write a setlist dict object into disk in JSON format 

        Parameters
        ----------
        setlist_name: str
            a string representing the setlist name
        setlist_dir: str
            the directory to write the setlist
        setlist_object: dict
            the dictionary containing the setlist details
        """

        # Determine the setlist name
        local_output_file = "{}/{}".format(setlist_dir, setlist_name)
        
        # Prepare the JSON object and write it into disk
        json_object = json.dumps(setlist_object, indent=4)
        with open(local_output_file, "w") as json_file:
            json_file.write(json_object)
        
    def write_concerts_to_json(self, concerts_file, output_dir):
        """
        Opens the concerts file and for every concert included, it searches every concert in setlist.fm. When finding it, it writes the setlist into disk in JSON format
        """

        # Determine concerts file and loaded it into a dataframe
        abs_concerts_file = "{}/{}".format(self._concerts_dir, concerts_file)
        concerts_df = pd.read_csv(abs_concerts_file, keep_default_na=False)

        # Determine and check setlist directory
        setlist_dir = "{}/{}".format(self._setlists_dir, output_dir)
        checkDirAndCreate("Setlist", setlist_dir)

        # Iterate through all concerts in the concerts file
        for index, row in concerts_df.iterrows():
            # Read information for each concert
            group = row.Group
            day = row.Day
            month = row.Month
            year = row.Year
            json_day = row.JSON_Day
            json_month = row.JSON_Month
            json_year = row.JSON_Year

            json_day = day if not json_day else json_day
            json_month = month if not json_month else json_month
            json_year = year if not json_year else json_year

            concert_date = datetime.date(int(year), int(month), int(day))
            playlist_date = datetime.date(int(json_year), int(json_month), int(json_day))
            
            # Search the setlist
            result = self.__get_setlist(group, concert_date)

            if result != None:
                setlist_name = "{}_{}_{}.json".format(playlist_date, index+1, group)
                self.__write_setlist_to_json(setlist_name, setlist_dir, result)


class SpotifyClient(GenericClient):
    """
    Class to handle calls to Spotify API and create playlist from JSON files
    ...

    Attributes
    ----------
    _setlists_dir : str
        a string representing the base dir where the setlists will be placed once they are read from setlist.fm
    _spotify_client_id : str
        a string representing the client ID to connect to Spotify API
    _spotify_client_secret : str
        a string representing the secret to connect to Spotify API
    _spotify_redirect_uri : str
        a string representing the redirect URL for Spotify
    _sp: Spotify
        the Spotify client to call APIs
    """
    def __init__(self, debug = False):
        """
        Initializes the object with the Spotify client from .ini file
        
        Parameters
        ----------
        debug: bool
            whether or nor DEBUG traces are going to be included int the logs
        """

        self._setlists_dir = None
        self._spotify_client_id = None
        self._spotify_client_secret = None
        self._spotify_redirect_uri = None
        self._sp = None

        super().__init__(debug)

        self.__completeConfiguration()

        self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=self._spotify_client_id, 
                                                             client_secret=self._spotify_client_secret, 
                                                             redirect_uri=self._spotify_redirect_uri,
                                                             scope="playlist-modify-public")
                                                             )
    def __completeConfiguration(self):
        """
        Completetes the configuration from the setlist_to_playlist.ini file
        """

        global_config = dict(self._config._sections['GLOBAL_CONFIG'])
        setlist_config = dict(self._config._sections['SPOTIFY'])

        self._setlists_dir = global_config["setlists_dir"]

        self._spotify_client_id = setlist_config["spotify_client_id"]
        self._spotify_client_secret = setlist_config["spotify_client_secret"]
        self._spotify_redirect_uri = setlist_config["spotify_redirect_uri"]

        self._logger.debug("setlists_dir={}".format(self._setlists_dir))
        self._logger.debug("spotify_client_id={}".format(self._spotify_client_id))
        self._logger.debug("spotify_client_secret={}".format(self._spotify_client_secret))
        self._logger.debug("spotify_redirect_uri={}".format(self._spotify_redirect_uri))

    def __read_setlists_from_json(self, input_dir):
        """
        Reads a setlist dict object from disk in JSON format and returns a dictionary with all setlists

        Parameters
        ----------
        input_dir: str
            the directory where the setlist was produced

        Returns
        -------
        dict
            a dictionary including 1 key per concert and 1 JSON with the setlist as value
        """

        # Determine the directory and read all JSON files    
        year_dir = "{}/{}".format(self._setlists_dir, input_dir)
        concerts_files = list_files(year_dir, ".json")

        concerts_dict = dict()

        # Read every setlist and add it to the dictionary to be returned
        for concert in concerts_files:
            concert_file_name = os.path.split(concert)[1].split(".json")[0]

            with open(concert, 'r') as json_file:
                # Reading from json file
                json_object = json.load(json_file)
                concerts_dict[concert_file_name] = json_object

        return concerts_dict

    def __create_spotify_playlist(self, playlist_name):
        """
        Creates a Spotify playlist

        Parameters
        ----------
        playlist_name: str
            the name of the playlist to be created

        Returns
        -------
        string
            a string with the playlist ID
        """

        user_id = self._sp.current_user()["id"]
        playlist = self._sp.user_playlist_create(user_id, playlist_name)
        return playlist["id"]
    
    def __add_tracks_to_playlist(self, playlist_id, track_uris):
        """
        Adds a list of tracks to a Spotify playlist

        Parameters
        ----------
        playlist_id: str
            the playlist ID where the tracks will be added
        track_uris: list
            the list of tracks to be added
        """
        self._sp.playlist_add_items(playlist_id, track_uris)

    def __search_spotify_track(self, track_name, artist_name):
        """
        Searches a track on Spotify

        Parameters
        ----------
        track_name: str
            the name of the track to be searched
        artist_name: str
            the name of the artist to be searched

        Returns
        -------
        string
            the URI of the found track, or None if the track is not found
        """

        # Prepare the query
        query = "{} {}".format(track_name, artist_name)
        # Search the tack
        results = self._sp.search(q=query, type="track", limit=1)
        # Get the results
        if results["tracks"]["items"]:
            result = results["tracks"]["items"][0]
            artist_found = result["artists"][0]["name"]
            track_found = result["name"]
            uri = result["uri"]
            # If the artist or track found are different than the ones to be search, write a warning in the log
            if (artist_found.lower() != artist_name.lower()) or (track_found.lower() != track_name.lower()) :
                self._logger.warning("Artist found '{}' vs '{}'. Track found '{}' vs '{}'".format(artist_found, artist_name, track_found, track_name))

            return uri
        else:
            return None

    def __get_playlist_id_by_name(self, playlist_name):
        """
        Adds a list of tracks to a Spotify playlist

        Parameters
        ----------
        playlist_name: str
            the playlist name to be found

        Returns
        -------
        playlist_id: str
            the playlist ID
        """

        user_id = self._sp.current_user()["id"]
        playlists = self._sp.user_playlists(user_id)

        for playlist in playlists["items"]:
            if playlist["name"] == playlist_name:
                return playlist["id"]

        return None

    def populate_year_spotify_playlist(self, input_dir, playlist_name = None):
        """
        Reads all setlists for a given year from disk, and for each setlist it searches all songs on Spotify and adds them into a playlist

        Parameters
        ----------
        input_dir: str
            the directory that will be processed
        playlist_name: str
            the playlist name to be populated
        """

        # Use the playlist name provided as argument (or uses a default name) to get the playlist ID to be processed
        if playlist_name != None:
            playlist_id = self.__get_playlist_id_by_name(playlist_name)
            if playlist_id == None:
                self._logger.info("Playlist '{}' not found. Creating it".format(playlist_name))
                playlist_id = self.__create_spotify_playlist(playlist_name)
        else:
            playlist_id = self.__create_spotify_playlist("Concerts_{}".format(input_dir))

        # Read all concerts for the given input_dir
        concerts_dict = self.__read_setlists_from_json(input_dir)

        # For each concert, read all songs in the setlist, search the song on Spotify and add it to the playlist
        for concert_name, setlist_json in concerts_dict.items():
            track_uris = []
            artist_name = setlist_json["setlist"][0]["artist"]["name"]
            for set_item in setlist_json["setlist"][0]["sets"]["set"]:
                for song in set_item["song"]:
                    song_name = song["name"]
                    track_uri = self.__search_spotify_track(song_name, artist_name)
                    if track_uri:
                        track_uris.append(track_uri)
                        self._logger.debug("Adding artist/song {}/{} to playlist {}".format(artist_name, song_name, playlist_name))
                    else:
                        self._logger.error("Artist/song {}/{} not found".format(artist_name, song_name))

            if track_uris:
                self.__add_tracks_to_playlist(playlist_id, track_uris)
                self._logger.info("Concert '{}' added successfully".format(concert_name))
            else:
                self._logger.error("No matching tracks found on Spotify for concert '{}'".format(concert_name)) 

if __name__ == "__main__":
    """
    It checks the paramters passed from the command line: 
        num_iterations: number of complete iterations of the experiment.
                        Each experiment consist of sending (producing) the messages of the tables configured in the cluster_properties.ini file
        test_base_dir: the base directory from which the experiment will run
        debug (optional): whether or DEBUG traces are being included in the logs
    """

    if len(sys.argv) < 2:
            print("You have to specify a command (download_setlists or create_playlist)")
            print("Usage: {} download_setlists | create_playlist".format(os.path.basename(__file__)))
            sys.exit()

    parser = argparse.ArgumentParser()

    subparser = parser.add_subparsers(dest='command')

    download = subparser.add_parser('download_setlists')
    create = subparser.add_parser('create_playlist')

    download.add_argument('--concerts_file', type=str, required=True, help='The csv file containing the concerts information')
    download.add_argument('--output_dir', type=str, required=True, help='The directory to write the setlists')
    download.add_argument('--debug', dest='debug_flag_download', help='Whether or not to produce DEBUG traces in the logs')

    create.add_argument('--playlist_name', type=str, required=True, help='The playlist name to be created on Spotify')
    create.add_argument('--input_dir', type=str, required=True, help='The directory to read the setlists from')
    create.add_argument('--debug', dest='debug_flag_create', help='Whether or not to produce DEBUG traces in the logs')

    args = parser.parse_args()    
    if args.command == 'download_setlists':
        concerts_file = args.concerts_file
        output_dir = args.output_dir
        debug =  False if not args.debug_flag_download else args.debug_flag_download == 'True'

        setlist_client = SetlistClient(debug = debug)
        setlist_client.write_concerts_to_json(concerts_file, output_dir)
        # /tf/FinallyFriday/setlist_to_playlist.py download_setlists --concerts_file Concerts.csv --output_dir 2023_x --debug True

    elif args.command == 'create_playlist':
        input_dir = args.input_dir
        playlist_name = args.playlist_name
        debug =  False if not args.debug_flag_create else args.debug_flag_create == 'True'

        spotify_client = SpotifyClient(debug = debug)
        spotify_client.populate_year_spotify_playlist(input_dir, playlist_name)
        # /tf/FinallyFriday/setlist_to_playlist.py create_playlist --input_dir 2023_x --playlist_name Test_name --debug True