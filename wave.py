# -*- coding: utf-8 -*-
import re, cgi, logging, email, datetime

from waveapi import ops
from waveapi import robot
from waveapi import events
from waveapi import element
from django.utils import simplejson
from google.appengine.ext import db
from google.appengine.api import mail
from google.appengine.api import xmpp
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from waveapi import appengine_robot_runner

BOT_OAUTH_KEY    = REPLACE_ME
BOT_OAUTH_SECRET = REPLACE_ME

BOT_VERIF_TOKEN  = REPLACE_ME
BOT_VERIF_KEY    = REPLACE_ME

class AppUser(db.Model):
    email = db.StringProperty()
    wave_email = db.StringProperty()
    received_at = db.DateTimeProperty(auto_now_add=True)

class Log(db.Model):
    email = db.StringProperty()
    content = db.TextProperty()
    received_at = db.DateTimeProperty(auto_now_add=True)

def append_to_wave(wavelet, message):
  blip = wavelet.root_blip
  logging.info("HUM")
  logging.info(message)
  blip.append(message.replace('\r\n','\n'))
  return blip

class MainPage(webapp.RequestHandler):
  robot = None
  def __init__(self,robot):
    self.robot = robot
    super

  def post(self):
    log = Log()
    log.email = users.get_current_user().email()
    log.content = str(self.request.POST)
    log.put()
    wave = self.robot.new_wave(domain='googlewave.com', participants=['live-note@appspot.com', str(self.request.POST['waveuser']),])
    blip = append_to_wave(wave,self.request.get('content').encode('utf-8'))
    self.robot.submit(wave)
    u = AppUser.gql("WHERE email = :1", log.email)
    if int(u.count()) <= 0:
      u = AppUser()
      u.email = str(users.get_current_user().email())
      u.put()
    else:
      u = u[0]
    
    u.wave_email = str(self.request.POST['waveuser'])
    u.put()
    self.redirect('/')
    
  def get(self):   
    log = Log()
    log.email = users.get_current_user().email()
    log.content = str(self.request.GET)
    log.put()
    u = AppUser.gql("WHERE email = :1", log.email)
    if int(u.count()) <= 0:
      default_wave_email = "login@googlewave.com"
    else:
      u = u[0]
      default_wave_email = u.wave_email
      
    self.response.out.write("""
           <html>
          <head>
          <title>Live Note!</title>
              <meta name="viewport" content="width=320; initial-scale=1.0; maximum-scale=1.0; user-scalable=0;"/> 
    <link rel="apple-touch-icon" href="static/livenote.gif" /> 
    <meta name="apple-touch-fullscreen" content="yes" /> 
    <link rel="stylesheet" title="Default" href="static/theme.css"  type="text/css"/> 
    <script type="application/x-javascript" src="static/iui.js"></script> 
  <link rel="alternate stylesheet" title="iPhoneDevCamp" href="static/ipdc-theme.css"  type="text/css"/> 
  <script type="text/javascript">
  </script>
  </head>
  <body>
    <div class="toolbar"> 
      <h1 id="pageTitle"></h1> 
      <a id="backButton" class="button" href="#"></a> 
      <a class="button" href="#about">About</a> 
    </div> 
    
    <ul id="home" title="Live Note!" selected="true"> 
        <li><a href="#newnote">New note</a></li> 
        <li><a href="#about">About</a></li> 
    </ul> 
    
    
    <div id="newnote" class="panel" title="New note"> 
        <h2>Write text and/or attach media</h2> 

        <form id="new-note" 
            action="/"
            enctype="x-www-form-urlencoded"
            method="post" > 
                <label for="waveuser">Your Wave username (login@googlewave.com)</label>
                 <input type="text" name="waveuser" id="waveuser" value="%(email)s"/><br />
                <label for="content">Content to send to Wave</label><br />
                <textarea name="content" cols=80 rows=10></textarea>
                <input type="submit" name="submit" value="Send to Wave!"/>
        </form> 
    </div> 

<div id="about" class="panel" title="About"> 
   <h2>How does it work?</h2><br/> 
  Very simple: enter some text here. That will create automatically a Wavelet (and its parent Wave if you are a first-time user. Only you will be able to access the wave.<br />
  What's great?<br />
  <ol>
  <li>You can use this interface</li>
   <li>You can add live-note@appspot.com to Google Talk and start chatting with the app: your notes will be taken</li>
    <li>Wave will be your only place to store your notes.</li>
  </ol>
  </div>
</body></html>""" % { 'email' : default_wave_email })
 
class MailHandler(InboundMailHandler):

  def receive(self, mail_message):
    bot = robot.Robot('Live Note',
      image_url='http://www.istockphoto.com/file_thumbview_approve/3284516/2/istockphoto_3284516-note-paper.jpg',
      profile_url='')
    bot.set_verification_token_info(BOT_VERIF_KEY,BOT_VERIF_TOKEN)
    bot.setup_oauth(BOT_OAUTH_KEY, BOT_OAUTH_SECRET, server_rpc_base="http://gmodules.com/api/rpc")

    m = re.search("[\w\.-]+@[\w\.-]+",mail_message.sender)
    cleansed_mail = m.group(0)
    log = Log()
    log.email = cleansed_mail
    log.content = str(mail_message)
    log.put()
    u = AppUser.gql("WHERE email = :1", log.email)
    if int(u.count()) <= 0:
      mail.send_mail(sender="Live-Note <live-note@live-note.appspotmail.com>",
              to=mail_message.sender,
              subject="Hold on a second stranger!",
              body="""
      Hello, please activate your account by using at least once the web interface at http://live-note.appspot.com.
""")
    else:
      user = u[0]
      wave = bot.new_wave(domain='googlewave.com', participants=['live-note@appspot.com', user.wave_email])
      bodies = mail_message.bodies("text/plain")

      for content_type, body in bodies:
        blip = append_to_wave(wave,body.decode().encode('utf-8'))

      res = bot.submit(wave)
      mail.send_mail(sender="Live-Note <live-note@live-note.appspotmail.com>",
              to=mail_message.sender,
              subject="Your message has been added to Google Wave",
              body="""
      You can access using this URL: https://wave.google.com/wave/#restored:wave:%(waveid)s .
      """ % { 'waveid' : str(res[0]['data']['waveId']).replace('+',"%252B") } )

       
class XMPPHandler(webapp.RequestHandler):
  robot = None
  def __init__(self,robot):
    self.robot = robot
    super
    
  def post(self):
    message = xmpp.Message(self.request.POST)
    email = cgi.escape(self.request.get('from')).split("/")[0]
    body = message.body
    log = Log()
    log.email = email
    log.content = body
    log.put()
    u = AppUser.gql("WHERE email = :1", log.email)
    if int(u.count()) <= 0:
      user = AppUser()
      user.email = email            
      user.put()
      message.reply("Hello, please activate your account by using at least once the web interface at http://live-note.appspot.com.")
    else:
      user = u[0]
      wave = self.robot.new_wave(domain='googlewave.com', participants=['live-note@appspot.com', user.wave_email])
      blip = append_to_wave(wave,body.encode('utf-8'))
      self.robot.submit(wave)
      message.reply("Message saved!")

if __name__ == '__main__':
  removey = robot.Robot('Live Note',
      image_url='http://www.istockphoto.com/file_thumbview_approve/3284516/2/istockphoto_3284516-note-paper.jpg',
      profile_url='')
  removey.set_verification_token_info(BOT_VERIF_KEY, BOT_VERIF_TOKEN)
  removey.setup_oauth(BOT_OAUTH_KEY, BOT_OAUTH_SECRET, server_rpc_base="http://gmodules.com/api/rpc")
  appengine_robot_runner.run(removey, debug=True, extra_handlers=[('/', lambda: MainPage(removey)),('/_ah/xmpp/message/chat/', lambda: XMPPHandler(removey)), MailHandler.mapping(),])
