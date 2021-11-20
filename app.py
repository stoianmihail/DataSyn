import os
import time
import json
import flask
import pandas as pd
# import firebase_admin
# from firebase_admin import db, credentials, storage
from pydub import AudioSegment
import speech_recognition as sr
import gtts

'''
# Fetch credentials.
cred = None
if 'DYNO' in os.environ:
  json_data = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
  json_data['private_key'] = json_data['private_key'].replace('\\n', '\n')
  cred = credentials.Certificate(json_data)
else:
  cred = credentials.Certificate('private-key.json')

# And initialize the app.
firebase_admin.initialize_app(cred, {
  'databaseURL': 'https://hyper-tone-default-rtdb.firebaseio.com',
  'storageBucket': 'hyper-tone.appspot.com',
})
'''
'''
# Load the model.
from src.predict import HyperTone
ht = HyperTone(f'model/model-1634386470.hdf5')
'''
# Initialize the Flask app.
from flask_cors import CORS, cross_origin

app = flask.Flask(__name__, template_folder='templates', static_folder='static')
cors = CORS(app)

# The app must use https for recording to work!
# Only trigger SSLify if the app is running on Heroku,
# acc. https://stackoverflow.com/questions/15116312/redirect-http-to-https-on-flaskheroku/22137608.
from flask_sslify import SSLify
if 'DYNO' in os.environ:
  sslify = SSLify(app)

georgy_sentences = {
  0: "Ok!",
  1: "Perfect! How was it compared to yesterday?",
  2: "Nice! Do you have any predictions for tomorrow?",
  3: "Ok, then make sure that we have enough drivers for tomorrow evening."
}

import difflib

def matches(large_string, query_string, threshold=0.85):
  words = large_string.lower().split()
  for word in words:
    s = difflib.SequenceMatcher(None, word, query_string.lower())
    match = ''.join(word[i:i+n] for i, j, n in s.get_matching_blocks() if n)
    if len(match) / float(len(query_string.lower())) >= threshold:
      return True
  return False

def get_current_meal():
  if False:
    prefix = 'Enjoy your '
    import datetime
    now = datetime.datetime.now()
    if now.hour <= 10:
      return prefix + 'breakfast'
    elif now.hour <= 16:
      return prefix + 'lunch'
    else:
      return prefix + 'dinner'
  else:
    return 'Did the jury like your pitch?'


from kats.consts import TimeSeriesData

# Import the param and model classes for Prophet model
from kats.models.prophet import ProphetModel, ProphetParams

class Solver:
  def __init__(self):
    self.counter = 0
    self.last_cmd_served = 'init'
    self.fallback_sentences = {
      0 : "Hey Georgy! I've got some news for you!",
      1 : "Today the average number of drives per hour was 500, and the peek hour was at 3pm",
      2 : "The total increase was about 5 percent",
      3 : "Looking back and taking into account the concert tomorrow evening, I expect a further increase of 10 percent",
      4 : "Of course! Enjoy your dinner!"
    }

  def load_data(self):
    self.df = pd.read_csv('dataset/data.csv')
    ts = TimeSeriesData(self.df)

    # create a model param instance
    params = ProphetParams(seasonality_mode='multiplicative') # additive mode gives worse results

    # create a prophet model instance
    m = ProphetModel(ts, params)

    # fit model simply by calling m.fit()
    m.fit()

    # make prediction for next week.
    self.fcst = m.predict(steps=7 * 24 * 2, freq="30min")
    
    print(type(self.fcst))
    print(self.fcst.head())

    # Build the forecast.
    self.fcst = self.fcst[['time', 'fcst']]
    self.fcst = self.fcst.rename(columns = {'fcst': 'value'})

    print('after renaming')
    print(self.fcst.head())

  def get_today(self):
    return self.df.iloc[-1]['time']

  def get_yesterday(self):
    td = self.get_today().split(' ')[0] + ' 00:00:00'
    return self.df.loc[self.df['time'] < td].iloc[-1]['time']

  def get_tomorrow(self):
    return self.fcst.iloc[0]['time']

  def get_range_side(self, time, isStart):
    if isStart:
      return str(time).split(' ')[0] + ' 00:00:00'
    else:
      return str(time).split(' ')[0] + ' 23:30:00'  

  def get_day_time(self, day):
    if day == 'today':
      return self.get_today()
    elif day == 'yesterday':
      return self.get_yesterday()
    else:
      assert day == 'tomorrow'
      return self.get_tomorrow()
    
  def get_avg_drives_per_hour(self, day):
    time = self.get_day_time(day)

    # Determine the range.
    lhs, rhs = self.get_range_side(time, True), self.get_range_side(time, False)
      
    print(f'[get_avg] time={time}')

    # And get the average.
    if day == 'today' or day == 'yesterday':
      mask = (self.df['time'] >= lhs) & (self.df['time'] <= rhs)
      return self.df.loc[mask]['value'].sum() / 24
    else:
      print('inside in tomorrow!')
      mask = (self.fcst['time'] >= lhs) & (self.fcst['time'] <= rhs)
      
      print(f"sum={self.fcst.loc[mask]['value'].sum()}")
      return self.fcst.loc[mask]['value'].sum() / 24

  def get_day_peak(self, day):
    time = self.get_day_time(day)

    # Determine the range.
    lhs, rhs = self.get_range_side(time, True), self.get_range_side(time, False)

    # And get the average.
    if day == 'today' or day == 'yesterday':
      mask = (self.df['time'] >= lhs) & (self.df['time'] <= rhs)
      return self.df.loc[mask].max()['time']
    else:
      mask = (self.fcst['time'] >= lhs) & (self.fcst['time'] <= rhs)
      return self.fcst.loc[mask].max()['time']

  def refresh(self):
    self.counter = 0
    self.last_cmd_served = 'init'

  def counter_to_sentence(self):
    return georgy_sentences[self.counter % 4]

  # def get_report(self, day):
  #   return {'type' : day, 'data' : None}

  # def get_data(self, cmd_type):
  #   if cmd_type == 'yesterday':
  #     return "The total increase was about 5 percent"
  #   elif cmd_type == 'prediction':
  #     return "Looking back and taking into account the concert tomorrow evening, I expect a further increase of 10 percent"

    #  return self.compare_report('yesterday', self.get_today_report(), self.get_yesterday_report())
    #   return self.compare_report('prediction', self.get_tomorrow_report(), self.get_today_report())
    
  # def compare_report(self, cmd_type, a, b):
  #   if cmd_type == 'yesterday':

  #   return 'test'

  def solve_today_request(self):
    # sentences[1]
    # "Today the average number of drives per hour was 500, and the peek hour was at 3pm",
    average_per_hour = self.get_avg_drives_per_hour('today')
    peak_hour = self.get_day_peak('today')
    peak_hour = int(peak_hour.split(' ')[1].split(':')[0])
    ret = ''
    if peak_hour >= 13:
      ret = str(peak_hour - 12) + 'pm'
    else:
      ret = str(peak_hour) + 'am'  
    return f'Today the average number of drives per hour was {int(average_per_hour)}, and the peek hour was at {ret}'

  def solve_yesterday_request(self):
    # sentences [2]
    # The total increase was about 5 percent
    avg_today = self.get_avg_drives_per_hour('today')
    avg_yesterday = self.get_avg_drives_per_hour('yesterday')
    ratio = (avg_today - avg_yesterday) / avg_yesterday

    print(f'avg_today={avg_today}, avg_yesterday={avg_yesterday}, ratio={ratio}')

    print(f'[solve_yesterday] ratio={ratio}')

    if ratio > 0:
      return f'The total increase was about {int(ratio * 100)} percent'
    else:
      return f'The total decrease was about {int(-ratio * 100)} percent'  

  def solve_tomorrow_request(self):
    # sentences[3]
    # "Looking back and taking into account the concert tomorrow evening, I expect a further increase of 10 percent"
    avg_today = self.get_avg_drives_per_hour('today')
    avg_tomorrow = self.get_avg_drives_per_hour('tomorrow')
    ratio = (avg_tomorrow - avg_today) / avg_today

    print(f'avg_today={avg_today}, avg_tomorrow={avg_tomorrow}, ratio={ratio}')

    ret = ''
    if ratio > 0:
      ret = f'increase of {int(ratio * 100)}'
      return f'Looking back and taking into account the concert tomorrow evening, I expect a {ret} percent'
    else:
      ret = f'decrease of {int(-ratio * 100)}'
      return f'Looking back and taking into account the current measures, I expect a {ret} percent'
    
  def respond(self, cmd_type):
    self.last_cmd_served = cmd_type
    if cmd_type == 'today':
      return self.solve_today_request()
    elif cmd_type == 'yesterday':
      return self.solve_yesterday_request()
    elif cmd_type == 'tomorrow':
      return self.solve_tomorrow_request()
    assert 0

  def analyze(self, cmd):
    print(f'[analyze] cmd={cmd}')
    if matches(cmd, 'then') or matches(cmd, 'sure'):
      print('[order]')
      return f'Of course! {get_current_meal()}'
    elif matches(cmd, 'yesterday'):
      print('[yesterday]')
      return self.respond('yesterday')
    elif matches(cmd, 'prediction') or matches(cmd, 'tomorrow'):
      print('[tomorrow]')
      return self.respond('tomorrow')
    elif matches(cmd, 'ok') or self.last_cmd_served == 'init':
      print('[ok]')
      return self.respond('today')
    print('[repeat]')
    return "I'm sorry Georgy, I couldn't understand what you've just said."

  def convert_into_mp3(self, result):
    import random
    import string
    random_key = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(4))
    filename = f'recordings/response-{str(random_key)}.mp3'
    t = gtts.gTTS(result)
    t.save(filename)
    return filename

  def solve(self, cmd):
    res = self.analyze(cmd)
    return self.convert_into_mp3(res)

@app.route("/cmd", methods=['GET', 'POST'])
@cross_origin()
def cmd():
  if flask.request.method == 'GET':
    print("GET!")
    return {'success' : True}
  else:  
    print("in cmd")
    print(json.loads(flask.request.form['json']))
    solver.refresh()
    return flask.send_file("static/audio/init.mp3", mimetype="audio/mp3")#, as_attachment=True)

# @app.route('/access', methods=['GET', 'POST'])
# def access():
#   print(f"request={flask.request.method}")
#   if flask.request.method == 'GET':
#     print("GET!")
#     return {'success' : True}
#   if flask.request.method == 'POST':
#     return {'tone' : 0, 'success' : True}

solver = Solver()
solver.load_data()

@app.route('/record', methods=['GET', 'POST'])
def record():
  print(f"request={flask.request.method}")
  if flask.request.method == 'GET':
    print("GET!")
    return {'success' : True}
  if flask.request.method == 'POST':
    # Fetch the file.
    file = flask.request.files['audio']
    
    # Fetch the IP.
    ip = flask.request.environ.get('HTTP_X_REAL_IP', flask.request.remote_addr)

    # Create a directory if we don't have one.
    if not os.path.exists('recordings'):
      os.mkdir('recordings')

    # Build the filepath.
    filename = f'{ip}-{int(time.time())}-{file.filename}'
    wavFilepath = os.path.join(app.root_path, 'recordings', f'{filename}.wav')
    mp3Filepath = os.path.join(app.root_path, 'recordings', f'{filename}.mp3')
    file.save(wavFilepath)

    # Convert to mp3 (for debug purposes)
    AudioSegment.from_wav(wavFilepath).export(mp3Filepath, format='mp3')

    file_audio = sr.AudioFile(wavFilepath)

    # use the audio file as the audio source                                        
    r = sr.Recognizer()
    with file_audio as source:
      audio_text = r.record(source)

      print(type(audio_text))
      cmd = None
      if True:
        cmd = solver.counter_to_sentence()
        solver.counter += 1
      else:
        cmd = r.recognize_google(audio_text)

      print(f'counter={solver.counter}, cmd={cmd}')

      # TODO: does it work to directly send the mp3 file, since it's not static?
      # TODO: maybe save to firebase first.
      
      return flask.send_file(solver.solve(cmd), mimetype="audio/mp3")#, as_attachment=True)

# Set up the main route
@app.route('/', methods=['GET', 'POST'])
def main():
  print(f"Inside main: {flask.request.method}")
  
  # GET? Then just render the initial form, to get input
  if flask.request.method == 'GET':
    return(flask.render_template('index.html'))

if __name__ == '__main__':
  app.run()
