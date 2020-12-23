#!/usr/bin/env python
import json
import logging
import os
import pathlib
import time

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

  def __init__(self):
    self.sp = sunpower.Sunpower()

  def poll_forever(self):
    while True:
      # poll forever
      now = time.time()
      if self.last_poll + self.interval > now:
        time.sleep(now-(self.last_poll+self.interval))
      self.poll()
  
  def poll(self):
    print('Polling Sunpower')
    components = self.sp.components()
    last = {'power': 0.0}

    for c in components['items']:
      line = f"{c['ComDvcSn']} {c['DvcTy']}: "
      if c['DvcTy'] == 'inverter': #LastData' in c and 'p3phsumKw' in c['LastData']:
        line += f"{round(c['LastData']['p3phsumKw'],3)}kW at {c['LastData']['msmtEps']}"
        last['power'] += c['LastData']['p3phsumKw']
      elif c['DvcTy'] == 'power meter':
        line += f"last reading at {c['LastData']['msmtEps']}"
        last['power_time'] = c['LastData']['msmtEps']
      elif c['DvcTy'] == 'logger':
        line += f"last response at {c['LastData']['begTmWdwEps']}, {c['LastData']['dvcComErrCt']} comm errors"
        last['comm_time'] = c['LastData']['begTmWdwEps']
      
    line = f"{last['comm_time']} - System was producing {round(last['power'],3)}kW at {last['power_time']}"
    if line != self.last_line:
      logging.info(line)
      self.last_line = line

if __name__ == '__main__':
  monitor = SPMonitor()
  monitor.poll_forever()
