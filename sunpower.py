#!/usr/bin/env python

import os, sys, pathlib
import requests
import json
import pprint
import logging
import time
import datetime

pp = pprint.PrettyPrinter(indent=2)

LOGFILE = os.path.join(pathlib.Path.home(), '.log', 'sunpower.log')
CREDENTIALS = os.path.join(pathlib.Path.home(), '.credentials', 'sunpower.json')

API_BASE_URL = 'https://elhapi.edp.sunpower.com/v1/elh'

class Sunpower:
  expires = datetime.datetime.now() 
  def authorize(self):
    with open(CREDENTIALS, 'r') as f:
      creds = json.load(f)
    res = requests.post(url=f'{API_BASE_URL}/authenticate', data=creds)
    self.authobj = json.loads(res.content)
    self.expires = datetime.datetime.fromtimestamp(self.authobj['expiresEpm']/1000.0)
    logging.info(f'Authorized account {self.authobj["username"]}, expires: {self.expires}')

  def power(self):
    return self.generic('power')
  
  def activity(self):
    return self.generic('activity')

  def alerts(self):
    return self.generic('alerts')

  def components(self):
    return self.generic('components')
  
  def energy(self,start_time,end_time):
    # expect times as a datetime objec
    params = {'async': False, 'starttime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),'endtime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),'interval': 'HOUR'}
    # Expect structure like:
    # energydata: [
    #   'time, generated, used,'
    # ]
    return self.generic('energy',params=params)

  def check_auth(self):
    if datetime.datetime.now() >= self.expires:
      # Need to re-up the token
      logging.info(f'Re-Authorizing due to expired token')
      self.authorize()

  def generic(self,call,params={'async': False}):
    self.check_auth()
    res = requests.get (url=f'{API_BASE_URL}/address/{self.authobj["addressId"]}/{call}',
                        headers={'Authorization': f'SP-CUSTOM {self.authobj["tokenID"]}'},
                        params=params)
    return self.handle_result(res,call)


  def handle_result(self,res,call):
    if res.status_code != 200:
      logging.warning(f'HTTP Error in {call} call: {res.status_code}')
      return None
    else:
      return json.loads(res.content)

if __name__ == '__main__':
  logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOGFILE),
        logging.StreamHandler()
    ])
  sp = Sunpower()

  pp.pprint(sp.power())
  pp.pprint(sp.alerts())
  print(datetime.datetime.fromtimestamp(sp.activity()/1000)) # Returns the timestamp with the latest activity from the device

  components = sp.components()
  for c in components['items']:
    line = f"{c['ComDvcSn']} {c['DvcTy']}: "
    if c['DvcTy'] == 'inverter': #LastData' in c and 'p3phsumKw' in c['LastData']:
      line += f"{round(c['LastData']['p3phsumKw'],3)}kW at {c['LastData']['msmtEps']}"
    elif c['DvcTy'] == 'power meter':
      line += f"last reading at {c['LastData']['msmtEps']}"
    elif c['DvcTy'] == 'logger':
      line += f"last response at {c['LastData']['begTmWdwEps']}, {c['LastData']['dvcComErrCt']} comm errors"
    else:
      pp.pprint(c)
    print(line)

  start = datetime.datetime.fromisoformat('2020-07-01')
  end = datetime.datetime.fromisoformat('2020-07-31')
  pp.pprint(sp.energy(start,end))