
from flask import Flask, render_template, request, redirect, session, url_for

# python modules for data manipulation and visualization
import pandas as pd
import mpld3
import seaborn as sns
import matplotlib
import os
import time

# this fixes the problem with threading in matplotlib
matplotlib.use('Agg')

# spotify api authorization and call handling library
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def top_tracks_cleaner(data):
	x = []
	s = data['items']

	for i in s:
		x.append({
        	'song': i['name'],
            'album': i['album']['name'],
            'artists': [artist['name'] for artist in i['artists']],
            'id': i['id'],
            'popularity': i['popularity'],
            'img': i['album']['images'][0]['url']
            })
	
	return x

def top_artists_cleaner(data):
	x = []
	s = data['items']

	for i in s:
		x.append({
        	'artist': i['name'],
            'genres': i['genres'],
            'id': i['id'],
            'popularity': i['popularity'],
            'images': i['images'][0]['url']
			})
	
	return x


app = Flask(__name__)
app.secret_key = 'wowza'
TOKEN_CODE = "token_info"

# function passed to jinja
@app.context_processor
def track_string_format():
	
	def delengthener(name: str):
	
		if len(name) > 20:
			return name[:20] + '...'
	
		return name


	return dict(delengthener=delengthener)


# TEST  --------

cache_handler = spotipy.cache_handler.MemoryCacheHandler()


# ENDTEST -------


# spotipy authentification object
auth_manager = SpotifyOAuth(
	scope=['user-top-read',
	'user-read-recently-played',
	'user-library-read'
	],
	client_id=os.environ['CLIENT_ID'],
	client_secret=os.environ['CLIENT_SECRET'],
	redirect_uri=f"https://spotifyrewrapped.herokuapp.com/",
	show_dialog=True,
	cache_handler=cache_handler
	)


# home route. renders index.html 
@app.route('/', methods=['GET', 'POST'])
def home():

	# executes if api sends a get request with the 'code' argument
	if request.args.get('code'):
		
		# this saves the auth token into a session object
		# session['access_token'] = request.args.get('code')
		# with open('cache.txt', 'w') as cache:
		# 	cache.write(str(request.args))
		
		session.clear()
		token_info = auth_manager.get_access_token(request.args.get('code'))
		session[TOKEN_CODE] = token_info    

		# this saves the auth token into a session object
		#session['access_token'] = request.args.get('code')

		return redirect('/user_data')
	
	#if os.path.exists(".cache"): 
	#	os.remove(".cache")
	
	# initial load in template this renders essentially only renders on the first load
	return render_template('index.html')



# this route is essentially only the middleman so the page doesnt save
@app.route('/login', methods=['POST'])
def login_function():

	auth_url = auth_manager.get_authorize_url()
	return redirect(auth_url)


def get_token(): 
    token_info = session.get(TOKEN_CODE, None)
    if not token_info: 
        raise "exception"
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60 
    if (is_expired): 
        token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
    return token_info 


@app.route('/user_data')
def user_data():
	
	try: 
		token_info = get_token()
	except: 
		print("user not logged in")
		return redirect("/")

	# with open('cache.txt', 'r') as cache:
	# 	auth_manager.get_access_token(cache.read())
	# sp = spotipy.Spotify(auth_manager=auth_manager)
	# os.remove('cache.txt')

	auth_manager.get_access_token(session.get('access_token'))
	sp = spotipy.Spotify(auth_manager=auth_manager)

	if not request.args.get('time_range'):
		return redirect('/user_data?time_range=short_term&search=tracks')

	# checks url for a num argument and assigns num variable to the arg
	# default is 10
	if request.args.get('num'):
		num = int(request.args.get('num'))
	else:
		num = 10


	# return your top tracks and a matplot viz
	if request.args.get('search') == 'tracks':

		# api call to get top songs in some range, clean and set as df
		time_range = request.args['time_range']

		# calling for the user data and simultaneously cleaning/framing
		df = pd.DataFrame(
			top_tracks_cleaner(
				sp.current_user_top_tracks(limit=50, time_range=time_range)))


		# saving IDs for future calls
		id_list = df['id'].to_list()

		# api call to grab the features of those songs from their IDs
		features_json = sp.audio_features(id_list)
		features_df = pd.DataFrame(features_json)

		# merge the two df on their ID
		merged = pd.merge(df, features_df).drop(labels=['uri', 'track_href', 'analysis_url', 'duration_ms'], axis=1)


		# plotting each feature / saving the svg in a dictionary
		sns.set_style('dark')
		sns.set_context("paper")

		histogram_svg_elements = {}
		histogrammable_features = ['popularity', 'key', 'loudness', 'tempo']

		for feature in histogrammable_features:
			song_feature_series = merged[feature]


			fig = sns.displot(data=song_feature_series, kde=True, height=4, aspect=1).set(ylabel=None, xlabel=None).fig


			# using mpld3 library to save as an html svg
			histogram_svg_elements[feature] = mpld3.fig_to_html(fig)
			matplotlib.pyplot.clf()


		features = merged[['danceability', 'energy', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence']]

		return render_template(
			'user_data.html',
			plots=histogram_svg_elements,
			data=merged,
			time=time_range,
			num=num
			)

	
	#return your top artists
	if request.args.get('search') == 'artists':

		# api call to get top songs in some range, clean and set as df
		time_range = request.args['time_range']

		# calling for the user data and simultaneously cleaning/framing
		df = pd.DataFrame(
			top_artists_cleaner(
				sp.current_user_top_artists(limit=50, time_range=time_range)))


		# collecting genres
		genre_dict = {}
		for genre_list in df['genres'].to_list():
			for genre in genre_list:
				for word in genre.split():
					if word not in genre_dict:
						genre_dict[word] = 1
					else:
						genre_dict[word] += 1
		
		# grab top user genres
		top_10_genre_2dlist = sorted(genre_dict.items(), key=lambda item: item[1])[:10]

		# ax = sns.barplot(data=top_10_genre_2dlist)
		# genre_plot = ax.get_figure()

		return str(top_10_genre_2dlist) 
		# render_template(
		# 	'user_data_artists.html',
		# 	data=df,
		# 	time=time_range,
		#	num=num
		# 	)




	# if neither condition is met
	return '<a href="/">Home</a>'





if __name__ == '__main__':
	app.run(debug=True)