
import cgi
import smtplib
import xmlrpc.client
from email.mime.text import MIMEText
from email.utils import parseaddr

from twisted.internet import threads
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from .utils import Utils


class Register(Resource):
    isLeaf = True
    
    allowedMethods = ("GET","POST")
    
    
    def __init__(self, state):
        Resource.__init__(self)
        self.state = state

    _form = (
        '<html><title>{0}</title>'
        '<body><form method="POST">'
        '<p>Your E-mail address: <input name="email" type="text" /></p>'
        '<p>Your ETB server IP: <input name="ip" type="text" /></p>'
        '<p>Your ETB server port: <input name="port" type="text" /></p>'
        '<input type="hidden" name="registration_id" id="registration_id" value="{1}" />'
        '<p><input type="submit" value="Submit"></p>'
        '</form></body></html>'
        )

    _response = (
        '<html><title>{0}</title><body>'
        '<h2> Email Sent! </h2>'
        'I have sent a confirmation email to:<br>'
        '<p><b>{1}</b></p>'
        'If you click on the link contained in that email, your ETB server should be linked to '
        'a newly allocated one of ours.'
        '</body></html>'
        )

    _message = (
        'Click:\n'
        'http://{0}:{1}/confirm/{2}'
        '\n'
        'To create your requested ETB server'
        )
    
    _error = (
        '<html><title>ETB Server Request</title><body>'
        'Nope - not happy: {0}'
        '</body></html>'
        )

    _reason = "but it's a mystery!"

    def render_GET(self, request):
        title = Utils.uuid()
        return self._form.format(title, title)

    def render_POST(self, request):
        self.request = request;
        if(self._validatePost(request)):
            d = threads.deferToThread(self._processPost)
            return NOT_DONE_YET
        else:
            return self._error.format(self._reason)
        
        
    def _delayed_render_POST(self, result):
        yada = ''
        if result:
            e_id, e_email, e_ip, e_port = list(map(cgi.escape, (self.id, self.email, self.ip, self.port)))
            yada = self._response.format(e_id, e_email, e_ip, e_port, result)
        else:
            yada = self._error.format(self._reason)
        self.request.write(yada)
        self.request.finish()

        
    def _validatePost(self, request):
        self.id = request.args["registration_id"][0]
        self.email = request.args["email"][0]
        self.ip = request.args["ip"][0]
        self.port = request.args["port"][0]
        if(self.id and self.email and self.ip and self.port):
            return True
        else:
            self._reason = 'we really need an email address, an ip address, and port before we can get started.'
            return False


    def _validateEmail(self):
        name, address = parseaddr(self.email)
        if address:
            self.email = address
            return True
        else:
            self._reason = 'without a valid email address, your confirmation email will remain unread.'
            return False

    def _insertRequest(self):
        self.confirm = Utils.uuid()
        row = (self.email, self.ip, self.port, self.id, self.confirm)
        return self.state.dbpool.runQuery("INSERT INTO users (email, host, port, request, confirmation) VALUES(?, ?, ?, ?, ?)", row)


    def _processPost(self):
        #validate the email address
        if(not self._validateEmail()):
            print("validateEmail failed!")
            self._delayed_render_POST(False);
            return
        #ping the etb server
        if(not self._validateServer()):
            print("validateServer failed!")
            self._delayed_render_POST(False);
            return
        #create the database entries
        d = self._insertRequest()
        #send the confirmation email
        d.addCallback(self._sendConfirmation)
        #render yay or nay 
        d.addCallback(self._delayed_render_POST)
        return

    def _validateServer(self):
        uri = "http://{host}:{port}" . format(host=self.ip, port=self.port)
        try:
            proxy = xmlrpc.client.ServerProxy(uri)
            proxy.test()
        except Exception as e:
            self._reason = 'your server needs to be up and running (and accessible) before I make the effort of creating you one of our nodes.'
            print(e)
            return False
        return True

    def _sendConfirmation(self, result):
        me = self.state.config['mail_sender']
        host = self.state.config['metaserver_name_or_ip']
        port = self.state.config['metaserver_listening_port']
        mail_server_name =  self.state.config['mail_server_name']
        mail_server_port =  int(self.state.config['mail_server_port'])
        you = self.email
        content = self._message.format(host, port, self.confirm)
        msg = MIMEText(content)
        msg['Subject'] = 'ETB Confirmation email'
        msg['From'] = me
        msg['To'] = you
        print("Attempting to send email!")
        mail_server = smtplib.SMTP(mail_server_name, mail_server_port)
        mail_server.sendmail(me, [you], msg.as_string())
        mail_server.quit()       
        print("Email sent!")
        return True
    
