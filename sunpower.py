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
    # https://elhapi.edp.sunpower.com/v1/elh/address/135905/energy?endtime=2020-12-22T12:48:01&interval=HOUR&starttime=2020-11-30T00:00:00
    # https://elhapi.edp.sunpower.com/v1/elh/address/135905/energy?endtime=2020-12-22T12:48:01&interval=HOUR&starttime=2020-11-30T00:00:00
    # expect start_time as a datetime object
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
    print(f'{API_BASE_URL}/address/{self.authobj["addressId"]}/{call}')
    return self.handle_result(res,call)


  def handle_result(self,res,call):
    if res.status_code != 200:
      logging.warning(f'HTTP Error in {call} call: {res.status_code}')
      return None
    else:
      return json.loads(res.content)

class SPMonitor():
  interval = 5 # seconds between polls
  data = {}
  last_poll = 0
  last_line = ''

  def __init__(self,sp):
    self.sp = sp

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
      # else:
      #   pp.pprint(c)
      # print(line)

if __name__ == '__main__':
  opt = None
  if len(sys.argv) == 2:
    if sys.argv[1] == 'test':
      opt = 'all'
  elif len(sys.argv) == 3:
    if sys.argv[1] == 'test' and sys.argv[2]:
      opt = sys.argv[2]

  logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOGFILE),
        logging.StreamHandler()
    ])
  sp = Sunpower()
  if opt is None:
    mon = SPMonitor(sp)
    mon.poll_forever()
  elif opt is not None:
    if opt in ['all','power']:
      pp.pprint(sp.power())
    elif opt in ['all','alerts']:
      pp.pprint(sp.alerts())
    elif opt in ['all','activity']:
      print(datetime.datetime.fromtimestamp(sp.activity()/1000)) # Returns the timestamp with the latest activity from the device
    elif opt in ['all','components']:
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
    elif opt in ['all','energy']:
      start = datetime.datetime.fromisoformat('2020-07-01')
      end = datetime.datetime.fromisoformat('2020-07-31')
      pp.pprint(sp.energy(start,end))
  else:
    print('Usage:')
    print('To run all calls to see retrieved information:')
    print('> python sunpower.py test [test-name]')
    print('To start the poller:')
    print('> python sunpower.py')
    print('To start the poller and show a QT GUI:')
    print('> python sunpower.py gui')