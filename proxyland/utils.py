import uuid, xmlrpclib, socket

class Utils: 

    @staticmethod
    def uuid():
        return str(uuid.uuid4())

    @staticmethod
    def server_is_up(host, port):
        url = "http://{0}:{1}".format(host, port)
        server = xmlrpclib.Server(url)
        try: 
            server.test()
        except Exception as e:
            return False
        return True

    @staticmethod
    def get_open_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port
