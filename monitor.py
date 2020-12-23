#!/usr/bin/env python
import datetime
import json
import logging
import os
import pathlib
import time
import traceback

import requests

import sunpower

PB_TOKEN = os.path.join(pathlib.Path.home(), '.credentials', 'pushbullet')
LOGFILE = os.path.join(pathlib.Path.home(), '.log', 'sunpower.log')

logging.basicConfig(
  format='%(asctime)s %(levelname)-8s %(message)s',
  level=logging.INFO,
  datefmt='%Y-%m-%d %H:%M:%S',
  handlers=[
      logging.FileHandler(LOGFILE),
      logging.StreamHandler()
  ])

def pushbullet_message(title,body):
  msg = {"type": "note", "title": title, "body": body}
  with open(PB_TOKEN, 'r') as f:
    TOKEN = f.readline().rstrip()
  resp = requests.post('https://api.pushbullet.com/v2/pushes', 
                        data=json.dumps(msg),
                        headers={'Authorization': 'Bearer ' + TOKEN,
                                'Content-Type': 'application/json'})
  if resp.status_code != 200:
    raise Exception('Error',resp.status_code)
  else:
    logging.info(f'Sent pushbullet message: {title}:{body}') 

class SPMonitor():
  interval = 5 # seconds between polls
  data = {}
  last_poll = 0
  last_line = ''
  error_count = 0
  last_notified = datetime.datetime.now() - datetime.timedelta(days=365000)
  def __init__(self,age_limit_days,notification_limit_days):
    self.sp = sunpower.Sunpower()
    self.age_limit_seconds = age_limit_days*24*3600
    self.age_limit_days = age_limit_days
    self.notification_limit_seconds = notification_limit_days*24*3600

  def poll_forever(self):
    pushbullet_message('Starting Sunpower Monitor',f'Polling every {self.interval} seconds')
    while True:
      # poll forever
      now = time.time()
      if self.last_poll + self.interval > now:
        time.sleep(now-(self.last_poll+self.interval))
      try:
        self.poll()
      except KeyboardInterrupt:
        exit()
      except:
        self.error_count += 1
        logging.error(traceback.format_exc())
        if self.error_count > 10:
          pushbullet_message('Sunpower Monitor quitting due to errors',f'Latest error: \n{traceback.format_exc()}')
          exit()
  
  def poll(self):
    components = self.sp.components()
    last = {'power': 0.0}
    oldest_time = datetime.datetime.now()
    oldest_data = ''
    for c in components['items']:
      line = f"{c['ComDvcSn']} {c['DvcTy']}: "
      if c['DvcTy'] == 'inverter': #LastData' in c and 'p3phsumKw' in c['LastData']:
        dt = datetime.datetime.strptime(c['LastData']['msmtEps'], '%Y-%m-%dT%H:%M:%SZ')
        line += f"{round(c['LastData']['p3phsumKw'],3)}kW at {c['LastData']['msmtEps']}"
        last['power'] += c['LastData']['p3phsumKw']
      elif c['DvcTy'] == 'power meter':
        data = f"last reading at {c['LastData']['msmtEps']}"
        last['power_time'] = c['LastData']['msmtEps']
        dt = datetime.datetime.strptime(c['LastData']['msmtEps'], '%Y-%m-%dT%H:%M:%SZ')
      elif c['DvcTy'] == 'logger':
        last['comm_time'] = c['LastData']['begTmWdwEps']
        last['comm_errors'] = c['LastData']['dvcComErrCt']
        dt = datetime.datetime.strptime(c['LastData']['begTmWdwEps'], '%Y-%m-%dT%H:%M:%SZ')
      if dt < oldest_time:
        oldest_time = dt
    line = f"{last['comm_time']} - System was producing {round(last['power'],3)}kW at "
    line += f"{last['power_time']} with {last['comm_errors']} communication errors"
    if line != self.last_line:
      logging.info(line)
      self.last_line = line
    now = datetime.datetime.now()
    if abs((now - oldest_time).total_seconds()) > self.age_limit_seconds \
      and abs((now-self.last_notified).total_seconds()) > self.notification_limit_seconds:
      pushbullet_message(f'Sunpower Data older than {self.age_limit_days} day(s)',line)
      self.last_notified = datetime.datetime.now()

if __name__ == '__main__':
  monitor = SPMonitor(1,1)
  monitor.poll_forever()
