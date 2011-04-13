import ibid
from ibid.config import IntOption, Option
from ibid.plugins import Processor, match, handler, periodic
from ibid.utils import human_join
from ibid.db import IbidUnicode, IbidUnicodeText, Integer, DateTime, \
                    Table, Column, ForeignKey, UniqueConstraint, \
                    relation, IntegrityError, Base, VersionedSchema
from ibid.event import Event                    
import os, stat
from glob import glob
import ConfigParser as configparser

groups = {}
config = configparser.RawConfigParser()
config.read('logwatch.ini')

# Read in the logwatch.ini file
for section in config.sections():
  groups[section] = {'files': [], 'alerts': []}

  for files in config.get(section, 'files').split(','):
    for filename in glob(files.strip()):
      groups[section]['files'].append(filename)

  try:
    for alert in config.get(section, 'alert').split(','):
      groups[section]['alerts'].append(alert.strip())
  except configparser.NoOptionError:
    pass


class LogWatch(Processor):
  interval = IntOption('interval', 'Update Poll interval (in seconds)', 1)

  files = {}

  def incoming(self, target, filename, group, data):
    reply = u" == %(filename)s (%(group)s) == \n%(data)s" % {u'group': group, u'filename': filename, u'data': data.strip()}

    ibid.dispatcher.send({'reply': reply,
        'source': 'jabber',
        'target': target,
    })


  def setup(self):
    super(LogWatch, self).setup()

    # Start tailing all the setup alerts immediatly
    for section, group in groups.iteritems():
      for target in group['alerts']:
        for filename in group['files']:
          self.add_tail(target, filename, filename)


  @periodic(config_key='interval', initial_delay=15)
  def update(self, event):
    for filename, obj in self.files.iteritems():
      # Try call the callback if we can
      data = obj['fileobj'].read()
      if data:
        for (target, group) in obj['events']:
          self.incoming(target, filename, group, data)

      # Try get the latest file stats
      try: nstat = os.stat(filename)
      except: nstat = obj['fstat'] 

      # Check if the file changed, if so start from beginning again
      if nstat[stat.ST_DEV] != obj['fstat'][stat.ST_DEV] or nstat[stat.ST_INO] != obj['fstat'][stat.ST_INO]:
        obj['fileobj']= open(filename)
        obj['fstat'] = os.fstat(obj['fileobj'].fileno())

  def add_tail(self, target, filename, name):
    if not filename in self.files:
      fileobj = open(filename)
      fileobj.seek(0, 2)

      self.files[filename] = {'fileobj': fileobj, 'fstat': os.fstat(fileobj.fileno()), 'events': []}

    for event in self.files[filename]['events']:
      if event[0] == target: return False

    self.files[filename]['events'].append((target, name))
    return True

  def remove_tail(self, target, filename):
    if not filename in self.files:
      return

    self.files[filename]['events'] = [x for x in self.files[filename]['events'] if x[0] != target]

  @match(r'^tail ([/^ ]+|"/[^"]*")$')
  def tail_file(self, event, filename):
    # Strip off quotes if needed
    if filename[0] == filename[-1] == '"':
      filename = filename[1:-1]

    if not os.path.exists(filename):
      event.addresponse(u"Sorry, I could not find %(filename)s", {u'filename': filename})
    else:
      event.addresponse(u"Aiight, I'm watching %(filename)s for you.", {u'filename': filename})
      self.add_tail(event['sender']['id'], filename, 'manual')

  @match(r'^tail ([a-z-]+)$')
  def tail_group(self, event, group):
    if group in groups:
      for filename in groups[group]['files']:
        self.add_tail(event['sender']['id'], filename, group)
      event.addresponse(u"Aiight, I'm watching %(group)s for you.", {u'group': group})
    else:
      event.addresponse(u"Sorry, I could not find the group %(group)s", {u'group': group})

  @match(r'^untail ([a-z-]+)$')
  def untail_group(self, event, group):
    if group in groups:
      for filename in groups[group]['files']:
        self.remove_tail(event['sender']['id'], filename)
      event.addresponse(u"Aiight, You're no longer tailing %(group)s.", {u'group': group})
    else:
      event.addresponse(u"Sorry, I could not find the group %(group)s", {u'group': group})

if __name__ == "__main__":
  print groups

