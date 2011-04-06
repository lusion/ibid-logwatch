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

class LogWatch(Processor):
  interval = IntOption('interval', 'Update Poll interval (in seconds)', 1)

  files = {}

  def incoming(self, target, name, data):
    reply = u" == %(name)s == \n%(data)s" % {u'name': name, u'data': data.strip()}

    ibid.dispatcher.send({'reply': reply,
        'source': 'jabber',
        'target': target,
    })


  def setup(self):
    super(LogWatch, self).setup()
    targets = []
    for line in file('logwatch.txt').read().split("\n"):
      if line and line[0] == '@':
        targets = [x.strip() for x in line[1:].split(',')]
      else:
        for filename in glob(line.strip()):
          for target in targets:
            self.tail_file(target, filename, filename)




  @periodic(config_key='interval', initial_delay=15)
  def update(self, event):
    for filename, obj in self.files.iteritems():
      # Try call the callback if we can
      data = obj['fileobj'].read()
      if data:
        for (target, name) in obj['events']:
          self.incoming(target, name, data)

      # Try get the latest file stats
      try: nstat = os.stat(filename)
      except: nstat = obj['fstat'] 

      # Check if the file changed, if so start from beginning again
      if nstat[stat.ST_DEV] != obj['fstat'][stat.ST_DEV] or nstat[stat.ST_INO] != obj['fstat'][stat.ST_INO]:
        obj['fileobj']= open(filename)
        obj['fstat'] = os.fstat(obj['fileobj'].fileno())

  def tail_file(self, target, filename, name):

    if not filename in self.files:
      fileobj = open(filename)
      fileobj.seek(0, 2)

      self.files[filename] = {'fileobj': fileobj, 'fstat': os.fstat(fileobj.fileno()), 'events': []}
    self.files[filename]['events'].append((target, name))

  @match(r'^tail ([^ ]+|"[^"]*") as (.+)$')
  def tail_as(self, event, filename, name):
    # Strip off quotes if needed
    if filename[0] == filename[-1] == '"':
      filename = filename[1:-1]

    if not os.path.exists(filename):
      event.addresponse(u"Sorry, I could not find %(filename)s", {u'filename': filename})
    else:
      event.addresponse(u"Aiight, I'm watching %(name)s for you.", {u'name': name})
      self.tail_file(event['sender']['id'], filename, name)

  @match(r'^tail ([^ ]+|"[^"]*")$')
  def tail(self, event, filename):
    # Strip off quotes if needed
    if filename[0] == filename[-1] == '"':
      filename = filename[1:-1]

    self.tail_as(event, filename, os.path.basename(filename))
