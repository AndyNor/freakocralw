# -*- coding: utf-8 -*-
import urllib.request, urllib.error, urllib.parse
from time import sleep
from random import randint
import re
from html.parser import HTMLParser
import json
import os
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import sys

"""
This program will look for mention of music from the freakonomics podcast.
We buffer the result of the crawling, but retry against spotify in case of new releases
"""

def load_json(path):
	try:
		with open(path, "r") as source:
			return json.load(source)
	except IOError:
		print("Unable to load json file")
		return []


def save_json(path, data, mode="w"):
	try:
		with open(path, mode) as dest:
			dest.write(json.dumps(data, indent=4))
	except IOError:
			print("Unable to save json file")


def fetch_url(url, wait, cookie=False):
	req = urllib.request.Request(url, headers={'User-Agent' : "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36"})
	if cookie:
		req.add_header('cookie', cookie)
	try:
		conn = urllib.request.urlopen(req)
		wait_time = (float(randint(5,20)) / 10) * wait
		if wait_time > 0:
			print("waiting %s seconds" % wait_time)
			sleep(wait_time)
		# status code, visited page, headers and the page body
		return (conn.getcode(), conn.geturl(), conn.info(), conn.read().decode('utf-8'))
	except:
		return False


def locate_urls(body, target_domain):
	regex_match_old = "https?://[www.]*%s/\d{4}/\d{2}/\d{2}/[a-z0-9-]*/" % target_domain
	links_old = re.findall(regex_match_old, body, re.IGNORECASE)

	regex_match_new = "https?://[www.]*%s/podcast/[a-z0-9-_]*" % target_domain
	links_new = re.findall(regex_match_new, body, re.IGNORECASE)

	return list(set(links_old + links_new))


def find_music_tags(status, body, link):
	new_tags = []

	tags = re.findall("\[\s?MUSIC\s?:\s?([^\]]*)\]", body, re.IGNORECASE)
	if len(tags) > 0:
		print("Found old music tags")
		for tag in tags:
			new_tags.append((tag, link))

	tags = re.findall("<p><b>MUSIC:\s?(.*)(?=</b></p>)", body, re.IGNORECASE)
	if len(tags) > 0:
		print("Found clean music tags")
		for tag in tags:
			new_tags.append((tag, link))

	summary_tags = re.findall("<strong>MUSIC(.*)(?=</strong>)</strong>\s*</p>\s*<ul>(.*)(?=</ul>)", body, re.IGNORECASE|re.DOTALL|re.MULTILINE)
	try:
		tags = summary_tags[0].split("</li>")
		print("Found new music tags")
		for tag in tags:
			tag = tag.replace("<li>", "")
			tag = tag.replace("</li>", "")
			new_tags.append((tag, link))
	except:
		pass

	print("Found %s new music tags" % len(new_tags))
	return new_tags


def load_crawl_store(target_domain, archive_page, delay, queue_visited_path, music_tags_raw_path):
	archive_page_url = "http://%s%s" % (target_domain, archive_page)
	queue_visited = load_json(queue_visited_path)
	print("Loaded already crawled linked. Found %s links" % len(queue_visited))
	music_tags_raw = load_json(music_tags_raw_path)
	print("Loaded existing raw music urls. Found %s urls" % len(music_tags_raw))

	status, url, headers, body = fetch_url(archive_page_url, 0)  # no delay getting first page
	cookie = headers.get('Set-Cookie')
	all_urls = locate_urls(body, target_domain)
	print(("Searched archive page. Found %s links" % len(all_urls)))

	visited_pages = 0
	for link in all_urls:
		if link not in queue_visited:
			fetch_data = fetch_url(link, delay, cookie)
			if fetch_data:
				status, url, headers, body = fetch_data
				print(("Scanning %s") % url)
				if status == 200:
					new_tags = find_music_tags(status, body, link)
					if len(new_tags) > 0:
						for tag in new_tags:
							music_tags_raw.append(tag)
				else:
					print("Host did not return HTTP 200")

				queue_visited.append(link)
				visited_pages += 1
			else:
				print(("Scanning if %s failed") % (link))

	if visited_pages == 0:
		print("All episodes already scanned")


	print(("Done scanning new episodes. Found %s new episodes" % visited_pages))
	save_json(queue_visited_path, queue_visited)
	save_json(music_tags_raw_path, music_tags_raw)
	print("New results are saved")


####################################################################################


class MLStripper(HTMLParser):
	def __init__(self):
		super().__init__()
		self.reset()
		self.fed = []

	def handle_data(self, d):
		self.fed.append(d)

	def get_data(self):
		return ''.join(self.fed)

def strip_tags(html):
	s = MLStripper()
	s.feed(html)
	return s.get_data()

def match_music_tags(tag):
	match = re.match(r"\s*([^,;:-]*)[,;:-]?\s*\[([^(]*?)\]\s*\(\s*from:?\s*([^\)]*)\)", tag)
	if match is not None:
		artist, track, album = match.group(1), match.group(2), match.group(3)

	else:
		match = re.match(r"\s*([^,;:-]*)[,;:-]?\s*\"?([^(]*?)\"?\s*\(\s*from:?\s*([^\)]*)\)", tag)
		if match is not None:
			artist, track, album = match.group(1), match.group(2), match.group(3)

		else:
			match = re.match(r"\s*([\w\s\.]*)[\W]*([\w\s]*)[\W]?", tag)
			if match is not None:
				artist, track = match.group(1), match.group(2)
				album = ""

			else:
				track = tag  # last resort
				album = ""

	if len(track) > 70:  # probably no title this long
		return False

	if len(artist) == 0:
		artist = album

	return (artist, track, album)

def parse_raw_tags(music_tags_raw_path):
	music_tags_raw = load_json(music_tags_raw_path)
	parsed_songs = []
	for line in music_tags_raw:
		tag = strip_tags(line[0])
		tag = tag.replace("\n", "") #no need for newlines
		tag = tag.replace("”", "").replace("“", "") #no need for quote symbols
		if len(tag) > 3: #if less than 3 probably nothing
			artist_song_album = match_music_tags(tag)
			if artist_song_album:
				parsed_songs.append(artist_song_album)
			else:
				print("Failed on: %s" % tag)

	parsed_songs = sorted(set(parsed_songs))
	print(("The parser was able to find %s unique songs") % len(parsed_songs))
	song_dict = []
	for song in parsed_songs:
		song_dict.append({
			"artist": song[0],
			"track": song[1],
			"album": song[2],
			})
	return song_dict


####################################################################################


def spotify_lookup(spotify_link, song, spotify_results_limit):
	query_artist = song["artist"]
	query_track = song["track"]
	query_album = song["album"]
	query = '%s %s %s' % (query_artist, query_album, query_track)
	try:
		results = spotify_link.search(q=query, type='track', limit=spotify_results_limit)
		tracks = results['tracks']['items']
		tracks = sorted(tracks, key=lambda x: x['popularity'], reverse=True)
		if len(tracks) > 0:
			selected_track = tracks[0]  # we only care about the most popular (most likely) match
			artists = ""
			for artist in selected_track['artists']:
				artists += artist['name'] + ", "
			artists = artists[:-2].encode("utf8")
			album = selected_track['album']['name'].encode("utf8")
			track_name = selected_track['name'].encode("utf8")
			uri = selected_track['uri']

			return ({
				"artists": artists,
				"album": album,
				"track_name": track_name,
				"uri": uri
			})

		else:
			return False
	except:
		print ("Spotify API crash...")

def spotify_engine(parsed_songs, spotify_clientid, spotify_secret, located_songs_path, spotify_results_limit, delay_spotify):
	previously_reported = load_json(located_songs_path)
	token = SpotifyClientCredentials(client_id=spotify_clientid, client_secret=spotify_secret).get_access_token()
	spotify_link = Spotify(auth=token)

	new_spotify_uris = []
	print("Starting lookup with Spotify")

	for song in parsed_songs:
		song_details = spotify_lookup(spotify_link, song, spotify_results_limit)
		wait_time = (float(randint(5, 20)) / 10) * delay_spotify
		sys.stdout.write('.')
		sys.stdout.flush()
		sleep(wait_time)

		if song_details:
			if song_details["uri"] not in previously_reported:
				print("\nSearched for %s by %s (from %s)" % (song["track"], song["artist"], song["album"]))  # artist:0, song:1, album:2
				print("\nFound %s by %s (%s)" % (song_details["track_name"], song_details["artists"], song_details["album"]))
				new_spotify_uris.append(song_details["uri"])

	print("\nFound %s new songs on Spotify" % len(new_spotify_uris))
	for spotify_uri in new_spotify_uris:
		previously_reported.append(spotify_uri)
	save_json(located_songs_path, previously_reported)
	print("Paste these into a spotify playlist:")
	for song in new_spotify_uris:
		print(song)


####################################################################################


script_path = os.path.dirname(os.path.realpath(__file__))
from secrets import load_secrets

crawler_delay = 5  # seconds
queue_visited_path = "%s/data_visited_links.json" % script_path
music_tags_raw_path = "%s/data_raw_tags.json" % script_path
target_domain = "freakonomics.com"
archive_page = "/archive/"  # the index page for podcasts
#Load json with previously crawled links, go to archive page, crawl it, and crawl all new links not seen before and save lines containing songs..
load_crawl_store(target_domain, archive_page, crawler_delay, queue_visited_path, music_tags_raw_path)

#Load all raw song information ever found and parse it for album, artist and song name
parsed_songs = parse_raw_tags(music_tags_raw_path)

spotify_results_limit = 3
delay_spotify = 0.1
load_secrets() # It will put the secrets as environment variables
spotify_clientid = os.environ['spotify_clientid']
spotify_secret = os.environ['spotify_secret']
located_songs_path = "%s/data_located_songs.json" % script_path
# look up all parsed songs (song name, album, artist) and print out new unique spotify-URIs
spotify_engine(parsed_songs, spotify_clientid, spotify_secret, located_songs_path, spotify_results_limit, delay_spotify)

