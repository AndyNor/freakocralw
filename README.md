# freakocralw
An ugly but fairly functional python job trying really hard to figure out what music has been played on the freakonomics podcast.

## requirements
Requires python3 and uses spotipy.

"pip install spotipy" ("pip install --user spotipy" might be needed)

Secrets are stored a file configured to "freakocrawl.secrets.py", and must contain spotify clientID and API-key. 

Rename "freakocrawl.secrets.example.py" and insert your own API-key from Spotify.

## running
From a console, current path set the the root of the script

run "python freakocrawl.py"
